"""
VITALdb Knowledge Updater - VITALdb 知识库更新工具
动态更新病毒工具知识库
"""
import os
import json
from typing import Dict, Any, Optional, List
from pathlib import Path
from tools.base import ToolBase


class VitaldbUpdater(ToolBase):
    """VITALdb 知识库更新工具"""
    
    @property
    def name(self) -> str:
        return "vitaldb_updater"
    
    @property
    def description(self) -> str:
        return """更新 VITALdb 病毒工具知识库。

**使用场景：**
- 查询特定病毒工具的用法
- 列出某个分类下的所有工具
- 获取工具的详细信息

**参数：**
- action: 操作类型 (list_categories/list_tools/get_tool_info/search)
- category: 分类名称 (assembly/alignment/qc/variant/phylogenetics/classification/sequence/visualization/utilities)
- tool_name: 工具名称（用于查询具体工具）"""
    
    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "操作类型",
                    "enum": ["list_categories", "list_tools", "get_tool_info", "search"]
                },
                "category": {
                    "type": "string",
                    "description": "分类名称"
                },
                "tool_name": {
                    "type": "string",
                    "description": "工具名称"
                },
                "query": {
                    "type": "string",
                    "description": "搜索关键词"
                }
            }
        }
    
    # 分类映射
    CATEGORIES = {
        "assembly": "病毒基因组组装",
        "alignment": "病毒比对与映射",
        "qc": "病毒序列质控",
        "variant": "变异检测",
        "phylogenetics": "进化分析",
        "classification": "病毒分类",
        "sequence": "序列处理",
        "visualization": "可视化",
        "utilities": "实用工具"
    }
    
    def __init__(self, config=None):
        super().__init__()
        self._load_knowledge()
    
    def _load_knowledge(self):
        """加载知识库"""
        from config_loader import get_skill_dir
        skill_dir = get_skill_dir()
        self.knowledge_dir = os.path.join(skill_dir, "knowledge", "vitaldb")
        
        # 加载工具索引
        self.tools_index = self._build_tools_index()
    
    def _build_tools_index(self) -> Dict[str, Any]:
        """构建工具索引"""
        # 静态工具数据（可在运行时从文件扩展）
        tools_data = {
            "assembly": {
                "name": "病毒基因组组装",
                "tools": [
                    {"name": "SPAdes", "desc": "通用组装工具，支持病毒"},
                    {"name": "MEGAHIT", "desc": "高效短读组装"},
                    {"name": "Canu", "desc": "长读长组装"},
                    {"name": "Flye", "desc": "长读长组装"},
                    {"name": "Velvet", "desc": "经典组装器"},
                    {"name": "Raven", "desc": "快速长读组装"},
                    {"name": "VIP", "desc": "病毒识别和组装"}
                ]
            },
            "alignment": {
                "name": "病毒比对与映射",
                "tools": [
                    {"name": "BWA", "desc": "Burrows-Wheeler比对器"},
                    {"name": "Bowtie2", "desc": "快速比对工具"},
                    {"name": "Minimap2", "desc": "长读长比对"},
                    {"name": "STAR", "desc": "RNA-seq比对"},
                    {"name": "HISAT2", "desc": "快速RNA-seq比对"},
                    {"name": "ViReMa", "desc": "病毒reads映射"},
                    {"name": "Samtools", "desc": "SAM/BAM处理"}
                ]
            },
            "qc": {
                "name": "病毒序列质控",
                "tools": [
                    {"name": "FastQC", "desc": "测序质量评估"},
                    {"name": "Fastp", "desc": "快速质控预处理"},
                    {"name": "Trimmomatic", "desc": "序列修剪"},
                    {"name": "Cutadapt", "desc": "接头去除"},
                    {"name": "PRINSEQ", "desc": "质控过滤"},
                    {"name": "MultiQC", "desc": "质控报告汇总"}
                ]
            },
            "variant": {
                "name": "变异检测",
                "tools": [
                    {"name": "FreeBayes", "desc": "贝叶斯变异检测"},
                    {"name": "GATK", "desc": "基因组分析工具包"},
                    {"name": "LoFreq", "desc": "低频变异检测"},
                    {"name": "iVar", "desc": "病毒变异分析"},
                    {"name": "VarScan", "desc": "变异调用"},
                    {"name": "SnpEff", "desc": "变异注释"}
                ]
            },
            "phylogenetics": {
                "name": "进化分析",
                "tools": [
                    {"name": "IQ-TREE", "desc": "高效最大似然树"},
                    {"name": "RAxML", "desc": "最大似然树"},
                    {"name": "FastTree", "desc": "快速ML树"},
                    {"name": "MEGA", "desc": "分子进化分析"},
                    {"name": "PAML", "desc": "分子进化分析"},
                    {"name": "HyPhy", "desc": "选择压力分析"},
                    {"name": "Nextstrain", "desc": "实时进化分析"}
                ]
            },
            "classification": {
                "name": "病毒分类",
                "tools": [
                    {"name": "BLAST", "desc": "序列比对搜索"},
                    {"name": "DIAMOND", "desc": "快速蛋白比对"},
                    {"name": "Kraken2", "desc": "快速分类"},
                    {"name": "KrakenUniq", "desc": "唯一k-mer分类"},
                    {"name": "MMseqs2", "desc": "超快速序列搜索"},
                    {"name": "TaxonKit", "desc": "分类学命令行工具"}
                ]
            },
            "sequence": {
                "name": "序列处理",
                "tools": [
                    {"name": "SeqKit", "desc": "序列处理神器"},
                    {"name": "BioPython", "desc": "生物计算Python库"},
                    {"name": "BEDTools", "desc": "基因组区间工具"},
                    {"name": "Seqtk", "desc": "序列子集提取"},
                    {"name": "Primer3", "desc": "引物设计"}
                ]
            },
            "visualization": {
                "name": "可视化",
                "tools": [
                    {"name": "JBrowse", "desc": "基因组浏览器"},
                    {"name": "IGV", "desc": "高通量数据可视化"},
                    {"name": "Artemis", "desc": "基因组查看器"},
                    {"name": "FigTree", "desc": "系统发育树查看"},
                    {"name": "iTOL", "desc": "进化树在线可视化"}
                ]
            },
            "utilities": {
                "name": "实用工具",
                "tools": [
                    {"name": "SRA Toolkit", "desc": "NCBI数据下载"},
                    {"name": "Snakemake", "desc": "工作流管理"},
                    {"name": "Nextflow", "desc": "流程编排"},
                    {"name": "Galaxy", "desc": "图形化分析平台"},
                    {"name": "Docker", "desc": "容器化"}
                ]
            }
        }
        return tools_data
    
    def execute(self, action: str = "list_categories", category: str = "", tool_name: str = "", query: str = "", **kwargs) -> str:
        """执行知识库查询"""
        if action == "list_categories":
            return self._list_categories()
        elif action == "list_tools":
            return self._list_tools(category)
        elif action == "get_tool_info":
            return self._get_tool_info(tool_name, category)
        elif action == "search":
            return self._search_tools(query)
        else:
            return f"错误: 未知操作 - {action}"
    
    def _list_categories(self) -> str:
        """列出所有分类"""
        categories = []
        for key, info in self.tools_index.items():
            categories.append({
                "id": key,
                "name": info["name"],
                "tool_count": len(info["tools"])
            })
        
        output = [f"VITALdb 知识库共 {len(categories)} 个分类:\n"]
        for c in categories:
            output.append(f"  - {c['id']}: {c['name']} ({c['tool_count']} 个工具)")
        
        return "\n".join(output)
    
    def _list_tools(self, category: str) -> str:
        """列出指定分类的工具"""
        if not category:
            return "错误: 请指定分类"
        
        if category not in self.tools_index:
            return f"错误: 未知分类 '{category}'"
        
        info = self.tools_index[category]
        output = [f"分类: {info['name']} (共 {len(info['tools'])} 个工具)\n"]
        
        for tool in info["tools"]:
            output.append(f"  - {tool['name']}: {tool['desc']}")
        
        return "\n".join(output)
    
    def _get_tool_info(self, tool_name: str, category: str = "") -> str:
        """获取工具详细信息"""
        if not tool_name:
            return "错误: 请指定工具名称"
        
        tool_name_lower = tool_name.lower()
        
        # 搜索所有分类
        for cat_id, info in self.tools_index.items():
            if category and cat_id != category:
                continue
            for tool in info["tools"]:
                if tool["name"].lower() == tool_name_lower:
                    return f"""=== 工具详情 ===
名称: {tool['name']}
分类: {info['name']}
描述: {tool['desc']}"""
        
        return f"错误: 未找到工具 '{tool_name}'"
    
    def _search_tools(self, query: str) -> str:
        """搜索工具"""
        if not query:
            return "错误: 请输入搜索关键词"
        
        query_lower = query.lower()
        results = []
        
        for cat_id, info in self.tools_index.items():
            for tool in info["tools"]:
                if (query_lower in tool["name"].lower() or 
                    query_lower in tool["desc"].lower()):
                    results.append({
                        "tool": tool,
                        "category": cat_id,
                        "category_name": info["name"]
                    })
        
        if not results:
            return f"未找到匹配 '{query}' 的工具"
        
        output = [f"搜索 '{query}' 找到 {len(results)} 个结果:\n"]
        for r in results:
            output.append(f"  - {r['tool']['name']} ({r['category_name']}): {r['tool']['desc']}")
        
        return "\n".join(output)
    
    def to_openai_functions(self) -> Dict[str, Any]:
        """转换为 OpenAI Function Calling 格式"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "description": "操作类型",
                            "enum": ["list_categories", "list_tools", "get_tool_info", "search"]
                        },
                        "category": {
                            "type": "string",
                            "description": "分类名称"
                        },
                        "tool_name": {
                            "type": "string",
                            "description": "工具名称"
                        },
                        "query": {
                            "type": "string",
                            "description": "搜索关键词"
                        }
                    }
                }
            }
        }


def get_instance(config=None) -> VitaldbUpdater:
    """获取工具实例"""
    return VitaldbUpdater(config)
