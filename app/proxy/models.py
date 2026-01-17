"""代理管理数据模型"""
from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field, HttpUrl
from datetime import datetime


class ProxyConfig(BaseModel):
    """代理配置模型"""
    name: str = Field(..., description="代理名称")
    proxy_type: Literal["http", "https", "socks5"] = Field(..., description="代理类型")
    host: str = Field(..., description="代理主机")
    port: int = Field(..., description="代理端口", ge=1, le=65535)
    username: Optional[str] = Field(None, description="用户名")
    password: Optional[str] = Field(None, description="密码")
    enabled: bool = Field(default=True, description="是否启用")
    tags: List[str] = Field(default_factory=list, description="标签")
    timeout: int = Field(default=30, description="超时时间（秒）")
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: Optional[datetime] = None
    
    @property
    def proxy_url(self) -> str:
        """生成代理 URL"""
        auth = ""
        if self.username and self.password:
            auth = f"{self.username}:{self.password}@"
        return f"{self.proxy_type}://{auth}{self.host}:{self.port}"


class ProxyConfigUpdate(BaseModel):
    """代理配置更新模型"""
    name: Optional[str] = None
    proxy_type: Optional[Literal["http", "https", "socks5"]] = None
    host: Optional[str] = None
    port: Optional[int] = None
    username: Optional[str] = None
    password: Optional[str] = None
    enabled: Optional[bool] = None
    tags: Optional[List[str]] = None
    timeout: Optional[int] = None
    updated_at: datetime = Field(default_factory=datetime.now)


class ProxyTestRequest(BaseModel):
    """代理测试请求"""
    proxy_name: str = Field(..., description="要测试的代理名称")
    test_url: str = Field(default="https://httpbin.org/ip", description="测试 URL")
    timeout: int = Field(default=30, description="测试超时时间")


class ProxyResponse(BaseModel):
    """代理响应模型"""
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None


class ProxyTestResult(BaseModel):
    """代理测试结果"""
    proxy_name: str
    success: bool
    response_time: Optional[float] = None
    response_data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class ProxyStats(BaseModel):
    """代理统计信息"""
    total: int
    enabled: int
    disabled: int
    by_type: Dict[str, int] = Field(default_factory=dict)


__all__ = [
    "ProxyConfig",
    "ProxyConfigUpdate",
    "ProxyTestRequest",
    "ProxyResponse",
    "ProxyTestResult",
    "ProxyStats",
]
