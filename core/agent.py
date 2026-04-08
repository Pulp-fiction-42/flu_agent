"""
BioAgent 核心类
参考 POPGENAGENT 架构设计，引入 Planner-Executor 模式
支持三角色 Agent 模式（Ask-Plan-Craft）

V2 升级：
- Docker 容器化执行器
- 多用户会话隔离
- Evaluator 结果验证集成
- "校准弃权"机制
"""
import json
import os
import requests
import asyncio
import httpx
from typing import Dict, List, Any, Optional, AsyncGenerator
from .prompts import SYSTEM_PROMPT
from .ask_agent import AskAgent
from .plan_agent import PlanAgent
from .craft_agent import CraftAgent
from .evaluator import ResultEvaluator, ResultStatus
from .session_manager import SessionManager, get_session_manager


class FluAgent:
    """
    BioAgent - 生物信息学分析 Agent (重构版)
    支持：
    - Planner-Executor 双阶段模式（复杂任务）
    - 直接 FC 模式（简单任务）
    - 工具自动发现与 Function Calling
    - 工作流引擎
    - 知识库上下文注入
    - 会话记忆管理
    """
    
    def __init__(
        self,
        name: str = "FluAgent",
        model: str = None,
        enable_planner: bool = False,  # 默认关闭，模型升级后可启用
        planner_threshold: int = 2,
        session_id: str = None,
        _base_url: str = None,   # 运行时覆盖（来自 provider_manager 选择）
        _api_key: str = None,    # 运行时覆盖
    ):
        from config_loader import get_config, get_llm_config
        from tools.base import ToolRegistry
        from tools import discover_and_register_tools
        
        cfg = get_config()
        llm_cfg = get_llm_config()
        
        self.name = name
        self.model = model or cfg.llm.model
        self.enable_planner = enable_planner and cfg.agent.enable_planner
        self.planner_threshold = planner_threshold or cfg.agent.planner_threshold
        self.session_id = session_id
        
        # FC 循环配置
        self.max_tool_rounds = cfg.agent.max_tool_rounds
        
        # LLM 配置（支持运行时覆盖）
        self.llm_base_url = _base_url or cfg.llm.base_url
        self.llm_api_key = _api_key or cfg.llm.api_key
        self.llm_timeout = cfg.llm.timeout
        self.temperature = cfg.llm.temperature
        
        # 对话历史
        self.conversation_history: List[Dict[str, str]] = []

        # 待保存内容（退出时询问是否保存）
        self.pending_save: Optional[Dict[str, str]] = None
        
        # 加载知识库
        self.knowledge_context = self._load_knowledge()
        
        # 加载工具
        discover_and_register_tools()
        self._load_workflows()
        
        self.tools = ToolRegistry.to_openai_functions()
        
        # 构建系统提示词
        self.system_prompt = self._build_system_prompt()
        
        # Planner 和 Executor 实例
        self.planner = None
        self.executor = None
        if self.enable_planner:
            from .planner import Planner
            from .executor import Executor
            self.planner = Planner(
                llm_base_url=self.llm_base_url,
                model=self.model,
                temperature=self.temperature,
                timeout=self.llm_timeout,
            )
            self.executor = Executor(
                llm_base_url=self.llm_base_url,
                model=self.model,
                temperature=self.temperature,
                timeout=self.llm_timeout,
                tools=self.tools,
            )
        
        # 三角色 Agent（Ask-Plan-Craft）
        self.multi_agent_enabled = cfg.multi_agent.enable
        self.ask_agent = None
        self.plan_agent = None
        self.craft_agent = None

        # V2 新增：结果评估器（校准弃权机制）
        self.evaluator = ResultEvaluator({
            "min_success_score": 0.7,
            "max_retries": 3,
        })
        self.calibration_enabled = cfg.multi_agent.calibration_enable

        # V2 新增：Docker 执行器
        self.docker_executor = None
        self.docker_enabled = cfg.docker.enable

        if self.multi_agent_enabled:
            # 创建 LLM 客户端封装
            llm_client = lambda messages, tools=None: self._call_llm(messages, tools=tools)
            # 创建工具执行器封装
            tool_executor = lambda name, args: self._execute_tool(name, args)

            self.ask_agent = AskAgent(
                llm_client=llm_client,
                max_rounds=cfg.multi_agent.ask.max_rounds,
            )
            self.plan_agent = PlanAgent(
                llm_client=llm_client,
                tools=self.tools,
                validate_dataflow=cfg.multi_agent.plan.validate_dataflow,
            )
            self.craft_agent = CraftAgent(
                llm_client=llm_client,
                tool_executor=tool_executor,
                tools=self.tools,
                max_tool_rounds=cfg.multi_agent.craft.max_tool_rounds,
                retry_on_fail=cfg.multi_agent.craft.retry_on_fail,
            )
            print(f"[FluAgent] 三角色模式已启用: Ask-Plan-Craft")

        # V2：初始化 Docker 执行器
        if self.docker_enabled:
            try:
                from .docker_executor import DockerExecutor
                self.docker_executor = DockerExecutor()
                if self.docker_executor.is_available():
                    print(f"[FluAgent] Docker 执行器已启用")
                else:
                    print(f"[FluAgent] Docker 不可用，降级到本地执行")
                    self.docker_executor = None
            except Exception as e:
                print(f"[FluAgent] Docker 执行器初始化失败: {e}")
                self.docker_executor = None

        # V2：会话管理器
        self.session_manager = get_session_manager()
        self.current_session = self.session_manager.create_session()
    
    def _load_knowledge(self) -> str:
        """加载知识库内容"""
        from config_loader import get_knowledge_dir
        
        knowledge_context = []
        knowledge_dir = get_knowledge_dir()
        
        if os.path.exists(knowledge_dir):
            for filename in os.listdir(knowledge_dir):
                if filename.endswith('.md'):
                    filepath = os.path.join(knowledge_dir, filename)
                    with open(filepath, 'r', encoding='utf-8') as f:
                        content = f.read()
                        knowledge_context.append(f"\n\n=== {filename} ===\n{content}")
        
        return "\n".join(knowledge_context)
    
    def _load_workflows(self):
        """加载工作流引擎（作为知识参考，不注册为工具）"""
        try:
            # 不再注册 workflow_run 工具，只加载工作流信息用于知识库
            from workflow.runner_tool import register_workflow_tools
            register_workflow_tools()  # 现在是空操作
            from workflow import get_engine
            engine = get_engine()
            wf_count = len(engine.workflows)
            print(f"[FluAgent] 已加载 {wf_count} 个工作流（作为知识参考）")
        except Exception as e:
            print(f"[FluAgent] 警告: 工作流引擎加载失败: {e}")
    
    def _build_system_prompt(self) -> str:
        """构建系统提示词"""
        tools_info = "\n".join([
            f"- {t['function']['name']}: {t['function']['description'][:80]}"
            for t in self.tools
        ])
        
        # 工作流信息（作为知识参考，不暴露为可调用工具）
        workflow_info = ""
        try:
            from workflow import list_workflows
            workflows = list_workflows()
            if workflows:
                workflow_info = "\n可用工作流:\n"
                for wf in workflows:
                    workflow_info += f"- {wf['name']}: {wf['description']}"
                    if wf.get("triggers"):
                        workflow_info += f" (适用场景: {', '.join(wf['triggers'])})"
                    workflow_info += "\n"
                workflow_info += "\n注意：仅当用户明确要求'运行工作流'时才使用 workflow_run。"
        except Exception:
            pass
        
        return SYSTEM_PROMPT.format(
            tools_info=tools_info,
            workflow_info=workflow_info,
            knowledge=self.knowledge_context,
        )
    
    def chat(self, user_input: str) -> str:
        """
        处理用户输入 - 统一 FC 循环模式
        LLM 自主决定调用哪些工具，Agent 执行并回填结果，循环直到完成
        """
        # 初始化消息
        messages = [
            {"role": "system", "content": self.system_prompt},
            *self.conversation_history,
            {"role": "user", "content": user_input}
        ]
        
        # 多轮 FC 循环
        max_rounds = self.max_tool_rounds
        for round_idx in range(max_rounds):
            result = self._call_llm(messages, tools=self.tools)
            
            if "error" in result:
                return f"错误: {result['error']}"
            
            choices = result.get("choices", [])
            if not choices:
                return "错误: LLM 未返回有效响应（choices 为空）"
            
            message = choices[0].get("message", {})
            tool_calls = message.get("tool_calls", [])
            
            if not tool_calls:
                # 无工具调用，直接返回回复
                content = message.get("content", "")
                self.conversation_history.append({"role": "user", "content": user_input})
                self.conversation_history.append({"role": "assistant", "content": content})
                return self._save_result(user_input, content)
            
            # 有工具调用，执行并回填结果
            tool_results = []
            for tc in tool_calls:
                func = tc.get("function", {})
                tool_name = func.get("name")
                args = json.loads(func.get("arguments", "{}"))
                
                result_str = self._execute_tool(tool_name, args)
                tool_results.append({
                    "tool_call_id": tc.get("id", ""),
                    "content": result_str
                })
                
                # 添加工具调用和结果到消息
                messages.append({"role": "assistant", "content": None, "tool_calls": [tc]})
                messages.append({"role": "tool", "tool_call_id": tc.get("id", ""), "content": result_str})
            
            # 循环继续，LLM 会根据工具结果决定下一步
        
        # 达到最大轮次，返回最后结果
        result = "已达到最大工具调用轮次，请检查任务是否完成。"
        return self._save_result(user_input, result)
    
    def _save_result(self, user_input: str, result: str) -> str:
        """收集待保存内容（不再自动保存，退出时询问用户）"""
        # 存储待保存内容
        self.pending_save = {
            "user_input": user_input,
            "result": result,
        }
        return result

    def save_pending(self) -> Optional[str]:
        """保存待保存内容到 reports 目录，返回文件路径"""
        if not self.pending_save:
            return None

        import datetime
        from config_loader import get_reports_dir

        try:
            reports_dir = get_reports_dir()
            os.makedirs(reports_dir, exist_ok=True)

            # 生成文件名
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"analysis_{timestamp}.md"
            filepath = os.path.join(reports_dir, filename)

            # 构建报告内容
            report_content = f"""# FluAgent 分析报告

**时间**: {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## 用户需求

{self.pending_save['user_input']}

## 分析结果

{self.pending_save['result']}

---
*由 FluAgent v2.0 生成*
"""

            # 保存文件
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(report_content)

            self.pending_save = None
            return filepath

        except Exception as e:
            print(f"[FluAgent] 警告: 保存结果失败: {e}")
            return None
    
    def _find_similar_tool(self, tool_name: str) -> Optional[str]:
        """从已注册工具中找到最相似的工具名（模糊匹配）"""
        from tools.base import ToolRegistry
        import difflib
        
        available_tools = list(ToolRegistry._tools.keys())
        if not available_tools:
            return None
        
        # 使用 difflib 找最相似的工具名
        matches = difflib.get_close_matches(tool_name, available_tools, n=1, cutoff=0.6)
        return matches[0] if matches else None
    
    def _execute_tool(self, tool_name: str, args: Dict) -> str:
        """执行工具（带模糊匹配自动纠正和结果评估）"""
        from tools import execute_tool
        from tools.base import ToolRegistry

        # 精确匹配
        if ToolRegistry.has_tool(tool_name):
            try:
                result = execute_tool(tool_name, **args)

                # V2：结果评估
                if self.calibration_enabled:
                    eval_result = self.evaluator.evaluate(tool_name, result)
                    if eval_result.status == ResultStatus.FAILURE:
                        # 校准弃权：返回结果同时提示可能的问题
                        suggestions = "\n".join(
                            f"  - {s}" for s in eval_result.suggestions
                        )
                        result = (
                            f"{result}\n\n"
                            f"⚠️ [校准弃权] 检测到执行可能存在问题:\n"
                            f"{suggestions}\n\n"
                            f"建议：如有疑问，请咨询领域专家确认结果。"
                        )
                return result
            except Exception as e:
                return f"工具执行错误: {str(e)}"
        
        # 模糊匹配：尝试找到最相似的工具名
        best_match = self._find_similar_tool(tool_name)
        if best_match:
            # 尝试自动映射参数（针对常见参数名错误）
            import inspect
            try:
                sig = inspect.signature(execute_tool)
                param_names = list(sig.parameters.keys())
                
                # 如果原始参数不在目标工具中，尝试映射
                corrected_args = {}
                for k, v in args.items():
                    if k in param_names:
                        corrected_args[k] = v
                    elif k == "input_file" and "file" in param_names:
                        corrected_args["file"] = v
                    elif k == "output_file" and "output" in param_names:
                        corrected_args["output"] = v
                    else:
                        corrected_args[k] = v  # 保留原参数，让工具报错
                
                result = execute_tool(best_match, **corrected_args)
                return f"[自动纠正工具名: '{tool_name}' → '{best_match}', 参数已适配]\n{result}"
            except Exception as e:
                return f"工具名已自动纠正为 '{best_match}'，但参数适配失败: {str(e)}\n请检查工具参数格式。"
        
        # 无法匹配
        available = ", ".join(ToolRegistry._tools.keys())
        return f"错误: 未知工具 '{tool_name}'。\n可用工具: {available}"
    
    def _call_llm(
        self,
        messages: List[Dict[str, str]],
        tools: List[Dict] = None,
        model: str = None,
        temperature: float = None,
    ) -> Dict[str, Any]:
        """调用 LLM API（支持本地 Ollama 和远程 API）"""
        model = model or self.model
        temperature = temperature or self.temperature
        
        headers = {"Content-Type": "application/json"}
        # API Key 认证（本地 Ollama 不需要）
        if self.llm_api_key:
            headers["Authorization"] = f"Bearer {self.llm_api_key}"
        
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "stream": False
        }
        
        if tools:
            payload["tools"] = tools
        
        # 智能拼接 URL，支持多种 base_url 格式
        if self.llm_base_url.endswith("/v1/chat/completions"):
            llm_url = self.llm_base_url
        elif self.llm_base_url.endswith("/v1"):
            llm_url = f"{self.llm_base_url}/chat/completions"
        else:
            llm_url = f"{self.llm_base_url}/v1/chat/completions"
        
        try:
            response = requests.post(
                llm_url,
                headers=headers,
                json=payload,
                timeout=self.llm_timeout
            )
            response.raise_for_status()
            data = response.json()

            # 兼容非标准 API 响应格式
            if "choices" not in data:
                # 心流等 API 的业务错误格式: {"status": "435", "msg": "Model not support"}
                if "msg" in data or "error" in data or "status" in data:
                    err_msg = data.get("msg") or data.get("error", {}).get("message", "")
                    status = data.get("status", "")
                    return {"error": f"API 错误 (status={status}): {err_msg}"}
                # 尝试从嵌套结构中提取
                if "message" in data and "content" in data["message"]:
                    # 格式: {"message": {"content": "..."}}
                    data["choices"] = [{"message": data["message"]}]
                elif "content" in data:
                    # 格式: {"content": "..."}
                    data["choices"] = [{"message": {"role": "assistant", "content": data["content"]}}]
                elif "response" in data:
                    # Ollama 原生格式: {"response": "..."}
                    data["choices"] = [{"message": {"role": "assistant", "content": data["response"]}}]
                else:
                    # 无法解析的格式，返回友好错误
                    return {"error": f"API 返回格式不兼容: {json.dumps(data, ensure_ascii=False)[:500]}"}

            return data
        except requests.exceptions.Timeout:
            return {"error": f"LLM调用超时（{self.llm_timeout}s），请尝试：1) 缩小问题范围 2) 增大config.yaml中timeout值"}
        except requests.exceptions.ConnectionError:
            return {"error": "无法连接LLM服务，请确认Ollama正在运行或API地址正确"}
        except requests.exceptions.HTTPError as e:
            if e.response is not None and e.response.status_code == 401:
                return {"error": "API Key 认证失败，请检查 config.yaml 中的 api_key 配置"}
            return {"error": f"LLM调用失败: {str(e)}"}
        except requests.exceptions.RequestException as e:
            return {"error": f"LLM调用失败: {str(e)}"}
    
    def _extract_content(self, result: Dict) -> str:
        """从响应中提取内容"""
        choices = result.get("choices", [])
        if not choices:
            return "错误: 无有效响应"
        
        message = choices[0].get("message", {})
        return message.get("content", "")
    
    async def _call_llm_async(
        self,
        messages: List[Dict[str, str]],
        tools: List[Dict] = None,
        model: str = None,
        temperature: float = None,
        stream: bool = False,
    ) -> Any:
        """异步调用 LLM API"""
        model = model or self.model
        temperature = temperature or self.temperature
        
        headers = {"Content-Type": "application/json"}
        if self.llm_api_key:
            headers["Authorization"] = f"Bearer {self.llm_api_key}"
        
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "stream": stream
        }
        if tools:
            payload["tools"] = tools
            
        if self.llm_base_url.endswith("/v1/chat/completions"):
            llm_url = self.llm_base_url
        elif self.llm_base_url.endswith("/v1"):
            llm_url = f"{self.llm_base_url}/chat/completions"
        else:
            llm_url = f"{self.llm_base_url}/v1/chat/completions"

        async with httpx.AsyncClient(timeout=self.llm_timeout) as client:
            if not stream:
                response = await client.post(llm_url, headers=headers, json=payload)
                response.raise_for_status()
                return response.json()
            else:
                # Streaming handled externally
                return client.stream("POST", llm_url, headers=headers, json=payload)

    async def chat_stream(self, user_input: str) -> AsyncGenerator[str, None]:
        """
        处理用户输入 - 异步流式模式
        """
        messages = [
            {"role": "system", "content": self.system_prompt},
            *self.conversation_history,
            {"role": "user", "content": user_input}
        ]
        
        max_rounds = self.max_tool_rounds
        for round_idx in range(max_rounds):
            # 记录当前轮次的完整内容，用于回填历史
            full_content = ""
            tool_calls = []
            
            headers = {"Content-Type": "application/json"}
            if self.llm_api_key:
                headers["Authorization"] = f"Bearer {self.llm_api_key}"
            
            payload = {
                "model": self.model,
                "messages": messages,
                "temperature": self.temperature,
                "stream": True
            }
            if self.tools:
                payload["tools"] = self.tools

            llm_url = self.llm_base_url
            if not (llm_url.endswith("/v1/chat/completions") or llm_url.endswith("/chat/completions")):
                 llm_url = f"{llm_url.rstrip('/')}/v1/chat/completions"

            async with httpx.AsyncClient(timeout=self.llm_timeout) as client:
                async with client.stream("POST", llm_url, headers=headers, json=payload) as response:
                    if response.status_code != 200:
                        yield f"错误: API 返回 {response.status_code}"
                        return

                    async for line in response.aiter_lines():
                        if not line or not line.startswith("data: "):
                            continue
                        
                        data_str = line[6:]
                        if data_str == "[DONE]":
                            break
                        
                        try:
                            data = json.loads(data_str)
                            delta = data['choices'][0]['delta']
                            
                            if "content" in delta and delta["content"]:
                                content = delta["content"]
                                full_content += content
                                yield content
                            
                            if "tool_calls" in delta:
                                for tc_delta in delta["tool_calls"]:
                                    if len(tool_calls) <= tc_delta["index"]:
                                        tool_calls.append({
                                            "id": tc_delta.get("id", ""),
                                            "type": "function",
                                            "function": {"name": "", "arguments": ""}
                                        })
                                    
                                    curr = tool_calls[tc_delta["index"]]
                                    if "id" in tc_delta:
                                        curr["id"] = tc_delta["id"]
                                    if "function" in tc_delta:
                                        if "name" in tc_delta["function"]:
                                            curr["function"]["name"] += tc_delta["function"]["name"]
                                        if "arguments" in tc_delta["function"]:
                                            curr["function"]["arguments"] += tc_delta["function"]["arguments"]
                        except Exception as e:
                            print(f"Error parsing stream: {e}")
                            continue

            if not tool_calls:
                # 无工具调用，结束
                self.conversation_history.append({"role": "user", "content": user_input})
                self.conversation_history.append({"role": "assistant", "content": full_content})
                self._save_result(user_input, full_content)
                return

            # 有工具调用
            messages.append({"role": "assistant", "content": None, "tool_calls": tool_calls})
            
            for tc in tool_calls:
                tool_name = tc["function"]["name"]
                try:
                    args = json.loads(tc["function"]["arguments"])
                except:
                    args = {}
                
                yield f"\n\n> 正在执行工具: {tool_name}...\n"
                result_str = self._execute_tool(tool_name, args)
                yield f"\n工具结果: \n{result_str}\n\n"
                
                messages.append({"role": "tool", "tool_call_id": tc["id"], "content": result_str})
            
            # 继续下一轮 LLM 调用

    def reset_conversation(self):
        """重置对话历史"""
        self.conversation_history = []
    
    def get_conversation_history(self) -> List[Dict[str, str]]:
        """获取对话历史"""
        return self.conversation_history.copy()
    
    def chat_v2(self, user_input: str) -> str:
        """
        处理用户输入 - 三角色 Agent 模式（Ask-Plan-Craft）
        
        工作流程：
        1. Ask Agent: 需求理解与多轮澄清
        2. Plan Agent: 技术路线规划 + 数据流校验
        3. Craft Agent: 按计划执行 + 生成报告
        """
        if not self.multi_agent_enabled:
            # 自动启用三角色模式
            cfg = None
            try:
                from config_loader import get_config
                cfg = get_config()
            except Exception:
                pass
            
            if cfg:
                # 重新初始化三角色
                self.multi_agent_enabled = True
                llm_client = lambda messages, tools=None: self._call_llm(messages, tools=tools)
                tool_executor = lambda name, args: self._execute_tool(name, args)
                
                self.ask_agent = AskAgent(
                    llm_client=llm_client,
                    max_rounds=cfg.multi_agent.ask.max_rounds,
                )
                self.plan_agent = PlanAgent(
                    llm_client=llm_client,
                    tools=self.tools,
                    validate_dataflow=cfg.multi_agent.plan.validate_dataflow,
                )
                self.craft_agent = CraftAgent(
                    llm_client=llm_client,
                    tool_executor=tool_executor,
                    tools=self.tools,
                    max_tool_rounds=cfg.multi_agent.craft.max_tool_rounds,
                    retry_on_fail=cfg.multi_agent.craft.retry_on_fail,
                )
        
        # ========== Stage 1: Ask Agent - 需求理解与澄清 ==========
        print("\n" + "="*50)
        print("[Stage 1] Ask Agent - 需求理解")
        print("="*50)
        
        ask_result = self.ask_agent.process(
            user_input=user_input,
            conversation_history=self.conversation_history,
        )
        
        # 如果需要澄清，返回澄清问题
        if ask_result.get("status") == "clarify":
            self.conversation_history.append({"role": "user", "content": user_input})
            self.conversation_history.append({"role": "assistant", "content": ask_result.get("message", "")})
            return f"{ask_result.get('message', '')}\n\n（您可以直接回答上述问题，或提供更多信息）"
        
        # 需求已明确
        clarified_input = ask_result.get("summary", user_input)
        print(f"需求已明确: {clarified_input[:100]}...")
        
        # ========== Stage 2: Plan Agent - 技术路线规划 ==========
        print("\n" + "="*50)
        print("[Stage 2] Plan Agent - 技术路线规划")
        print("="*50)
        
        plan_result = self.plan_agent.process(
            user_input=clarified_input,
            knowledge=self.knowledge_context,
        )
        
        if plan_result.get("status") == "error":
            return f"计划制定失败: {plan_result.get('message', '')}"
        
        plan = plan_result.get("plan", {})
        print(f"计划: {plan.get('plan', 'N/A')[:100]}...")
        
        # 检查数据流校验结果
        dataflow = plan.get("dataflow_check", {})
        if not dataflow.get("valid", True):
            issues = dataflow.get("issues", [])
            warning_msg = "\n⚠️ 数据流问题:\n" + "\n".join(f"  - {issue}" for issue in issues)
            print(warning_msg)
        
        # ========== Stage 3: Craft Agent - 任务执行 ==========
        print("\n" + "="*50)
        print("[Stage 3] Craft Agent - 任务执行")
        print("="*50)
        
        craft_result = self.craft_agent.process(
            user_input=clarified_input,
            plan=plan,
        )
        
        # 记录对话历史
        self.conversation_history.append({"role": "user", "content": user_input})
        
        if craft_result.get("status") == "success":
            report = craft_result.get("report", "")
            self.conversation_history.append({"role": "assistant", "content": report})
            result = f"✅ 任务执行完成！\n\n{report}"
        elif craft_result.get("status") == "partial":
            report = craft_result.get("report", "")
            summary = craft_result.get("summary", "")
            self.conversation_history.append({"role": "assistant", "content": f"{summary}\n\n{report}"})
            result = f"⚠️ 任务部分完成\n{summary}\n\n{report}"
        else:
            error_msg = craft_result.get("summary", "执行失败")
            self.conversation_history.append({"role": "assistant", "content": error_msg})
            result = f"❌ 任务执行失败: {error_msg}"
        
        # 保存结果到 reports 目录
        return self._save_result(user_input, result)
