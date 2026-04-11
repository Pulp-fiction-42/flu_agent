"""
FluAgent V3.0 API
基于 V3_plan.md 的多用户高并发生信 Agent 平台

特性：
- JWT 多用户认证
- 权限校验中间件
- 异步任务队列
- 会话数据隔离
"""
import os
import sys
import json
import uuid
import sqlite3
import hashlib
import datetime
import threading
from typing import Dict, List, Any, Optional
from functools import lru_cache

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, UploadFile, File, HTTPException, Body, Depends, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel
import jwt

from config_loader import get_config
from core.agent import FluAgent
from core.session_manager import SessionManager, get_session_manager
from core.task_queue import get_task_queue, TaskStatus

# ==================== JWT 认证模块 ====================

JWT_SECRET = os.environ.get("JWT_SECRET", "fluagent-secret-key-change-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24

# 模拟用户存储（生产环境应使用数据库）
_users_db: Dict[str, Dict] = {}


class UserAuth:
    """简易用户认证（生产环境应集成真实用户系统）"""

    @staticmethod
    def hash_password(password: str) -> str:
        return hashlib.sha256(password.encode()).hexdigest()

    @staticmethod
    def verify_password(password: str, hashed: str) -> bool:
        return UserAuth.hash_password(password) == hashed

    @staticmethod
    def create_token(user_id: str, username: str) -> str:
        """创建 JWT token"""
        payload = {
            "user_id": user_id,
            "username": username,
            "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=JWT_EXPIRATION_HOURS),
            "iat": datetime.datetime.utcnow(),
        }
        return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

    @staticmethod
    def decode_token(token: str) -> Optional[Dict]:
        """解码 JWT token"""
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            return payload
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None


# ==================== 请求/响应模型 ====================

class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(BaseModel):
    username: str
    password: str


class ConversationCreateRequest(BaseModel):
    title: Optional[str] = None

class ChatRequest(BaseModel):
    message: str
    model: Optional[str] = None
    files: Optional[List[str]] = []
    conversation_id: Optional[str] = None  # 关联到特定对话


class TaskSubmitRequest(BaseModel):
    task_type: str
    args: Optional[List] = []
    kwargs: Optional[Dict] = {}


# ==================== 依赖注入 ====================

async def get_current_user(authorization: str = Header(None)) -> Dict:
    """获取当前用户（从 JWT token）"""
    if not authorization:
        raise HTTPException(status_code=401, detail="未提供认证令牌")

    # 提取 Bearer token
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="无效的认证格式")

    token = parts[1]
    payload = UserAuth.decode_token(token)

    if not payload:
        raise HTTPException(status_code=401, detail="令牌已过期或无效")

    return payload


async def get_current_user_optional(authorization: str = Header(None)) -> Optional[Dict]:
    """可选的用户认证（不强制）"""
    if not authorization:
        return None
    try:
        parts = authorization.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            return UserAuth.decode_token(parts[1])
    except Exception:
        pass
    return None


# ==================== FastAPI 应用 ====================

app = FastAPI(
    title="FluAgent V3.0 API",
    description="多用户高并发生信 Agent 平台",
    version="3.0.0",
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应限制
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全局会话管理器
session_manager = get_session_manager()
task_queue = get_task_queue()

MODEL_CATALOG_TTL_SECONDS = max(int(os.environ.get("MODEL_CATALOG_TTL_SECONDS", "120")), 5)
MODEL_CATALOG_PROBE_TIMEOUT_SECONDS = max(int(os.environ.get("MODEL_CATALOG_PROBE_TIMEOUT_SECONDS", "3")), 1)


class ModelCatalogCache:
    """内存中的模型目录快照，避免请求路径上做在线探测。"""

    def __init__(self, ttl_seconds: int = 120, probe_timeout_seconds: int = 3):
        self.ttl_seconds = ttl_seconds
        self.probe_timeout_seconds = probe_timeout_seconds
        self._lock = threading.Lock()
        self._models: List[Dict[str, Any]] = []
        self._provider_health: List[Dict[str, Any]] = []
        self._last_refreshed_at: Optional[datetime.datetime] = None
        self._last_refresh_started_at: Optional[datetime.datetime] = None
        self._last_error: Optional[str] = None
        self._refreshing = False
        self._prime_from_config()

    def _prime_from_config(self):
        from core.provider_manager import build_model_catalog, load_providers

        providers = load_providers()
        models = build_model_catalog(providers)
        provider_health = [
            {
                "provider": provider.name,
                "type": provider.type,
                "base_url": provider.base_url,
                "auto_discover": provider.auto_discover,
                "available": None,
                "models": list(provider.models),
                "configured_models": list(provider.models),
                "model_count": len(provider.models),
                "last_checked_at": None,
            }
            for provider in providers
        ]

        with self._lock:
            self._models = models
            self._provider_health = provider_health

    def _utcnow(self) -> datetime.datetime:
        return datetime.datetime.utcnow()

    def _to_iso(self, value: Optional[datetime.datetime]) -> Optional[str]:
        if value is None:
            return None
        return value.isoformat() + "Z"

    def _is_stale_unlocked(self, now: Optional[datetime.datetime] = None) -> bool:
        if self._last_refreshed_at is None:
            return True
        now = now or self._utcnow()
        age = (now - self._last_refreshed_at).total_seconds()
        return age >= self.ttl_seconds

    def refresh_async(self, force: bool = False) -> bool:
        with self._lock:
            if self._refreshing:
                return False
            if not force and not self._is_stale_unlocked():
                return False
            self._refreshing = True
            self._last_refresh_started_at = self._utcnow()

        thread = threading.Thread(target=self._refresh_worker, daemon=True)
        thread.start()
        return True

    def _refresh_worker(self):
        try:
            from core.provider_manager import build_model_catalog, collect_provider_health, load_providers

            providers = load_providers()
            health = collect_provider_health(
                providers,
                timeout=self.probe_timeout_seconds,
            )
            resolved_models = {
                item["provider"]: item["models"]
                for item in health
                if item.get("models")
            }
            models = build_model_catalog(providers, resolved_models)
            checked_at = self._utcnow()
            provider_health = [
                {
                    **item,
                    "model_count": len(item.get("models", [])),
                    "last_checked_at": self._to_iso(checked_at),
                }
                for item in health
            ]

            with self._lock:
                self._models = models
                self._provider_health = provider_health
                self._last_refreshed_at = checked_at
                self._last_error = None
        except Exception as exc:
            with self._lock:
                self._last_error = str(exc)
        finally:
            with self._lock:
                self._refreshing = False

    def get_models(self) -> List[Dict[str, Any]]:
        self.refresh_async()
        with self._lock:
            return [dict(item) for item in self._models]

    def get_status(self) -> Dict[str, Any]:
        self.refresh_async()
        with self._lock:
            now = self._utcnow()
            age_seconds = None
            if self._last_refreshed_at is not None:
                age_seconds = max(0.0, (now - self._last_refreshed_at).total_seconds())

            return {
                "ttl_seconds": self.ttl_seconds,
                "probe_timeout_seconds": self.probe_timeout_seconds,
                "refreshing": self._refreshing,
                "stale": self._is_stale_unlocked(now),
                "last_refresh_started_at": self._to_iso(self._last_refresh_started_at),
                "last_refreshed_at": self._to_iso(self._last_refreshed_at),
                "age_seconds": age_seconds,
                "last_error": self._last_error,
                "model_count": len(self._models),
                "providers": [dict(item) for item in self._provider_health],
            }


model_catalog_cache = ModelCatalogCache(
    ttl_seconds=MODEL_CATALOG_TTL_SECONDS,
    probe_timeout_seconds=MODEL_CATALOG_PROBE_TIMEOUT_SECONDS,
)


@app.on_event("startup")
async def warm_model_catalog_cache():
    model_catalog_cache.refresh_async(force=True)

# ==================== 对话持久化存储 ====================

class ConversationStore:
    """SQLite-based conversation persistence"""

    def __init__(self, db_path: str = None):
        if db_path is None:
            cfg = get_config()
            os.makedirs(os.path.join(cfg.paths.data_dir, "sessions"), exist_ok=True)
            db_path = os.path.join(cfg.paths.data_dir, "sessions", "conversations.db")
        self.db_path = db_path
        self._lock = threading.Lock()
        self._init_db()

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._lock:
            conn = self._get_conn()
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    conversation_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    files TEXT DEFAULT '[]',
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_conversations_user ON conversations(user_id, updated_at DESC);
                CREATE INDEX IF NOT EXISTS idx_messages_conv ON messages(conversation_id, created_at ASC);
            """)
            conn.commit()
            conn.close()

    def create_conversation(self, user_id: str, title: str = "New Chat") -> Dict:
        now = datetime.datetime.utcnow().isoformat()
        conv_id = uuid.uuid4().hex[:16]
        with self._lock:
            conn = self._get_conn()
            conn.execute(
                "INSERT INTO conversations (id, user_id, title, created_at, updated_at) VALUES (?,?,?,?,?)",
                (conv_id, user_id, title, now, now)
            )
            conn.commit()
            conn.close()
        return {"id": conv_id, "user_id": user_id, "title": title, "created_at": now, "updated_at": now}

    def list_conversations(self, user_id: str) -> List[Dict]:
        with self._lock:
            conn = self._get_conn()
            rows = conn.execute(
                "SELECT id, title, created_at, updated_at FROM conversations WHERE user_id=? ORDER BY updated_at DESC",
                (user_id,)
            ).fetchall()
            conn.close()
        return [dict(r) for r in rows]

    def get_conversation(self, conv_id: str, user_id: str) -> Optional[Dict]:
        with self._lock:
            conn = self._get_conn()
            row = conn.execute(
                "SELECT * FROM conversations WHERE id=? AND user_id=?",
                (conv_id, user_id)
            ).fetchone()
            if not row:
                conn.close()
                return None
            msgs = conn.execute(
                "SELECT role, content, files, created_at FROM messages WHERE conversation_id=? ORDER BY created_at ASC",
                (conv_id,)
            ).fetchall()
            conn.close()
        return {
            **dict(row),
            "messages": [
                {"role": m["role"], "content": m["content"], "files": json.loads(m["files"] or "[]"), "created_at": m["created_at"]}
                for m in msgs
            ]
        }

    def add_message(self, conv_id: str, role: str, content: str, files: List[str] = None):
        now = datetime.datetime.utcnow().isoformat()
        msg_id = uuid.uuid4().hex
        with self._lock:
            conn = self._get_conn()
            conn.execute(
                "INSERT INTO messages (id, conversation_id, role, content, files, created_at) VALUES (?,?,?,?,?,?)",
                (msg_id, conv_id, role, content, json.dumps(files or []), now)
            )
            conn.execute(
                "UPDATE conversations SET updated_at=? WHERE id=?",
                (now, conv_id)
            )
            conn.commit()
            conn.close()

    def update_title(self, conv_id: str, user_id: str, title: str):
        with self._lock:
            conn = self._get_conn()
            conn.execute(
                "UPDATE conversations SET title=? WHERE id=? AND user_id=?",
                (title, conv_id, user_id)
            )
            conn.commit()
            conn.close()

    def delete_conversation(self, conv_id: str, user_id: str) -> bool:
        with self._lock:
            conn = self._get_conn()
            cur = conn.execute(
                "DELETE FROM conversations WHERE id=? AND user_id=?",
                (conv_id, user_id)
            )
            deleted = cur.rowcount > 0
            conn.commit()
            conn.close()
        return deleted


# 全局对话存储实例
_conv_store = ConversationStore()

# Agent 实例缓存 (conversation_id -> FluAgent)
_agent_cache: Dict[str, FluAgent] = {}

def get_agent_for_conversation(conv_id: str, model: str = None, history: List[Dict] = None) -> FluAgent:
    """获取或创建对话专属 Agent，并注入历史消息"""
    if conv_id not in _agent_cache:
        agent = FluAgent(session_id=conv_id, model=model)
        if history:
            agent.conversation_history = [
                {"role": m["role"], "content": m["content"]}
                for m in history
            ]
        _agent_cache[conv_id] = agent
    elif model and _agent_cache[conv_id].model != model:
        agent = FluAgent(session_id=conv_id, model=model)
        _agent_cache[conv_id] = agent
    return _agent_cache[conv_id]


# ==================== 认证接口 ====================

@app.post("/api/auth/register", tags=["认证"])
async def register(req: RegisterRequest):
    """用户注册"""
    # 检查用户名是否已存在
    for user in _users_db.values():
        if user["username"] == req.username:
            raise HTTPException(status_code=400, detail="用户名已存在")

    user_id = hashlib.md5(str(uuid.uuid4()).encode()).hexdigest()[:12]
    user = {
        "user_id": user_id,
        "username": req.username,
        "password_hash": UserAuth.hash_password(req.password),
        "created_at": datetime.datetime.now().isoformat(),
    }
    _users_db[user_id] = user

    return {"user_id": user_id, "username": req.username}


@app.post("/api/auth/login", tags=["认证"])
async def login(req: LoginRequest):
    """用户登录"""
    # 查找用户
    user = None
    for u in _users_db.values():
        if u["username"] == req.username:
            user = u
            break

    if not user or not UserAuth.verify_password(req.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    token = UserAuth.create_token(user["user_id"], user["username"])

    return {
        "token": token,
        "user_id": user["user_id"],
        "username": user["username"],
    }


# ==================== 工具与模型接口 ====================

@app.get("/api/health")
async def health_check():
    return {"status": "ok", "version": "3.0.0"}


@app.get("/api/models")
async def get_models():
    return model_catalog_cache.get_models()


@app.get("/api/models/health", dependencies=[Depends(get_current_user)])
async def get_models_health():
    return model_catalog_cache.get_status()


@app.post("/api/models/refresh", dependencies=[Depends(get_current_user)])
async def refresh_models_catalog():
    started = model_catalog_cache.refresh_async(force=True)
    status = model_catalog_cache.get_status()
    return {
        "refresh_started": started,
        **status,
    }


@app.get("/api/tools", dependencies=[Depends(get_current_user)])
async def get_tools():
    try:
        from tools import discover_and_register_tools
        discover_and_register_tools()
        from tools.base import ToolRegistry
        tools = ToolRegistry.list_tools()
        return [{"name": t.name, "description": t.description} for t in tools]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 文件上传接口 ====================

@app.post("/api/upload", dependencies=[Depends(get_current_user)])
async def upload_files(
    files: List[UploadFile] = File(...),
    current_user: Dict = Depends(get_current_user),
):
    """文件上传（带用户隔离，路径稳定）"""
    user_id = current_user["user_id"]
    
    # 使用稳定的用户目录，不使用随机会话 UUID
    upload_dir = os.path.join(get_config().paths.data_dir, "uploads", user_id)
    os.makedirs(upload_dir, exist_ok=True)

    uploaded_files = []
    for file in files:
        safe_filename = os.path.basename(file.filename)
        dest_path = os.path.normpath(os.path.join(upload_dir, safe_filename))

        with open(dest_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)

        uploaded_files.append({
            "filename": safe_filename,
            "path": dest_path,
            "size": len(content),
            "user_id": user_id,
        })

    return {
        "message": f"Successfully uploaded {len(files)} files",
        "files": uploaded_files,
    }


# ==================== 聊天接口 ====================

@app.post("/api/chat", dependencies=[Depends(get_current_user)])
async def chat(
    payload: ChatRequest = Body(...),
    current_user: Dict = Depends(get_current_user),
):
    """聊天接口（支持上下文注入和状态保持）"""
    message = payload.message
    if not message:
        raise HTTPException(status_code=400, detail="Message is required")

    user_id = current_user["user_id"]
    conv_id = payload.conversation_id

    # 获取或创建对话
    if conv_id:
        conv = _conv_store.get_conversation(conv_id, user_id)
        if not conv:
            raise HTTPException(status_code=404, detail="对话不存在")
        history = conv["messages"]
    else:
        # 用第一条消息前20字作为标题
        title = message[:20] + ("..." if len(message) > 20 else "")
        conv = _conv_store.create_conversation(user_id, title)
        conv_id = conv["id"]
        history = []

    agent = get_agent_for_conversation(conv_id, model=payload.model, history=history)

    # 注入已上传文件上下文
    full_prompt = message
    if payload.files:
        files_list = "\n".join([f"- {f}" for f in payload.files])
        full_prompt = f"用户当前已上传/选好的文件列表如下：\n{files_list}\n\n用户问题：{message}"

    # 保存用户消息
    _conv_store.add_message(conv_id, "user", message, payload.files or [])

    result = agent.chat(full_prompt)

    # 保存 AI 回复
    _conv_store.add_message(conv_id, "assistant", result)

    return {"result": result, "user_id": user_id, "conversation_id": conv_id}


@app.post("/api/chat/stream", dependencies=[Depends(get_current_user)])
async def chat_stream(
    payload: ChatRequest = Body(...),
    current_user: Dict = Depends(get_current_user),
):
    """流式聊天接口（支持上下文注入和状态保持）"""
    message = payload.message
    if not message:
        raise HTTPException(status_code=400, detail="Message is required")

    user_id = current_user["user_id"]
    conv_id = payload.conversation_id

    # 获取或创建对话
    if conv_id:
        conv = _conv_store.get_conversation(conv_id, user_id)
        if not conv:
            raise HTTPException(status_code=404, detail="对话不存在")
        history = conv["messages"]
    else:
        title = message[:20] + ("..." if len(message) > 20 else "")
        conv = _conv_store.create_conversation(user_id, title)
        conv_id = conv["id"]
        history = []

    agent = get_agent_for_conversation(conv_id, model=payload.model, history=history)

    # 注入已上传文件上下文
    full_prompt = message
    if payload.files:
        files_list = "\n".join([f"- {f}" for f in payload.files])
        full_prompt = f"用户当前已上传/选好的文件列表如下：\n{files_list}\n\n用户问题：{message}"

    # 保存用户消息
    _conv_store.add_message(conv_id, "user", message, payload.files or [])

    full_response = ""

    async def event_generator():
        nonlocal full_response
        # 首先以 JSON 头部发送 conversation_id，让前端知道对话 ID
        yield f"__CONV_ID__:{conv_id}\n"
        try:
            async for chunk in agent.chat_stream(full_prompt):
                full_response += chunk
                yield chunk
        except Exception as e:
            yield f"Error: {str(e)}"
        finally:
            # 流结束后持久化 AI 回复
            if full_response:
                _conv_store.add_message(conv_id, "assistant", full_response)

    return StreamingResponse(event_generator(), media_type="text/plain")


# ==================== 对话管理接口 ====================

@app.get("/api/conversations", dependencies=[Depends(get_current_user)])
async def list_conversations(current_user: Dict = Depends(get_current_user)):
    """列出当前用户所有对话"""
    user_id = current_user["user_id"]
    convs = _conv_store.list_conversations(user_id)
    return {"conversations": convs}


@app.post("/api/conversations", dependencies=[Depends(get_current_user)])
async def create_conversation(
    req: ConversationCreateRequest = Body(default=ConversationCreateRequest()),
    current_user: Dict = Depends(get_current_user)
):
    """创建新对话"""
    user_id = current_user["user_id"]
    title = req.title or "New Chat"
    conv = _conv_store.create_conversation(user_id, title)
    return conv


@app.get("/api/conversations/{conv_id}", dependencies=[Depends(get_current_user)])
async def get_conversation(
    conv_id: str,
    current_user: Dict = Depends(get_current_user)
):
    """获取对话详情及消息历史"""
    user_id = current_user["user_id"]
    conv = _conv_store.get_conversation(conv_id, user_id)
    if not conv:
        raise HTTPException(status_code=404, detail="对话不存在")
    return conv


@app.delete("/api/conversations/{conv_id}", dependencies=[Depends(get_current_user)])
async def delete_conversation(
    conv_id: str,
    current_user: Dict = Depends(get_current_user)
):
    """删除对话"""
    user_id = current_user["user_id"]
    ok = _conv_store.delete_conversation(conv_id, user_id)
    if not ok:
        raise HTTPException(status_code=404, detail="对话不存在")
    # 同时清理内存中的 agent
    _agent_cache.pop(conv_id, None)
    return {"success": True}


@app.patch("/api/conversations/{conv_id}/title", dependencies=[Depends(get_current_user)])
async def update_conversation_title(
    conv_id: str,
    body: Dict = Body(...),
    current_user: Dict = Depends(get_current_user)
):
    """更新对话标题"""
    user_id = current_user["user_id"]
    title = body.get("title", "")
    if not title.strip():
        raise HTTPException(status_code=400, detail="标题不能为空")
    _conv_store.update_title(conv_id, user_id, title)
    return {"success": True}



# ==================== 异步任务接口 ====================

@app.post("/api/tasks/submit", dependencies=[Depends(get_current_user)])
async def submit_task(
    req: TaskSubmitRequest,
    current_user: Dict = Depends(get_current_user),
):
    """提交异步任务"""
    user_id = current_user["user_id"]
    session_id = current_user.get("session_id")

    task_id = task_queue.submit(
        task_type=req.task_type,
        args=tuple(req.args) if req.args else (),
        kwargs=req.kwargs or {},
        user_id=user_id,
        session_id=session_id,
    )

    return {
        "task_id": task_id,
        "status": "pending",
        "message": "任务已提交",
    }


@app.get("/api/tasks/{task_id}", dependencies=[Depends(get_current_user)])
async def get_task_status(
    task_id: str,
    current_user: Dict = Depends(get_current_user),
):
    """获取任务状态"""
    task = task_queue.get_status(task_id)

    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    # 权限校验：只能查看自己的任务
    if task.result and task.result.get("user_id") != current_user["user_id"]:
        raise HTTPException(status_code=403, detail="无权访问此任务")

    return {
        "task_id": task.task_id,
        "task_type": task.task_type,
        "status": task.status,
        "progress": task.progress,
        "created_at": task.created_at,
        "started_at": task.started_at,
        "completed_at": task.completed_at,
        "result": task.result,
        "error": task.error,
    }


@app.get("/api/tasks", dependencies=[Depends(get_current_user)])
async def list_tasks(
    status: str = None,
    limit: int = 100,
    current_user: Dict = Depends(get_current_user),
):
    """列出用户任务"""
    user_id = current_user["user_id"]
    tasks = task_queue.list_tasks(user_id=user_id, status=status, limit=limit)

    return {
        "tasks": [
            {
                "task_id": t.task_id,
                "task_type": t.task_type,
                "status": t.status,
                "progress": t.progress,
                "created_at": t.created_at,
            }
            for t in tasks
        ],
        "total": len(tasks),
    }


@app.post("/api/tasks/{task_id}/cancel", dependencies=[Depends(get_current_user)])
async def cancel_task(
    task_id: str,
    current_user: Dict = Depends(get_current_user),
):
    """取消任务"""
    task = task_queue.get_status(task_id)

    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    if task.result and task.result.get("user_id") != current_user["user_id"]:
        raise HTTPException(status_code=403, detail="无权操作此任务")

    success = task_queue.cancel(task_id)
    return {"success": success, "message": "任务已取消" if success else "任务无法取消"}


# ==================== 会话管理接口 ====================

@app.get("/api/sessions", dependencies=[Depends(get_current_user)])
async def list_sessions(current_user: Dict = Depends(get_current_user)):
    """列出用户的所有会话"""
    user_id = current_user["user_id"]
    sessions = session_manager.list_user_sessions(user_id)

    return {
        "sessions": [
            {
                "session_id": s.session_id,
                "created_at": s.created_at.isoformat(),
                "last_active": s.last_active.isoformat(),
                "data_dir": s.data_dir,
            }
            for s in sessions
        ]
    }


@app.post("/api/sessions/create", dependencies=[Depends(get_current_user)])
async def create_session(current_user: Dict = Depends(get_current_user)):
    """创建新会话"""
    user_id = current_user["user_id"]
    session = session_manager.create_session(user_id)

    return {
        "session_id": session.session_id,
        "data_dir": session.data_dir,
    }


# ==================== 权限校验工具函数 ====================

def validate_file_access(session_id: str, file_path: str) -> bool:
    """验证文件访问权限（防止路径穿越）"""
    return session_manager.validate_path(session_id, file_path)


# ==================== 启动 ====================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
