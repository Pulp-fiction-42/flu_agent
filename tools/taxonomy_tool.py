"""
分类鉴定工具封装
包含 Kraken2（快速分类）, 简化版分类报告
"""
import os
from .base import ToolBase, ToolRegistry
from . import utils
import config


class Kraken2Tool(ToolBase):
    """Kraken2 快速序列分类工具"""

    @property
    def name(self) -> str:
        return "kraken2_classify"

    @property
    def description(self) -> str:
        return (
            "使用 Kraken2 对测序数据进行快速物种分类。基于 k-mer 精确比对，速度极快。"
            "可用于病原体鉴定、微生物组分析。需预先构建或下载分类数据库。"
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "input_file": {"type": "string", "description": "输入 FASTQ 文件路径（R1）"},
                "input_file2": {"type": "string", "description": "输入 FASTQ R2 路径（双端时提供）", "default": ""},
                "db": {"type": "string", "description": "Kraken2 数据库路径"},
                "output_dir": {"type": "string", "description": "输出目录", "default": ""},
                "report_level": {"type": "integer", "description": "报告层级: 1=域, 2=界, 3=门, 4=纲, 5=目, 6=科, 7=属, 8=种", "default": 0},
                "confidence": {"type": "number", "description": "置信度阈值（0-1）", "default": 0.1},
                "threads": {"type": "integer", "description": "线程数", "default": config.DEFAULT_THREADS},
            },
            "required": ["input_file", "db"],
        }

    def execute(self, input_file: str, db: str, input_file2: str = "",
                output_dir: str = "", report_level: int = 0,
                confidence: float = 0.1, threads: int = None) -> str:
        err = utils.check_file_exists(input_file)
        if err:
            return err
        if not os.path.isdir(db):
            return f"错误: Kraken2 数据库目录不存在: {db}"
        if threads is None:
            threads = config.DEFAULT_THREADS

        tool_path = utils.resolve_path(config.KRAKEN2_PATH)
        if not os.path.isfile(tool_path):
            return "错误: kraken2 未安装。请运行: conda install -c bioconda kraken2"

        if not output_dir:
            output_dir = os.getcwd()
        os.makedirs(output_dir, exist_ok=True)
        base = os.path.splitext(os.path.basename(input_file))[0]
        report_file = os.path.join(output_dir, f"{base}_kraken2.report.txt")
        output_file = os.path.join(output_dir, f"{base}_kraken2.output.txt")

        cmd = [tool_path, "--db", db, "--threads", str(threads),
               "--confidence", str(confidence),
               "--report", report_file, "--output", output_file]

        if input_file2:
            cmd.extend([input_file, input_file2])
        else:
            cmd.extend(["--paired", input_file])

        result = utils.run_command(cmd, timeout=1200)

        if result["success"]:
            output = f"[Kraken2] 分类完成\n数据库: {db}\n报告: {report_file}\n"
            if os.path.exists(report_file):
                with open(report_file) as f:
                    lines = f.readlines()
                # 显示非零比例的分类
                for line in lines:
                    parts = line.strip().split("\t")
                    if len(parts) >= 6:
                        pct = float(parts[0])
                        if pct >= 0.01:  # 只显示 >=0.01% 的分类
                            output += line
            return output
        else:
            return f"[错误] Kraken2 分类失败: {result['stderr']}"


class TaxonkitTool(ToolBase):
    """Taxonkit 分类学信息查询工具"""

    @property
    def name(self) -> str:
        return "taxonkit_query"

    @property
    def description(self) -> str:
        return (
            "使用 Taxonkit 查询 NCBI 分类信息。根据物种 TaxID 查询完整分类信息（界门纲目科属种）、"
            "拉丁名、rank 等。也可根据物种名称查询 TaxID。"
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "taxid": {"type": "string", "description": "NCBI TaxID（如 9606 表示人类）"},
                "sci_name": {"type": "string", "description": "物种拉丁名（与 taxid 二选一）"},
                "show_lineage": {"type": "boolean", "description": "是否显示完整分类谱系", "default": True},
                "show_rank": {"type": "boolean", "description": "是否显示各级 rank", "default": True},
            },
            "required": [],
        }

    def execute(self, taxid: str = "", sci_name: str = "", show_lineage: bool = True,
                show_rank: bool = True) -> str:
        tool_path = utils.resolve_path(config.TAXONKIT_PATH)
        if not os.path.isfile(tool_path):
            return "错误: taxonkit 未安装。请检查路径: " + config.TAXONKIT_PATH

        # 如果提供物种名，先查询 TaxID
        if sci_name and not taxid:
            cmd = [tool_path, "list", "--ids", sci_name]
            result = utils.run_command(cmd)
            if result["success"] and result["stdout"]:
                taxid = result["stdout"].strip().split("\n")[0]
            else:
                return f"错误: 无法找到物种 '{sci_name}' 的 TaxID"

        if not taxid:
            return "错误: 请提供 taxid 或 sci_name"

        # 查询分类信息
        cmd = [tool_path, "lineage", taxid]
        if show_rank:
            cmd.append("--show-rank")

        result = utils.run_command(cmd)

        if result["success"]:
            output = f"[Taxonkit] 分类信息查询结果\nTaxID: {taxid}\n"
            if show_lineage:
                output += "\n分类谱系:\n"
            output += result["stdout"]
            return output
        else:
            return f"[错误] Taxonkit 查询失败: {result['stderr']}"

    def get_taxid(self, sci_name: str) -> str:
        """根据物种名获取 TaxID（内部方法）"""
        tool_path = utils.resolve_path(config.TAXONKIT_PATH)
        cmd = [tool_path, "list", "--ids", sci_name]
        result = utils.run_command(cmd)
        if result["success"] and result["stdout"]:
            return result["stdout"].strip().split("\n")[0]
        return ""


def register_all_tools():
    """注册所有分类鉴定工具"""
    for tool_cls in [Kraken2Tool, TaxonkitTool]:
        ToolRegistry.register(tool_cls())
