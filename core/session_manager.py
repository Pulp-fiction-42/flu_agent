"""
用户会话与权限管理模块
基于 V2_plan.md 的多用户隔离设计
"""
import os
import uuid
import hashlib
from typing import Dict, Optional, List
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class User:
    """用户信息"""
    user_id: str
    username: str
    created_at: datetime = field(default_factory=datetime.now)
    last_active: datetime = field(default_factory=datetime.now)
    storage_quota: int = 1024 * 1024 * 1024  # 1GB 默认配额
    is_active: bool = True


@dataclass
class Session:
    """会话信息"""
    session_id: str
    user_id: str
    created_at: datetime = field(default_factory=datetime.now)
    last_active: datetime = field(default_factory=datetime.now)
    data_dir: str = ""


class SessionManager:
    """
    会话管理器

    功能：
    - 多用户会话隔离
    - 文件目录物理隔离 (data/uploads/{user_id}/{session_id})
    - 权限校验中间件
    - 会话超时管理
    """

    def __init__(self, base_data_dir: str = "data"):
        self.base_data_dir = base_data_dir
        self.uploads_dir = os.path.join(base_data_dir, "uploads")
        self.sessions: Dict[str, Session] = {}
        self.users: Dict[str, User] = {}

        # 确保目录存在
        os.makedirs(self.uploads_dir, exist_ok=True)

    def create_session(self, user_id: str = None) -> Session:
        """
        创建新会话

        Args:
            user_id: 用户ID（可选，自动生成）

        Returns:
            Session 对象
        """
        if user_id is None:
            user_id = self._generate_user_id()

        session_id = str(uuid.uuid4())

        # 构建隔离的数据目录
        session_dir = os.path.join(
            self.uploads_dir,
            user_id,
            session_id
        )
        os.makedirs(session_dir, exist_ok=True)

        session = Session(
            session_id=session_id,
            user_id=user_id,
            data_dir=session_dir
        )

        self.sessions[session_id] = session
        return session

    def get_session(self, session_id: str) -> Optional[Session]:
        """获取会话信息"""
        return self.sessions.get(session_id)

    def validate_path(self, session_id: str, file_path: str) -> bool:
        """
        验证文件路径是否在会话目录内（防止路径穿越）

        Args:
            session_id: 会话ID
            file_path: 要访问的文件路径

        Returns:
            是否合法
        """
        session = self.get_session(session_id)
        if not session:
            return False

        # 解析绝对路径
        abs_path = os.path.abspath(file_path)
        abs_session_dir = os.path.abspath(session.data_dir)

        # 确保路径在会话目录内
        return abs_path.startswith(abs_session_dir)

    def get_user_dir(self, user_id: str) -> str:
        """获取用户根目录"""
        return os.path.join(self.uploads_dir, user_id)

    def get_session_dir(self, session_id: str) -> Optional[str]:
        """获取会话目录"""
        session = self.get_session(session_id)
        return session.data_dir if session else None

    def list_user_sessions(self, user_id: str) -> List[Session]:
        """列出用户的所有会话"""
        return [
            s for s in self.sessions.values()
            if s.user_id == user_id
        ]

    def cleanup_session(self, session_id: str) -> bool:
        """
        清理会话（删除会话目录）

        注意：只清理会话目录，保留用户目录
        """
        session = self.get_session(session_id)
        if not session:
            return False

        try:
            if os.path.exists(session.data_dir):
                import shutil
                shutil.rmtree(session.data_dir)
            del self.sessions[session_id]
            return True
        except Exception as e:
            print(f"[SessionManager] 清理会话失败: {e}")
            return False

    def _generate_user_id(self) -> str:
        """生成用户ID"""
        return hashlib.md5(
            str(uuid.uuid4()).encode()
        ).hexdigest()[:12]

    def register_user(self, username: str) -> User:
        """
        注册新用户（简化版本，不含密码）

        注意：生产环境应使用 proper 认证
        """
        user_id = self._generate_user_id()
        user = User(
            user_id=user_id,
            username=username
        )
        self.users[user_id] = user
        return user

    def get_user(self, user_id: str) -> Optional[User]:
        """获取用户信息"""
        return self.users.get(user_id)


# 全局单例
_session_manager = None


def get_session_manager() -> SessionManager:
    """获取全局 SessionManager 单例"""
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager


def validate_session_access(session_id: str, file_path: str) -> bool:
    """便捷函数：验证会话文件访问"""
    return get_session_manager().validate_path(session_id, file_path)