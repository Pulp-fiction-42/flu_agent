"""
比对与排序工具封装
包含 minimap2（快速映射）、bwa（比对）、samtools（BAM处理）、blastn（序列比对）、diamond（蛋白比对）
"""
import os
from .base import ToolBase, ToolRegistry
from . import utils
import config


class Minimap2Tool(ToolBase):
    """minimap2 快速序列映射工具"""

    @property
    def name(self) -> str:
        return "minimap2_map"

    @property
    def description(self) -> str:
        return (
            "使用 minimap2 将测序 reads 映射到参考基因组。支持短读段和长读段。"
            "速度快、内存低，适合大规模数据比对。输出 SAM/BAM 格式。"
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "input_file": {"type": "string", "description": "输入 FASTQ/FASTA 文件（reads）"},
                "reference": {"type": "string", "description": "参考基因组 FASTA 文件"},
                "output_dir": {"type": "string", "description": "输出目录", "default": ""},
                "preset": {"type": "string", "description": "预设模式: sr（短读段）, map-ont（纳米孔）, map-pb（PacBio）, asm5（基因组比对）", "default": "sr"},
                "threads": {"type": "integer", "description": "线程数", "default": config.DEFAULT_THREADS},
            },
            "required": ["input_file", "reference"],
        }

    def execute(self, input_file: str, reference: str, output_dir: str = "",
                preset: str = "sr", threads: int = None) -> str:
        err = utils.check_file_exists(input_file)
        if err:
            return err
        err = utils.check_file_exists(reference)
        if err:
            return err
        if threads is None:
            threads = config.DEFAULT_THREADS

        tool_path = utils.resolve_path(config.MINIMAP2_PATH)
        if not os.path.isfile(tool_path):
            return "错误: minimap2 未安装。请运行: conda install -c bioconda minimap2"

        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
            base = os.path.splitext(os.path.basename(input_file))[0]
            out_file = os.path.join(output_dir, f"{base}.sam")
        else:
            out_file = "-"

        cmd = [tool_path, "-t", str(threads), "-x", preset, "-a",
               reference, input_file]
        result = utils.run_command(cmd)

        if result["success"]:
            output = f"[minimap2] 比对完成\n比对模式: {preset}\n"
            if output_dir and out_file != "-":
                # 保存到文件
                with open(out_file, 'w') as f:
                    f.write(result["stdout"])
                output += f"SAM 文件: {out_file}\n"
                output += f"比对读段数: {result['stdout'].count(chr(10))}\n"
            else:
                output += result["stdout"][:2000]
            return output
        else:
            return f"[错误] minimap2 比对失败: {result['stderr']}"


class SamtoolsTool(ToolBase):
    """Samtools BAM/SAM 处理工具"""

    @property
    def name(self) -> str:
        return "samtools_process"

    @property
    def description(self) -> str:
        return (
            "使用 samtools 处理 SAM/BAM 文件。支持格式转换、排序、索引、统计。"
            "子命令: sort（排序）, view（格式转换/过滤）, flagstat（统计）, idxstats（索引统计）, depth（深度）。"
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "input_file": {"type": "string", "description": "输入 SAM/BAM 文件路径"},
                "command": {"type": "string", "description": "samtools 子命令: sort, view, flagstat, idxstats, depth", "default": "flagstat"},
                "output_dir": {"type": "string", "description": "输出目录", "default": ""},
                "threads": {"type": "integer", "description": "线程数", "default": config.DEFAULT_THREADS},
            },
            "required": ["input_file"],
        }

    def execute(self, input_file: str, command: str = "flagstat", output_dir: str = "",
                threads: int = None) -> str:
        err = utils.check_file_exists(input_file)
        if err:
            return err
        if threads is None:
            threads = config.DEFAULT_THREADS

        tool_path = utils.resolve_path(config.SAMTOOLS_PATH)
        if not os.path.isfile(tool_path):
            return "错误: samtools 未安装。请运行: conda install -c bioconda samtools"

        valid_commands = ["sort", "view", "flagstat", "idxstats", "depth"]
        if command not in valid_commands:
            return f"错误: 不支持的 samtools 子命令 '{command}'。支持: {', '.join(valid_commands)}"

        cmd = [tool_path, command]
        if command == "sort":
            cmd.extend(["-@", str(threads)])
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)
                base = os.path.splitext(os.path.basename(input_file))[0]
                cmd.extend(["-o", os.path.join(output_dir, f"{base}_sorted.bam")])
            else:
                cmd.append("-")  # stdout
            cmd.append(input_file)
            result = utils.run_command(cmd)
        else:
            cmd.append(input_file)
            result = utils.run_command(cmd)

        if result["success"]:
            output = f"[samtools {command}] 执行成功\n"
            if result["stdout"]:
                output += result["stdout"][:3000]
            if output_dir and command == "sort":
                output += f"\n排序文件已保存到: {output_dir}"
            return output
        else:
            return f"[错误] samtools {command} 失败: {result['stderr']}"


class BlastnTool(ToolBase):
    """BLASTn 核酸序列比对工具"""

    @property
    def name(self) -> str:
        return "blastn_search"

    @property
    def description(self) -> str:
        return (
            "使用 BLASTn 将核酸序列与 NCBI 数据库进行比对。支持本地数据库和在线比对。"
            "用于序列鉴定、同源性搜索。建议对病毒序列使用 nt 数据库进行种属鉴定。"
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "查询序列 FASTA 文件"},
                "db": {"type": "string", "description": "BLAST 数据库名（本地）或 'nt'（在线 NCBI）", "default": "nt"},
                "max_target_seqs": {"type": "integer", "description": "最大返回比对数", "default": 10},
                "evalue": {"type": "number", "description": "E-value 阈值", "default": 1e-5},
                "out_format": {"type": "string", "description": "输出格式: 6=制表符, 0=配对, 5=XML", "default": "6"},
                "output_dir": {"type": "string", "description": "输出目录", "default": ""},
                "threads": {"type": "integer", "description": "线程数", "default": config.DEFAULT_THREADS},
            },
            "required": ["query"],
        }

    def execute(self, query: str, db: str = "nt", max_target_seqs: int = 10,
                evalue: float = 1e-5, out_format: str = "6", output_dir: str = "",
                threads: int = None) -> str:
        err = utils.check_file_exists(query)
        if err:
            return err
        if threads is None:
            threads = config.DEFAULT_THREADS

        tool_path = utils.resolve_path(config.BLASTN_PATH)
        if not os.path.isfile(tool_path):
            return "错误: blastn 未安装。请运行: conda install -c bioconda blast"

        cmd = [tool_path, "-query", query, "-db", db,
               "-max_target_seqs", str(max_target_seqs),
               "-evalue", str(evalue), "-outfmt", out_format,
               "-num_threads", str(threads)]

        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
            base = os.path.splitext(os.path.basename(query))[0]
            out_file = os.path.join(output_dir, f"{base}_blastn.tsv")
            cmd.extend(["-out", out_file])

        result = utils.run_command(cmd, timeout=1200)

        if result["success"]:
            output = f"[BLASTn] 比对完成\n数据库: {db}\n"
            if output_dir:
                output += f"结果已保存到: {out_file}\n"
            output += result["stdout"][:3000]
            return output
        else:
            return f"[错误] BLASTn 比对失败: {result['stderr']}"


class DiamondTool(ToolBase):
    """DIAMOND 快速蛋白比对工具"""

    @property
    def name(self) -> str:
        return "diamond_search"

    @property
    def description(self) -> str:
        return (
            "使用 DIAMOND 进行快速的蛋白序列比对（BLASTX/BLASTP）。速度比 BLAST 快 500-20000 倍。"
            "适用于大规模数据的蛋白功能注释。支持 nr 数据库比对。"
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "查询 FASTA/FASTQ 文件"},
                "db": {"type": "string", "description": "DIAMOND 数据库路径（需预先用 makedb 构建）"},
                "mode": {"type": "string", "description": "比对模式: blastp（蛋白-蛋白）, blastx（核酸-蛋白）", "default": "blastx"},
                "max_target_seqs": {"type": "integer", "description": "最大返回比对数", "default": 10},
                "evalue": {"type": "number", "description": "E-value 阈值", "default": 1e-5},
                "output_dir": {"type": "string", "description": "输出目录", "default": ""},
                "threads": {"type": "integer", "description": "线程数", "default": config.DEFAULT_THREADS},
            },
            "required": ["query", "db"],
        }

    def execute(self, query: str, db: str, mode: str = "blastx",
                max_target_seqs: int = 10, evalue: float = 1e-5,
                output_dir: str = "", threads: int = None) -> str:
        err = utils.check_file_exists(query)
        if err:
            return err
        if threads is None:
            threads = config.DEFAULT_THREADS

        tool_path = utils.resolve_path(config.DIAMOND_PATH)
        if not os.path.isfile(tool_path):
            return f"错误: diamond 未找到。路径: {config.DIAMOND_PATH}"

        if not output_dir:
            output_dir = os.getcwd()
        os.makedirs(output_dir, exist_ok=True)
        base = os.path.splitext(os.path.basename(query))[0]
        out_file = os.path.join(output_dir, f"{base}_diamond.tsv")
        daa_file = os.path.join(output_dir, f"{base}_diamond.daa")

        cmd = [tool_path, mode, "-d", db, "-q", query,
               "-o", out_file, "-k", str(max_target_seqs),
               "-e", str(evalue), "-p", str(threads),
               "--tmpdir", output_dir, "-daa", daa_file]

        result = utils.run_command(cmd, timeout=1200)

        if result["success"]:
            output = f"[DIAMOND] 比对完成\n模式: {mode}\n数据库: {db}\n"
            output += f"结果: {out_file}\n"
            # 显示前几行结果
            if os.path.exists(out_file):
                with open(out_file) as f:
                    lines = f.readlines()[:20]
                if lines:
                    output += "\n前20行结果:\n" + "".join(lines)
            return output
        else:
            return f"[错误] DIAMOND 比对失败: {result['stderr']}"


def register_all_tools():
    """注册所有比对与排序工具"""
    for tool_cls in [Minimap2Tool, SamtoolsTool, BlastnTool, DiamondTool]:
        ToolRegistry.register(tool_cls())
