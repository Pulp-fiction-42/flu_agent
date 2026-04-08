"""
Web UI 模块
基于 Gradio 的 Web 界面
支持多用户、对话历史、用户反馈
"""
import os
import sys
import gradio as gr
from typing import List, Tuple, Dict, Optional
import uuid
from datetime import datetime

# 确保可以导入 basic-agent 模块
skill_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if skill_dir not in sys.path:
    sys.path.insert(0, skill_dir)


class FluAgentWeb:
    """FluAgent Web 界面（支持多用户）"""

    def __init__(self):
        self.agent = None
        self.model_map: Dict[str, Dict] = {}
        self.current_user: Optional[str] = None
        self.current_session_id: Optional[str] = None
        self.user_memory = {}  # {session_id: conversation_history}
        self.auto_save = False  # 默认不保存
        self.is_initialized = False  # 防止 app.load 时触发模型切换
        self._init_agent()

    def _init_agent(self):
        """初始化 Agent（使用 config.yaml 默认配置）"""
        try:
            from core.agent import FluAgent
            self.agent = FluAgent()
            print("[FluAgent Web] Agent 初始化成功")
        except Exception as e:
            print(f"[FluAgent Web] Agent 初始化失败: {e}")

    def _detect_models(self) -> List[Dict]:
        """检测可用模型，返回模型列表"""
        from core.provider_manager import detect_available_providers
        providers = detect_available_providers()
        models = []

        # 优先添加 MiniMax 模型
        minimax_models = []
        other_models = []

        for p in providers:
            for m in p.resolved_models:
                label = f"[{p.name}] {m}"
                self.model_map[label] = {
                    "base_url": p.base_url,
                    "api_key": p.api_key,
                    "model": m,
                }
                if "minimax" in p.name.lower() or "MiniMax" in p.name:
                    minimax_models.append(label)
                else:
                    other_models.append(label)

        # MiniMax 优先
        models = minimax_models + other_models
        return models

    def switch_model(self, model_label: str) -> str:
        """切换模型，返回状态信息"""
        if not model_label or model_label not in self.model_map:
            return "请选择一个有效的模型"

        info = self.model_map[model_label]
        try:
            from core.agent import FluAgent
            self.agent = FluAgent(
                model=info["model"],
                _base_url=info["base_url"],
                _api_key=info["api_key"],
            )
            return f"已切换到: {model_label}"
        except Exception as e:
            return f"切换失败: {e}"

    def chat(self, message: str, history: List[Tuple[str, str]], user_id: str) -> Tuple[str, List[Tuple[str, str]]]:
        """处理聊天"""
        if not self.agent:
            return "Agent 未初始化，请检查配置", history

        try:
            response = self.agent.chat(message)

            # 过滤掉 think 标签（避免 Gradio 解析问题）
            response = self._clean_response(response)

            # 保存到历史记录（创建新列表以确保 Gradio 能检测到变化）
            new_history = history + [(message, response)]

            # 保存到 user_memory
            if self.current_session_id:
                self.user_memory[self.current_session_id] = new_history

            # 如果开启自动保存，则保存到数据库
            if self.auto_save:
                self._save_messages_to_db(user_id)

            return response, new_history
        except Exception as e:
            import traceback
            traceback.print_exc()
            return f"错误: {str(e)}", history

    def _clean_response(self, text: str) -> str:
        """清理响应中的 think 标签和其他可能引起问题的内容"""
        import re
        # 移除<think>...</think>think标签及其内容
        text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
        # 移除多余的空白行
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()

    def _save_messages_to_db(self, user_id: str):
        """保存消息到数据库"""
        if not self.current_session_id or self.current_session_id not in self.user_memory:
            return

        try:
            from core.memory import Memory
            memory = Memory()
            memory.create_session(
                session_id=self.current_session_id,
                metadata={"user_id": user_id}
            )

            history = self.user_memory[self.current_session_id]
            for user_msg, assistant_msg in history:
                if user_msg:
                    memory.save_message("user", user_msg)
                if assistant_msg:
                    memory.save_message("assistant", assistant_msg)
        except Exception as e:
            print(f"[FluAgent] 保存消息失败: {e}")

    def update_session_name(self, history: List[Tuple[str, str]]) -> str:
        """根据聊天内容生成会话主题名称"""
        if not history:
            return "新会话"
        # 取第一条用户消息的前20个字符作为主题
        first_user_msg = ""
        for user_msg, _ in history:
            if user_msg:
                first_user_msg = user_msg[:20]
                break
        if not first_user_msg:
            return "新会话"
        return f"{first_user_msg}..."

    def upload_file(self, file):
        """处理文件上传"""
        if file is None:
            return "未选择文件"

        from config_loader import get_config
        cfg = get_config()
        upload_dir = os.path.join(cfg.paths.data_dir, "uploads")
        os.makedirs(upload_dir, exist_ok=True)

        import shutil
        filename = os.path.basename(file.name)
        dest_path = os.path.join(upload_dir, filename)
        shutil.copy(file.name, dest_path)

        return f"文件已上传: {filename}\n保存路径: {dest_path}"

    def save_feedback(self, user_id: str, rating: int, comment: str = "") -> str:
        """保存用户反馈"""
        if not self.current_session_id:
            return "错误: 没有活动会话"

        try:
            from core.memory import Memory
            memory = Memory()
            memory.save_feedback(
                session_id=self.current_session_id,
                user_id=user_id or "anonymous",
                message_index=0,
                rating=rating,
                comment=comment
            )
            return f"感谢您的反馈！评级: {rating}星"
        except Exception as e:
            return f"反馈保存失败: {e}"

    def get_session_history(self, user_id: str) -> List[Dict]:
        """获取用户会话历史"""
        try:
            from core.memory import Memory
            memory = Memory()
            return memory.list_user_sessions(user_id, limit=50)
        except Exception as e:
            print(f"[FluAgent] 获取会话历史失败: {e}")
            return []

    def load_session(self, session_id: str) -> Tuple[List[Tuple[str, str]], str]:
        """加载指定会话，返回(历史记录, 会话主题)"""
        try:
            from core.memory import Memory
            memory = Memory()
            session = memory.load_session(session_id)
            if session:
                history = []
                for msg in session.messages:
                    if msg.role == "user":
                        history.append((msg.content, ""))
                    elif msg.role == "assistant":
                        if history:
                            user_msg, _ = history[-1]
                            history[-1] = (user_msg, msg.content)
                        else:
                            history.append(("", msg.content))
                self.current_session_id = session_id
                self.user_memory[session_id] = history
                session_name = session.metadata.get("name", "历史会话") if session.metadata else "历史会话"
                return history, session_name
        except Exception as e:
            print(f"[FluAgent] 加载会话失败: {e}")
        return [], "新会话"

    def append_session_to_current(self, session_id: str) -> Tuple[List[Tuple[str, str]], str]:
        """将指定会话的历史记录追加到当前会话"""
        try:
            from core.memory import Memory
            memory = Memory()
            session = memory.load_session(session_id)
            if session:
                history = []
                for msg in session.messages:
                    if msg.role == "user":
                        history.append((msg.content, ""))
                    elif msg.role == "assistant":
                        if history:
                            user_msg, _ = history[-1]
                            history[-1] = (user_msg, msg.content)
                        else:
                            history.append(("", msg.content))
                # 追加到当前会话
                if self.current_session_id and self.current_session_id in self.user_memory:
                    self.user_memory[self.current_session_id].extend(history)
                    return self.user_memory[self.current_session_id], "已追加历史记录"
                else:
                    # 没有当前会话，创建新的
                    self.current_session_id = str(uuid.uuid4())
                    self.user_memory[self.current_session_id] = history
                    return history, "已加载历史会话"
        except Exception as e:
            print(f"[FluAgent] 追加历史会话失败: {e}")
        return [], "操作失败"

    def new_session(self) -> Tuple[str, List, str]:
        """创建新会话"""
        self.current_session_id = str(uuid.uuid4())
        self.user_memory[self.current_session_id] = []
        return self.current_session_id, [], "新会话"

    def set_auto_save(self, auto_save: bool):
        """设置是否自动保存"""
        self.auto_save = auto_save

    def get_auto_save(self) -> bool:
        return self.auto_save


# ===== 分析任务快捷选项 =====
ANALYSIS_TASKS = [
    "亚型鉴定 (HA/NA)",
    "系统发育分析 (Phylogeny)",
    "序列比对 (Alignment)",
    "质控分析 (QC)",
    "基因组组装 (Assembly)",
    "变异检测 (Variant)",
    "抗原分析 (Antigenic)",
    "宿主溯源 (Host Origin)",
]


def create_app() -> gr.Blocks:
    """创建 Gradio 应用"""
    web = FluAgentWeb()

    with gr.Blocks(title="FluAgent - 生物信息学分析助手") as app:
        # 顶部标题
        gr.Markdown("# FluAgent - 生物信息学分析助手")

        # ===== 右上角：用户登录区域 =====
        with gr.Row():
            with gr.Column(scale=9):
                pass  # 左侧占位
            with gr.Column(scale=3):
                with gr.Row():
                    user_input = gr.Textbox(
                        placeholder="用户名",
                        show_label=False,
                        scale=2,
                    )
                    login_btn = gr.Button("登录/注册", size="sm", scale=1)
                login_status = gr.Textbox(label="当前用户", interactive=False, lines=1)

        with gr.Row():
            # ===== 左侧：主聊天区域 =====
            with gr.Column(scale=3):
                # 历史会话选择
                gr.Markdown("### 历史会话")
                with gr.Row():
                    session_dropdown = gr.Dropdown(
                        label="选择会话",
                        choices=[],
                        interactive=True,
                        scale=3,
                    )
                    load_session_btn = gr.Button("加载", size="sm", scale=1)

                new_session_btn = gr.Button("新建会话", size="sm")

                # 会话主题
                session_name = gr.Textbox(label="会话主题", placeholder="自动生成或手动输入", lines=1)

                # 聊天界面
                chatbot = gr.Chatbot(
                    label="对话历史",
                    height=500,
                )

                # 输入区域
                with gr.Row():
                    msg_input = gr.Textbox(
                        label="输入",
                        placeholder="请输入您的分析需求...",
                        scale=4,
                        show_label=False,
                    )
                    submit_btn = gr.Button("发送", variant="primary", scale=1)

                # 操作按钮
                with gr.Row():
                    clear_btn = gr.Button("清除对话", size="sm")
                    feedback_btn = gr.Button("提交反馈", size="sm")
                    save_toggle = gr.Checkbox(label="自动保存会话", value=False, scale=1)

                # 反馈区域（隐藏）
                with gr.Group(visible=False) as feedback_group:
                    with gr.Row():
                        rating_slider = gr.Slider(1, 5, value=5, step=1, label="评分 (1-5星)")
                    feedback_comment = gr.Textbox(label="反馈意见（可选）", placeholder="请输入您的建议...")
                    submit_feedback_btn = gr.Button("确认反馈")
                    feedback_status = gr.Textbox(label="反馈状态", interactive=False)

            # ===== 右侧：工具栏 =====
            with gr.Column(scale=1):
                # 模型选择
                gr.Markdown("### 模型选择")
                with gr.Row():
                    model_dropdown = gr.Dropdown(
                        label="选择模型",
                        choices=[],
                        interactive=True,
                        scale=4,
                    )
                    refresh_btn = gr.Button("刷新", size="sm", scale=1)
                model_status = gr.Textbox(label="状态", interactive=False, lines=1)

                # 文件上传
                gr.Markdown("### 文件上传")
                file_input = gr.File(
                    label="上传数据文件",
                    file_count="single",
                )
                upload_btn = gr.Button("上传文件", size="sm")
                upload_status = gr.Textbox(label="上传状态", interactive=False, lines=1)

                # 快捷分析任务
                gr.Markdown("### 快捷分析任务")
                task_buttons = []
                for task in ANALYSIS_TASKS:
                    btn = gr.Button(task, size="sm")
                    task_buttons.append(btn)

                # 分析说明
                gr.Markdown("""
                **使用说明：**
                1. 选择上方快捷任务，系统将优先使用相关知识库
                2. 或直接输入您的分析需求
                3. 可上传 fasta/fastq 文件进行分析
                """)

        # ===== 事件处理 =====

        # 登录
        def login(user_id):
            if not user_id.strip():
                return "请输入用户名", gr.update()
            web.current_user = user_id.strip()
            sessions = web.get_session_history(user_id)
            session_choices = []
            for s in sessions:
                name = s.get("metadata", {}).get("name", s["session_id"][:8])
                session_choices.append(f"{name} | {s['session_id'][8:]}...")
            return f"已登录: {user_id}", gr.update(choices=session_choices)

        login_btn.click(login, [user_input], [login_status, session_dropdown])

        # 新建会话
        def on_new_session():
            session_id, history, name = web.new_session()
            return session_id, convert_history_format(history), name, gr.update()

        new_session_btn.click(on_new_session, [], [session_dropdown, chatbot, session_name, session_dropdown])

        # 加载会话（追加到当前）
        def on_load_session(session_display):
            if not session_display:
                return [], "请选择会话", gr.update()
            # 从 display 解析 session_id
            parts = session_display.split(" | ")
            if len(parts) >= 2:
                session_id = parts[-1].replace("...", "")
                sessions = web.get_session_history(web.current_user or "anonymous")
                for s in sessions:
                    if s["session_id"].endswith(session_id) or session_id in s["session_id"]:
                        # 追加历史到当前会话
                        history, msg = web.append_session_to_current(s["session_id"])
                        name = web.update_session_name(history)
                        return convert_history_format(history), msg, name
            return [], "加载失败", ""

        load_session_btn.click(on_load_session, [session_dropdown], [chatbot, session_name, session_name])

        # 模型刷新
        def refresh_models():
            models = web._detect_models()
            choices = models if models else ["无可用模型"]
            status_msg = f"检测到 {len(models)} 个可用模型" if models else "未检测到可用模型"
            default_model = None
            for choice in choices:
                if "minimax" in choice.lower():
                    default_model = choice
                    break
            if not default_model and choices:
                default_model = choices[0]
            return (
                gr.update(choices=choices, value=default_model),
                status_msg
            )

        def on_app_load():
            result = refresh_models()
            web.is_initialized = True
            return result

        app.load(fn=on_app_load, outputs=[model_dropdown, model_status])
        refresh_btn.click(fn=refresh_models, outputs=[model_dropdown, model_status])

        # 切换模型
        is_initialized = False  # 标志位，防止 app.load 时触发切换
        def on_model_change(model_label):
            if not model_label or not is_initialized:
                return ""
            return web.switch_model(model_label)

        model_dropdown.change(
            fn=on_model_change,
            inputs=[model_dropdown],
            outputs=[model_status],
        )

        # 保存开关
        def on_save_toggle(auto_save):
            web.set_auto_save(auto_save)
            return f"自动保存: {'已开启' if auto_save else '已关闭'}"

        save_toggle.change(on_save_toggle, [save_toggle], [model_status])

        # 转换历史格式：[(msg, resp), ...] -> [{'role': 'user', 'content': msg}, ...]
        def convert_history_to_gradio_format(history):
            """将历史记录转换为 Gradio 6.x 要求的格式"""
            if not history:
                return []
            # 检查是否已经是 dict 格式（Gradio 6.x 传入）
            if isinstance(history[0], dict):
                return history
            # 否则是 tuple 格式，转换
            result = []
            for user_msg, assistant_msg in history:
                if user_msg:
                    result.append({"role": "user", "content": user_msg})
                if assistant_msg:
                    result.append({"role": "assistant", "content": assistant_msg})
            return result

        # 转换历史格式：[{...}] -> [(msg, resp), ...]
        def convert_history_from_gradio_format(history):
            """将 Gradio 6.x 历史格式转换为 tuple 格式"""
            if not history:
                return []
            result = []
            i = 0
            while i < len(history):
                msg = history[i]
                if isinstance(msg, dict) and msg.get("role") == "user":
                    user_content = msg.get("content", "")
                    assistant_content = ""
                    if i + 1 < len(history):
                        next_msg = history[i + 1]
                        if isinstance(next_msg, dict) and next_msg.get("role") == "assistant":
                            assistant_content = next_msg.get("content", "")
                            i += 1
                    result.append((user_content, assistant_content))
                i += 1
            return result

        # 聊天
        def respond(message, history):
            if not message.strip():
                return "", convert_history_to_gradio_format(history)
            user_id = web.current_user or "anonymous"
            # 转换 Gradio 格式为 tuple 格式
            history_tuples = convert_history_from_gradio_format(history)
            response, history_tuples = web.chat(message, history_tuples, user_id)
            # 更新会话主题
            name = web.update_session_name(history_tuples)
            return "", convert_history_to_gradio_format(history_tuples), name

        submit_btn.click(
            respond,
            [msg_input, chatbot],
            [msg_input, chatbot, session_name]
        )
        msg_input.submit(
            respond,
            [msg_input, chatbot],
            [msg_input, chatbot, session_name]
        )

        # 清除
        def clear_history():
            if web.agent:
                web.agent.reset_conversation()
            if web.current_session_id and web.current_session_id in web.user_memory:
                web.user_memory[web.current_session_id] = []
            return [], "新会话"

        clear_btn.click(clear_history, [], [chatbot, session_name])

        # 显示/隐藏反馈
        def toggle_feedback():
            return gr.update(visible=True)

        feedback_btn.click(fn=toggle_feedback, outputs=[feedback_group])

        # 提交反馈
        def submit_feedback(rating, comment):
            user_id = web.current_user or "anonymous"
            return web.save_feedback(user_id, rating, comment)

        submit_feedback_btn.click(
            submit_feedback,
            [rating_slider, feedback_comment],
            [feedback_status]
        )

        # 文件上传
        def handle_upload(file):
            return web.upload_file(file)

        upload_btn.click(handle_upload, [file_input], [upload_status])

        # 快捷任务按钮 - 预填充消息
        def on_task_click(task_name):
            prompt_map = {
                "亚型鉴定 (HA/NA)": "请帮我进行流感病毒亚型鉴定（HA和NA），我上传了序列文件。",
                "系统发育分析 (Phylogeny)": "请帮我进行系统发育分析，构建进化树。",
                "序列比对 (Alignment)": "请帮我进行多序列比对分析。",
                "质控分析 (QC)": "请帮我对测序数据进行质量控制和过滤。",
                "基因组组装 (Assembly)": "请帮我进行基因组组装。",
                "变异检测 (Variant)": "请帮我进行变异位点检测和分析。",
                "抗原分析 (Antigenic)": "请帮我进行抗原性分析。",
                "宿主溯源 (Host Origin)": "请帮我进行宿主溯源分析。",
            }
            return prompt_map.get(task_name, task_name)

        for btn, task in zip(task_buttons, ANALYSIS_TASKS):
            btn.click(fn=lambda t=task: on_task_click(t), inputs=[], outputs=[msg_input])

        # 示例问题（放在输入框下方作为提示）
        gr.Markdown("""
        **示例问题：**
        - 统计 sequences.fasta 文件的序列数量
        - 对 sample.fastq 进行质控
        - 搜索 PubMed 流感病毒相关文献
        """)

    return app


def launch_web(share: bool = False, debug: bool = False, port: int = 7861, use_ngrok: bool = False):
    """启动 Web 服务"""
    from config_loader import get_config

    cfg = get_config()
    app = create_app()

    # ngrok 支持
    public_url = None
    if use_ngrok:
        try:
            from pyngrok import ngrok
            tunnel = ngrok.connect(port)
            public_url = tunnel.public_url
            print(f"\n{'='*60}")
            print(f"ngrok 公网访问已启用!")
            print(f"公网链接: {public_url}")
            print(f"注意: 免费版 ngrok 链接会在重启后变化")
            print(f"{'='*60}\n")
        except ImportError:
            print("[FluAgent] 警告: pyngrok 未安装，无法使用 ngrok")
        except Exception as e:
            print(f"[FluAgent] ngrok 启动失败: {e}")

    app.launch(
        server_name="0.0.0.0",
        server_port=port,
        share=share,
        debug=debug,
    )


if __name__ == "__main__":
    launch_web()
