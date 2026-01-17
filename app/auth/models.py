"""认证数据模型"""
from typing import Optional
from pydantic import BaseModel, Field
from datetime import datetime


class AuthConfig(BaseModel):
    """认证配置模型"""
    name: str = Field(..., description="认证名称")
    auth_type: str = Field(..., description="认证类型: basic, bearer, apikey, custom")
    config: dict = Field(default_factory=dict, description="认证配置参数")
    enabled: bool = Field(default=True, description="是否启用")
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: Optional[datetime] = None


class AuthConfigUpdate(BaseModel):
    """认证配置更新模型"""
    name: Optional[str] = None
    auth_type: Optional[str] = None
    config: Optional[dict] = None
    enabled: Optional[bool] = None
    updated_at: datetime = Field(default_factory=datetime.now)


class AuthResponse(BaseModel):
    """认证响应模型"""
    success: bool
    message: str
    data: Optional[dict] = None


class BasicAuthConfig(AuthConfig):
    """Basic 认证配置"""
    auth_type: str = "basic"
    username: str
    password: str


class BearerAuthConfig(AuthConfig):
    """Bearer Token 认证配置"""
    auth_type: str = "bearer"
    token: str
    token_prefix: str = "Bearer"


class APIKeyAuthConfig(AuthConfig):
    """API Key 认证配置"""
    auth_type: str = "apikey"
    key_name: str = "X-API-Key"
    key_value: str
    header_location: str = "header"  # header or query


class CustomAuthConfig(AuthConfig):
    """自定义认证配置"""
    auth_type: str = "custom"
    headers: dict = Field(default_factory=dict)
    query_params: dict = Field(default_factory=dict)


__all__ = [
    "AuthConfig",
    "AuthConfigUpdate",
    "AuthResponse",
    "BasicAuthConfig",
    "BearerAuthConfig",
    "APIKeyAuthConfig",
    "CustomAuthConfig",
]
