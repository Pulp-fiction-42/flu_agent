"""
工具执行辅助函数
统一封装 subprocess 调用、文件检查、结果格式化
"""
import os
import subprocess
import config


def run_command(cmd: list, timeout: int = None, cwd: str = None, input_content: str = None) -> dict:
    """
    执行外部命令并返回结构化结果

    Args:
        cmd: 命令列表
        timeout: 超时时间（秒）
        cwd: 工作目录
        input_content: 标准输入内容（可选）

    Returns:
        {"success": bool, "stdout": str, "stderr": str, "returncode": int}
    """
    if timeout is None:
        timeout = config.COMMAND_TIMEOUT

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, cwd=cwd,
            input=input_content
        )
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
            "returncode": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "stdout": "",
            "stderr": f"命令执行超时（{timeout}秒）: {' '.join(cmd)}",
            "returncode": -1,
        }
    except FileNotFoundError:
        cmd_name = cmd[0] if cmd else "unknown"
        return {
            "success": False,
            "stdout": "",
            "stderr": f"工具未找到: {cmd_name}。请确认已安装并配置正确路径。",
            "returncode": -1,
        }
    except Exception as e:
        return {
            "success": False,
            "stdout": "",
            "stderr": f"执行异常: {str(e)}",
            "returncode": -1,
        }


def check_file_exists(file_path: str) -> str:
    """检查文件是否存在，不存在时返回错误信息"""
    if not os.path.exists(file_path):
        return f"错误: 文件不存在: {file_path}"
    if not os.path.isfile(file_path):
        return f"错误: 不是有效文件: {file_path}"
    return ""


def resolve_path(primary: str, fallback: str = "") -> str:
    """解析工具路径，主路径不存在时尝试备用"""
    return config.resolve_tool_path(primary, fallback)


def ensure_output_dir(file_path: str) -> str:
    """确保输出文件的父目录存在"""
    parent = os.path.dirname(file_path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    return file_path


def format_result(result: dict, tool_name: str = "") -> str:
    """将 run_command 结果格式化为可读文本"""
    if result["success"]:
        output = result["stdout"]
        if tool_name:
            output = f"[{tool_name}] 执行成功\n{output}"
        return output
    else:
        return f"[错误] {result['stderr']}"


def truncate_output(text: str, max_chars: int = 4000) -> str:
    """截断过长的输出文本"""
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + f"\n\n... (输出已截断，共 {len(text)} 字符)"
