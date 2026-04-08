"""
Craft Agent - 任务执行
"""
import json
from typing import Dict, List, Any, Optional


class CraftAgent:
    """
    Craft Agent：任务执行
    
    职责：
    - 按照计划执行每个分析步骤
    - 处理执行中的异常情况
    - 生成最终分析报告
    """
    
    def __init__(
        self,
        llm_client,
        tool_executor,
        tools: List[Dict] = None,
        max_tool_rounds: int = 10,
        retry_on_fail: bool = True,
    ):
        self.llm_client = llm_client
        self.tool_executor = tool_executor
        self.tools = tools or []
        self.max_tool_rounds = max_tool_rounds
        self.retry_on_fail = retry_on_fail
    
    def process(self, user_input: str, plan: Dict) -> Dict[str, Any]:
        """
        执行分析任务
        
        Args:
            user_input: 原始用户需求
            plan: Plan Agent 制定的计划
            
        Returns:
            {
                "status": "success" | "error" | "partial",
                "executed_steps": [...],
                "summary": "...",
                "report": "..."
            }
        """
        from .prompts import CRAFT_AGENT_PROMPT
        
        # 构建工具列表
        tools_info = "\n".join([
            f"- {t['function']['name']}: {t['function']['description'][:80]}"
            for t in self.tools
        ])
        
        # 格式化计划
        plan_text = self._format_plan(plan)
        
        # 构建提示词
        prompt = CRAFT_AGENT_PROMPT.format(
            user_input=user_input,
            plan=plan_text,
            available_tools=tools_info,
        )
        
        executed_steps = []
        all_success = True
        
        # 按计划顺序执行每个步骤
        steps = plan.get("steps", [])
        for i, step in enumerate(steps):
            step_result = self._execute_step(step, i + 1)
            executed_steps.append(step_result)
            
            if not step_result.get("success", False):
                all_success = False
                if not self.retry_on_fail:
                    # 如果不允许重试，停止执行
                    break
        
        # 构建结果
        status = "success" if all_success else "partial"
        
        # 生成总结和报告
        summary = self._generate_summary(executed_steps, plan)
        report = self._generate_report(user_input, executed_steps, plan)
        
        return {
            "status": status,
            "executed_steps": executed_steps,
            "summary": summary,
            "report": report
        }
    
    def _format_plan(self, plan: Dict) -> str:
        """格式化计划为可读文本"""
        lines = []
        lines.append(f"计划: {plan.get('plan', 'N/A')}")
        lines.append("\n步骤:")
        
        for step in plan.get("steps", []):
            lines.append(f"  {step.get('step_id', '?')}. {step.get('tool', 'N/A')}")
            lines.append(f"     描述: {step.get('description', 'N/A')}")
            lines.append(f"     输入: {step.get('input', 'N/A')}")
            lines.append(f"     输出: {step.get('output', 'N/A')}")
            lines.append("")
        
        return "\n".join(lines)
    
    def _execute_step(self, step: Dict, step_id: int) -> Dict[str, Any]:
        """执行单个步骤"""
        tool_name = step.get("tool", "")
        step_desc = step.get("description", "")
        
        if not tool_name:
            return {
                "step_id": step_id,
                "tool": "",
                "result": "跳过：未指定工具",
                "success": False,
                "error": "未指定工具"
            }
        
        # 解析输入参数
        args = self._parse_args(step.get("input", ""))
        
        # 执行工具
        result_str = ""
        try:
            result_str = self.tool_executor(tool_name, args)
        except Exception as e:
            return {
                "step_id": step_id,
                "tool": tool_name,
                "result": f"执行失败: {str(e)}",
                "success": False,
                "error": str(e)
            }
        
        # 限制结果长度
        if len(result_str) > 2000:
            result_str = result_str[:2000] + "\n... (结果已截断)"
        
        return {
            "step_id": step_id,
            "tool": tool_name,
            "result": result_str[:500],  # 只保留摘要
            "full_result": result_str,
            "success": True,
            "error": None
        }
    
    def _parse_args(self, input_str: str) -> Dict[str, Any]:
        """从输入描述中解析参数（简化版）"""
        # 简单实现：尝试从输入描述中提取文件名
        args = {}
        
        if not input_str:
            return args
        
        # 尝试提取文件路径
        import re
        file_pattern = r'[\w/]+\.(fa|fasta|fastq|fq|fna|faa|txt|bed|vcf|bam|sam|json|yaml|tsv|csv)'
        matches = re.findall(file_pattern, input_str)
        
        if matches:
            args["file"] = matches[0]
        
        return args
    
    def _generate_summary(self, executed_steps: List[Dict], plan: Dict) -> str:
        """生成执行总结"""
        total = len(executed_steps)
        success = sum(1 for s in executed_steps if s.get("success", False))
        
        return f"执行完成：{success}/{total} 个步骤成功"
    
    def _generate_report(self, user_input: str, executed_steps: List[Dict], plan: Dict) -> str:
        """生成分析报告"""
        lines = []
        
        lines.append("=" * 50)
        lines.append("生物信息学分析报告")
        lines.append("=" * 50)
        lines.append("")
        
        lines.append(f"需求: {user_input}")
        lines.append("")
        
        lines.append("执行步骤:")
        lines.append("-" * 40)
        
        for step in executed_steps:
            status = "✓" if step.get("success") else "✗"
            tool = step.get("tool", "N/A")
            result = step.get("result", "N/A")
            
            lines.append(f"{status} 步骤 {step.get('step_id', '?')}: {tool}")
            lines.append(f"   结果: {result}")
            
            if step.get("error"):
                lines.append(f"   错误: {step.get('error')}")
            lines.append("")
        
        lines.append("-" * 40)
        lines.append(f"总计: {len(executed_steps)} 个步骤")
        
        return "\n".join(lines)
