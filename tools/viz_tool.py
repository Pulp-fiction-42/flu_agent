"""
可视化工具
提供序列质量控制图、统计图表、系统发育树可视化等功能
"""
import os
import subprocess
import config
from typing import Dict, Any
from .base import ToolBase, ToolRegistry


class PlotSequenceQualityTool(ToolBase):
    """绘制序列质量图工具"""
    
    @property
    def name(self) -> str:
        return "plot_sequence_quality"
    
    @property
    def description(self) -> str:
        return "绘制序列质量控制图，使用 FastQC 生成质量报告。适用于快速了解 FASTQ 数据的质量分布。"
    
    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "input_file": {"type": "string", "description": "输入的 FASTQ 文件路径"},
                "output_dir": {"type": "string", "description": "输出目录（默认当前目录）", "default": "."}
            },
            "required": ["input_file"]
        }
    
    def execute(self, input_file: str, output_dir: str = ".") -> str:
        cmd = [config.resolve_tool_path(config.FASTQC_PATH), "-o", output_dir, input_file]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            if result.returncode == 0:
                base_name = os.path.splitext(os.path.basename(input_file))[0]
                html_file = os.path.join(output_dir, f"{base_name}_fastqc.html")
                return f"质量控制图生成成功: {html_file}"
            else:
                return f"错误: {result.stderr}"
        except Exception as e:
            return f"错误: {str(e)}"


class PlotSequenceLengthDistTool(ToolBase):
    """绘制序列长度分布图工具"""
    
    @property
    def name(self) -> str:
        return "plot_sequence_length_dist"
    
    @property
    def description(self) -> str:
        return "获取序列长度分布统计信息。使用 seqkit stats 获取序列长度信息。"
    
    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "input_file": {"type": "string", "description": "输入的 FASTA/FASTQ 文件路径"}
            },
            "required": ["input_file"]
        }
    
    def execute(self, input_file: str) -> str:
        cmd = [config.resolve_tool_path(config.SEQKIT_PATH), "stats", "-a", input_file]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if result.returncode == 0:
                return result.stdout
            else:
                return f"错误: {result.stderr}"
        except Exception as e:
            return f"错误: {str(e)}"


class PlotGCContentTool(ToolBase):
    """绘制 GC 含量分布图工具"""
    
    @property
    def name(self) -> str:
        return "plot_gc_content"
    
    @property
    def description(self) -> str:
        return "计算并显示 GC 含量分布。使用 seqkit gc 命令。"
    
    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "input_file": {"type": "string", "description": "输入的 FASTA/FASTQ 文件路径"}
            },
            "required": ["input_file"]
        }
    
    def execute(self, input_file: str) -> str:
        cmd = [config.resolve_tool_path(config.SEQKIT_PATH), "gc", input_file]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if result.returncode == 0:
                return result.stdout
            else:
                return f"错误: {result.stderr}"
        except Exception as e:
            return f"错误: {str(e)}"


class PlotNucleotideCompositionTool(ToolBase):
    """绘制核苷酸组成图工具"""
    
    @property
    def name(self) -> str:
        return "plot_nucleotide_composition"
    
    @property
    def description(self) -> str:
        return "计算核苷酸组成。使用 seqkit nucl 命令。"
    
    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "input_file": {"type": "string", "description": "输入的 FASTA/FASTQ 文件路径"}
            },
            "required": ["input_file"]
        }
    
    def execute(self, input_file: str) -> str:
        cmd = [config.resolve_tool_path(config.SEQKIT_PATH), "nucl", input_file]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if result.returncode == 0:
                return result.stdout
            else:
                return f"错误: {result.stderr}"
        except Exception as e:
            return f"错误: {str(e)}"


class PlotKmerFrequencyTool(ToolBase):
    """绘制 K-mer 频率图工具"""
    
    @property
    def name(self) -> str:
        return "plot_kmer_frequency"
    
    @property
    def description(self) -> str:
        return "计算 K-mer 频率分布。使用 seqkit freq 命令。k 默认值为 4。"
    
    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "input_file": {"type": "string", "description": "输入的 FASTA/FASTQ 文件路径"},
                "k": {"type": "integer", "description": "K-mer 大小", "default": 4}
            },
            "required": ["input_file"]
        }
    
    def execute(self, input_file: str, k: int = 4) -> str:
        cmd = [config.resolve_tool_path(config.SEQKIT_PATH), "freq", "-l", str(k), input_file]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if result.returncode == 0:
                return result.stdout[:2000]
            else:
                return f"错误: {result.stderr}"
        except Exception as e:
            return f"错误: {str(e)}"


def register_all_tools():
    """注册所有可视化工具"""
    tools = [
        PlotSequenceQualityTool(),
        PlotSequenceLengthDistTool(),
        PlotGCContentTool(),
        PlotNucleotideCompositionTool(),
        PlotKmerFrequencyTool(),
    ]
    for tool in tools:
        ToolRegistry.register(tool)
