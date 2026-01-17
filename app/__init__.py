"""CLIProxyAPI - 命令行代理 API 管理工具"""
from .settings import settings, DATA_DIR, LOGS_DIR
from .logger import logger, console
from .auth import auth_service
from .stores import store_service
from .proxy import proxy_service
from .iflow import iflow_auth_service, iflow_executor_service


__version__ = "0.1.0"
__all__ = [
    "settings",
    "DATA_DIR",
    "LOGS_DIR",
    "logger",
    "console",
    "auth_service",
    "store_service",
    "proxy_service",
    "iflow_auth_service",
    "iflow_executor_service",
    "__version__",
]
