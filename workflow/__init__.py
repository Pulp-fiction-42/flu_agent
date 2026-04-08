"""
工作流自动发现与加载
"""
from .engine import WorkflowEngine

_engine_instance = None


def get_engine() -> WorkflowEngine:
    """获取全局 WorkflowEngine 单例"""
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = WorkflowEngine()
        _engine_instance.load_workflows()
    return _engine_instance


def list_workflows():
    """列出所有可用工作流"""
    return get_engine().list_workflows()


def run_workflow(name: str, params: dict):
    """执行指定工作流"""
    return get_engine().run_workflow(name, params)


def match_trigger(user_input: str):
    """根据用户输入匹配触发关键字"""
    return get_engine().match_trigger(user_input)
