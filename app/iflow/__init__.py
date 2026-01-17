"""iFlow 模块 - iFlow 认证和 API 代理"""
from .auth import (
    IFLOW_OAUTH_TOKEN_ENDPOINT,
    IFLOW_OAUTH_AUTHORIZE_ENDPOINT,
    IFLOW_USER_INFO_ENDPOINT,
    IFLOW_SUCCESS_REDIRECT_URL,
    IFLOW_API_KEY_ENDPOINT,
    IFLOW_DEFAULT_API_BASE_URL,
    IFLOW_OAUTH_CLIENT_ID,
    IFLOW_OAUTH_CLIENT_SECRET,
    IFLOW_CALLBACK_PORT,
    IFLOW_AUTH_DIR,
    IFlowTokenData,
    IFlowTokenStorage,
    generate_auth_filename,
    extract_bx_auth,
    normalize_cookie,
)
from .service import (
    IFlowOAuthServer,
    IFlowAuthService,
    IFlowExecutorService,
    iflow_auth_service,
    iflow_executor_service,
)
from .models import (
    IFlowAuthConfig,
    IFlowAuthResponse,
    IFlowLoginRequest,
    IFlowChatMessage,
    IFlowChatCompletionRequest,
    IFlowChatCompletionChunk,
    IFlowChatCompletionResponse,
    IFlowTokenRefreshRequest,
    IFlowCookieAuthRequest,
)
from .routes import router


__version__ = "0.1.0"

__all__ = [
    # 认证配置
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
    # 数据类
    "IFlowTokenData",
    "IFlowTokenStorage",
    # 工具函数
    "generate_auth_filename",
    "extract_bx_auth",
    "normalize_cookie",
    # 服务类
    "IFlowOAuthServer",
    "IFlowAuthService",
    "IFlowExecutorService",
    "iflow_auth_service",
    "iflow_executor_service",
    # 数据模型
    "IFlowAuthConfig",
    "IFlowAuthResponse",
    "IFlowLoginRequest",
    "IFlowChatMessage",
    "IFlowChatCompletionRequest",
    "IFlowChatCompletionChunk",
    "IFlowChatCompletionResponse",
    "IFlowTokenRefreshRequest",
    "IFlowCookieAuthRequest",
    # 路由
    "router",
    "__version__",
]
