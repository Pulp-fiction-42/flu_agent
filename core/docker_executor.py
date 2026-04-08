"""
Docker 执行器 - 容器化工具执行
基于 V2_plan.md 的安全沙箱隔离设计
"""
import os
import shutil
import uuid
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

# 可选导入 docker
try:
    import docker
    from docker.errors import ImageNotFound, ContainerError, NotFound
    DOCKER_AVAILABLE = True
except ImportError:
    docker = None
    ImageNotFound = Exception
    ContainerError = Exception
    NotFound = Exception
    DOCKER_AVAILABLE = False


@dataclass
class ContainerResult:
    """容器执行结果"""
    success: bool
    stdout: str
    stderr: str
    exit_code: int
    error: Optional[str] = None


class DockerExecutor:
    """
    Docker 容器化执行器

    特性：
    - 容器内执行生物信息学工具
    - 自动挂载用户数据目录
    - 执行后立即销毁容器确保隔离
    - 支持工具版本控制和可重现
    """

    # 预定义工具镜像映射
    TOOL_IMAGES = {
        "irma": "staphb/irma:latest",
        "fastp": "staphb/fastp:latest",
        "fastqc": "staphb/fastqc:latest",
        "spades": "staphb/spades:latest",
        "megahit": "staphb/megahit:latest",
        "bwa": "staphb/bwa:latest",
        "minimap2": "staphb/minimap2:latest",
        "samtools": "staphb/samtools:latest",
        "iqtree2": "cecc:/quantai/iqtree2:latest",
        "mafft": "biocontainers/mafft:latest",
        "kraken2": "staphb/kraken2:latest",
        # 默认镜像
        "_default": "ubuntu:22.04",
    }

    def __init__(
        self,
        base_dir: str = None,
        timeout: int = 3600,
        auto_pull: bool = True,
    ):
        """
        Args:
            base_dir: 基础数据目录
            timeout: 执行超时（秒）
            auto_pull: 自动拉取镜像
        """
        self.base_dir = base_dir or "/tmp/fluagent/docker"
        self.timeout = timeout
        self.auto_pull = auto_pull

        # 确保基础目录存在
        os.makedirs(self.base_dir, exist_ok=True)

        # 初始化 Docker 客户端
        self.client = None
        self.available = False

        if not DOCKER_AVAILABLE:
            print("[DockerExecutor] Docker 模块未安装，请运行: pip install docker")
            return

        try:
            self.client = docker.from_env()
            # 测试连接
            self.client.ping()
            self.available = True
        except Exception as e:
            print(f"[DockerExecutor] Docker 不可用: {e}")
            self.client = None
            self.available = False

    def execute(
        self,
        tool_name: str,
        command: List[str],
        input_files: Dict[str, str] = None,
        output_files: List[str] = None,
        working_dir: str = "/data",
        image: str = None,
        env_vars: Dict[str, str] = None,
    ) -> ContainerResult:
        """
        在 Docker 容器中执行命令

        Args:
            tool_name: 工具名称
            command: 命令列表
            input_files: 输入文件映射 {容器内路径: 宿主机路径}
            output_files: 输出文件列表
            working_dir: 工作目录
            image: Docker 镜像（默认根据工具名自动选择）
            env_vars: 环境变量

        Returns:
            ContainerResult
        """
        if not self.available:
            return ContainerResult(
                success=False,
                stdout="",
                stderr="",
                exit_code=-1,
                error="Docker 不可用，请确保 Docker 已启动"
            )

        # 选择镜像
        docker_image = image or self.TOOL_IMAGES.get(
            tool_name, self.TOOL_IMAGES["_default"]
        )

        # 拉取镜像
        if self.auto_pull:
            self._pull_image(docker_image)

        # 创建临时工作目录
        run_id = str(uuid.uuid4())[:8]
        temp_dir = os.path.join(self.base_dir, f"run_{run_id}")
        os.makedirs(temp_dir, exist_ok=True)

        try:
            # 准备绑定挂载
            binds = {temp_dir: {"bind": working_dir, "mode": "rw"}}

            # 复制输入文件到临时目录
            if input_files:
                for container_path, host_path in input_files.items():
                    if os.path.exists(host_path):
                        dest = os.path.join(temp_dir, os.path.basename(container_path))
                        if os.path.isdir(host_path):
                            shutil.copytree(host_path, dest)
                        else:
                            shutil.copy2(host_path, dest)

            # 环境变量
            container_env = env_vars or {}
            container_env["PATH"] = "/usr/local/bin:/usr/bin:/bin"

            # 执行容器
            container = self.client.containers.run(
                docker_image,
                command=command,
                working_dir=working_dir,
                volumes=binds,
                environment=container_env,
                remove=True,  # 执行后自动删除
                detach=False,
                timeout=self.timeout,
            )

            return ContainerResult(
                success=container.exit_code == 0,
                stdout=container.output.decode("utf-8", errors="replace"),
                stderr="",
                exit_code=container.exit_code,
            )

        except ImageNotFound:
            return ContainerResult(
                success=False,
                stdout="",
                stderr="",
                exit_code=-1,
                error=f"镜像不存在: {docker_image}"
            )
        except ContainerError as e:
            return ContainerResult(
                success=False,
                stdout="",
                stderr=str(e),
                exit_code=-1,
                error=f"容器执行错误: {str(e)}"
            )
        except NotFound as e:
            return ContainerResult(
                success=False,
                stdout="",
                stderr="",
                exit_code=-1,
                error=f"资源未找到: {str(e)}"
            )
        except Exception as e:
            return ContainerResult(
                success=False,
                stdout="",
                stderr="",
                exit_code=-1,
                error=f"执行失败: {str(e)}"
            )
        finally:
            # 清理临时目录
            try:
                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir)
            except Exception:
                pass

    def execute_simple(
        self,
        tool_name: str,
        command: str,
        work_dir: str = "/data",
    ) -> ContainerResult:
        """
        简化执行接口（字符串命令）

        Args:
            tool_name: 工具名称
            command: 命令字符串
            work_dir: 工作目录

        Returns:
            ContainerResult
        """
        return self.execute(
            tool_name=tool_name,
            command=["sh", "-c", command],
            working_dir=work_dir,
        )

    def _pull_image(self, image: str):
        """拉取 Docker 镜像"""
        try:
            print(f"[DockerExecutor] 拉取镜像: {image}")
            self.client.images.pull(image)
        except Exception as e:
            print(f"[DockerExecutor] 拉取镜像失败: {e}")

    def is_available(self) -> bool:
        """检查 Docker 是否可用"""
        return self.available

    def list_images(self) -> List[str]:
        """列出本地镜像"""
        if not self.available:
            return []
        return [img.tags[0] for img in self.client.images.list() if img.tags]


# 全局单例
_docker_executor = None


def get_docker_executor() -> DockerExecutor:
    """获取全局 DockerExecutor 单例"""
    global _docker_executor
    if _docker_executor is None:
        _docker_executor = DockerExecutor()
    return _docker_executor


def execute_in_container(
    tool_name: str,
    command: List[str],
    **kwargs
) -> ContainerResult:
    """便捷函数：在容器中执行命令"""
    return get_docker_executor().execute(tool_name, command, **kwargs)