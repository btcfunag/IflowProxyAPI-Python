"""存储管理数据模型"""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


class StoreConfig(BaseModel):
    """存储配置模型"""
    name: str = Field(..., description="存储名称")
    store_type: str = Field(..., description="存储类型: local, http, memory")
    config: Dict[str, Any] = Field(default_factory=dict, description="存储配置参数")
    enabled: bool = Field(default=True, description="是否启用")
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: Optional[datetime] = None


class StoreConfigUpdate(BaseModel):
    """存储配置更新模型"""
    name: Optional[str] = None
    store_type: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    enabled: Optional[bool] = None
    updated_at: datetime = Field(default_factory=datetime.now)


class LocalStoreConfig(StoreConfig):
    """本地文件存储配置"""
    store_type: str = "local"
    base_path: str = Field(..., description="本地存储基础路径")
    create_subdirs: bool = True


class HTTPStoreConfig(StoreConfig):
    """HTTP 存储配置"""
    store_type: str = "http"
    base_url: str = Field(..., description="HTTP 存储基础 URL")
    auth_ref: Optional[str] = Field(None, description="引用的认证配置名称")
    timeout: int = 30


class MemoryStoreConfig(StoreConfig):
    """内存存储配置"""
    store_type: str = "memory"
    max_items: int = 1000
    max_size_mb: int = 100


class StoreItem(BaseModel):
    """存储项模型"""
    key: str = Field(..., description="存储键")
    value: Any = Field(..., description="存储值")
    content_type: Optional[str] = None
    size: int = 0
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: Optional[datetime] = None


class StoreResponse(BaseModel):
    """存储响应模型"""
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None


__all__ = [
    "StoreConfig",
    "StoreConfigUpdate",
    "LocalStoreConfig",
    "HTTPStoreConfig",
    "MemoryStoreConfig",
    "StoreItem",
    "StoreResponse",
]
