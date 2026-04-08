#!/usr/bin/env python3
"""
FluAgent 入口文件
导入并使用 core.agent 中的 FluAgent 类
"""

from core.agent import FluAgent

__all__ = ["FluAgent"]


def create_flu_agent(model: str = None, **kwargs) -> FluAgent:
    """创建 FluAgent 生物信息学分析 Agent"""
    return FluAgent(model=model, **kwargs)


if __name__ == "__main__":
    agent = create_bio_agent()
    agent.run()
