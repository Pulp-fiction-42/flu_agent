"""
WorkflowRunnerTool - 将工作流引擎注册为 Function Calling 工具
LLM 可以通过此工具触发任意工作流的执行
"""
from typing import Any, Dict
from tools.base import ToolBase, ToolRegistry
from workflow import get_engine, list_workflows


class WorkflowRunnerTool(ToolBase):
    """工作流执行工具 - 让 LLM 可以触发预定义的工作流"""

    @property
    def name(self) -> str:
        return "workflow_run"

    @property
    def description(self) -> str:
        workflows = list_workflows()
        if not workflows:
            return "执行预定义的生信分析工作流（目前无可用工作流）"

        wf_list = "\n".join([
            f"  - {wf['name']}: {wf['description']}" for wf in workflows
        ])
        param_list = ""
        for wf in workflows:
            if wf.get("params"):
                param_list += f"\n  [{wf['name']}]: " + ", ".join([
                    f"{p['name']}({'必填' if p['required'] else '可选'})"
                    for p in wf["params"]
                ])

        return (
            "执行预定义的生信分析工作流。工作流是多个工具的自动化流水线，"
            "可以一键完成从质控到组装到分析的全流程。\n\n"
            f"可用工作流:\n{wf_list}\n"
            f"参数说明:{param_list}\n\n"
            "使用方式: 指定 workflow_name 和对应的参数即可触发完整流程。"
        )

    @property
    def parameters(self) -> Dict[str, Any]:
        # 动态生成参数 schema，基于已加载的工作流
        properties = {
            "workflow_name": {
                "type": "string",
                "description": "工作流名称",
                "enum": [wf["name"] for wf in list_workflows()],
            },
            "input_file": {
                "type": "string",
                "description": "输入文件路径（如 FASTQ 文件）",
            },
            "output_dir": {
                "type": "string",
                "description": "输出目录（默认自动创建）",
            },
            "skip_steps": {
                "type": "string",
                "description": "要跳过的步骤名称，逗号分隔（如 'kraken2_classify'）",
                "default": "",
            },
        }

        # 动态添加各工作流的特定参数
        for wf in list_workflows():
            for p in wf.get("params", []):
                if p["name"] not in properties and p["name"] not in ["input_file", "output_dir"]:
                    properties[p["name"]] = {
                        "type": "string",
                        "description": p.get("description", ""),
                    }

        return {
            "type": "object",
            "properties": properties,
            "required": ["workflow_name"],
        }

    def execute(self, workflow_name: str, input_file: str = "",
                output_dir: str = "", skip_steps: str = "", **kwargs) -> str:
        engine = get_engine()

        # 检查工作流是否存在
        workflow = engine.get_workflow(workflow_name)
        if not workflow:
            available = [wf["name"] for wf in list_workflows()]
            return f"错误: 工作流 '{workflow_name}' 不存在。可用: {available}"

        # 构建参数
        params = {}
        if input_file:
            params["input_file"] = input_file
        if output_dir:
            params["output_dir"] = output_dir
        # 传递其他工作流特定参数
        for key, value in kwargs.items():
            if value and key not in ["skip_steps"]:
                params[key] = value

        # 处理跳过步骤
        skip_list = [s.strip() for s in skip_steps.split(",") if s.strip()]
        if skip_list:
            for step in workflow.get("steps", []):
                if step.get("tool") in skip_list or step.get("name") in skip_list:
                    step["skip"] = True

        # 执行工作流
        result = engine.run_workflow(workflow_name, params)
        return result.summary_for_llm


class WorkflowListTool(ToolBase):
    """工作流列表查询工具"""

    @property
    def name(self) -> str:
        return "workflow_list"

    @property
    def description(self) -> str:
        return "列出所有可用的生信分析工作流及其描述、步骤和所需参数。"

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {},
        }

    def execute(self) -> str:
        workflows = list_workflows()
        if not workflows:
            return "当前无可用工作流。请在 workflow/ 目录下添加 YAML 定义文件。"

        lines = ["可用工作流:\n"]
        for wf in workflows:
            lines.append(f"### {wf['name']}")
            lines.append(f"描述: {wf['description']}")
            lines.append(f"步骤数: {wf['steps']}")
            if wf.get("triggers"):
                lines.append(f"触发关键字: {', '.join(wf['triggers'])}")
            if wf.get("params"):
                param_desc = "\n".join([
                    f"  - {p['name']}{'(必填)' if p['required'] else ''}: {p['description']}"
                    for p in wf["params"]
                ])
                lines.append(f"参数:\n{param_desc}")
            lines.append("")

        return "\n".join(lines)


def register_workflow_tools():
    """将工作流相关工具注册到 ToolRegistry
    注意：workflow_run 已降级为知识参考，不再自动注册为工具
    如需重新启用，请在 config.yaml 中设置 enable_workflow_tool: true
    """
    # 工作流降级为知识库参考，不注册为可调用工具
    # 如需恢复工具调用，取消下方注释:
    # ToolRegistry.register(WorkflowRunnerTool())
    # ToolRegistry.register(WorkflowListTool())
    # print("[BioAgent] 已注册工作流工具: workflow_run, workflow_list")
    pass
