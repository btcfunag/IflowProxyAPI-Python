"""
简化版 URL 登录模块 - 适用于 Kivy 安卓应用（优化版）

使用方式：
    # 在 Kivy 应用中
    from app.iflow.simplified_login import create_login_session
    
    result = create_login_session()  # 返回 session_id 和 login_url
    # result = {"session_id": "...", "login_url": "...", "expires_in": 600}
"""

import json
import secrets
import threading
import time
import sys
import sqlite3  # 添加 sqlite3 导入
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from pathlib import Path
from urllib.parse import urlencode

# 尝试相对导入，如果失败则使用独立的日志和配置
try:
    from ..logger import logger
    from ..settings import DATA_DIR
    from .auth import (
        IFLOW_OAUTH_AUTHORIZE_ENDPOINT,
        IFLOW_OAUTH_CLIENT_ID,
        IFLOW_CALLBACK_PORT,
    )
    _USE_RELATIVE_IMPORT = True
except ImportError:
    _USE_RELATIVE_IMPORT = False
    
    class SimpleLogger:
        def __init__(self):
            self.log_file = None
        
        def info(self, msg):
            print(f"[INFO] {msg}", flush=True)
            self._write_log("INFO", msg)
        
        def error(self, msg):
            print(f"[ERROR] {msg}", flush=True)
            self._write_log("ERROR", msg)
        
        def warning(self, msg):
            print(f"[WARNING] {msg}", flush=True)
            self._write_log("WARNING", msg)
        
        def debug(self, msg):
            print(f"[DEBUG] {msg}", flush=True)
            self._write_log("DEBUG", msg)
        
        def _write_log(self, level, msg):
            """写入日志到文件"""
            try:
                if self.log_file is None:
                    log_dir = Path("/storage/emulated/0/000CLIProxyAPI-Python/logs")
                    log_dir.mkdir(parents=True, exist_ok=True)
                    self.log_file = str(log_dir / "simplified_login.log")
                
                with open(self.log_file, "a", encoding="utf-8") as f:
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    f.write(f"{timestamp} | {level: <8} | {msg}\n")
            except Exception:
                pass
    
    logger = SimpleLogger()
    DATA_DIR = Path("/storage/emulated/0/000CLIProxyAPI-Python/data")
    
    # 默认配置
    IFLOW_OAUTH_AUTHORIZE_ENDPOINT = "https://iflow.cn/oauth"
    IFLOW_OAUTH_CLIENT_ID = "10009311001"
    IFLOW_CALLBACK_PORT = 11451

# 配置
DEFAULT_SERVER_URL = "http://localhost:8000"
SESSION_EXPIRE_SECONDS = 1800  # 30分钟（原来600秒只有10分钟）


# ============ SQLite 会话存储 ============

class SessionDatabase:
    """SQLite 会话数据库 - 持久化存储登录会话"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self.db_path = DATA_DIR / "simplified_login_sessions.db"
        self._init_db()
        self._initialized = True
    
    def _init_db(self):
        """初始化数据库"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS login_sessions (
                        session_id TEXT PRIMARY KEY,
                        status TEXT DEFAULT 'pending',
                        email TEXT,
                        api_key TEXT,
                        auth_data TEXT,
                        server_url TEXT,
                        created_at TEXT,
                        expire_at TEXT
                    )
                """)
                # 创建索引
                conn.execute("CREATE INDEX IF NOT EXISTS idx_expire_at ON login_sessions(expire_at)")
                conn.commit()
            logger.info(f"会话数据库初始化完成: {self.db_path}")
        except Exception as e:
            logger.error(f"初始化会话数据库失败: {e}")
    
    def create_session(self, session_id: str, server_url: str = "") -> bool:
        """创建新的登录会话"""
        try:
            now = datetime.now()
            expire_at = now + timedelta(seconds=SESSION_EXPIRE_SECONDS)
            
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT INTO login_sessions 
                    (session_id, status, server_url, created_at, expire_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (session_id, "pending", server_url, now.isoformat(), expire_at.isoformat()))
                
                conn.commit()
                logger.debug(f"创建会话: {session_id}")
                return True
        except Exception as e:
            logger.error(f"创建会话失败: {e}")
            return False
    
    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """获取会话信息"""
        try:
            # 先清理过期会话
            self._cleanup_expired()
            
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("""
                    SELECT * FROM login_sessions WHERE session_id = ?
                """, (session_id,))
                
                row = cursor.fetchone()
                if row:
                    auth_data = {}
                    if row['auth_data']:
                        try:
                            auth_data = json.loads(row['auth_data'])
                        except:
                            pass
                    
                    return {
                        "session_id": row['session_id'],
                        "status": row['status'],
                        "email": row['email'],
                        "api_key": row['api_key'],
                        "auth_data": auth_data,
                        "server_url": row['server_url'],
                        "created_at": row['created_at'],
                        "expire_at": row['expire_at'],
                    }
                return None
        except Exception as e:
            logger.error(f"获取会话失败: {e}")
            return None
    
    def complete_session(
        self,
        session_id: str,
        email: str,
        api_key: str,
        auth_data: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """完成登录会话"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    UPDATE login_sessions 
                    SET status = 'completed', email = ?, api_key = ?, auth_data = ?
                    WHERE session_id = ?
                """, (email, api_key, json.dumps(auth_data or {}), session_id))
                
                conn.commit()
                logger.info(f"登录会话完成: {session_id}, {email}")
                return conn.total_changes > 0
        except Exception as e:
            logger.error(f"完成会话失败: {e}")
            return False
    
    def fail_session(self, session_id: str, reason: str = "") -> bool:
        """标记登录会话失败"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    UPDATE login_sessions 
                    SET status = 'failed', auth_data = ?
                    WHERE session_id = ?
                """, (json.dumps({"error": reason}), session_id))
                
                conn.commit()
                logger.info(f"登录会话失败: {session_id}, reason: {reason}")
                return conn.total_changes > 0
        except Exception as e:
            logger.error(f"标记会话失败: {e}")
            return False
    
    def get_status(self, session_id: str) -> Dict[str, Any]:
        """获取登录状态"""
        session = self.get_session(session_id)
        
        if not session:
            return {"status": "not_found"}
        
        if session["status"] == "completed":
            result = {
                "status": "completed",
                "email": session["email"],
                "api_key": session["api_key"],
            }
            result.update(session.get("auth_data", {}))
            return result
        
        if session["status"] == "failed":
            return {
                "status": "failed",
                "message": session.get("auth_data", {}).get("error", "登录失败"),
            }
        
        # 计算剩余时间
        try:
            expire_at = datetime.fromisoformat(session["expire_at"])
            expires_in = int((expire_at - datetime.now()).total_seconds())
            return {"status": "pending", "expires_in": max(0, expires_in)}
        except:
            return {"status": "pending", "expires_in": SESSION_EXPIRE_SECONDS}
    
    def _cleanup_expired(self):
        """清理过期的会话"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    DELETE FROM login_sessions WHERE expire_at < ?
                """, (datetime.now().isoformat(),))
                
                conn.commit()
        except Exception as e:
            logger.error(f"清理过期会话失败: {e}")


# 内存缓存（用于快速访问，同时有 SQLite 持久化）
_session_cache: Dict[str, Dict[str, Any]] = {}
_cache_lock = threading.Lock()


class LoginSession:
    """登录会话类（保留用于内存缓存兼容）"""
    
    def __init__(
        self,
        session_id: str,
        status: str = "pending",
        email: str = "",
        api_key: str = "",
        expire_at: Optional[datetime] = None,
        auth_data: Optional[Dict[str, Any]] = None,
    ):
        self.session_id = session_id
        self.status = status
        self.email = email
        self.api_key = api_key
        self.expire_at = expire_at or datetime.now() + timedelta(seconds=SESSION_EXPIRE_SECONDS)
        self.auth_data = auth_data or {}
    
    def is_expired(self) -> bool:
        return datetime.now() > self.expire_at
    
    def is_completed(self) -> bool:
        return self.status == "completed"
    
    def is_failed(self) -> bool:
        return self.status == "failed"


class LoginStatusManager:
    """登录状态管理器 - 使用 SQLite 持久化存储"""
    
    _db: Optional[SessionDatabase] = None
    
    @classmethod
    def _get_db(cls) -> SessionDatabase:
        """获取数据库实例"""
        if cls._db is None:
            cls._db = SessionDatabase()
        return cls._db
    
    @classmethod
    def create_session(cls, state: str, server_url: str = "") -> LoginSession:
        """创建新的登录会话（同时存储到 SQLite 和内存缓存）"""
        # 清理过期的会话
        cls._cleanup()
        
        # 创建会话
        session = LoginSession(session_id=state)
        
        # 保存到 SQLite
        db = cls._get_db()
        db.create_session(state, server_url)
        
        # 保存到内存缓存
        with _cache_lock:
            _session_cache[state] = {
                "status": "pending",
                "expire_at": session.expire_at,
            }
        
        print(f"[INFO] 创建登录会话: {state}", flush=True)
        logger.info(f"创建登录会话: {state}")
        return session
    
    @classmethod
    def get_session(cls, session_id: str) -> Optional[LoginSession]:
        """获取会话（优先从内存缓存读取）"""
        # 先检查内存缓存
        with _cache_lock:
            cached = _session_cache.get(session_id)
            if cached and datetime.now() > cached["expire_at"]:
                # 缓存已过期，删除
                del _session_cache[session_id]
                cached = None
        
        if cached is None:
            # 从 SQLite 读取
            db = cls._get_db()
            session_data = db.get_session(session_id)
            
            if session_data is None:
                return None
            
            # 恢复到内存缓存
            with _cache_lock:
                _session_cache[session_id] = {
                    "status": session_data["status"],
                    "expire_at": datetime.fromisoformat(session_data["expire_at"]),
                }
            
            return LoginSession(
                session_id=session_data["session_id"],
                status=session_data["status"],
                email=session_data.get("email", ""),
                api_key=session_data.get("api_key", ""),
                expire_at=datetime.fromisoformat(session_data["expire_at"]),
                auth_data=session_data.get("auth_data", {}),
            )
        
        # 从缓存创建会话对象
        return LoginSession(
            session_id=session_id,
            status=cached["status"],
            expire_at=cached["expire_at"],
        )
    
    @classmethod
    def complete_session(
        cls,
        session_id: str,
        email: str,
        api_key: str,
        auth_data: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """完成登录会话"""
        db = cls._get_db()
        success = db.complete_session(session_id, email, api_key, auth_data)
        
        if success:
            with _cache_lock:
                if session_id in _session_cache:
                    _session_cache[session_id]["status"] = "completed"
            
            print(f"[INFO] 登录会话完成: {session_id}, {email}", flush=True)
            logger.info(f"登录会话完成: {session_id}, {email}")
        
        return success
    
    @classmethod
    def fail_session(cls, session_id: str, reason: str = "") -> bool:
        """标记登录会话失败"""
        db = cls._get_db()
        success = db.fail_session(session_id, reason)
        
        if success:
            with _cache_lock:
                if session_id in _session_cache:
                    _session_cache[session_id]["status"] = "failed"
            
            print(f"[INFO] 登录会话失败: {session_id}, reason: {reason}", flush=True)
            logger.info(f"登录会话失败: {session_id}, reason: {reason}")
        
        return success
    
    @classmethod
    def get_status(cls, session_id: str) -> Dict[str, Any]:
        """获取登录状态"""
        db = cls._get_db()
        return db.get_status(session_id)
    
    @classmethod
    def _cleanup(cls):
        """清理过期的会话"""
        db = cls._get_db()
        db._cleanup_expired()


# 为了调试，打印当前所有会话
def print_all_sessions():
    """打印当前所有会话（用于调试）"""
    db = SessionDatabase()
    
    try:
        with sqlite3.connect(db.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT session_id, status, created_at, expire_at 
                FROM login_sessions 
                ORDER BY created_at DESC
                LIMIT 20
            """)
            
            sessions = cursor.fetchall()
            
            print(f"\n{'='*60}", flush=True)
            print(f"当前会话数量: {len(sessions)}", flush=True)
            
            for row in sessions:
                expire_at = datetime.fromisoformat(row['expire_at'])
                remaining = int((expire_at - datetime.now()).total_seconds())
                
                print(f"  - {row['session_id'][:20]}... | 状态: {row['status']} | 剩余: {remaining}秒", flush=True)
            
            print(f"{'='*60}\n", flush=True)
            
    except Exception as e:
        print(f"[ERROR] 打印会话列表失败: {e}", flush=True)


def generate_authorization_url(
    state: str,
    server_url: str = "",
    port: int = IFLOW_CALLBACK_PORT,
) -> str:
    """
    生成 iFlow OAuth 授权 URL
    
    Args:
        state: 随机状态参数，用于防止 CSRF 攻击
        server_url: 服务器地址，用于构建回调 URL
        port: OAuth 回调端口（此版本未使用，因为使用服务器端回调）
    
    Returns:
        授权 URL 字符串
    """
    # 回调 URL 使用主服务器的 /api/iflow/callback 端点
    # 注意：FastAPI 路由注册时加了 /api 前缀
    redirect_uri = f"{server_url}/api/iflow/callback"
    
    params = {
        "loginMethod": "phone",
        "type": "phone",
        "redirect": redirect_uri,
        "state": state,
        "client_id": IFLOW_OAUTH_CLIENT_ID,
    }
    
    auth_url = f"{IFLOW_OAUTH_AUTHORIZE_ENDPOINT}?{urlencode(params)}"
    return auth_url, redirect_uri


def create_login_session(server_url: str = DEFAULT_SERVER_URL) -> Dict[str, Any]:
    """
    创建简化版登录会话
    
    生成授权 URL 和会话 ID，用户在浏览器中完成登录后，
    Kivy 应用通过轮询获取登录结果。
    
    Args:
        server_url: 服务器地址，用于构建回调 URL
    
    Returns:
        包含 session_id, login_url, expires_in 的字典
    """
    print(f"[DEBUG] create_login_session called with server_url={server_url}", flush=True)
    logger.debug(f"create_login_session called with server_url={server_url}")
    
    # 生成随机 state
    state = secrets.token_urlsafe(16)
    print(f"[DEBUG] Generated state: {state}", flush=True)
    logger.debug(f"Generated state: {state}")
    
    # 创建登录会话（同时存储到 SQLite 和内存）
    session = LoginStatusManager.create_session(state, server_url)
    print(f"[DEBUG] Session created in SQLite and memory", flush=True)
    logger.debug(f"Session created in SQLite and memory")
    
    # 生成授权 URL
    login_url, redirect_uri = generate_authorization_url(state, server_url)
    
    print(f"[INFO] 创建登录会话成功!", flush=True)
    print(f"[INFO] Session ID: {state}", flush=True)
    print(f"[INFO] 授权 URL: {login_url}", flush=True)
    print(f"[INFO] 回调 URL: {redirect_uri}", flush=True)
    print(f"[INFO] 有效期: {SESSION_EXPIRE_SECONDS}秒 ({SESSION_EXPIRE_SECONDS // 60}分钟)", flush=True)
    
    logger.info(f"创建登录会话成功: {state}")
    logger.info(f"授权 URL: {login_url}")
    logger.info(f"回调 URL: {redirect_uri}")
    
    # 打印当前所有会话
    print_all_sessions()
    
    return {
        "session_id": state,
        "login_url": login_url,
        "redirect_uri": redirect_uri,
        "expires_in": SESSION_EXPIRE_SECONDS,
    }


def get_login_status(session_id: str) -> Dict[str, Any]:
    """
    获取登录状态
    
    Args:
        session_id: 会话 ID
    
    Returns:
        包含状态的字典：pending/completed/failed/not_found
    """
    return LoginStatusManager.get_status(session_id)


def complete_login_session(
    session_id: str,
    email: str,
    api_key: str,
    auth_data: Optional[Dict[str, Any]] = None,
) -> bool:
    """
    完成登录会话
    
    Args:
        session_id: 会话 ID
        email: 用户邮箱
        api_key: API Key
        auth_data: 其他认证数据
    
    Returns:
        是否成功
    """
    return LoginStatusManager.complete_session(session_id, email, api_key, auth_data)


def fail_login_session(session_id: str, reason: str = "") -> bool:
    """
    标记登录会话失败
    
    Args:
        session_id: 会话 ID
        reason: 失败原因
    
    Returns:
        是否成功
    """
    return LoginStatusManager.fail_session(session_id, reason)


def auto_login(
    server_url: str = DEFAULT_SERVER_URL,
    timeout: int = 300,
    poll_interval: int = 2,
) -> Dict[str, Any]:
    """
    自动完成登录（无需用户输入）

    1. 创建登录会话
    2. 自动打开浏览器（如果失败会打印网址）
    3. 等待登录结果

    Args:
        server_url: 服务器地址
        timeout: 超时时间（秒）
        poll_interval: 轮询间隔（秒）

    Returns:
        成功: {"success": True, "email": "...", "api_key": "...", "login_url": "..."}
        失败: {"success": False, "message": "..."}
    """
    # 强制刷新输出
    sys.stdout.flush()
    print(f"\n{'='*60}", flush=True)
    print(f"        iFlow 自动登录", flush=True)
    print(f"{'='*60}", flush=True)
    print(f"服务器: {server_url}", flush=True)
    sys.stdout.flush()
    
    try:
        # 1. 创建登录会话
        print("正在创建登录会话...", flush=True)
        sys.stdout.flush()
        session_data = create_login_session(server_url)
        session_id = session_data["session_id"]
        login_url = session_data["login_url"]
        
        print(f"✓ 会话创建成功！", flush=True)
        print(f"✓ Session ID: {session_id}", flush=True)
        print(f"✓ 有效期: {session_data['expires_in']}秒", flush=True)
        sys.stdout.flush()
        
        # 打印登录网址（使用分隔线突出显示）
        print(f"\n{'='*60}", flush=True)
        print(f"登录网址 (请复制到浏览器):", flush=True)
        print(f"{login_url}", flush=True)
        print(f"{'='*60}\n", flush=True)
        sys.stdout.flush()
        
    except Exception as e:
        print(f"\n[ERROR] 创建会话失败: {e}", flush=True)
        import traceback
        traceback.print_exc()
        sys.stdout.flush()
        return {"success": False, "message": f"创建会话失败: {str(e)}"}
    
    # 2. 尝试打开浏览器
    browser_opened = False
    try:
        print("正在尝试打开浏览器...", flush=True)
        sys.stdout.flush()
        import webbrowser
        webbrowser.open(login_url)
        print("✓ 已发送打开浏览器请求", flush=True)
        browser_opened = True
    except Exception as e:
        print(f"[WARNING] 打开浏览器失败: {e}", flush=True)
        print("[INFO] 请手动在浏览器中打开上面的登录网址", flush=True)
    sys.stdout.flush()
    
    # 3. 等待登录结果
    print(f"\n等待登录完成...（超时: {timeout}秒）", flush=True)
    print("请在浏览器中完成登录", flush=True)
    print("状态变化时会显示在这里\n", flush=True)
    sys.stdout.flush()
    
    start_time = time.time()
    last_status = ""
    
    while time.time() - start_time < timeout:
        status = get_login_status(session_id)
        st = status.get("status", "")
        
        # 只在状态改变时打印
        if st != last_status:
            print(f"[状态] {st}", flush=True)
            last_status = st
            sys.stdout.flush()
        
        if st == "completed":
            print(f"\n{'='*60}", flush=True)
            print(f"  登录成功！", flush=True)
            print(f"  账号: {status.get('email')}", flush=True)
            print(f"{'='*60}\n", flush=True)
            sys.stdout.flush()
            return {
                "success": True,
                "email": status.get("email"),
                "api_key": status.get("api_key"),
                "login_url": login_url,
                "browser_opened": browser_opened,
                "session_id": session_id,
            }
        
        if st == "not_found":
            print(f"\n[ERROR] 会话已过期或不存在", flush=True)
            print(f"[INFO] Session ID: {session_id}", flush=True)
            print_all_sessions()
            sys.stdout.flush()
            return {
                "success": False,
                "message": "会话已过期",
                "login_url": login_url,
                "browser_opened": browser_opened,
                "session_id": session_id,
            }
        
        if st == "failed":
            print(f"\n[ERROR] 登录失败: {status.get('message', '未知错误')}", flush=True)
            sys.stdout.flush()
            return {
                "success": False,
                "message": status.get("message", "登录失败"),
                "login_url": login_url,
                "browser_opened": browser_opened,
            }
        
        time.sleep(poll_interval)
    
    print(f"\n[ERROR] 登录超时（{timeout}秒）", flush=True)
    print(f"登录网址: {login_url}", flush=True)
    print("请在浏览器中完成登录后刷新此页面\n", flush=True)
    sys.stdout.flush()
    return {
        "success": False,
        "message": f"登录超时（{timeout}秒）",
        "login_url": login_url,
        "browser_opened": browser_opened,
    }


def async_auto_login(
    server_url: str = DEFAULT_SERVER_URL,
    timeout: int = 300,
) -> Dict[str, Any]:
    """异步版本的自动登录（用于 Kivy）"""
    result = {"success": False, "message": "处理中"}
    
    def do_login():
        nonlocal result
        result = auto_login(server_url, timeout)
    
    thread = threading.Thread(target=do_login, daemon=True)
    thread.start()
    thread.join()
    
    return result


# 兼容旧代码的别名
SimplifiedLoginManager = LoginStatusManager


__all__ = [
    "LoginSession",
    "LoginStatusManager",
    "SimplifiedLoginManager",
    "create_login_session",
    "get_login_status",
    "complete_login_session",
    "fail_login_session",
    "generate_authorization_url",
    "auto_login",
    "async_auto_login",
    "print_all_sessions",
]


if __name__ == "__main__":
    # 直接运行时的自动化测试
    print("\n" + "=" * 60, flush=True)
    print("        iFlow 简化版登录测试", flush=True)
    print("=" * 60, flush=True)
    
    result = auto_login()
    
    print("\n" + "=" * 60, flush=True)
    
    if result["success"]:
        print("  登录成功！", flush=True)
        print(f"  账号: {result['email']}", flush=True)
        print(f"  API Key: {result.get('api_key', 'N/A')[:20]}...", flush=True)
    else:
        print(f"  登录失败: {result['message']}", flush=True)
        login_url = result.get("login_url", "")
        if login_url:
            print(f"  登录网址: {login_url}", flush=True)
            print("  （如浏览器未自动打开，请手动复制网址到浏览器）", flush=True)
    
    print("=" * 60 + "\n", flush=True)
