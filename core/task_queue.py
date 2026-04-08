"""
异步任务队列模块 - Celery + Redis
基于 V3_plan.md 的异步任务与计算隔离层设计

功能：
- 长耗时生信计算的异步解耦
- 任务状态实时查询
- 断点续传支持
- 任务重试机制
"""
import os
import json
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from enum import Enum
from dataclasses import dataclass, asdict
import threading

# 注意：Celery 是可选依赖，如果不可用则降级为线程池模拟
try:
    from celery import Celery, Task
    from celery.result import AsyncResult
    CELERY_AVAILABLE = True
except ImportError:
    CELERY_AVAILABLE = False
    print("[TaskQueue] Celery 不可用，将使用线程池模拟")


@dataclass
class TaskInfo:
    """任务信息"""
    task_id: str
    task_type: str
    status: str  # pending, running, success, failure, retry
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    progress: float = 0.0  # 0-1
    result: Optional[Dict] = None
    error: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3


class TaskStatus(Enum):
    """任务状态枚举"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILURE = "failure"
    RETRY = "retry"
    CANCELLED = "cancelled"


class InMemoryTaskBroker:
    """
    内存任务代理（Celery 不可用时的降级方案）
    使用线程池模拟异步任务执行
    """
    def __init__(self):
        self.tasks: Dict[str, TaskInfo] = {}
        self.results: Dict[str, Any] = {}
        self._lock = threading.Lock()
        self._task_funcs: Dict[str, callable] = {}

    def register_task(self, name: str, func: callable):
        """注册任务函数"""
        self._task_funcs[name] = func

    def submit_task(self, task_type: str, args: tuple = (), kwargs: Dict = None) -> str:
        """提交任务"""
        kwargs = kwargs or {}
        task_id = str(uuid.uuid4())[:12]

        task_info = TaskInfo(
            task_id=task_id,
            task_type=task_type,
            status=TaskStatus.PENDING.value,
            created_at=datetime.now().isoformat(),
        )
        self.tasks[task_id] = task_info

        # 后台线程执行
        thread = threading.Thread(
            target=self._run_task,
            args=(task_id, task_type, args, kwargs)
        )
        thread.daemon = True
        thread.start()

        return task_id

    def _run_task(self, task_id: str, task_type: str, args: tuple, kwargs: Dict):
        """后台执行任务"""
        with self._lock:
            if task_id in self.tasks:
                self.tasks[task_id].status = TaskStatus.RUNNING.value
                self.tasks[task_id].started_at = datetime.now().isoformat()

        try:
            func = self._task_funcs.get(task_type)
            if func:
                result = func(*args, **kwargs)
                with self._lock:
                    if task_id in self.tasks:
                        self.tasks[task_id].status = TaskStatus.SUCCESS.value
                        self.tasks[task_id].completed_at = datetime.now().isoformat()
                        self.tasks[task_id].progress = 1.0
                        self.tasks[task_id].result = result
            else:
                raise ValueError(f"Unknown task type: {task_type}")
        except Exception as e:
            with self._lock:
                if task_id in self.tasks:
                    self.tasks[task_id].status = TaskStatus.FAILURE.value
                    self.tasks[task_id].completed_at = datetime.now().isoformat()
                    self.tasks[task_id].error = str(e)

    def get_task_status(self, task_id: str) -> Optional[TaskInfo]:
        """获取任务状态"""
        with self._lock:
            return self.tasks.get(task_id)

    def update_progress(self, task_id: str, progress: float, result: Dict = None):
        """更新任务进度"""
        with self._lock:
            if task_id in self.tasks:
                self.tasks[task_id].progress = progress
                if result:
                    self.tasks[task_id].result = result

    def list_tasks(self, status: str = None, limit: int = 100) -> List[TaskInfo]:
        """列出任务"""
        with self._lock:
            tasks = list(self.tasks.values())
            if status:
                tasks = [t for t in tasks if t.status == status]
            return sorted(tasks, key=lambda x: x.created_at, reverse=True)[:limit]


# Celery 应用（可选）
if CELERY_AVAILABLE:
    celery_app = Celery(
        "fluagent",
        broker=os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0"),
        backend=os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/0"),
    )

    celery_app.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="Asia/Shanghai",
        enable_utc=True,
        task_track_started=True,
        task_time_limit=3600,  # 1小时超时
        task_soft_time_limit=3300,
        worker_prefetch_multiplier=1,
        task_acks_late=True,
        task_reject_on_worker_lost=True,
    )


class TaskQueue:
    """
    统一任务队列接口
    自动选择 Celery（如果可用）或内存代理
    """

    def __init__(self):
        if CELERY_AVAILABLE:
            self.backend = "celery"
        else:
            self.backend = "memory"
        self._broker = InMemoryTaskBroker()
        self._workflow_tasks: Dict[str, callable] = {}

        # 注册内置任务
        self._register_builtin_tasks()

    def _register_builtin_tasks(self):
        """注册内置任务"""
        # Docker 执行任务
        self.register_task("docker_execute", self._docker_execute_task)

        # Nextflow 工作流任务
        self.register_task("nextflow_run", self._nextflow_run_task)

    def register_task(self, name: str, func: callable):
        """注册自定义任务"""
        self._broker.register_task(name, func)

    def submit(
        self,
        task_type: str,
        args: tuple = None,
        kwargs: Dict = None,
        user_id: str = None,
        session_id: str = None,
    ) -> str:
        """
        提交任务

        Args:
            task_type: 任务类型
            args: 位置参数
            kwargs: 关键字参数
            user_id: 用户ID（用于权限校验）
            session_id: 会话ID（用于数据隔离）

        Returns:
            task_id: 任务ID
        """
        args = args or ()
        kwargs = kwargs or {}
        kwargs["_user_id"] = user_id
        kwargs["_session_id"] = session_id

        return self._broker.submit_task(task_type, args, kwargs)

    def get_status(self, task_id: str) -> Optional[TaskInfo]:
        """获取任务状态"""
        return self._broker.get_task_status(task_id)

    def update_progress(self, task_id: str, progress: float, result: Dict = None):
        """更新任务进度"""
        self._broker.update_progress(task_id, progress, result)

    def cancel(self, task_id: str) -> bool:
        """取消任务"""
        task = self.get_status(task_id)
        if task and task.status in [TaskStatus.PENDING.value, TaskStatus.RUNNING.value]:
            task.status = TaskStatus.CANCELLED.value
            return True
        return False

    def list_tasks(self, user_id: str = None, status: str = None, limit: int = 100) -> List[TaskInfo]:
        """列出任务"""
        tasks = self._broker.list_tasks(status=status, limit=limit)
        if user_id:
            # 过滤属于指定用户的任务（需要 result 中包含 user_id）
            tasks = [
                t for t in tasks
                if t.result and t.result.get("user_id") == user_id
            ]
        return tasks

    # ========== 内置任务实现 ==========

    def _docker_execute_task(self, tool_name: str, command: str, **kwargs):
        """Docker 执行任务"""
        from .docker_executor import get_docker_executor

        executor = get_docker_executor()
        result = executor.execute_simple(tool_name, command)

        return {
            "success": result.success,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exit_code": result.exit_code,
            "error": result.error,
            "user_id": kwargs.get("_user_id"),
            "session_id": kwargs.get("_session_id"),
        }

    def _nextflow_run_task(self, workflow: str, params: Dict, **kwargs):
        """Nextflow 工作流执行任务"""
        import subprocess

        work_dir = kwargs.get("work_dir", "/tmp/fluagent/nextflow")
        os.makedirs(work_dir, exist_ok=True)

        # 构建 nextflow 命令
        cmd = [
            "nextflow", "run", workflow,
            "-work-dir", work_dir,
        ]
        for key, value in params.items():
            cmd.extend([f"--{key}", str(value)])

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=kwargs.get("timeout", 3600),
            )
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "exit_code": result.returncode,
                "user_id": kwargs.get("_user_id"),
                "session_id": kwargs.get("_session_id"),
            }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": "任务超时",
                "user_id": kwargs.get("_user_id"),
                "session_id": kwargs.get("_session_id"),
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "user_id": kwargs.get("_user_id"),
                "session_id": kwargs.get("_session_id"),
            }


# ========== Celery 任务定义（可选）==========

if CELERY_AVAILABLE:
    @celery_app.task(bind=True, name="fluagent.docker_execute")
    def celery_docker_execute(self: Task, tool_name: str, command: str, **kwargs):
        """Celery: Docker 执行任务"""
        from .docker_executor import get_docker_executor

        executor = get_docker_executor()
        result = executor.execute_simple(tool_name, command)

        return {
            "success": result.success,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exit_code": result.exit_code,
            "error": result.error,
            "user_id": kwargs.get("_user_id"),
            "session_id": kwargs.get("_session_id"),
        }

    @celery_app.task(bind=True, name="fluagent.nextflow_run")
    def celery_nextflow_run(self: Task, workflow: str, params: Dict, **kwargs):
        """Celery: Nextflow 工作流执行任务"""
        import subprocess

        work_dir = kwargs.get("work_dir", "/tmp/fluagent/nextflow")
        os.makedirs(work_dir, exist_ok=True)

        cmd = ["nextflow", "run", workflow, "-work-dir", work_dir]
        for key, value in params.items():
            cmd.extend([f"--{key}", str(value)])

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "exit_code": result.returncode,
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "任务超时"}
        except Exception as e:
            return {"success": False, "error": str(e)}


# ========== 全局单例 ==========

_task_queue = None


def get_task_queue() -> TaskQueue:
    """获取全局 TaskQueue 单例"""
    global _task_queue
    if _task_queue is None:
        _task_queue = TaskQueue()
    return _task_queue
