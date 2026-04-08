"""
Memory 模块 - 会话记忆管理
支持短期记忆和 SQLite 持久化
"""
import json
import sqlite3
import os
from datetime import datetime
from typing import List, Dict, Optional
from dataclasses import dataclass, field, asdict
import uuid


@dataclass
class Message:
    """单条消息"""
    role: str  # "user" | "assistant" | "system"
    content: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    tool_calls: Optional[List[Dict]] = None


@dataclass
class Session:
    """会话"""
    session_id: str
    created_at: str
    updated_at: str
    messages: List[Message] = field(default_factory=list)
    metadata: Dict = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "session_id": self.session_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "messages": [asdict(m) for m in self.messages],
            "metadata": self.metadata,
        }


class Memory:
    """
    记忆管理器
    - 短期记忆：当前会话的消息列表
    - 长期记忆：SQLite 数据库持久化
    """
    
    def __init__(self, db_path: str = "data/sessions/fluagent.db"):
        self.db_path = db_path
        self._init_db()
        
        # 当前会话
        self.current_session: Optional[Session] = None
        self.short_term_memory: List[Message] = []
    
    def _init_db(self):
        """初始化数据库"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                metadata TEXT
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                tool_calls TEXT,
                FOREIGN KEY (session_id) REFERENCES sessions(session_id)
            )
        """)
        
        # 用户画像表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_profiles (
                user_id TEXT PRIMARY KEY,
                name TEXT,
                preferences TEXT,  -- JSON: 工具偏好、分析类型偏好等
                history TEXT,      -- JSON: 历史任务类型统计
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        
        # 工具使用统计表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tool_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tool_name TEXT NOT NULL,
                session_id TEXT NOT NULL,
                success INTEGER DEFAULT 1,
                duration REAL,
                timestamp TEXT NOT NULL
            )
        """)

        # 用户反馈表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                user_id TEXT,
                message_index INTEGER,
                rating INTEGER,
                comment TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (session_id) REFERENCES sessions(session_id)
            )
        """)

        conn.commit()
        conn.close()
    
    def create_session(self, session_id: Optional[str] = None, metadata: Dict = None) -> Session:
        """创建新会话"""
        now = datetime.now().isoformat()
        session_id = session_id or str(uuid.uuid4())
        
        session = Session(
            session_id=session_id,
            created_at=now,
            updated_at=now,
            messages=[],
            metadata=metadata or {}
        )
        
        # 保存到数据库
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            "INSERT INTO sessions (session_id, created_at, updated_at, metadata) VALUES (?, ?, ?, ?)",
            (session_id, now, now, json.dumps(session.metadata))
        )
        
        conn.commit()
        conn.close()
        
        self.current_session = session
        self.short_term_memory = []
        
        return session
    
    def load_session(self, session_id: str) -> Optional[Session]:
        """加载会话"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 获取会话信息
        cursor.execute(
            "SELECT session_id, created_at, updated_at, metadata FROM sessions WHERE session_id = ?",
            (session_id,)
        )
        row = cursor.fetchone()
        
        if not row:
            conn.close()
            return None
        
        session_id, created_at, updated_at, metadata_json = row
        metadata = json.loads(metadata_json or "{}")
        
        # 获取消息
        cursor.execute(
            "SELECT role, content, timestamp, tool_calls FROM messages WHERE session_id = ? ORDER BY id",
            (session_id,)
        )
        
        messages = []
        for role, content, timestamp, tool_calls_json in cursor.fetchall():
            tool_calls = json.loads(tool_calls_json) if tool_calls_json else None
            messages.append(Message(
                role=role,
                content=content,
                timestamp=timestamp,
                tool_calls=tool_calls
            ))
        
        conn.close()
        
        session = Session(
            session_id=session_id,
            created_at=created_at,
            updated_at=updated_at,
            messages=messages,
            metadata=metadata
        )
        
        self.current_session = session
        self.short_term_memory = messages.copy()
        
        return session
    
    def save_message(self, role: str, content: str, tool_calls: Optional[List[Dict]] = None):
        """保存消息"""
        now = datetime.now().isoformat()
        
        message = Message(
            role=role,
            content=content,
            timestamp=now,
            tool_calls=tool_calls
        )
        
        # 添加到短期记忆
        self.short_term_memory.append(message)
        
        # 如果有当前会话，保存到数据库
        if self.current_session:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute(
                "INSERT INTO messages (session_id, role, content, timestamp, tool_calls) VALUES (?, ?, ?, ?, ?)",
                (
                    self.current_session.session_id,
                    role,
                    content,
                    now,
                    json.dumps(tool_calls) if tool_calls else None
                )
            )
            
            # 更新会话时间
            cursor.execute(
                "UPDATE sessions SET updated_at = ? WHERE session_id = ?",
                (now, self.current_session.session_id)
            )
            
            conn.commit()
            conn.close()
            
            self.current_session.messages.append(message)
    
    def get_recent_messages(self, n: int = 10) -> List[Message]:
        """获取最近 N 条消息"""
        return self.short_term_memory[-n:]
    
    def clear_short_term(self):
        """清除短期记忆"""
        self.short_term_memory = []
    
    def list_sessions(self, limit: int = 20) -> List[Dict]:
        """列出最近会话"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT session_id, created_at, updated_at, metadata FROM sessions ORDER BY updated_at DESC LIMIT ?",
            (limit,)
        )
        
        sessions = []
        for session_id, created_at, updated_at, metadata_json in cursor.fetchall():
            sessions.append({
                "session_id": session_id,
                "created_at": created_at,
                "updated_at": updated_at,
                "metadata": json.loads(metadata_json or "{}")
            })
        
        conn.close()
        return sessions
    
    def delete_session(self, session_id: str):
        """删除会话"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
        cursor.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
        
        conn.commit()
        conn.close()
        
        if self.current_session and self.current_session.session_id == session_id:
            self.current_session = None
            self.short_term_memory = []
    
    # ========== 用户画像方法 ==========
    
    def save_user_profile(self, user_id: str, name: str = None, preferences: Dict = None):
        """保存用户画像"""
        now = datetime.now().isoformat()
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT OR REPLACE INTO user_profiles 
            (user_id, name, preferences, history, created_at, updated_at)
            VALUES (?, ?, ?, ?, COALESCE((SELECT created_at FROM user_profiles WHERE user_id = ?), ?), ?)
        """, (
            user_id,
            name,
            json.dumps(preferences or {}),
            json.dumps({}),
            user_id,
            now,
            now
        ))
        
        conn.commit()
        conn.close()
    
    def load_user_profile(self, user_id: str) -> Optional[Dict]:
        """加载用户画像"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT user_id, name, preferences, history, created_at, updated_at FROM user_profiles WHERE user_id = ?",
            (user_id,)
        )
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
        return {
            "user_id": row[0],
            "name": row[1],
            "preferences": json.loads(row[2] or "{}"),
            "history": json.loads(row[3] or "{}"),
            "created_at": row[4],
            "updated_at": row[5],
        }
    
    def update_user_preferences(self, user_id: str, preferences: Dict):
        """更新用户偏好"""
        now = datetime.now().isoformat()
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 先获取现有偏好
        cursor.execute("SELECT preferences FROM user_profiles WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        
        if row:
            existing = json.loads(row[0] or "{}")
            existing.update(preferences)
            new_preferences = json.dumps(existing)
        else:
            new_preferences = json.dumps(preferences)
        
        cursor.execute(
            "UPDATE user_profiles SET preferences = ?, updated_at = ? WHERE user_id = ?",
            (new_preferences, now, user_id)
        )
        
        conn.commit()
        conn.close()
    
    def record_tool_usage(self, tool_name: str, session_id: str, success: bool = True, duration: float = None):
        """记录工具使用"""
        now = datetime.now().isoformat()
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO tool_usage (tool_name, session_id, success, duration, timestamp)
            VALUES (?, ?, ?, ?, ?)
        """, (tool_name, session_id, 1 if success else 0, duration, now))
        
        conn.commit()
        conn.close()
    
    def get_tool_usage_stats(self, tool_name: str = None, days: int = 30) -> Dict:
        """获取工具使用统计"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if tool_name:
            cursor.execute("""
                SELECT tool_name, 
                       COUNT(*) as total,
                       SUM(success) as success_count,
                       AVG(duration) as avg_duration
                FROM tool_usage 
                WHERE tool_name = ? AND timestamp > datetime('now', '-' || ? || ' days')
                GROUP BY tool_name
            """, (tool_name, days))
            row = cursor.fetchone()
            conn.close()
            
            if not row:
                return {"tool_name": tool_name, "total": 0, "success_rate": 0.0}
            
            return {
                "tool_name": row[0],
                "total": row[1],
                "success_count": row[2] or 0,
                "success_rate": (row[2] or 0) / row[1] if row[1] > 0 else 0,
                "avg_duration": row[3] or 0,
            }
        else:
            cursor.execute("""
                SELECT tool_name, COUNT(*) as total, SUM(success) as success_count
                FROM tool_usage 
                WHERE timestamp > datetime('now', '-' || ? || ' days')
                GROUP BY tool_name
                ORDER BY total DESC
                LIMIT 10
            """, (days,))
            
            results = []
            for row in cursor.fetchall():
                results.append({
                    "tool_name": row[0],
                    "total": row[1],
                    "success_count": row[2] or 0,
                    "success_rate": (row[2] or 0) / row[1] if row[1] > 0 else 0,
                })
            
            conn.close()
            return {"top_tools": results, "period_days": days}

    # ========== 反馈管理方法 ==========

    def save_feedback(self, session_id: str, user_id: str, message_index: int,
                      rating: int, comment: str = None) -> bool:
        """保存用户反馈"""
        now = datetime.now().isoformat()

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute("""
                INSERT INTO feedback (session_id, user_id, message_index, rating, comment, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (session_id, user_id, message_index, rating, comment, now))
            conn.commit()
            return True
        except Exception as e:
            print(f"[FluAgent] 保存反馈失败: {e}")
            return False
        finally:
            conn.close()

    def get_user_sessions(self, user_id: str, limit: int = 20) -> List[Dict]:
        """获取指定用户的所有会话"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT s.session_id, s.created_at, s.updated_at, s.metadata,
                   COUNT(m.id) as message_count
            FROM sessions s
            LEFT JOIN messages m ON s.session_id = m.session_id
            WHERE s.metadata LIKE ?
            GROUP BY s.session_id
            ORDER BY s.updated_at DESC
            LIMIT ?
        """, (f'%\"user_id\": \"{user_id}\"%', limit))

        sessions = []
        for row in cursor.fetchall():
            sessions.append({
                "session_id": row[0],
                "created_at": row[1],
                "updated_at": row[2],
                "metadata": json.loads(row[3] or "{}"),
                "message_count": row[4],
            })

        conn.close()
        return sessions

    def list_user_sessions(self, user_id: str, limit: int = 20) -> List[Dict]:
        """获取用户会话列表（按更新时间倒序）"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT session_id, created_at, updated_at, metadata
            FROM sessions
            ORDER BY updated_at DESC
            LIMIT ?
        """, (limit,))

        sessions = []
        for row in cursor.fetchall():
            sessions.append({
                "session_id": row[0],
                "created_at": row[1],
                "updated_at": row[2],
                "metadata": json.loads(row[3] or "{}"),
            })

        conn.close()
        return sessions

    def get_feedback_stats(self, days: int = 30) -> Dict:
        """获取反馈统计"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                COUNT(*) as total,
                AVG(rating) as avg_rating,
                SUM(CASE WHEN rating >= 4 THEN 1 ELSE 0 END) as positive,
                SUM(CASE WHEN rating <= 2 THEN 1 ELSE 0 END) as negative
            FROM feedback
            WHERE created_at > datetime('now', '-' || ? || ' days')
        """, (days,))

        row = cursor.fetchone()
        conn.close()

        return {
            "total": row[0] or 0,
            "avg_rating": round(row[1], 2) if row[1] else 0,
            "positive_count": row[2] or 0,
            "negative_count": row[3] or 0,
            "period_days": days,
        }

