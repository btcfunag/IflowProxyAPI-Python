"""日志配置模块 - 使用 loguru (纯 Python)"""
import sys
from pathlib import Path
from rich.console import Console
from .settings import settings, LOGS_DIR

# 确保 logs 目录存在
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# 配置 loguru
def setup_logger():
    """配置日志系统"""
    from loguru import logger
    
    # 移除默认处理器
    logger.remove()
    
    # 添加控制台输出
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level=settings.LOG_LEVEL,
        colorize=True,
        backtrace=True,
        diagnose=True
    )
    
    # 添加文件输出
    logger.add(
        settings.LOG_FILE,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level=settings.LOG_LEVEL,
        rotation="10 MB",
        retention="7 days",
        compression="zip",
        backtrace=True,
        diagnose=True
    )
    
    return logger

# 初始化 logger
logger = setup_logger()

# console - Rich 控制台对象
console = Console()

# 导出
__all__ = ["logger", "console"]