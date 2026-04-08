"""
其他辅助工具封装
包含 swarm（OTU聚类）、circos（基因组可视化）、hhblits/hhsearch（蛋白结构比对）
"""
import os
from .base import ToolBase, ToolRegistry
from . import utils
import config


class SwarmTool(ToolBase):
    """Swarm OTU 聚类工具"""

    @property
    def name(self) -> str:
        return "swarm_cluster"

    @property
    def description(self) -> str:
        return (
            "使用 Swarm 进行快速去噪和 OTU/ASV 聚类。基于序列差异的自然聚类算法。"
            "适用于 16S/18S 扩增子数据的物种聚类，比传统 OTU 方法更精确。"
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "input_file": {"type": "string", "description": "输入 FASTA 文件（排序后的扩增子序列）"},
                "output_dir": {"type": "string", "description": "输出目录", "default": ""},
                "differences": {"type": "integer", "description": "允许的差异碱基数（默认1）", "default": 1},
                "threads": {"type": "integer", "description": "线程数", "default": config.DEFAULT_THREADS},
            },
            "required": ["input_file"],
        }

    def execute(self, input_file: str, output_dir: str = "", differences: int = 1,
                threads: int = None) -> str:
        err = utils.check_file_exists(input_file)
        if err:
            return err
        if threads is None:
            threads = config.DEFAULT_THREADS

        tool_path = utils.resolve_path(config.SWARM_PATH)
        if not os.path.isfile(tool_path):
            return f"错误: swarm 未安装。路径: {config.SWARM_PATH}"

        if not output_dir:
            output_dir = os.getcwd()
        os.makedirs(output_dir, exist_ok=True)
        base = os.path.splitext(os.path.basename(input_file))[0]
        out_file = os.path.join(output_dir, f"{base}_swarm.swarms")
        stats_file = os.path.join(output_dir, f"{base}_swarm_stats.tsv")

        cmd = [tool_path, "-d", str(differences), "-t", str(threads),
               "-o", out_file, "-s", stats_file, input_file]

        result = utils.run_command(cmd)

        if result["success"]:
            output = f"[Swarm] 聚类完成\n差异阈值: {differences}\n结果: {out_file}\n"
            if os.path.exists(stats_file):
                with open(stats_file) as f:
                    output += f"\n统计:\n{f.read()[:2000]}"
            return output
        else:
            return f"[错误] Swarm 聚类失败: {result['stderr']}"


class CircosTool(ToolBase):
    """Circos 基因组可视化工具"""

    @property
    def name(self) -> str:
        return "circos_plot"

    @property
    def description(self) -> str:
        return (
            "使用 Circos 生成基因组环形可视化图。需要预先准备配置文件和输入数据。"
            "适用于展示基因组结构变异、共线性分析、比较基因组学结果等。"
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "config_file": {"type": "string", "description": "Circos 配置文件路径（.conf）"},
                "output_dir": {"type": "string", "description": "输出目录（默认与配置文件同目录）", "default": ""},
                "output_file": {"type": "string", "description": "输出图片文件名（如 circos.png）", "default": "circos.png"},
            },
            "required": ["config_file"],
        }

    def execute(self, config_file: str, output_dir: str = "",
                output_file: str = "circos.png") -> str:
        err = utils.check_file_exists(config_file)
        if err:
            return err

        tool_path = utils.resolve_path(config.CIRCOS_PATH)
        if not os.path.isfile(tool_path):
            return f"错误: circos 未安装。路径: {config.CIRCOS_PATH}"

        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
        else:
            output_dir = os.path.dirname(os.path.abspath(config_file))

        out_path = os.path.join(output_dir, output_file)

        cmd = [tool_path, "-conf", config_file, "-outputdir", output_dir,
               "-outputfile", output_file]

        result = utils.run_command(cmd, timeout=300)

        if result["success"]:
            output = f"[Circos] 图表生成完成\n"
            if os.path.exists(out_path):
                output += f"图片: {out_path}\n"
            else:
                output += result["stdout"][:2000]
            return output
        else:
            return f"[错误] Circos 失败: {result['stderr']}"


class HhblitsTool(ToolBase):
    """HHblits 蛋白远程同源性搜索工具"""

    @property
    def name(self) -> str:
        return "hhblits_search"

    @property
    def description(self) -> str:
        return (
            "使用 HHblits 搜索蛋白序列的远程同源物。基于隐马尔可夫模型（HMM）迭代搜索。"
            "比 PSI-BLAST 更灵敏，适用于检测远缘同源蛋白、蛋白结构预测。"
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "input_file": {"type": "string", "description": "输入 FASTA/A3M 文件"},
                "database": {"type": "string", "description": "HHblits 数据库路径或名称（如 uniclust30_2020_06）"},
                "iterations": {"type": "integer", "description": "迭代次数（默认3）", "default": 3},
                "output_dir": {"type": "string", "description": "输出目录", "default": ""},
                "threads": {"type": "integer", "description": "线程数", "default": config.DEFAULT_THREADS},
            },
            "required": ["input_file", "database"],
        }

    def execute(self, input_file: str, database: str, iterations: int = 3,
                output_dir: str = "", threads: int = None) -> str:
        err = utils.check_file_exists(input_file)
        if err:
            return err
        if threads is None:
            threads = config.DEFAULT_THREADS

        tool_path = utils.resolve_path(config.HHBLITS_PATH)
        if not os.path.isfile(tool_path):
            return f"错误: hhblits 未安装。路径: {config.HHBLITS_PATH}"

        if not output_dir:
            output_dir = os.getcwd()
        os.makedirs(output_dir, exist_ok=True)
        base = os.path.splitext(os.path.basename(input_file))[0]
        out_file = os.path.join(output_dir, f"{base}_hhblits.a3m")

        cmd = [tool_path, "-i", input_file, "-d", database,
               "-n", str(iterations), "-oa3m", out_file,
               "-cpu", str(threads)]

        result = utils.run_command(cmd, timeout=600)

        if result["success"]:
            output = f"[HHblits] 远程同源搜索完成\n数据库: {database}\n"
            output += f"结果: {out_file}\n"
            output += result["stdout"][-2000:]
            return output
        else:
            return f"[错误] HHblits 搜索失败: {result['stderr']}"


class HhsearchTool(ToolBase):
    """HHsearch 蛋白结构比对工具"""

    @property
    def name(self) -> str:
        return "hhsearch_search"

    @property
    def description(self) -> str:
        return (
            "使用 HHsearch 进行蛋白 HMM-HMM 比对。检测蛋白质结构相似性，预测蛋白功能。"
            "常与 HHblits 联用：先用 HHblits 生成查询 HMM，再用 HHsearch 与结构数据库比对。"
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "input_file": {"type": "string", "description": "输入 HHM 文件（可由 hhblits 生成）"},
                "database": {"type": "string", "description": "HHsearch 数据库路径"},
                "output_dir": {"type": "string", "description": "输出目录", "default": ""},
                "threads": {"type": "integer", "description": "线程数", "default": config.DEFAULT_THREADS},
            },
            "required": ["input_file", "database"],
        }

    def execute(self, input_file: str, database: str, output_dir: str = "",
                threads: int = None) -> str:
        err = utils.check_file_exists(input_file)
        if err:
            return err
        if threads is None:
            threads = config.DEFAULT_THREADS

        tool_path = utils.resolve_path(config.HHSEARCH_PATH)
        if not os.path.isfile(tool_path):
            return f"错误: hhsearch 未安装。路径: {config.HHSEARCH_PATH}"

        if not output_dir:
            output_dir = os.getcwd()
        os.makedirs(output_dir, exist_ok=True)
        base = os.path.splitext(os.path.basename(input_file))[0]
        out_file = os.path.join(output_dir, f"{base}_hhsearch.hhr")

        cmd = [tool_path, "-i", input_file, "-d", database,
               "-o", out_file, "-cpu", str(threads)]

        result = utils.run_command(cmd, timeout=600)

        if result["success"]:
            output = f"[HHsearch] 结构比对完成\n数据库: {database}\n"
            output += f"结果: {out_file}\n"
            if os.path.exists(out_file):
                with open(out_file) as f:
                    output += f.read()[:3000]
            return output
        else:
            return f"[错误] HHsearch 比对失败: {result['stderr']}"


def register_all_tools():
    """注册所有其他辅助工具"""
    for tool_cls in [SwarmTool, CircosTool, HhblitsTool, HhsearchTool]:
        ToolRegistry.register(tool_cls())
