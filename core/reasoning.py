"""
推理路由模块 - 任务分类与路由
根据任务类型选择合适的处理策略
"""
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from enum import Enum


class TaskType(Enum):
    """任务类型"""
    SEQUENCE_OPERATION = "sequence_operation"  # 序列操作
    QC = "qc"                    # 质量控制
    ASSEMBLY = "assembly"        # 组装
    ALIGNMENT = "alignment"      # 比对
    EVOLUTION = "evolution"      # 进化分析
    TAXONOMY = "taxonomy"        # 分类学
    VISUALIZATION = "visualization"  # 可视化
    KNOWLEDGE = "knowledge"      # 知识查询
    ANALYSIS = "analysis"        # 综合分析
    GENERAL = "general"          # 通用对话


class ProcessStrategy(Enum):
    """处理策略"""
    DIRECT_FC = "direct_fc"      # 直接函数调用
    PLANNER_EXECUTOR = "planner_executor"  # 计划-执行模式
    WORKFLOW = "workflow"        # 工作流模式
    SEARCH = "search"           # 搜索模式


@dataclass
class TaskAnalysis:
    """任务分析结果"""
    task_type: TaskType
    suggested_strategy: ProcessStrategy
    confidence: float  # 0-1
    relevant_tools: List[str] = field(default_factory=list)
    workflow_hint: str = ""
    reasoning: str = ""


class ReasoningRouter:
    """
    推理路由器
    - 分析用户任务
    - 分类任务类型
    - 推荐处理策略
    """
    
    # 任务关键词映射
    TASK_KEYWORDS = {
        TaskType.SEQUENCE_OPERATION: [
            "统计", "序列", "长度", "gc", "转换", "提取", "过滤", "去重", "排序", "stats", "seq"
        ],
        TaskType.QC: [
            "质控", "质量", "过滤", "fastp", "fastqc", "multiqc", "trim", "qc", "clean"
        ],
        TaskType.ASSEMBLY: [
            "组装", "assembly", "spades", "megahit", "组装", "拼接"
        ],
        TaskType.ALIGNMENT: [
            "比对", "映射", "align", "map", "minimap2", "bwa", "blast"
        ],
        TaskType.EVOLUTION: [
            "进化", "系统发育", "树", "phylogeny", "tree", "mafft", "iqtree", "codeml", "选择压力"
        ],
        TaskType.TAXONOMY: [
            "分类", "鉴定", "taxonomy", "kraken", "species", "物种"
        ],
        TaskType.VISUALIZATION: [
            "可视化", "画图", "绘图", "图", "plot", "visualize", "draw"
        ],
        TaskType.KNOWLEDGE: [
            "知识", "查询", "工具", "方法", "介绍", "什么是", "怎么", "如何", "请告诉我"
        ],
    }
    
    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.planner_threshold = self.config.get("planner_threshold", 2)
    
    def analyze(self, user_input: str, context: Dict = None) -> TaskAnalysis:
        """
        分析用户任务
        
        Args:
            user_input: 用户输入
            context: 上下文信息
        
        Returns:
            TaskAnalysis 任务分析结果
        """
        user_input_lower = user_input.lower()
        
        # 1. 识别任务类型
        task_type = self._classify_task(user_input_lower)
        
        # 2. 确定处理策略
        strategy = self._determine_strategy(task_type, user_input_lower, context)
        
        # 3. 推荐相关工具
        relevant_tools = self._recommend_tools(task_type, user_input_lower)
        
        # 4. 生成推理过程
        reasoning = self._generate_reasoning(task_type, strategy, relevant_tools)
        
        # 5. 计算置信度
        confidence = self._calculate_confidence(task_type, user_input_lower)
        
        return TaskAnalysis(
            task_type=task_type,
            suggested_strategy=strategy,
            confidence=confidence,
            relevant_tools=relevant_tools,
            reasoning=reasoning
        )
    
    def _classify_task(self, user_input: str) -> TaskType:
        """分类任务类型"""
        scores = {tt: 0 for tt in TaskType}
        
        for task_type, keywords in self.TASK_KEYWORDS.items():
            for keyword in keywords:
                if keyword in user_input:
                    scores[task_type] += 1
        
        # 找出得分最高的类型
        max_score = max(scores.values())
        
        if max_score == 0:
            return TaskType.GENERAL
        
        for tt, score in scores.items():
            if score == max_score:
                return tt
        
        return TaskType.GENERAL
    
    def _determine_strategy(self, task_type: TaskType, user_input: str, context: Dict = None) -> ProcessStrategy:
        """确定处理策略"""
        # 知识查询类使用搜索策略
        if task_type == TaskType.KNOWLEDGE:
            # 检查是否需要搜索
            if any(kw in user_input for kw in ["最新", "现在", "search", "查一下"]):
                return ProcessStrategy.SEARCH
            return ProcessStrategy.DIRECT_FC
        
        # 工作流关键词
        workflow_keywords = ["工作流", "pipeline", "流程", "批量", "运行"]
        if any(kw in user_input for kw in workflow_keywords):
            return ProcessStrategy.WORKFLOW
        
        # 复杂任务使用计划-执行模式
        complex_keywords = ["多步", "多个", "复杂", "完整", "分析", "整个"]
        if any(kw in user_input for kw in complex_keywords):
            return ProcessStrategy.PLANNER_EXECUTOR
        
        # 默认使用直接 FC
        return ProcessStrategy.DIRECT_FC
    
    def _recommend_tools(self, task_type: TaskType, user_input: str) -> List[str]:
        """推荐相关工具"""
        tool_map = {
            TaskType.SEQUENCE_OPERATION: ["seqkit_stats", "seqkit_fx2tab", "seqkit_grep"],
            TaskType.QC: ["fastp_qc", "fastqc_report", "multiqc_report"],
            TaskType.ASSEMBLY: ["spades_assembly", "megahit_assembly"],
            TaskType.ALIGNMENT: ["minimap2_map", "samtools_process", "blastn_search"],
            TaskType.EVOLUTION: ["mafft_align", "iqtree_build", "codeml_analyze"],
            TaskType.TAXONOMY: ["kraken2_classify", "taxonkit_query"],
            TaskType.VISUALIZATION: ["plot_sequence_quality", "plot_gc_content"],
            TaskType.KNOWLEDGE: ["vitaldb_updater", "web_search"],
        }
        
        return tool_map.get(task_type, [])
    
    def _generate_reasoning(self, task_type: TaskType, strategy: ProcessStrategy, tools: List[str]) -> str:
        """生成推理说明"""
        reasoning = f"任务类型: {task_type.value} | "
        reasoning += f"处理策略: {strategy.value}"
        
        if tools:
            reasoning += f" | 推荐工具: {', '.join(tools[:3])}"
        
        return reasoning
    
    def _calculate_confidence(self, task_type: TaskType, user_input: str) -> float:
        """计算分类置信度"""
        if task_type == TaskType.GENERAL:
            return 0.3
        
        # 根据关键词匹配数量计算置信度
        keywords = self.TASK_KEYWORDS.get(task_type, [])
        matches = sum(1 for kw in keywords if kw in user_input)
        
        confidence = min(0.5 + matches * 0.15, 0.95)
        return confidence
    
    def should_use_planner(self, analysis: TaskAnalysis, tool_count_hint: int = None) -> bool:
        """
        判断是否应该使用 Planner
        
        Args:
            analysis: 任务分析结果
            tool_count_hint: 预估工具数量
        
        Returns:
            是否使用 Planner
        """
        # 明确指定使用工作流
        if analysis.suggested_strategy == ProcessStrategy.WORKFLOW:
            return False  # 工作流单独处理
        
        # 知识查询不使用 Planner
        if analysis.task_type == TaskType.KNOWLEDGE:
            return False
        
        # 简单任务不使用 Planner
        if analysis.suggested_strategy == ProcessStrategy.DIRECT_FC:
            return False
        
        # 复杂任务使用 Planner
        if analysis.suggested_strategy == ProcessStrategy.PLANNER_EXECUTOR:
            return True
        
        # 根据置信度判断
        if tool_count_hint and tool_count_hint >= self.planner_threshold:
            return True
        
        return analysis.confidence < 0.7


# 全局实例
_reasoning_router: Optional[ReasoningRouter] = None


def get_reasoning_router() -> ReasoningRouter:
    """获取推理路由器全局实例"""
    global _reasoning_router
    if _reasoning_router is None:
        _reasoning_router = ReasoningRouter()
    return _reasoning_router
