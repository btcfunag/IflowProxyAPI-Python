#!/usr/bin/env python3
"""iFlow 接口测试脚本"""
import asyncio
import sys
import os

# 添加项目根目录到 Python 路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from app.iflow.auth import (
    IFlowTokenData,
    IFlowTokenStorage,
    generate_auth_filename,
    extract_bx_auth,
    normalize_cookie,
)
from app.iflow.models import (
    IFlowAuthConfig,
    IFlowLoginRequest,
    IFlowChatCompletionRequest,
    IFlowChatMessage,
)


def test_auth_models():
    """测试认证数据模型"""
    print("测试认证数据模型...")
    
    # 测试 TokenData
    token_data = IFlowTokenData(
        access_token="test_access_token",
        refresh_token="test_refresh_token",
        api_key="test_api_key",
        email="test@example.com",
    )
    assert token_data.access_token == "test_access_token"
    assert token_data.api_key == "test_api_key"
    print("  ✓ IFlowTokenData 测试通过")
    
    # 测试 TokenStorage
    token_storage = IFlowTokenStorage(
        access_token="test_access_token",
        refresh_token="test_refresh_token",
        api_key="test_api_key",
        email="test@example.com",
    )
    assert token_storage.auth_type == "oauth"
    print("  ✓ IFlowTokenStorage 测试通过")
    
    # 测试生成文件名
    filename = generate_auth_filename("user@example.com")
    assert filename.startswith("iflow-user@example.com-")
    assert filename.endswith(".json")
    print(f"  ✓ 生成文件名测试通过: {filename}")
    
    # 测试提取 BXAuth
    cookie = "session=abc; BXAuth=xyz123; other=def"
    bx_auth = extract_bx_auth(cookie)
    assert bx_auth == "xyz123"
    print("  ✓ 提取 BXAuth 测试通过")
    
    # 测试标准化 Cookie
    normalized = normalize_cookie("BXAuth=xyz123; session=abc")
    assert normalized == "BXAuth=xyz123; session=abc;"
    print("  ✓ 标准化 Cookie 测试通过")
    
    print("认证数据模型测试通过！\n")


def test_request_models():
    """测试请求数据模型"""
    print("测试请求数据模型...")
    
    # 测试登录请求
    login_request = IFlowLoginRequest(no_browser=True, callback_port=8080)
    assert login_request.no_browser is True
    assert login_request.callback_port == 8080
    print("  ✓ IFlowLoginRequest 测试通过")
    
    # 测试 Chat Completion 消息
    message = IFlowChatMessage(role="user", content="你好")
    assert message.role == "user"
    assert message.content == "你好"
    print("  ✓ IFlowChatMessage 测试通过")
    
    # 测试 Chat Completion 请求
    chat_request = IFlowChatCompletionRequest(
        model="test-glm-4",
        messages=[
            IFlowChatMessage(role="system", content="你是助手"),
            IFlowChatMessage(role="user", content="你好"),
        ],
        stream=False,
        temperature=0.7,
    )
    assert chat_request.model == "test-glm-4"
    assert len(chat_request.messages) == 2
    assert chat_request.temperature == 0.7
    print("  ✓ IFlowChatCompletionRequest 测试通过")
    
    print("请求数据模型测试通过！\n")


def test_service_imports():
    """测试服务导入"""
    print("测试服务模块导入...")
    
    try:
        from app.iflow.service import (
            IFlowOAuthServer,
            IFlowAuthService,
            IFlowExecutorService,
            iflow_auth_service,
            iflow_executor_service,
        )
        print("  ✓ 服务模块导入成功")
        
        # 测试服务实例
        assert isinstance(iflow_auth_service, IFlowAuthService)
        assert isinstance(iflow_executor_service, IFlowExecutorService)
        print("  ✓ 服务实例测试通过")
        
    except ImportError as e:
        print(f"  ✗ 导入失败: {e}")
        return False
    
    print("服务模块测试通过！\n")
    return True


def test_route_imports():
    """测试路由导入"""
    print("测试路由模块导入...")
    
    try:
        from app.iflow.routes import router
        print("  ✓ 路由模块导入成功")
        print("  ✓ 路由包含的端点:")
        for route in router.routes:
            print(f"    - {route.methods} {route.path}")
        
    except ImportError as e:
        print(f"  ✗ 导入失败: {e}")
        return False
    
    print("路由模块测试通过！\n")
    return True


async def test_oauth_server():
    """测试 OAuth 服务器"""
    print("测试 OAuth 服务器...")
    
    try:
        from app.iflow.service import IFlowOAuthServer
        
        server = IFlowOAuthServer(port=11452)
        print("  ✓ OAuthServer 创建成功")
        
        # 测试启动
        started = await server.start()
        assert started is True
        print("  ✓ OAuthServer 启动成功")
        
        # 测试停止
        await server.stop()
        print("  ✓ OAuthServer 停止成功")
        
    except Exception as e:
        print(f"  ✗ OAuthServer 测试失败: {e}")
        return False
    
    print("OAuth 服务器测试通过！\n")
    return True


async def main():
    """主测试函数"""
    print("=" * 60)
    print("iFlow 接口测试")
    print("=" * 60)
    print()
    
    # 同步测试
    test_auth_models()
    test_request_models()
    
    # 测试导入
    if not test_service_imports():
        return False
    
    if not test_route_imports():
        return False
    
    # 异步测试
    if not await test_oauth_server():
        return False
    
    print("=" * 60)
    print("所有测试通过！")
    print("=" * 60)
    return True


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
