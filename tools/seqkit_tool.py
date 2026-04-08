"""
seqkit 工具封装
提供序列统计、格式转换、搜索、去重、排序等功能
"""
import os
import subprocess
import json
from typing import Optional
from .base import ToolBase, ToolRegistry
import config


class SeqkitStatsTool(ToolBase):
    """序列统计工具"""

    @property
    def name(self) -> str:
        return "seqkit_stats"

    @property
    def description(self) -> str:
        return "对 FASTA/FASTQ 文件进行序列统计，返回序列数、总长度、GC含量、平均长度等统计信息。适用于快速了解序列数据的基本特征。"

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "file": {
                    "type": "string",
                    "description": "输入的 FASTA/FASTQ 文件路径"
                },
                "verbose": {
                    "type": "boolean",
                    "description": "是否显示详细统计（包含每个序列的信息）",
                    "default": False
                },
                "threads": {
                    "type": "integer",
                    "description": "线程数",
                    "default": config.DEFAULT_THREADS
                }
            },
            "required": ["file"]
        }

    def execute(self, file: str, verbose: bool = False, threads: int = None) -> str:
        if threads is None:
            threads = config.DEFAULT_THREADS

        if not os.path.exists(file):
            return f"错误: 文件不存在: {file}"

        cmd = [config.SEQKIT_PATH, "stats", "-j", str(threads)]
        if verbose:
            cmd.append("-a")
        cmd.append(file)

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return result.stdout
        except subprocess.CalledProcessError as e:
            return f"seqkit 执行失败: {e.stderr}"


class SeqkitFx2TabTool(ToolBase):
    """序列格式转换工具 - 将 FASTA 转为表格格式"""

    @property
    def name(self) -> str:
        return "seqkit_fx2tab"

    @property
    def description(self) -> str:
        return "将 FASTA/FASTQ 格式转换为表格格式，可选择包含序列长度、GC含量、序列内容等字段。"

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "file": {
                    "type": "string",
                    "description": "输入的 FASTA/FASTQ 文件路径"
                },
                "out_file": {
                    "type": "string",
                    "description": "输出文件路径（可选，不提供则输出到 stdout）",
                    "default": ""
                },
                "with_seq": {
                    "type": "boolean",
                    "description": "是否包含序列内容",
                    "default": False
                },
                "with_qual": {
                    "type": "boolean",
                    "description": "是否包含质量分数（仅 FASTQ 有效）",
                    "default": False
                },
                "threads": {
                    "type": "integer",
                    "description": "线程数",
                    "default": config.DEFAULT_THREADS
                }
            },
            "required": ["file"]
        }

    def execute(self, file: str, out_file: str = "", with_seq: bool = False,
                with_qual: bool = False, threads: int = None) -> str:
        if threads is None:
            threads = config.DEFAULT_THREADS

        if not os.path.exists(file):
            return f"错误: 文件不存在: {file}"

        cmd = [config.SEQKIT_PATH, "fx2tab", "-j", str(threads)]
        if with_seq:
            cmd.append("-w")
        if with_qual:
            cmd.append("-q")
        cmd.append(file)

        if out_file:
            cmd.extend(["-o", out_file])

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            if out_file:
                return f"已保存到: {out_file}"
            return result.stdout
        except subprocess.CalledProcessError as e:
            return f"seqkit 执行失败: {e.stderr}"


class SeqkitGrepTool(ToolBase):
    """序列搜索工具 - 按 ID 或序列模式搜索"""

    @property
    def name(self) -> str:
        return "seqkit_grep"

    @property
    def description(self) -> str:
        return "按序列 ID、名称或序列模式搜索 FASTA/FASTQ 文件。支持正则表达式。"

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "file": {
                    "type": "string",
                    "description": "输入的 FASTA/FASTQ 文件路径"
                },
                "pattern": {
                    "type": "string",
                    "description": "搜索模式（序列 ID、名称或序列内容）"
                },
                "use_regex": {
                    "type": "boolean",
                    "description": "是否使用正则表达式",
                    "default": False
                },
                "ignore_case": {
                    "type": "boolean",
                    "description": "是否忽略大小写",
                    "default": False
                },
                "out_file": {
                    "type": "string",
                    "description": "输出文件路径（可选）",
                    "default": ""
                },
                "threads": {
                    "type": "integer",
                    "description": "线程数",
                    "default": config.DEFAULT_THREADS
                }
            },
            "required": ["file", "pattern"]
        }

    def execute(self, file: str, pattern: str, use_regex: bool = False,
                ignore_case: bool = False, out_file: str = "", threads: int = None) -> str:
        if threads is None:
            threads = config.DEFAULT_THREADS

        if not os.path.exists(file):
            return f"错误: 文件不存在: {file}"

        cmd = [config.SEQKIT_PATH, "grep", "-j", str(threads)]
        if use_regex:
            cmd.append("-r")
        if ignore_case:
            cmd.append("-i")
        if out_file:
            cmd.extend(["-o", out_file])
        cmd.extend([file, pattern])

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            if out_file:
                return f"已保存到: {out_file}\n找到 {result.stdout.count('>')} 条匹配序列"
            return result.stdout
        except subprocess.CalledProcessError as e:
            return f"seqkit 执行失败: {e.stderr}"


class SeqkitRmdupTool(ToolBase):
    """序列去重工具"""

    @property
    def name(self) -> str:
        return "seqkit_rmdup"

    @property
    def description(self) -> str:
        return "去除重复的序列，支持按序列内容、ID 或名称去重。"

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "file": {
                    "type": "string",
                    "description": "输入的 FASTA/FASTQ 文件路径"
                },
                "by": {
                    "type": "string",
                    "description": "去重方式: seq (序列内容), name (ID), id (序列ID)",
                    "default": "seq"
                },
                "out_file": {
                    "type": "string",
                    "description": "输出文件路径（可选）",
                    "default": ""
                },
                "threads": {
                    "type": "integer",
                    "description": "线程数",
                    "default": config.DEFAULT_THREADS
                }
            },
            "required": ["file"]
        }

    def execute(self, file: str, by: str = "seq", out_file: str = "", threads: int = None) -> str:
        if threads is None:
            threads = config.DEFAULT_THREADS

        if not os.path.exists(file):
            return f"错误: 文件不存在: {file}"

        # 参数映射: seq -> -s, name -> -n, id (默认)
        cmd = [config.SEQKIT_PATH, "rmdup", "-j", str(threads)]
        if by == "seq":
            cmd.append("-s")
        elif by == "name":
            cmd.append("-n")
        # id 是默认方式，不需要额外参数

        if out_file:
            cmd.extend(["-o", out_file])
        cmd.append(file)

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return result.stdout
        except subprocess.CalledProcessError as e:
            return f"seqkit 执行失败: {e.stderr}"


class SeqkitSortTool(ToolBase):
    """序列排序工具"""

    @property
    def name(self) -> str:
        return "seqkit_sort"

    @property
    def description(self) -> str:
        return "对序列进行排序，支持按序列长度、ID、名称或序列内容排序。"

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "file": {
                    "type": "string",
                    "description": "输入的 FASTA/FASTQ 文件路径"
                },
                "by": {
                    "type": "string",
                    "description": "排序方式: seq (序列内容), length (长度), name (名称), id (ID)",
                    "default": "name"
                },
                "reverse": {
                    "type": "boolean",
                    "description": "是否倒序",
                    "default": False
                },
                "out_file": {
                    "type": "string",
                    "description": "输出文件路径（可选）",
                    "default": ""
                },
                "threads": {
                    "type": "integer",
                    "description": "线程数",
                    "default": config.DEFAULT_THREADS
                }
            },
            "required": ["file"]
        }

    def execute(self, file: str, by: str = "name", reverse: bool = False,
                out_file: str = "", threads: int = None) -> str:
        if threads is None:
            threads = config.DEFAULT_THREADS

        if not os.path.exists(file):
            return f"错误: 文件不存在: {file}"

        cmd = [config.SEQKIT_PATH, "sort", "-j", str(threads), "-s", by]
        if reverse:
            cmd.append("-r")
        if out_file:
            cmd.extend(["-o", out_file])
        cmd.append(file)

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return result.stdout
        except subprocess.CalledProcessError as e:
            return f"seqkit 执行失败: {e.stderr}"


# 注册所有工具
def register_all_tools():
    """注册所有 seqkit 工具"""
    tools = [
        SeqkitStatsTool(),
        SeqkitFx2TabTool(),
        SeqkitGrepTool(),
        SeqkitRmdupTool(),
        SeqkitSortTool(),
    ]
    for tool in tools:
        ToolRegistry.register(tool)
