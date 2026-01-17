"""iFlow 数据模型"""
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from datetime import datetime


class IFlowAuthConfig(BaseModel):
    """iFlow 认证配置"""
    email: str = Field(..., description="用户邮箱或标识")
    api_key: str = Field(..., description="API Key")
    access_token: Optional[str] = Field(None, description="访问令牌")
    refresh_token: Optional[str] = Field(None, description="刷新令牌")
    expire: Optional[str] = Field(None, description="过期时间")
    auth_type: str = Field(default="oauth", description="认证类型: oauth 或 cookie")
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: Optional[datetime] = None


class IFlowAuthResponse(BaseModel):
    """iFlow 认证响应"""
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None


class IFlowLoginRequest(BaseModel):
    """iFlow 登录请求"""
    no_browser: bool = Field(default=False, description="是否不自动打开浏览器")
    callback_port: int = Field(default=11451, description="OAuth 回调端口")


class IFlowChatMessage(BaseModel):
    """iFlow 聊天消息"""
    role: str = Field(..., description="角色: system, user, assistant")
    content: str = Field(..., description="消息内容")


class IFlowChatCompletionRequest(BaseModel):
    """iFlow Chat Completion 请求"""
    model: str = Field(..., description="模型名称")
    messages: List[IFlowChatMessage] = Field(..., description="消息列表")
    stream: bool = Field(default=False, description="是否流式输出")
    max_tokens: Optional[int] = Field(None, description="最大 token 数")
    temperature: Optional[float] = Field(None, description="温度")
    top_p: Optional[float] = Field(None, description="top_p")
    presence_penalty: Optional[float] = Field(None, description="存在惩罚")
    frequency_penalty: Optional[float] = Field(None, description="频率惩罚")
    reasoning_effort: Optional[str] = Field(None, description="思考努力程度")


class IFlowChatCompletionChunk(BaseModel):
    """iFlow Chat Completion 流式块"""
    id: str
    object: str
    created: int
    model: str
    choices: List[Dict[str, Any]]
    usage: Optional[Dict[str, Any]] = None


class IFlowChatCompletionResponse(BaseModel):
    """iFlow Chat Completion 响应"""
    id: str
    object: str
    created: int
    model: str
    choices: List[Dict[str, Any]]
    usage: Optional[Dict[str, Any]] = None


class IFlowTokenRefreshRequest(BaseModel):
    """iFlow Token 刷新请求"""
    email: str = Field(..., description="用户邮箱")


class IFlowCookieAuthRequest(BaseModel):
    """iFlow Cookie 认证请求"""
    cookie: str = Field(..., description="浏览器 Cookie 字符串")


__all__ = [
    "IFlowAuthConfig",
    "IFlowAuthResponse",
    "IFlowLoginRequest",
    "IFlowChatMessage",
    "IFlowChatCompletionRequest",
    "IFlowChatCompletionChunk",
    "IFlowChatCompletionResponse",
    "IFlowTokenRefreshRequest",
    "IFlowCookieAuthRequest",
]
