"""
工作流引擎核心
解析 YAML 工作流定义，按步骤顺序执行工具链，支持参数传递和错误处理
"""
import os
import re
import yaml
from datetime import datetime
from typing import Any, Dict, List, Optional

import config
from tools.base import ToolRegistry


class StepResult:
    """单步执行结果"""

    def __init__(self, step_name: str, success: bool, output: str,
                 error: str = "", skipped: bool = False):
        self.step_name = step_name
        self.success = success
        self.output = output
        self.error = error
        self.skipped = skipped
        self.timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def to_dict(self) -> dict:
        return {
            "step": self.step_name,
            "success": self.success,
            "skipped": self.skipped,
            "output": self.output[:500],  # 摘要
            "error": self.error,
            "timestamp": self.timestamp,
        }


class WorkflowResult:
    """工作流执行结果"""

    def __init__(self, workflow_name: str, success: bool, steps: List[StepResult]):
        self.workflow_name = workflow_name
        self.success = success
        self.steps = steps
        self.start_time = datetime.now()
        self.end_time = datetime.now()

    @property
    def duration(self) -> str:
        delta = self.end_time - self.start_time
        return str(delta).split(".")[0]  # 去掉毫秒

    @property
    def total_steps(self) -> int:
        return len(self.steps)

    @property
    def successful_steps(self) -> int:
        return sum(1 for s in self.steps if s.success)

    @property
    def skipped_steps(self) -> int:
        return sum(1 for s in self.steps if s.skipped)

    @property
    def full_report(self) -> str:
        """生成完整文本报告"""
        lines = [
            f"# 工作流报告: {self.workflow_name}",
            f"执行时间: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}",
            f"总耗时: {self.duration}",
            f"状态: {'成功' if self.success else '失败'}",
            f"步骤: {self.successful_steps}/{self.total_steps} 成功",
            "",
        ]

        if self.skipped_steps > 0:
            lines.append(f"跳过: {self.skipped_steps} 个步骤\n")

        lines.append("---\n")

        for step in self.steps:
            status = "跳过" if step.skipped else ("成功" if step.success else "失败")
            lines.append(f"## 步骤: {step.step_name} [{status}]")
            lines.append(f"时间: {step.timestamp}")
            if step.output:
                # 截断过长的输出
                truncated = step.output[:3000]
                if len(step.output) > 3000:
                    truncated += "\n... (输出已截断)"
                lines.append(f"\n```\n{truncated}\n```\n")
            if step.error:
                lines.append(f"错误: {step.error}\n")

        return "\n".join(lines)

    @property
    def summary_for_llm(self) -> str:
        """生成供 LLM 上下文使用的摘要（限制长度）"""
        lines = [
            f"[工作流 {self.workflow_name}] {'完成' if self.success else '失败'} "
            f"({self.successful_steps}/{self.total_steps} 步骤成功)"
        ]

        for step in self.steps:
            status = "跳过" if step.skipped else ("OK" if step.success else "FAIL")
            # 只取输出前500字符
            output = step.output[:500] if step.output else ""
            if step.error:
                output = f"错误: {step.error}"
            lines.append(f"  [{status}] {step.step_name}: {output}")

        return "\n".join(lines)


class WorkflowEngine:
    """工作流执行引擎"""

    def __init__(self):
        self.workflows: Dict[str, dict] = {}
        self.workflow_dir = config.WORKFLOW_DIR

    def load_workflows(self) -> int:
        """加载所有工作流定义文件，返回加载数量"""
        self.workflows.clear()
        if not os.path.isdir(self.workflow_dir):
            os.makedirs(self.workflow_dir, exist_ok=True)
            return 0

        count = 0
        for filename in os.listdir(self.workflow_dir):
            if filename.endswith(".yaml") or filename.endswith(".yml"):
                filepath = os.path.join(self.workflow_dir, filename)
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        workflow = yaml.safe_load(f)
                    if workflow and "name" in workflow and "steps" in workflow:
                        self.workflows[workflow["name"]] = workflow
                        count += 1
                        print(f"[WorkflowEngine] 已加载工作流: {workflow['name']}")
                    else:
                        print(f"[WorkflowEngine] 警告: {filename} 缺少 name 或 steps 字段")
                except yaml.YAMLError as e:
                    print(f"[WorkflowEngine] 警告: 解析 {filename} 失败: {e}")
                except Exception as e:
                    print(f"[WorkflowEngine] 警告: 加载 {filename} 失败: {e}")

        return count

    def list_workflows(self) -> List[Dict[str, str]]:
        """列出所有可用工作流"""
        result = []
        for name, wf in self.workflows.items():
            info = {
                "name": name,
                "description": wf.get("description", ""),
                "steps": len(wf.get("steps", [])),
                "triggers": wf.get("triggers", []),
            }
            if wf.get("params"):
                info["params"] = [
                    {"name": p.get("name", ""), "description": p.get("description", ""),
                     "required": p.get("required", False)}
                    for p in wf["params"]
                ]
            result.append(info)
        return result

    def get_workflow(self, name: str) -> Optional[dict]:
        """获取工作流定义"""
        return self.workflows.get(name)

    def match_trigger(self, user_input: str) -> Optional[dict]:
        """根据用户输入匹配触发关键字，返回匹配的工作流"""
        input_lower = user_input.lower()
        for name, wf in self.workflows.items():
            for trigger in wf.get("triggers", []):
                if trigger.lower() in input_lower:
                    return wf
        return None

    def run_workflow(self, name: str, params: dict) -> WorkflowResult:
        """执行指定工作流"""
        workflow = self.workflows.get(name)
        if not workflow:
            return WorkflowResult(name, False, [
                StepResult("init", False, "", f"工作流 '{name}' 不存在")
            ])

        print(f"\n{'='*60}")
        print(f"[WorkflowEngine] 开始执行工作流: {name}")
        print(f"  描述: {workflow.get('description', '')}")
        print(f"  参数: {params}")
        print(f"{'='*60}")

        steps = workflow.get("steps", [])
        step_results: List[StepResult] = []
        context: Dict[str, Any] = {"params": params}
        workflow_success = True

        for step_def in steps:
            step_name = step_def.get("name", "unnamed")
            print(f"\n[步骤] {step_name}: {step_def.get('description', '')}")

            # 检查是否跳过
            if step_def.get("skip", False):
                print(f"  -> 跳过 (skip: true)")
                step_results.append(StepResult(step_name, True, "", skipped=True))
                context[step_name] = {"output": "(skipped)"}
                continue

            # 检查条件
            condition = step_def.get("condition")
            if condition and not self._evaluate_condition(condition, context):
                print(f"  -> 跳过 (条件不满足: {condition})")
                step_results.append(StepResult(step_name, True, "", skipped=True))
                context[step_name] = {"output": "(condition not met)"}
                continue

            # 解析参数（支持 ${step.output} 引用）
            step_params = self._resolve_params(step_def.get("params", {}), context)
            tool_name = step_def.get("tool", "")
            on_error = step_def.get("on_error", "abort")

            # 执行步骤
            result = self._execute_step(step_name, tool_name, step_params, on_error)
            step_results.append(result)

            # 更新上下文
            context[step_name] = {"output": result.output}

            # 处理错误
            if not result.success and not result.skipped:
                if on_error == "abort":
                    print(f"  -> 失败，终止工作流: {result.error}")
                    workflow_success = False
                    break
                elif on_error == "skip":
                    print(f"  -> 失败，跳过此步骤")
                    continue
                elif on_error == "continue":
                    print(f"  -> 失败，继续执行")

        final_result = WorkflowResult(name, workflow_success, step_results)
        final_result.end_time = datetime.now()
        print(f"\n{'='*60}")
        print(f"[WorkflowEngine] 工作流 {name} {'完成' if workflow_success else '失败'} "
              f"({final_result.successful_steps}/{final_result.total_steps} 步骤成功)")
        print(f"{'='*60}\n")

        # 保存报告
        report_path = os.path.join(
            config.REPORTS_DIR,
            f"workflow_{name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        )
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(final_result.full_report)
        print(f"[WorkflowEngine] 报告已保存: {report_path}")

        return final_result

    def _execute_step(self, step_name: str, tool_name: str, params: dict,
                      on_error: str) -> StepResult:
        """执行单个步骤"""
        # 检查工具是否注册
        if not ToolRegistry.has_tool(tool_name):
            msg = (f"工具 '{tool_name}' 未注册。"
                   f"可用工具: {[t.name for t in ToolRegistry.list_tools()]}")
            print(f"  -> 错误: {msg}")
            return StepResult(step_name, False, "", msg)

        # 执行工具
        try:
            from tools import execute_tool
            output = execute_tool(tool_name, **params)

            # 检查输出是否包含错误信息
            is_error = output.startswith("错误:") or output.startswith("[错误]")

            if is_error:
                print(f"  -> 失败: {output[:200]}")
                return StepResult(step_name, False, output, output[:200])
            else:
                print(f"  -> 成功")
                if output:
                    preview = output[:200].replace("\n", " ")
                    print(f"  -> {preview}...")
                return StepResult(step_name, True, output)

        except Exception as e:
            print(f"  -> 异常: {str(e)}")
            return StepResult(step_name, False, "", str(e))

    def _resolve_params(self, params: dict, context: dict) -> dict:
        """解析参数中的变量引用 ${step.output} 或 ${params.xxx}"""
        resolved = {}
        for key, value in params.items():
            if isinstance(value, str):
                resolved[key] = self._resolve_variable(value, context)
            elif isinstance(value, dict):
                resolved[key] = self._resolve_params(value, context)
            elif isinstance(value, list):
                resolved[key] = [
                    self._resolve_variable(v, context) if isinstance(v, str) else v
                    for v in value
                ]
            else:
                resolved[key] = value
        return resolved

    def _resolve_variable(self, value: str, context: dict) -> str:
        """替换单个变量引用"""
        pattern = r'\$\{([^}]+)\}'

        def replacer(match):
            var_path = match.group(1)
            parts = var_path.split(".", 1)

            if parts[0] in context:
                obj = context[parts[0]]
                if len(parts) > 1 and isinstance(obj, dict):
                    return str(obj.get(parts[1], match.group(0)))
                return str(obj) if isinstance(obj, str) else match.group(0)
            return match.group(0)

        return re.sub(pattern, replacer, value)

    def _evaluate_condition(self, condition: str, context: dict) -> bool:
        """简单条件判断"""
        # 检查上一步是否成功: "prev.success"
        if condition.endswith(".success"):
            step_name = condition.rsplit(".", 1)[0]
            if step_name in context:
                return not context[step_name].get("output", "").startswith("错误") and \
                       not context[step_name].get("output", "").startswith("[错误]")
        # 检查上一步输出是否包含: "step.output contains 'xxx'"
        if "contains" in condition:
            parts = condition.split("contains", 1)
            var_ref = parts[0].strip()
            search_text = parts[1].strip().strip("'\"")
            pattern = r'\$\{([^}]+)\}'
            m = re.search(pattern, var_ref)
            if m:
                var_path = m.group(1)
                parts_inner = var_path.split(".", 1)
                if parts_inner[0] in context:
                    obj = context[parts_inner[0]]
                    if len(parts_inner) > 1 and isinstance(obj, dict):
                        return search_text in obj.get(parts_inner[1], "")
            return False

        return True
