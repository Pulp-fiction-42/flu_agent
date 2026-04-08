"""
工具自动发现与注册
扫描 tools/ 目录下的所有工具模块，自动注册到 ToolRegistry
"""

from .base import ToolRegistry

# 工具模块列表 - 新增工具时在此添加
TOOL_MODULES = [
    "seqkit",       # 序列处理（stats/fx2tab/grep/rmdup/sort）
    "qc",           # 质控（fastp/fastqc/multiqc/cutadapt）
    "assembly",     # 组装（spades/megahit）
    "alignment",    # 比对（minimap2/samtools/blastn/diamond）
    "taxonomy",     # 分类（kraken2）
    "evolution",    # 进化（mafft/trimal/iqtree2/codeml）
    "viz",          # 可视化（质量图、长度分布、GC含量等）
    "other",        # 其他（swarm/circos/hhblits/hhsearch）
    "knowledge",    # 知识库工具（搜索/文本处理/VITALdb）
]


def discover_and_register_tools():
    """自动发现并注册所有工具"""
    for module_name in TOOL_MODULES:
        try:
            module = __import__(f"tools.{module_name}_tool",
                                fromlist=["register_all_tools"])
            module.register_all_tools()
            print(f"[FluAgent] 已加载工具模块: {module_name}")
        except ImportError as e:
            print(f"[FluAgent] 警告: 无法加载工具模块 {module_name}: {e}")
        except Exception as e:
            print(f"[FluAgent] 警告: 加载工具模块 {module_name} 时出错: {e}")


def get_available_tools():
    """获取所有可用工具信息"""
    tools = ToolRegistry.list_tools()
    return [
        {
            "name": t.name,
            "description": t.description,
            "parameters": t.parameters
        }
        for t in tools
    ]


def execute_tool(tool_name: str, **kwargs) -> str:
    """执行指定工具"""
    tool = ToolRegistry.get(tool_name)
    if not tool:
        return f"错误: 未知工具 '{tool_name}'"
    return tool.execute(**kwargs)
