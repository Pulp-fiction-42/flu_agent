"""
质控工具封装
包含 fastp（质控+过滤）、fastqc（质控报告）、multiqc（汇总报告）、cutadapt（接头去除）
"""
import os
from .base import ToolBase, ToolRegistry
from . import utils
import config


class FastpTool(ToolBase):
    """fastp 质控工具：快速过滤、质控、接头去除"""

    @property
    def name(self) -> str:
        return "fastp_qc"

    @property
    def description(self) -> str:
        return (
            "使用 fastp 对 FASTQ 文件进行质控和过滤。支持单端/双端数据、接头去除、"
            "质量过滤、长度过滤、 polyG/polyX 裁剪。输出过滤后的 FASTQ 和 HTML/JSON 质控报告。"
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "input_file": {"type": "string", "description": "输入 FASTQ 文件路径（R1）"},
                "input_file2": {"type": "string", "description": "输入 FASTQ R2 路径（双端测序时提供）", "default": ""},
                "output_dir": {"type": "string", "description": "输出目录", "default": ""},
                "qualified_quality": {"type": "integer", "description": "碱基质量阈值（默认20）", "default": 20},
                "length_required": {"type": "integer", "description": "最短读段长度（默认50）", "default": 50},
                "detect_adapter_for_pe": {"type": "boolean", "description": "自动检测双端接头（默认true）", "default": True},
                "trim_front": {"type": "integer", "description": "前端裁剪碱基数", "default": 0},
                "trim_tail": {"type": "integer", "description": "后端裁剪碱基数", "default": 0},
                "threads": {"type": "integer", "description": "线程数", "default": config.DEFAULT_THREADS},
            },
            "required": ["input_file"],
        }

    def execute(self, input_file: str, input_file2: str = "", output_dir: str = "",
                qualified_quality: int = 20, length_required: int = 50,
                detect_adapter_for_pe: bool = True, trim_front: int = 0, trim_tail: int = 0,
                threads: int = None) -> str:
        err = utils.check_file_exists(input_file)
        if err:
            return err
        if input_file2:
            err2 = utils.check_file_exists(input_file2)
            if err2:
                return err2

        if threads is None:
            threads = config.DEFAULT_THREADS

        tool_path = utils.resolve_path(config.FASTP_PATH)
        if not os.path.isfile(tool_path):
            return f"错误: fastp 未安装。请运行: conda install -c bioconda fastp"

        cmd = [tool_path, "-i", input_file, "-q", str(qualified_quality),
               "-l", str(length_required), "--thread", str(threads),
               "--disable_length_filtering", "--detect_adapter_for_pe",
               "--json", "/dev/stdout"]

        if input_file2:
            cmd.extend(["-I", input_file2])

        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
            base1 = os.path.splitext(os.path.basename(input_file))[0]
            cmd.extend(["-o", os.path.join(output_dir, f"{base1}_clean.fastq")])
            if input_file2:
                base2 = os.path.splitext(os.path.basename(input_file2))[0]
                cmd.extend(["-O", os.path.join(output_dir, f"{base2}_clean.fastq")])
            cmd.extend(["-h", os.path.join(output_dir, f"{base1}_fastp.html"),
                         "-j", os.path.join(output_dir, f"{base1}_fastp.json")])

        result = utils.run_command(cmd)
        output = utils.format_result(result, "fastp")
        if result["success"] and output_dir:
            output += f"\n质控文件已保存到: {output_dir}"
        return output


class FastqcTool(ToolBase):
    """FastQC 质控报告工具"""

    @property
    def name(self) -> str:
        return "fastqc_report"

    @property
    def description(self) -> str:
        return "使用 FastQC 生成 FASTQ 文件的质量控制报告，包含碱基质量分布、GC含量、接头污染等指标。"

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "files": {"type": "string", "description": "输入 FASTQ 文件路径，多个文件用逗号分隔"},
                "output_dir": {"type": "string", "description": "输出目录（默认当前目录）", "default": "."},
                "threads": {"type": "integer", "description": "线程数", "default": config.DEFAULT_THREADS},
            },
            "required": ["files"],
        }

    def execute(self, files: str, output_dir: str = ".", threads: int = None) -> str:
        if threads is None:
            threads = config.DEFAULT_THREADS

        tool_path = utils.resolve_path(config.FASTQC_PATH)
        if not os.path.isfile(tool_path):
            return "错误: fastqc 未安装。请运行: conda install -c bioconda fastqc"

        file_list = [f.strip() for f in files.split(",")]
        for f in file_list:
            err = utils.check_file_exists(f)
            if err:
                return err

        os.makedirs(output_dir, exist_ok=True)
        cmd = [tool_path, "-t", str(threads), "-o", output_dir] + file_list
        result = utils.run_command(cmd, timeout=300)
        output = utils.format_result(result, "fastqc")
        if result["success"]:
            output += f"\n报告已保存到: {output_dir}"
        return output


class MultiqcTool(ToolBase):
    """MultiQC 汇总报告工具"""

    @property
    def name(self) -> str:
        return "multiqc_report"

    @property
    def description(self) -> str:
        return "使用 MultiQC 将多个工具的质控报告汇总为一个综合 HTML 报告。支持 fastqc、fastp、samtools、blast 等工具的输出。"

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "input_dir": {"type": "string", "description": "包含各工具报告的目录路径"},
                "output_dir": {"type": "string", "description": "MultiQC 输出目录（默认为 input_dir 下）", "default": ""},
            },
            "required": ["input_dir"],
        }

    def execute(self, input_dir: str, output_dir: str = "") -> str:
        if not os.path.isdir(input_dir):
            return f"错误: 目录不存在: {input_dir}"

        tool_path = utils.resolve_path(config.MULTIQC_PATH)
        if not os.path.isfile(tool_path):
            return "错误: multiqc 未安装。请运行: conda install -c bioconda multiqc"

        if not output_dir:
            output_dir = input_dir
        cmd = [tool_path, input_dir, "-o", output_dir, "--force"]
        result = utils.run_command(cmd)
        output = utils.format_result(result, "multiqc")
        if result["success"]:
            output += f"\n报告已保存到: {output_dir}"
        return output


class CutadaptTool(ToolBase):
    """Cutadapt 接头去除工具"""

    @property
    def name(self) -> str:
        return "cutadapt_trim"

    @property
    def description(self) -> str:
        return "使用 cutadapt 去除 FASTQ 文件中的接头序列。支持自动检测接头、3'/5'端裁剪、最小长度过滤。"

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "input_file": {"type": "string", "description": "输入 FASTQ 文件路径"},
                "adapter": {"type": "string", "description": "接头序列（如 AGATCGGAAGAGC），不提供则自动检测", "default": ""},
                "output_dir": {"type": "string", "description": "输出目录", "default": ""},
                "min_length": {"type": "integer", "description": "最短保留长度", "default": 30},
                "quality_cutoff": {"type": "integer", "description": "3'端质量裁剪阈值", "default": 20},
                "threads": {"type": "integer", "description": "线程数", "default": config.DEFAULT_THREADS},
            },
            "required": ["input_file"],
        }

    def execute(self, input_file: str, adapter: str = "", output_dir: str = "",
                min_length: int = 30, quality_cutoff: int = 20, threads: int = None) -> str:
        err = utils.check_file_exists(input_file)
        if err:
            return err
        if threads is None:
            threads = config.DEFAULT_THREADS

        tool_path = utils.resolve_path(config.CUTADAPT_PATH)
        if not os.path.isfile(tool_path):
            return "错误: cutadapt 未安装。请运行: conda install -c bioconda cutadapt"

        cmd = [tool_path, "-j", str(threads), "-m", str(min_length),
               "-q", str(quality_cutoff)]

        if adapter:
            cmd.extend(["-a", adapter])

        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
            base = os.path.splitext(os.path.basename(input_file))[0]
            out_file = os.path.join(output_dir, f"{base}_trimmed.fastq")
            cmd.extend(["-o", out_file])
        else:
            out_file = ""

        cmd.append(input_file)

        result = utils.run_command(cmd)
        output = utils.format_result(result, "cutadapt")
        if result["success"] and output_dir:
            output += f"\n输出已保存到: {output_dir}"
        return output


def register_all_tools():
    """注册所有质控工具"""
    for tool_cls in [FastpTool, FastqcTool, MultiqcTool, CutadaptTool]:
        ToolRegistry.register(tool_cls())
