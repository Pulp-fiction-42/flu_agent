"""
进化分析工具封装
包含 mafft（多序列比对）、trimal（比对裁剪）、iqtree2（系统发育树）、codeml/baseml（选择压力分析）
"""
import os
from .base import ToolBase, ToolRegistry
from . import utils
import config


class MafftTool(ToolBase):
    """MAFFT 多序列比对工具"""

    @property
    def name(self) -> str:
        return "mafft_align"

    @property
    def description(self) -> str:
        return (
            "使用 MAFFT 进行多序列比对。支持快速（FFT-NS-2）和精确（L-INS-i）模式。"
            "适用于蛋白质和核酸序列比对，是系统发育分析的前置步骤。"
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "input_file": {"type": "string", "description": "输入 FASTA 文件（多条序列）"},
                "output_dir": {"type": "string", "description": "输出目录", "default": ""},
                "strategy": {"type": "string", "description": "比对策略: auto（自动）、localpair（精确L-INS-i）、genafpair（G-INS-i）、globalpair（FFT-NS-2快速）", "default": "auto"},
                "maxiterate": {"type": "integer", "description": "迭代次数（默认1000）", "default": 1000},
                "threads": {"type": "integer", "description": "线程数", "default": config.DEFAULT_THREADS},
            },
            "required": ["input_file"],
        }

    def execute(self, input_file: str, output_dir: str = "", strategy: str = "auto",
                maxiterate: int = 1000, threads: int = None) -> str:
        err = utils.check_file_exists(input_file)
        if err:
            return err
        if threads is None:
            threads = config.DEFAULT_THREADS

        tool_path = utils.resolve_path(config.MAFFT_PATH)
        if not os.path.isfile(tool_path):
            return "错误: mafft 未安装。请检查路径: " + config.MAFFT_PATH

        cmd = [tool_path, "--thread", str(threads),
               "--maxiterate", str(maxiterate)]

        if strategy == "localpair":
            cmd.append("--localpair")
        elif strategy == "genafpair":
            cmd.append("--genafpair")
        elif strategy == "globalpair":
            cmd.append("--globalpair")
        # auto 模式不指定

        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
            base = os.path.splitext(os.path.basename(input_file))[0]
            out_file = os.path.join(output_dir, f"{base}_aligned.fasta")
            cmd.extend(["--output", out_file])

        cmd.append(input_file)
        result = utils.run_command(cmd)

        if result["success"]:
            output = f"[MAFFT] 多序列比对完成\n策略: {strategy}\n"
            if output_dir:
                output += f"比对结果: {out_file}\n"
                # 统计比对信息
                seqkit = utils.resolve_path(config.SEQKIT_PATH)
                if os.path.isfile(seqkit):
                    stats = utils.run_command([seqkit, "stats", out_file])
                    if stats["success"]:
                        output += f"\n比对统计:\n{stats['stdout']}"
            else:
                output += utils.truncate_output(result["stdout"], 3000)
            return output
        else:
            return f"[错误] MAFFT 比对失败: {result['stderr']}"


class TrimalTool(ToolBase):
    """trimAl 比对裁剪工具"""

    @property
    def name(self) -> str:
        return "trimal_trim"

    @property
    def description(self) -> str:
        return (
            "使用 trimAl 对多序列比对结果进行裁剪，去除低质量比对区域。"
            "支持多种裁剪策略：自动模式、基于一致性、基于间隙。是系统发育分析前的重要步骤。"
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "input_file": {"type": "string", "description": "输入比对后的 FASTA/PHYLIP 文件"},
                "output_dir": {"type": "string", "description": "输出目录", "default": ""},
                "method": {"type": "string", "description": "裁剪方法: automated（自动）、automated1、gappyout（基于间隙）、strict（严格）", "default": "automated"},
                "threshold": {"type": "number", "description": "保留列的最小一致性比例（0-1，仅部分方法适用）", "default": 0.0},
            },
            "required": ["input_file"],
        }

    def execute(self, input_file: str, output_dir: str = "", method: str = "automated",
                threshold: float = 0.0) -> str:
        err = utils.check_file_exists(input_file)
        if err:
            return err

        tool_path = utils.resolve_path(config.TRIMAL_PATH)
        if not os.path.isfile(tool_path):
            return "错误: trimal 未安装。请检查路径: " + config.TRIMAL_PATH

        cmd = [tool_path, "-in", input_file]

        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
            base = os.path.splitext(os.path.basename(input_file))[0]
            out_file = os.path.join(output_dir, f"{base}_trimmed.fasta")
            cmd.extend(["-out", out_file])

        if method == "automated":
            cmd.append("-automated1")
        elif method == "gappyout":
            cmd.append("-gappyout")
        elif method == "strict":
            cmd.append("-strict")
        elif method == "automated1":
            cmd.append("-automated1")

        if threshold > 0:
            cmd.extend(["-gt", str(threshold)])

        result = utils.run_command(cmd)

        if result["success"]:
            output = f"[trimAl] 比对裁剪完成\n方法: {method}\n"
            if output_dir:
                output += f"裁剪结果: {out_file}\n"
            return output
        else:
            return f"[错误] trimAl 裁剪失败: {result['stderr']}"


class IqtreeTool(ToolBase):
    """IQ-TREE2 系统发育树构建工具"""

    @property
    def name(self) -> str:
        return "iqtree_build"

    @property
    def description(self) -> str:
        return (
            "使用 IQ-TREE2 构建最大似然系统发育树。自动选择最优替换模型（ModelFinder）。"
            "支持超度量树（超快 Bootstrap）、共识树、树可视化。是系统发育分析的主流工具。"
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "input_file": {"type": "string", "description": "输入比对后的 FASTA/PHYLIP 文件"},
                "output_dir": {"type": "string", "description": "输出目录", "default": ""},
                "model": {"type": "string", "description": "替换模型（如 HKY+G, GTR+G），留空自动选择（MFP）", "default": "MFP"},
                "bootstrap": {"type": "integer", "description": "Bootstrap 重复次数（0=不做, 1000=标准, ufboot=超快）", "default": 1000},
                "bootstrap_method": {"type": "string", "description": "Bootstrap 方法: ufboot（超快）, bnni（标准）", "default": "ufboot"},
                "threads": {"type": "integer", "description": "线程数", "default": config.DEFAULT_THREADS},
            },
            "required": ["input_file"],
        }

    def execute(self, input_file: str, output_dir: str = "", model: str = "MFP",
                bootstrap: int = 1000, bootstrap_method: str = "ufboot",
                threads: int = None) -> str:
        err = utils.check_file_exists(input_file)
        if err:
            return err
        if threads is None:
            threads = config.DEFAULT_THREADS

        tool_path = utils.resolve_path(config.IQTREE_PATH)
        if not os.path.isfile(tool_path):
            return "错误: iqtree2 未安装。请检查路径: " + config.IQTREE_PATH

        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
            import shutil
            # IQ-TREE 在输入文件同目录输出，先复制输入
            local_input = os.path.join(output_dir, os.path.basename(input_file))
            if os.path.abspath(input_file) != os.path.abspath(local_input):
                shutil.copy2(input_file, local_input)
        else:
            output_dir = os.path.dirname(input_file) or "."
            local_input = input_file

        cmd = [tool_path, "-s", local_input, "-m", model,
               "-T", str(threads), "-pre",
               os.path.splitext(local_input)[0]]

        if bootstrap > 0:
            if bootstrap_method == "ufboot":
                cmd.extend(["-bb", str(bootstrap), "-alrt", "1000"])
            else:
                cmd.extend(["-b", str(bootstrap)])

        result = utils.run_command(cmd, timeout=3600)

        if result["success"]:
            output = f"[IQ-TREE2] 系统发育树构建完成\n模型: {model}\n"
            tree_file = os.path.splitext(local_input)[0] + ".treefile"
            log_file = os.path.splitext(local_input)[0] + ".iqtree"
            if os.path.exists(tree_file):
                output += f"树文件: {tree_file}\n"
            if os.path.exists(log_file):
                # 提取模型选择结果
                with open(log_file) as f:
                    content = f.read()
                if "Best-fit model" in content:
                    import re
                    m = re.search(r"Best-fit model.*?:\s*(\S+)", content)
                    if m:
                        output += f"最优模型: {m.group(1)}\n"
            output += result["stdout"][-1000:]
            return output
        else:
            return f"[错误] IQ-TREE2 失败: {result['stderr']}"


class CodemlTool(ToolBase):
    """PAML codeml 选择压力分析工具"""

    @property
    def name(self) -> str:
        return "codeml_analyze"

    @property
    def description(self) -> str:
        return (
            "使用 PAML codeml 进行选择压力分析（dN/dS，即 ω 值计算）。"
            "检测编码序列中的正向选择位点。需要比对后的编码序列和系统发育树作为输入。"
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "alignment_file": {"type": "string", "description": "输入比对后的编码序列（PHYLIP 格式）"},
                "tree_file": {"type": "string", "description": "系统发育树文件（Newick 格式）"},
                "model": {"type": "string", "description": "分析模型: m0（one-ratio）, m1a（neutral）, m2a（selection）, m7（beta）, m8（beta&ω>1）", "default": "m7"},
                "output_dir": {"type": "string", "description": "输出目录", "default": ""},
            },
            "required": ["alignment_file", "tree_file"],
        }

    def execute(self, alignment_file: str, tree_file: str, model: str = "m7",
                output_dir: str = "") -> str:
        err = utils.check_file_exists(alignment_file)
        if err:
            return err
        err = utils.check_file_exists(tree_file)
        if err:
            return err

        tool_path = utils.resolve_path(config.CODEML_PATH)
        if not os.path.isfile(tool_path):
            return "错误: codeml 未安装。请检查路径: " + config.CODEML_PATH

        if not output_dir:
            output_dir = os.getcwd()
        os.makedirs(output_dir, exist_ok=True)

        # 生成 codeml 控制文件
        ctl_content = f"""seqfile = {os.path.abspath(alignment_file)}
treefile = {os.path.abspath(tree_file)}
outfile = {os.path.join(output_dir, f'codeml_{model}.out')}
runmode = 0
seqtype = 1
CodonFreq = 2
model = {model}
NSsites = {model[-1]}
icode = 0
fix_kappa = 0
kappa = 2
fix_omega = 0
omega = 0.4
getSE = 0
RateAncestor = 0
Small_Diff = 5e-7
cleandata = 0
"""
        ctl_path = os.path.join(output_dir, f"codeml_{model}.ctl")
        with open(ctl_path, 'w') as f:
            f.write(ctl_content)

        result = utils.run_command([tool_path, ctl_path], timeout=600)

        if result["success"]:
            output = f"[codeml] 选择压力分析完成\n模型: {model}\n"
            output_file_path = os.path.join(output_dir, f'codeml_{model}.out')
            if os.path.exists(output_file_path):
                with open(output_file_path) as f:
                    content = f.read()
                # 提取关键结果
                import re
                omega_match = re.search(r"omega\s*\(dN/dS\)\s*=\s*([\d.]+)", content)
                if omega_match:
                    output += f"omega (dN/dS): {omega_match.group(1)}\n"
                lnL_match = re.search(r"lnL\s*=\s*([-.\d]+)", content)
                if lnL_match:
                    output += f"lnL: {lnL_match.group(1)}\n"
            return output
        else:
            return f"[错误] codeml 分析失败: {result['stderr']}"


class BasemlgTool(ToolBase):
    """PAML basemlg 碱基替换速率分析工具"""

    @property
    def name(self) -> str:
        return "basemlg_analyze"

    @property
    def description(self) -> str:
        return (
            "使用 PAML baseml 进行碱基替换模式分析。"
            "估计不同位点的替换速率，适用于核酸序列进化分析。"
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "alignment_file": {"type": "string", "description": "输入比对后的核酸序列（PHYLIP 格式）"},
                "tree_file": {"type": "string", "description": "系统发育树文件（Newick 格式）"},
                "model": {"type": "string", "description": "碱基替换模型: 0 (JC69), 1 (K80), 2 (F84), 3 (GH), 4 (GT)", "default": "3"},
                "output_dir": {"type": "string", "description": "输出目录", "default": ""},
            },
            "required": ["alignment_file", "tree_file"],
        }

    def execute(self, alignment_file: str, tree_file: str, model: str = "3",
                output_dir: str = "") -> str:
        err = utils.check_file_exists(alignment_file)
        if err:
            return err
        err = utils.check_file_exists(tree_file)
        if err:
            return err

        tool_path = utils.resolve_path(config.BASEMLG_PATH)
        if not os.path.isfile(tool_path):
            return "错误: basemlg 未安装。请检查路径: " + config.BASEMLG_PATH

        if not output_dir:
            output_dir = os.getcwd()
        os.makedirs(output_dir, exist_ok=True)

        ctl_content = f"""seqfile = {os.path.abspath(alignment_file)}
treefile = {os.path.abspath(tree_file)}
outfile = {os.path.join(output_dir, 'basemlg.out')}
runmode = 0
seqtype = 0
model = {model}
fix_alpha = 1
alpha = 0
ncatG = 5
getSE = 0
RateAncestor = 0
Small_Diff = 5e-7
cleandata = 0
"""
        ctl_path = os.path.join(output_dir, "basemlg.ctl")
        with open(ctl_path, 'w') as f:
            f.write(ctl_content)

        result = utils.run_command([tool_path, ctl_path], timeout=600)

        if result["success"]:
            output = f"[basemlg] 碱基替换分析完成\n模型: {model}\n"
            output_file_path = os.path.join(output_dir, 'basemlg.out')
            if os.path.exists(output_file_path):
                with open(output_file_path) as f:
                    content = f.read()
                import re
                lnL_match = re.search(r"lnL\s*=\s*([-.\d]+)", content)
                if lnL_match:
                    output += f"lnL: {lnL_match.group(1)}\n"
            return output
        else:
            return f"[错误] basemlg 分析失败: {result['stderr']}"


class Yn00Tool(ToolBase):
    """PAML yn00 核苷酸水平的 dN/dS 分析工具"""

    @property
    def name(self) -> str:
        return "yn00_analyze"

    @property
    def description(self) -> str:
        return (
            "使用 PAML yn00 进行核酸序列间的 dN（非同义替换）和 dS（同义替换）计算。"
            "基于 Nei-Gojobori 方法，适用于成对序列的选择压力分析。"
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "alignment_file": {"type": "string", "description": "输入比对后的编码序列（FASTA/PHYLIP 格式）"},
                "output_dir": {"type": "string", "description": "输出目录", "default": ""},
            },
            "required": ["alignment_file"],
        }

    def execute(self, alignment_file: str, output_dir: str = "") -> str:
        err = utils.check_file_exists(alignment_file)
        if err:
            return err

        tool_path = utils.resolve_path(config.YN00_PATH)
        if not os.path.isfile(tool_path):
            return "错误: yn00 未安装。请检查路径: " + config.YN00_PATH

        if not output_dir:
            output_dir = os.getcwd()
        os.makedirs(output_dir, exist_ok=True)

        ctl_content = f"""seqfile = {os.path.abspath(alignment_file)}
outfile = {os.path.join(output_dir, 'yn00.out')}
outformat = 0
verbose = 1
codonfreq = 2
Nsites = 0
fix_kappa = 0
kappa = 2
fix_omega = 0
omega = 0.4
getSE = 0
"""
        ctl_path = os.path.join(output_dir, "yn00.ctl")
        with open(ctl_path, 'w') as f:
            f.write(ctl_content)

        result = utils.run_command([tool_path, ctl_path], timeout=600)

        if result["success"]:
            output = f"[yn00] dN/dS 分析完成\n"
            output_file_path = os.path.join(output_dir, 'yn00.out')
            if os.path.exists(output_file_path):
                with open(output_file_path) as f:
                    content = f.read()
                output += "结果已保存到: " + output_file_path + "\n"
                # 提取前几行关键结果
                lines = content.split('\n')[:30]
                output += "\n".join(lines)
            return output
        else:
            return f"[错误] yn00 分析失败: {result['stderr']}"


class EvolverTool(ToolBase):
    """PAML evolver 序列进化模拟工具"""

    @property
    def name(self) -> str:
        return "evolver_simulate"

    @property
    def description(self) -> str:
        return (
            "使用 PAML evolver 根据给定的系统发育树和进化模型模拟序列进化。"
            "可生成核酸序列或蛋白质序列，适用于进化方法验证和模拟研究。"
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "tree_file": {"type": "string", "description": "系统发育树文件（Newick 格式）"},
                "seq_length": {"type": "integer", "description": "序列长度（核苷酸或氨基酸）", "default": 1000},
                "seq_type": {"type": "string", "description": "序列类型: 1 (DNA), 2 (protein)", "default": "1"},
                "model": {"type": "string", "description": "替换模型参数（如 kappa, omega）", "default": ""},
                "output_dir": {"type": "string", "description": "输出目录", "default": ""},
            },
            "required": ["tree_file"],
        }

    def execute(self, tree_file: str, seq_length: int = 1000, seq_type: str = "1",
                model: str = "", output_dir: str = "") -> str:
        err = utils.check_file_exists(tree_file)
        if err:
            return err

        tool_path = utils.resolve_path(config.EVOLVER_PATH)
        if not os.path.isfile(tool_path):
            return "错误: evolver 未安装。请检查路径: " + config.EVOLVER_PATH

        if not output_dir:
            output_dir = os.getcwd()
        os.makedirs(output_dir, exist_ok=True)

        # evolver 命令行参数
        cmd = [tool_path, "1"]  # 1 = simulate sequences
        if seq_type == "1":
            cmd.extend(["-l", str(seq_length), "-f", "1"])  # DNA
        else:
            cmd.extend(["-l", str(seq_length), "-f", "2"])  # Protein

        # 创建包含树内容的文件
        with open(tree_file) as f:
            tree_content = f.read().strip()
        tree_input = os.path.join(output_dir, "evolver_tree.txt")
        with open(tree_input, 'w') as f:
            f.write(tree_content)

        result = utils.run_command(cmd, input_content=tree_content, timeout=60)

        if result["success"]:
            output = f"[evolver] 序列模拟完成\n序列长度: {seq_length}\n类型: {'DNA' if seq_type == '1' else 'Protein'}\n"
            # evolver 输出到当前目录
            out_files = [f for f in os.listdir(".") if f.startswith("evolver")]
            if out_files:
                output += f"生成文件: {', '.join(out_files)}\n"
            return output
        else:
            return f"[错误] evolver 模拟失败: {result['stderr']}"


class McmctreeTool(ToolBase):
    """PAML MCMCTree 贝叶斯分子钟分析工具"""

    @property
    def name(self) -> str:
        return "mcmctree_analyze"

    @property
    def description(self) -> str:
        return (
            "使用 PAML MCMCTree 进行贝叶斯分子钟分析。"
            "估算物种分化时间，需要比对后的序列和系统发育树作为输入。"
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "alignment_file": {"type": "string", "description": "输入比对后的编码序列（PHYLIP 格式）"},
                "tree_file": {"type": "string", "description": "系统发育树文件（Newick 格式）"},
                "clock_model": {"type": "string", "description": "分子钟模型: 1 (Strict), 2 (Relaxed)", "default": "2"},
                "output_dir": {"type": "string", "description": "输出目录", "default": ""},
            },
            "required": ["alignment_file", "tree_file"],
        }

    def execute(self, alignment_file: str, tree_file: str, clock_model: str = "2",
                output_dir: str = "") -> str:
        err = utils.check_file_exists(alignment_file)
        if err:
            return err
        err = utils.check_file_exists(tree_file)
        if err:
            return err

        tool_path = utils.resolve_path(config.MCMCTREE_PATH)
        if not os.path.isfile(tool_path):
            return "错误: mcmctree 未安装。请检查路径: " + config.MCMCTREE_PATH

        if not output_dir:
            output_dir = os.getcwd()
        os.makedirs(output_dir, exist_ok=True)

        # 生成 mcmctree 控制文件
        ctl_content = f"""seqfile = {os.path.abspath(alignment_file)}
treefile = {os.path.abspath(tree_file)}
outfile = {os.path.join(output_dir, 'mcmctree.out')}
ndata = 1
seqtype = 1
clock = {clock_model}
TipDate = 0.0
alpha = 0
ncatG = 5
fix_blength = 0
method = 0
nsample = 20000
samplefreq = 2
burnin = 2000
print = 1
"""

        ctl_path = os.path.join(output_dir, "mcmctree.ctl")
        with open(ctl_path, 'w') as f:
            f.write(ctl_content)

        result = utils.run_command([tool_path, ctl_path], timeout=3600)

        if result["success"]:
            output = f"[MCMCTree] 分子钟分析完成\n时钟模型: {'Strict' if clock_model == '1' else 'Relaxed'}\n"
            output += "注意: MCMCTree 计算耗时较长，请耐心等待结果。\n"
            output_file_path = os.path.join(output_dir, 'mcmctree.out')
            if os.path.exists(output_file_path):
                output += f"结果文件: {output_file_path}\n"
            return output
        else:
            return f"[错误] MCMCTree 分析失败: {result['stderr']}"


def register_all_tools():
    """注册所有进化分析工具"""
    for tool_cls in [MafftTool, TrimalTool, IqtreeTool, CodemlTool,
                     BasemlgTool, Yn00Tool, EvolverTool, McmctreeTool]:
        ToolRegistry.register(tool_cls())
