"""
评估反馈模块 - 工具执行结果评估与重试机制
"""
import re
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from enum import Enum


class ResultStatus(Enum):
    """执行结果状态"""
    SUCCESS = "success"
    PARTIAL = "partial"  # 部分成功
    FAILURE = "failure"
    ERROR = "error"      # 执行错误
    NEED_RETRY = "need_retry"  # 需要重试


@dataclass
class EvaluationResult:
    """评估结果"""
    status: ResultStatus
    message: str
    score: float = 0.0  # 0-1 评分
    details: Dict = field(default_factory=dict)
    suggestions: List[str] = field(default_factory=list)
    retry_count: int = 0


class ResultEvaluator:
    """
    工具执行结果评估器
    - 分析工具返回内容
    - 判断执行是否成功
    - 提供改进建议
    """
    
    # 常见错误模式
    ERROR_PATTERNS = [
        (r"error[:\s]", ResultStatus.ERROR),
        (r"failed[:\s]", ResultStatus.FAILURE),
        (r"cannot find", ResultStatus.FAILURE),
        (r"not found", ResultStatus.FAILURE),
        (r"no such file", ResultStatus.FAILURE),
        (r"permission denied", ResultStatus.FAILURE),
        (r"command not found", ResultStatus.FAILURE),
        (r"timeout", ResultStatus.NEED_RETRY),
        (r"connection refused", ResultStatus.NEED_RETRY),
    ]
    
    # 成功模式
    SUCCESS_PATTERNS = [
        r"success",
        r"completed",
        r"finished",
        r"done",
        r"生成成功",
        r"完成",
        r"成功",
    ]
    
    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.min_success_score = self.config.get("min_success_score", 0.7)
        self.max_retries = self.config.get("max_retries", 3)
    
    def evaluate(self, tool_name: str, result: str, context: Dict = None) -> EvaluationResult:
        """
        评估工具执行结果
        
        Args:
            tool_name: 工具名称
            result: 执行结果文本
            context: 额外上下文信息
        
        Returns:
            EvaluationResult 评估结果
        """
        context = context or {}
        
        # 检查错误
        for pattern, status in self.ERROR_PATTERNS:
            if re.search(pattern, result, re.IGNORECASE):
                return EvaluationResult(
                    status=status,
                    message=f"检测到错误: {result[:200]}",
                    score=0.0,
                    details={"pattern": pattern, "tool": tool_name},
                    suggestions=self._get_suggestions(tool_name, status, result)
                )
        
        # 检查成功标记
        has_success = any(
            re.search(p, result, re.IGNORECASE) 
            for p in self.SUCCESS_PATTERNS
        )
        
        # 检查输出内容
        result_lower = result.lower()
        
        # 空结果
        if not result or len(result.strip()) < 5:
            return EvaluationResult(
                status=ResultStatus.FAILURE,
                message="执行结果为空或过短",
                score=0.0,
                details={"tool": tool_name, "result_length": len(result)},
                suggestions=["检查工具是否正确执行", "确认输入参数是否正确"]
            )
        
        # 文件类工具：检查输出文件是否存在
        if "file" in tool_name.lower() or "output" in context:
            if not self._check_file_mentioned(result):
                return EvaluationResult(
                    status=ResultStatus.PARTIAL,
                    message="结果中未明确提到输出文件",
                    score=0.5,
                    details={"tool": tool_name},
                    suggestions=["确认文件是否生成", "检查输出路径是否正确"]
                )
        
        # 评估得分
        score = self._calculate_score(result, has_success)
        
        # 判断状态
        if score >= self.min_success_score:
            status = ResultStatus.SUCCESS
            message = "执行成功"
        elif score >= 0.4:
            status = ResultStatus.PARTIAL
            message = "部分成功"
        else:
            status = ResultStatus.FAILURE
            message = "执行可能失败"
        
        return EvaluationResult(
            status=status,
            message=message,
            score=score,
            details={
                "tool": tool_name,
                "has_success_marker": has_success,
                "result_length": len(result),
            },
            suggestions=self._get_suggestions(tool_name, status, result)
        )
    
    def _check_file_mentioned(self, result: str) -> bool:
        """检查结果中是否提到文件"""
        patterns = [
            r"\.(fa|fq|fasta|fastq|fa\.gz|fq\.gz|bam|sam|vcf)\b",
            r"生成.*文件",
            r"输出.*文件",
            r"saved",
            r"written",
            r"created",
        ]
        return any(re.search(p, result, re.IGNORECASE) for p in patterns)
    
    def _calculate_score(self, result: str, has_success: bool) -> float:
        """计算成功得分"""
        score = 0.5  # 基础分
        
        if has_success:
            score += 0.3
        
        # 根据结果长度调整
        if len(result) > 100:
            score += 0.1
        if len(result) > 1000:
            score += 0.1
        
        return min(score, 1.0)
    
    def _get_suggestions(self, tool_name: str, status: ResultStatus, result: str) -> List[str]:
        """获取改进建议"""
        suggestions = []
        
        if status == ResultStatus.ERROR:
            suggestions.append("检查工具是否正确安装")
            suggestions.append("查看错误信息确定具体问题")
        
        elif status == ResultStatus.FAILURE:
            if "not found" in result.lower():
                suggestions.append("检查输入文件路径是否正确")
            if "permission" in result.lower():
                suggestions.append("检查文件权限设置")
            suggestions.append("确认工具参数格式是否正确")
        
        elif status == ResultStatus.NEED_RETRY:
            suggestions.append("网络问题，可稍后重试")
            suggestions.append("检查服务是否正常运行")
        
        return suggestions
    
    def should_retry(self, eval_result: EvaluationResult, current_retry: int) -> bool:
        """判断是否需要重试"""
        if current_retry >= self.max_retries:
            return False
        
        return eval_result.status in [
            ResultStatus.NEED_RETRY,
            ResultStatus.ERROR,
            ResultStatus.FAILURE,
        ]
    
    def get_retry_params(self, eval_result: EvaluationResult) -> Dict:
        """获取重试参数建议"""
        return {
            "increase_timeout": eval_result.status == ResultStatus.NEED_RETRY,
            "reduce_scope": eval_result.status == ResultStatus.FAILURE,
            "suggestions": eval_result.suggestions,
        }


class FeedbackCollector:
    """
    反馈收集器
    - 收集用户反馈
    - 统计工具成功率
    - 记录常见问题
    """
    
    def __init__(self, db_path: str = None):
        self.db_path = db_path
        self.stats = {
            "total_calls": 0,
            "successful_calls": 0,
            "failed_calls": 0,
            "tool_stats": {},  # tool_name -> {success, failure, total}
        }
    
    def record(self, tool_name: str, eval_result: EvaluationResult):
        """记录执行结果"""
        self.stats["total_calls"] += 1
        
        if eval_result.status == ResultStatus.SUCCESS:
            self.stats["successful_calls"] += 1
        else:
            self.stats["failed_calls"] += 1
        
        # 工具统计
        if tool_name not in self.stats["tool_stats"]:
            self.stats["tool_stats"][tool_name] = {
                "success": 0, "failure": 0, "total": 0
            }
        
        stats = self.stats["tool_stats"][tool_name]
        stats["total"] += 1
        if eval_result.status == ResultStatus.SUCCESS:
            stats["success"] += 1
        else:
            stats["failure"] += 1
    
    def get_success_rate(self, tool_name: str = None) -> float:
        """获取成功率"""
        if tool_name:
            stats = self.stats["tool_stats"].get(tool_name)
            if not stats or stats["total"] == 0:
                return 0.0
            return stats["success"] / stats["total"]
        
        if self.stats["total_calls"] == 0:
            return 0.0
        return self.stats["successful_calls"] / self.stats["total_calls"]
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        return {
            **self.stats,
            "overall_success_rate": self.get_success_rate()
        }
    
    def reset_stats(self):
        """重置统计"""
        self.stats = {
            "total_calls": 0,
            "successful_calls": 0,
            "failed_calls": 0,
            "tool_stats": {},
        }
