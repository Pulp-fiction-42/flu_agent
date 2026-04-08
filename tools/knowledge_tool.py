"""
知识库工具 - 搜索、文本处理、VITALdb、网页抓取、PubMed
"""
from .base import ToolRegistry
from .search_tool import SearchTool
from .text_tool import TextProcessingTool
from .vitaldb_updater import VitaldbUpdater
from .web_fetch_tool import WebFetchTool
from .pubmed_tool import PubMedTool


def register_all_tools():
    """注册所有知识库工具"""
    try:
        ToolRegistry.register(SearchTool(None))
    except Exception as e:
        print(f"[FluAgent] 加载 SearchTool 失败: {e}")
    try:
        ToolRegistry.register(TextProcessingTool(None))
    except Exception as e:
        print(f"[FluAgent] 加载 TextProcessingTool 失败: {e}")
    try:
        ToolRegistry.register(VitaldbUpdater(None))
    except Exception as e:
        print(f"[FluAgent] 加载 VitaldbUpdater 失败: {e}")
    try:
        ToolRegistry.register(WebFetchTool(None))
    except Exception as e:
        print(f"[FluAgent] 加载 WebFetchTool 失败: {e}")
    try:
        ToolRegistry.register(PubMedTool(None))
    except Exception as e:
        print(f"[FluAgent] 加载 PubMedTool 失败: {e}")
