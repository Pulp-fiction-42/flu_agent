"""
工具管理器 - 工具描述增强与管理
"""
import json
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field


@dataclass
class ToolDescriptor:
    """工具描述符"""
    name: str
    description: str
    parameters: Dict = field(default_factory=dict)
    category: str = ""
    tags: List[str] = field(default_factory=list)
    examples: List[str] = field(default_factory=list)
    input_types: List[str] = field(default_factory=list)  # 支持的输入格式
    output_types: List[str] = field(default_factory=list)  # 输出的格式


class ToolsManager:
    """
    工具管理器
    - 工具元数据管理
    - 工具描述增强
    - 数据流校验
    - 工具推荐
    """
    
    # 工具分类定义
    CATEGORIES = {
        "sequence": ["seqkit"],
        "qc": ["fastp", "fastqc", "multiqc", "cutadapt"],
        "assembly": ["spades", "megahit"],
        "alignment": ["minimap2", "samtools", "blastn", "diamond"],
        "taxonomy": ["kraken2", "taxonkit"],
        "evolution": ["mafft", "trimal", "iqtree2", "codeml"],
        "viz": ["plot"],
        "knowledge": ["web_search", "text_processing", "vitaldb"],
    }
    
    # 文件格式映射
    FORMAT_MAPPING = {
        ".fa": "fasta",
        ".fasta": "fasta",
        ".fq": "fastq",
        ".fastq": "fastq",
        ".fa.gz": "fasta_gz",
        ".fq.gz": "fastq_gz",
        ".bam": "bam",
        ".sam": "sam",
        ".vcf": "vcf",
        ".bed": "bed",
        ".gtf": "gtf",
        ".gff": "gff",
        ".aln": "alignment",
        ".tree": "tree",
        ".tre": "tree",
    }
    
    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.tool_descriptors: Dict[str, ToolDescriptor] = {}
        self._load_builtin_descriptors()
    
    def _load_builtin_descriptors(self):
        """加载内置工具描述"""
        # 预定义一些常用工具的增强描述
        descriptors = {
            "seqkit_stats": ToolDescriptor(
                name="seqkit_stats",
                description="序列统计工具，计算序列数、总长度、GC含量、平均长度等",
                category="sequence",
                tags=["统计", "QC", "序列分析"],
                input_types=["fasta", "fastq", "fasta_gz", "fastq_gz"],
                output_types=["text", "json"],
                examples=["对 FASTQ 文件进行基本统计"]
            ),
            "fastp_qc": ToolDescriptor(
                name="fastp_qc",
                description="快速质控和预处理工具，支持接头去除、质量过滤",
                category="qc",
                tags=["质控", "过滤", "预处理"],
                input_types=["fastq", "fastq_gz"],
                output_types=["fastq", "json", "html"],
                examples=["对双端测序数据进行质控"]
            ),
            "minimap2_map": ToolDescriptor(
                name="minimap2_map",
                description="长读长序列比对工具",
                category="alignment",
                tags=["比对", "映射", "长读"],
                input_types=["fasta", "fastq", "bam", "sam"],
                output_types=["paf", "sam"],
                examples=["将 Nanopore  reads 映射到参考基因组"]
            ),
            "mafft_align": ToolDescriptor(
                name="mafft_align",
                description="多序列比对工具",
                category="evolution",
                tags=["比对", "多序列", "进化"],
                input_types=["fasta"],
                output_types=["fasta", "clustal"],
                examples=["对病毒序列进行多序列比对"]
            ),
            "iqtree_build": ToolDescriptor(
                name="iqtree_build",
                description="最大似然系统发育树构建",
                category="evolution",
                tags=["进化", "系统发育", "树"],
                input_types=["fasta", "alignment"],
                output_types=["tree", "iqtree"],
                examples=["构建病毒进化树"]
            ),
        }
        
        self.tool_descriptors.update(descriptors)
    
    def register_descriptor(self, descriptor: ToolDescriptor):
        """注册工具描述符"""
        self.tool_descriptors[descriptor.name] = descriptor
    
    def get_descriptor(self, tool_name: str) -> Optional[ToolDescriptor]:
        """获取工具描述符"""
        return self.tool_descriptors.get(tool_name)
    
    def enhance_description(self, tool_name: str, base_description: str) -> str:
        """
        增强工具描述
        
        在基础描述上添加：
        - 分类信息
        - 输入输出格式
        - 使用示例
        """
        desc = base_description
        descriptor = self.get_descriptor(tool_name)
        
        if descriptor:
            # 添加分类标签
            if descriptor.category:
                desc += f"\n\n**分类**: {descriptor.category}"
            
            # 添加支持的格式
            if descriptor.input_types:
                desc += f"\n\n**输入格式**: {', '.join(descriptor.input_types)}"
            if descriptor.output_types:
                desc += f"\n\n**输出格式**: {', '.join(descriptor.output_types)}"
            
            # 添加示例
            if descriptor.examples:
                desc += f"\n\n**示例**: {descriptor.examples[0]}"
        
        return desc
    
    def validate_data_flow(self, tools_sequence: List[Dict]) -> Dict[str, Any]:
        """
        验证工具序列的数据流兼容性
        
        Args:
            tools_sequence: [{"tool": "tool_name", "params": {...}}, ...]
        
        Returns:
            {"valid": bool, "errors": [...], "warnings": [...]}
        """
        errors = []
        warnings = []
        
        for i in range(len(tools_sequence) - 1):
            current = tools_sequence[i]
            next_tool = tools_sequence[i + 1]
            
            current_desc = self.get_descriptor(current.get("tool", ""))
            next_desc = self.get_descriptor(next_tool.get("tool", ""))
            
            if not current_desc or not next_desc:
                continue
            
            # 检查输出输入兼容性
            compatible = False
            for out_type in current_desc.output_types:
                if out_type in next_desc.input_types:
                    compatible = True
                    break
            
            if not compatible:
                warnings.append(
                    f"工具 '{current['tool']}' 输出格式可能不匹配 '{next_tool['tool']}' 的输入"
                )
        
        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
        }
    
    def recommend_tools(self, task: str, context: Dict = None) -> List[ToolDescriptor]:
        """
        根据任务推荐工具
        
        Args:
            task: 任务描述
            context: 上下文信息（如输入文件格式）
        
        Returns:
            推荐的工具描述符列表
        """
        task_lower = task.lower()
        results = []
        
        # 关键词匹配
        keywords_map = {
            "统计": ["seqkit_stats"],
            "质量": ["fastp_qc", "fastqc_report"],
            "质控": ["fastp_qc", "fastqc_report", "multiqc_report"],
            "组装": ["spades_assembly", "megahit_assembly"],
            "比对": ["minimap2_map", "blastn_search", "mafft_align"],
            "进化": ["iqtree_build", "mafft_align", "codeml_analyze"],
            "树": ["iqtree_build"],
            "变异": ["blastn_search", "diamond_search"],
            "分类": ["kraken2_classify", "taxonkit_query"],
        }
        
        matched_tools = set()
        for keyword, tools in keywords_map.items():
            if keyword in task_lower:
                matched_tools.update(tools)
        
        for tool_name in matched_tools:
            desc = self.get_descriptor(tool_name)
            if desc:
                results.append(desc)
        
        return results
    
    def get_tools_by_category(self, category: str) -> List[ToolDescriptor]:
        """按分类获取工具"""
        results = []
        for desc in self.tool_descriptors.values():
            if desc.category == category:
                results.append(desc)
        return results
    
    def get_all_categories(self) -> List[str]:
        """获取所有分类"""
        categories = set()
        for desc in self.tool_descriptors.values():
            if desc.category:
                categories.add(desc.category)
        return sorted(list(categories))


# 全局实例
_tools_manager: Optional[ToolsManager] = None


def get_tools_manager() -> ToolsManager:
    """获取工具管理器全局实例"""
    global _tools_manager
    if _tools_manager is None:
        _tools_manager = ToolsManager()
    return _tools_manager
