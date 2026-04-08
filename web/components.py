"""
Web 组件
自定义 Gradio 组件
"""
import gradio as gr
from typing import List, Tuple, Optional


class FileUploadPanel:
    """文件上传面板"""
    
    def __init__(self, label: str = "文件上传", file_count: str = "multiple"):
        self.label = label
        self.file_count = file_count
    
    def create(self):
        return gr.File(
            label=self.label,
            file_count=self.file_count,
            file_types=[".fasta", ".fastq", ".fq", ".vcf", ".bam", ".sam", ".txt"]
        )


class LogPanel:
    """日志显示面板"""
    
    def __init__(self, label: str = "执行日志", height: int = 300):
        self.label = label
        self.height = height
    
    def create(self):
        return gr.Textbox(
            label=self.label,
            interactive=False,
            lines=10,
            max_lines=self.height,
            show_copy_button=True
        )


class ToolStatusPanel:
    """工具状态面板"""
    
    def __init__(self):
        pass
    
    def create(self, tools_count: int = 0, tools_list: List[str] = None):
        return gr.JSON(
            label=f"可用工具 ({tools_count})",
            value={"count": tools_count, "tools": tools_list or []}
        )


class ResultPanel:
    """结果展示面板"""
    
    def __init__(self, label: str = "分析结果"):
        self.label = label
    
    def create(self):
        return gr.Textbox(
            label=self.label,
            interactive=False,
            lines=15,
            show_copy_button=True
        )


def create_sidebar(tools_count: int = 0, tools_list: List[str] = None):
    """创建侧边栏"""
    with gr.Column(scale=1):
        gr.Markdown("### 📁 文件上传")
        file_input = gr.File(
            label="上传数据文件",
            file_count="multiple",
        )
        upload_btn = gr.Button("上传文件")
        upload_status = gr.Textbox(label="上传状态", interactive=False)
        
        gr.Markdown("### ⚙️ 工具状态")
        tools_status = gr.JSON(
            label=f"可用工具 ({tools_count})",
            value={"count": tools_count, "tools": tools_list or []}
        )
        
        gr.Markdown("### 💾 会话信息")
        session_info = gr.JSON(
            label="当前会话",
            value={"session_id": "新建会话", "messages": 0}
        )
    
    return {
        "file_input": file_input,
        "upload_btn": upload_btn,
        "upload_status": upload_status,
        "tools_status": tools_status,
        "session_info": session_info,
    }


def create_chat_interface():
    """创建聊天界面"""
    with gr.Column(scale=3):
        gr.Markdown("## 🧬 BioAgent 对话")
        
        chatbot = gr.Chatbot(
            label="对话历史",
            height=500,
            show_copy_button=True,
        )
        
        with gr.Row():
            msg_input = gr.Textbox(
                label="输入",
                placeholder="请输入您的分析需求...",
                scale=4,
                lines=3,
            )
        
        with gr.Row():
            submit_btn = gr.Button("发送", variant="primary")
            clear_btn = gr.Button("清除对话")
    
    return {
        "chatbot": chatbot,
        "msg_input": msg_input,
        "submit_btn": submit_btn,
        "clear_btn": clear_btn,
    }


def create_examples():
    """创建示例问题"""
    return gr.Examples(
        examples=[
            ["统计 sequences.fasta 文件的序列数量、平均长度"],
            ["对 sample.fastq 进行质控，生成报告"],
            ["使用多序列比对后建树的工作流分析序列"],
            ["从 GenBank 下载流感病毒 HA 基因序列"],
            ["绘制序列长度分布图"],
        ],
        inputs=None,  # 动态设置
    )
