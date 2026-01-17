"""iFlow 认证模块 - OAuth2.0 认证和 Token 管理"""
import json
import asyncio
import base64
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from pathlib import Path
from ..logger import logger
from ..settings import DATA_DIR


# iFlow OAuth 配置常量
IFLOW_OAUTH_TOKEN_ENDPOINT = "https://iflow.cn/oauth/token"
IFLOW_OAUTH_AUTHORIZE_ENDPOINT = "https://iflow.cn/oauth"
IFLOW_USER_INFO_ENDPOINT = "https://iflow.cn/api/oauth/getUserInfo"
IFLOW_SUCCESS_REDIRECT_URL = "https://iflow.cn/oauth/success"

# iFlow API 配置
IFLOW_API_KEY_ENDPOINT = "https://platform.iflow.cn/api/openapi/apikey"
IFLOW_DEFAULT_API_BASE_URL = "https://apis.iflow.cn/v1"

# iFlow OAuth 客户端凭证
IFLOW_OAUTH_CLIENT_ID = "10009311001"
IFLOW_OAUTH_CLIENT_SECRET = "4Z3YjXycVsQvyGF1etiNlIBB4RsqSDtW"

# OAuth 回调端口
IFLOW_CALLBACK_PORT = 11451

# Token 存储目录
IFLOW_AUTH_DIR = DATA_DIR / "iflow_auths"
IFLOW_AUTH_DIR.mkdir(parents=True, exist_ok=True)


class IFlowTokenData:
    """iFlow Token 数据类"""
    
    def __init__(
        self,
        access_token: str = "",
        refresh_token: str = "",
        token_type: str = "",
        scope: str = "",
        expire: str = "",
        api_key: str = "",
        email: str = "",
        cookie: str = "",
    ):
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.token_type = token_type
        self.scope = scope
        self.expire = expire
        self.api_key = api_key
        self.email = email
        self.cookie = cookie
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "token_type": self.token_type,
            "scope": self.scope,
            "expire": self.expire,
            "api_key": self.api_key,
            "email": self.email,
            "cookie": self.cookie,
        }


class IFlowTokenStorage:
    """iFlow Token 存储类"""
    
    def __init__(
        self,
        access_token: str = "",
        refresh_token: str = "",
        last_refresh: str = "",
        expire: str = "",
        api_key: str = "",
        email: str = "",
        token_type: str = "",
        scope: str = "",
        cookie: str = "",
        auth_type: str = "oauth",
    ):
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.last_refresh = last_refresh
        self.expire = expire
        self.api_key = api_key
        self.email = email
        self.token_type = token_type
        self.scope = scope
        self.cookie = cookie
        self.auth_type = auth_type
        self.created_at = datetime.now(timezone.utc).isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "last_refresh": self.last_refresh,
            "expire": self.expire,
            "api_key": self.api_key,
            "email": self.email,
            "token_type": self.token_type,
            "scope": self.scope,
            "cookie": self.cookie,
            "auth_type": self.auth_type,
            "created_at": self.created_at,
        }
    
    def to_file_dict(self) -> Dict[str, Any]:
        """转换为文件存储格式（敏感信息可能需要加密）"""
        return self.to_dict()
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "IFlowTokenStorage":
        """从字典创建实例"""
        storage = cls()
        storage.access_token = data.get("access_token", "")
        storage.refresh_token = data.get("refresh_token", "")
        storage.last_refresh = data.get("last_refresh", "")
        storage.expire = data.get("expire", "")
        storage.api_key = data.get("api_key", "")
        storage.email = data.get("email", "")
        storage.token_type = data.get("token_type", "")
        storage.scope = data.get("scope", "")
        storage.cookie = data.get("cookie", "")
        storage.auth_type = data.get("auth_type", "oauth")
        storage.created_at = data.get("created_at", datetime.now(timezone.utc).isoformat())
        return storage


def generate_auth_filename(email: str) -> str:
    """生成认证文件名"""
    import hashlib
    timestamp = int(datetime.now().timestamp())
    safe_email = "".join(c if c.isalnum() or c in "@._-" else "_" for c in email)
    return f"iflow-{safe_email}-{timestamp}.json"


def extract_bx_auth(cookie: str) -> str:
    """从 Cookie 字符串中提取 BXAuth 值"""
    if not cookie:
        return ""
    parts = cookie.split(";")
    for part in parts:
        part = part.strip()
        if part.startswith("BXAuth="):
            return part[7:].strip()
    return ""


def normalize_cookie(raw_cookie: str) -> str:
    """标准化 Cookie 字符串"""
    trimmed = raw_cookie.strip()
    if not trimmed:
        raise ValueError("Cookie 不能为空")
    
    # 合并空格
    combined = " ".join(trimmed.split())
    if not combined.endswith(";"):
        combined += ";"
    
    # 检查是否包含 BXAuth
    if "BXAuth=" not in combined:
        raise ValueError("Cookie 必须包含 BXAuth 字段")
    
    return combined


__all__ = [
    "IFLOW_OAUTH_TOKEN_ENDPOINT",
    "IFLOW_OAUTH_AUTHORIZE_ENDPOINT",
    "IFLOW_USER_INFO_ENDPOINT",
    "IFLOW_SUCCESS_REDIRECT_URL",
    "IFLOW_API_KEY_ENDPOINT",
    "IFLOW_DEFAULT_API_BASE_URL",
    "IFLOW_OAUTH_CLIENT_ID",
    "IFLOW_OAUTH_CLIENT_SECRET",
    "IFLOW_CALLBACK_PORT",
    "IFLOW_AUTH_DIR",
    "IFlowTokenData",
    "IFlowTokenStorage",
    "generate_auth_filename",
    "extract_bx_auth",
    "normalize_cookie",
]
