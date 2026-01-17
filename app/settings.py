"""应用配置模块 - 纯 Python 实现"""
import os
from pathlib import Path
from typing import List

# 项目根目录
BASE_DIR = Path(__file__).parent.parent

# 目录配置
AUTHS_DIR = BASE_DIR / "auths"
LOGS_DIR = BASE_DIR / "logs"
DATA_DIR = BASE_DIR / "data"

# 确保目录存在
AUTHS_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

class Settings:
    """应用设置类"""
    
    # 应用信息
    APP_NAME: str = os.getenv("APP_NAME", "CLIProxyAPI")
    APP_VERSION: str = os.getenv("APP_VERSION", "1.0.0")
    DEBUG: bool = os.getenv("DEBUG", "false").lower() in ("true", "1", "yes")
    
    # 服务器设置
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    
    # CORS 设置
    CORS_ORIGINS: List[str] = ["*"]
    
    # 日志设置
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE: str = str(LOGS_DIR / "app.log")
    
    # 数据库设置
    DATABASE_URL: str = f"sqlite+aiosqlite:///{DATA_DIR}/proxyapi.db"
    
    # API 配置
    API_PREFIX: str = "/api/v1"
    
    # 文件配置
    MAX_FILE_SIZE: int = 10 * 1024 * 1024  # 10MB

settings = Settings()

# 为了兼容 main.py 的导入，添加别名
API_HOST = settings.HOST
API_PORT = settings.PORT
DEBUG = settings.DEBUG

# 导出配置
__all__ = [
    "Settings",
    "settings",
    "BASE_DIR",
    "AUTHS_DIR",
    "LOGS_DIR",
    "DATA_DIR",
    "API_HOST",
    "API_PORT",
    "DEBUG",
]