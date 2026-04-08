"""
组装工具封装
包含 SPAdes（基因组组装）、MEGAHIT（宏基因组组装）
"""
import os
from .base import ToolBase, ToolRegistry
from . import utils
import config


class SpadesTool(ToolBase):
    """SPAdes 基因组组装工具"""

    @property
    def name(self) -> str:
        return "spades_assembly"

    @property
    def description(self) -> str:
        return (
            "使用 SPAdes 进行 de novo 基因组组装。支持单端/双端数据、iontorrent 数据。"
            "适用于细菌、病毒等小基因组的组装。输出 contigs/scaffolds FASTA 文件。"
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "input_file": {"type": "string", "description": "输入 FASTQ 文件路径（R1）"},
                "input_file2": {"type": "string", "description": "输入 FASTQ R2 路径（双端时提供）", "default": ""},
                "output_dir": {"type": "string", "description": "输出目录（默认 spades_output）", "default": "spades_output"},
                "k_mers": {"type": "string", "description": "k-mer 大小列表，逗号分隔（如 '21,33,55,77'），留空自动选择", "default": ""},
                "min_contig_len": {"type": "integer", "description": "最短 contig 长度（默认500）", "default": 500},
                "threads": {"type": "integer", "description": "线程数", "default": config.DEFAULT_THREADS},
            },
            "required": ["input_file"],
        }

    def execute(self, input_file: str, input_file2: str = "", output_dir: str = "spades_output",
                k_mers: str = "", min_contig_len: int = 500, threads: int = None) -> str:
        err = utils.check_file_exists(input_file)
        if err:
            return err
        if threads is None:
            threads = config.DEFAULT_THREADS

        tool_path = utils.resolve_path(config.SPADES_PATH)
        if not os.path.isfile(tool_path):
            return "错误: spades 未安装。请运行: conda install -c bioconda spades"

        cmd = [tool_path, "-1", input_file, "-o", output_dir,
               "-t", str(threads), "--min-contig-len", str(min_contig_len)]

        if input_file2:
            cmd.extend(["-2", input_file2])

        if k_mers:
            cmd.extend(["-k", k_mers])

        result = utils.run_command(cmd, timeout=3600)

        if result["success"]:
            contigs_path = os.path.join(output_dir, "contigs.fasta")
            scaffolds_path = os.path.join(output_dir, "scaffolds.fasta")
            output = f"[SPAdes] 组装完成\n输出目录: {output_dir}\n"
            if os.path.exists(contigs_path):
                output += f"Contigs: {contigs_path}\n"
            if os.path.exists(scaffolds_path):
                output += f"Scaffolds: {scaffolds_path}\n"
            # 显示组装统计摘要
            import subprocess
            seqkit = utils.resolve_path(config.SEQKIT_PATH)
            if os.path.isfile(seqkit) and os.path.exists(contigs_path):
                stats = subprocess.run([seqkit, "stats", contigs_path],
                                       capture_output=True, text=True)
                if stats.returncode == 0:
                    output += f"\n组装统计:\n{stats.stdout}"
            return output
        else:
            return f"[错误] SPAdes 组装失败: {result['stderr']}"


class MegahitTool(ToolBase):
    """MEGAHIT 宏基因组/大基因组组装工具"""

    @property
    def name(self) -> str:
        return "megahit_assembly"

    @property
    def description(self) -> str:
        return (
            "使用 MEGAHIT 进行快速的 de novo 组装。适用于宏基因组、大基因组数据。"
            "比 SPAdes 更适合处理大规模数据，内存效率更高。"
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "input_file": {"type": "string", "description": "输入 FASTQ R1 文件路径"},
                "input_file2": {"type": "string", "description": "输入 FASTQ R2 路径（双端时提供）", "default": ""},
                "output_dir": {"type": "string", "description": "输出目录（默认 megahit_output）", "default": "megahit_output"},
                "min_contig_len": {"type": "integer", "description": "最短 contig 长度", "default": 500},
                "k_list": {"type": "string", "description": "k-mer 列表，逗号分隔", "default": ""},
                "threads": {"type": "integer", "description": "线程数", "default": config.DEFAULT_THREADS},
            },
            "required": ["input_file"],
        }

    def execute(self, input_file: str, input_file2: str = "", output_dir: str = "megahit_output",
                min_contig_len: int = 500, k_list: str = "", threads: int = None) -> str:
        err = utils.check_file_exists(input_file)
        if err:
            return err
        if threads is None:
            threads = config.DEFAULT_THREADS

        tool_path = utils.resolve_path(config.MEGAHIT_PATH)
        if not os.path.isfile(tool_path):
            return "错误: megahit 未安装。请运行: conda install -c bioconda megahit"

        cmd = [tool_path, "-1", input_file, "-o", output_dir,
               "-t", str(threads), "--min-contig-len", str(min_contig_len)]

        if input_file2:
            cmd.extend(["-2", input_file2])
        if k_list:
            cmd.extend(["-k", k_list])

        result = utils.run_command(cmd, timeout=3600)

        if result["success"]:
            contigs_path = os.path.join(output_dir, "final.contigs.fa")
            output = f"[MEGAHIT] 组装完成\n输出目录: {output_dir}\n"
            if os.path.exists(contigs_path):
                output += f"Contigs: {contigs_path}\n"
                import subprocess
                seqkit = utils.resolve_path(config.SEQKIT_PATH)
                if os.path.isfile(seqkit):
                    stats = subprocess.run([seqkit, "stats", contigs_path],
                                           capture_output=True, text=True)
                    if stats.returncode == 0:
                        output += f"\n组装统计:\n{stats.stdout}"
            return output
        else:
            return f"[错误] MEGAHIT 组装失败: {result['stderr']}"


def register_all_tools():
    """注册所有组装工具"""
    for tool_cls in [SpadesTool, MegahitTool]:
        ToolRegistry.register(tool_cls())
