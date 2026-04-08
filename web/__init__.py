"""
Web 模块初始化
"""

from .app import FluAgentWeb, create_app, launch_web

__all__ = [
    "FluAgentWeb",
    "create_app",
    "launch_web",
]
