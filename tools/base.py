"""
工具基类 - 所有生物信息学工具的抽象基类
每个工具需自描述：名称、描述、参数schema，供 LLM 智能选择
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List


class ToolBase(ABC):
    """工具抽象基类"""

    @property
    @abstractmethod
    def name(self) -> str:
        """工具名称"""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """工具功能描述，供 LLM 理解工具用途"""
        pass

    @property
    @abstractmethod
    def parameters(self) -> Dict[str, Any]:
        """
        参数 schema（OpenAI Function Calling 格式）
        {
            "type": "object",
            "properties": {
                "param_name": {
                    "type": "string",
                    "description": "参数说明"
                }
            },
            "required": ["param_name"]
        }
        """
        pass

    @abstractmethod
    def execute(self, **kwargs) -> str:
        """
        执行工具逻辑
        返回结果字符串（纯文本或 JSON 字符串）
        """
        pass

    def to_openai_function(self) -> Dict[str, Any]:
        """转换为 OpenAI Function Calling 格式"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters
            }
        }


class ToolRegistry:
    """工具注册中心"""

    _tools: Dict[str, ToolBase] = {}

    @classmethod
    def register(cls, tool: ToolBase):
        cls._tools[tool.name] = tool

    @classmethod
    def get(cls, name: str) -> ToolBase:
        return cls._tools.get(name)

    @classmethod
    def list_tools(cls) -> List[ToolBase]:
        return list(cls._tools.values())

    @classmethod
    def to_openai_functions(cls) -> List[Dict[str, Any]]:
        """获取所有工具的 Function Calling 定义"""
        return [tool.to_openai_function() for tool in cls._tools.values()]

    @classmethod
    def has_tool(cls, name: str) -> bool:
        """检查工具是否已注册"""
        return name in cls._tools

    @classmethod
    def tool_count(cls) -> int:
        """返回已注册工具数量"""
        return len(cls._tools)
