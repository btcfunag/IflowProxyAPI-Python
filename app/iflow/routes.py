"""iFlow API 路由 - iFlow 接口的 API 端点"""
import asyncio
import base64
import json
import secrets
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, HTTPException, Request
from .models import (
    IFlowAuthResponse,
    IFlowLoginRequest,
    IFlowChatCompletionRequest,
    IFlowChatCompletionResponse,
    IFlowTokenRefreshRequest,
    IFlowCookieAuthRequest,
)
from .service import (
    IFlowOAuthServer,
    IFlowAuthService,
    IFlowExecutorService,
    iflow_auth_service,
    iflow_executor_service,
)
from .auth import IFLOW_CALLBACK_PORT, IFLOW_AUTH_DIR
from ..logger import logger


# 创建路由器
router = APIRouter()

# OAuth 服务器实例（每次登录会创建新实例）
_oauth_server: Optional[IFlowOAuthServer] = None
_auth_service: Optional[IFlowAuthService] = None


def create_oauth_server() -> IFlowOAuthServer:
    """创建新的 OAuth 服务器实例"""
    return IFlowOAuthServer()


def get_auth_service() -> IFlowAuthService:
    """获取认证服务实例"""
    global _auth_service
    if _auth_service is None:
        _auth_service = IFlowAuthService()
    return _auth_service


# ============ OAuth 认证路由 ============

@router.post("/iflow/login", response_model=IFlowAuthResponse)
async def iflow_login(request: IFlowLoginRequest):
    """iFlow OAuth 登录"""
    import webbrowser
    
    auth_service = get_auth_service()
    # 每次登录创建新的OAuth服务器实例
    oauth_server = create_oauth_server()
    
    # 生成 state 参数
    state = secrets.token_urlsafe(16)
    
    # 生成授权 URL
    port = request.callback_port or IFLOW_CALLBACK_PORT
    auth_url, redirect_uri = auth_service.get_authorization_url(state, port)
    
    logger.info(f"开始 iFlow OAuth 登录，授权 URL: {auth_url}")
    
    # 启动 OAuth 回调服务器
    if not await oauth_server.start():
        raise HTTPException(status_code=500, detail="启动 OAuth 服务器失败")
    
    try:
        # 打开浏览器
        if not request.no_browser:
            try:
                webbrowser.open(auth_url)
                logger.info("已打开浏览器进行认证")
            except Exception as e:
                logger.warning(f"打开浏览器失败: {e}")
        
        # 等待回调
        result = await asyncio.wait_for(
            oauth_server.wait_for_callback(timeout=300.0),
            timeout=300.0,
        )
        
        if result is None:
            raise HTTPException(status_code=408, detail="OAuth 回调超时")
        
        # 检查错误
        if "error" in result:
            error_msg = result.get("error", "unknown_error")
            raise HTTPException(status_code=400, detail=f"OAuth 认证失败: {error_msg}")
        
        # 检查 state
        if result.get("state") != state:
            raise HTTPException(status_code=400, detail="OAuth state 不匹配")
        
        # 交换授权码
        token_data = await auth_service.exchange_code_for_tokens(
            result["code"],
            redirect_uri,
        )
        
        if token_data is None:
            raise HTTPException(status_code=500, detail="交换授权码失败")
        
        # 保存认证信息
        token_storage = auth_service.create_token_storage(token_data)
        saved_path = auth_service.save_auth(token_storage)
        
        logger.info(f"iFlow 认证成功，保存至: {saved_path}")
        
        return IFlowAuthResponse(
            success=True,
            message="iFlow 认证成功",
            data={
                "email": token_data.email,
                "api_key": token_data.api_key,
                "expire": token_data.expire,
                "saved_path": saved_path,
            },
        )
        
    except asyncio.TimeoutError:
        raise HTTPException(status_code=408, detail="OAuth 回调超时")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"iFlow 登录异常: {e}")
        raise HTTPException(status_code=500, detail=f"登录失败: {str(e)}")
    finally:
        await oauth_server.stop()


@router.post("/iflow/login/cookie", response_model=IFlowAuthResponse)
async def iflow_login_cookie(request: IFlowCookieAuthRequest):
    """iFlow Cookie 登录"""
    auth_service = get_auth_service()
    
    logger.info("开始 iFlow Cookie 登录")
    
    try:
        # 使用 Cookie 认证
        token_data = await auth_service.authenticate_with_cookie(request.cookie)
        
        if token_data is None:
            raise HTTPException(status_code=401, detail="Cookie 认证失败")
        
        # 保存认证信息
        token_storage = auth_service.create_token_storage(token_data)
        saved_path = auth_service.save_auth(token_storage)
        
        logger.info(f"iFlow Cookie 认证成功，保存至: {saved_path}")
        
        return IFlowAuthResponse(
            success=True,
            message="iFlow Cookie 认证成功",
            data={
                "email": token_data.email,
                "api_key": token_data.api_key,
                "expire": token_data.expire,
                "saved_path": saved_path,
            },
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"iFlow Cookie 登录异常: {e}")
        raise HTTPException(status_code=500, detail=f"登录失败: {str(e)}")


@router.get("/iflow/accounts", response_model=IFlowAuthResponse)
async def list_iflow_accounts():
    """列出所有 iFlow 账号"""
    auth_service = get_auth_service()
    
    try:
        auths = auth_service.load_all_auths()
        
        accounts = []
        for auth in auths:
            accounts.append({
                "email": auth.email,
                "api_key": auth.api_key[:10] + "..." if len(auth.api_key) > 10 else auth.api_key,
                "expire": auth.expire,
                "auth_type": auth.auth_type,
                "created_at": auth.created_at,
            })
        
        return IFlowAuthResponse(
            success=True,
            message="获取账号列表成功",
            data={
                "accounts": accounts,
                "total": len(accounts),
            },
        )
        
    except Exception as e:
        logger.error(f"获取账号列表异常: {e}")
        raise HTTPException(status_code=500, detail=f"获取账号列表失败: {str(e)}")


@router.delete("/iflow/accounts/{email}", response_model=IFlowAuthResponse)
async def delete_iflow_account(email: str):
    """删除 iFlow 账号"""
    from .auth import IFLOW_AUTH_DIR
    
    try:
        deleted = False
        for file_path in IFLOW_AUTH_DIR.glob("iflow-*.json"):
            try:
                data = json.loads(file_path.read_text())
                if data.get("email") == email:
                    file_path.unlink()
                    deleted = True
                    logger.info(f"删除账号: {email}")
                    break
            except Exception:
                continue
        
        if not deleted:
            raise HTTPException(status_code=404, detail="账号不存在")
        
        return IFlowAuthResponse(
            success=True,
            message="删除账号成功",
            data={"email": email},
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除账号异常: {e}")
        raise HTTPException(status_code=500, detail=f"删除账号失败: {str(e)}")


# ============ Chat Completion 路由 ============

@router.post("/iflow/chat/completions")
async def chat_completions(request: IFlowChatCompletionRequest):
    """iFlow Chat Completion（流式或非流式）"""
    executor = iflow_executor_service
    auth_service = iflow_auth_service
    
    try:
        # 加载认证信息
        if not request.model:
            raise HTTPException(status_code=400, detail="模型名称不能为空")
        
        # 从模型名称中提取邮箱（格式: email-model 或 email@domain-model）
        model_parts = request.model.split("-", 1)
        if len(model_parts) < 2:
            # 如果没有指定邮箱，使用第一个账号
            auths = auth_service.load_all_auths()
            if not auths:
                raise HTTPException(status_code=401, detail="未配置 iFlow 账号")
            auth_storage = auths[0]
        else:
            email = model_parts[0]
            auth_storage = auth_service.load_auth(email)
            
            if auth_storage is None:
                raise HTTPException(status_code=401, detail=f"账号 {email} 不存在")
        
        # 执行请求
        if request.stream:
            return executor.execute_chat_completion_stream(auth_storage, request)
        else:
            response = await executor.execute_chat_completion(auth_storage, request)
            return response.dict()
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Chat Completion 异常: {e}")
        raise HTTPException(status_code=500, detail=f"请求失败: {str(e)}")


@router.get("/iflow/models")
async def iflow_available_models():
    """获取 iFlow 可用的模型列表（带详细配置）"""
    auth_service = iflow_auth_service
    
    # iFlow 模型定义
    models = [
        {
            "id": "glm-4",
            "name": "GLM-4",
            "description": "最强模型，适合复杂任务",
            "capabilities": ["chat", "tools", "vision"],
            "max_tokens": 128000,
            "thinking_support": True,
        },
        {
            "id": "glm-4-plus",
            "name": "GLM-4 Plus",
            "description": "GLM-4 增强版",
            "capabilities": ["chat", "tools", "vision"],
            "max_tokens": 128000,
            "thinking_support": True,
        },
        {
            "id": "glm-4v",
            "name": "GLM-4V",
            "description": "视觉理解模型",
            "capabilities": ["chat", "vision"],
            "max_tokens": 128000,
            "thinking_support": False,
        },
        {
            "id": "glm-3-turbo",
            "name": "GLM-3 Turbo",
            "description": "快速响应模型",
            "capabilities": ["chat"],
            "max_tokens": 64000,
            "thinking_support": False,
        },
        {
            "id": "minimax-m2",
            "name": "MiniMax M2",
            "description": "高效推理模型",
            "capabilities": ["chat", "tools"],
            "max_tokens": 200000,
            "thinking_support": True,
        },
        {
            "id": "minimax-m2.1",
            "name": "MiniMax M2.1",
            "description": "MiniMax M2 增强版",
            "capabilities": ["chat", "tools"],
            "max_tokens": 200000,
            "thinking_support": True,
        },
    ]
    
    return {
        "success": True,
        "message": "获取模型列表成功",
        "data": {
            "models": models,
            "total": len(models),
            "format_note": "使用模型时需在模型名前加账号邮箱前缀，如: user@example.com-glm-4",
        },
    }


# ============ Token 刷新路由 ============

@router.post("/iflow/refresh", response_model=IFlowAuthResponse)
async def refresh_iflow_token(request: IFlowTokenRefreshRequest):
    """刷新 iFlow Token"""
    auth_service = iflow_auth_service
    
    try:
        # 加载认证信息
        auth_storage = auth_service.load_auth(request.email)
        
        if auth_storage is None:
            raise HTTPException(status_code=404, detail="账号不存在")
        
        # 检查认证类型
        if auth_storage.auth_type != "oauth":
            raise HTTPException(status_code=400, detail="Cookie 认证不支持刷新")
        
        # 刷新 Token
        if not auth_storage.refresh_token:
            raise HTTPException(status_code=400, detail="refresh_token 为空")
        
        token_data = await auth_service.refresh_tokens(auth_storage.refresh_token)
        
        if token_data is None:
            raise HTTPException(status_code=500, detail="刷新 Token 失败")
        
        # 更新认证信息
        auth_storage.access_token = token_data.access_token
        auth_storage.refresh_token = token_data.refresh_token
        auth_storage.expire = token_data.expire
        auth_storage.last_refresh = datetime.now(timezone.utc).isoformat()
        
        # 重新保存
        saved_path = auth_service.save_auth(auth_storage)
        
        logger.info(f"iFlow Token 刷新成功: {request.email}")
        
        return IFlowAuthResponse(
            success=True,
            message="Token 刷新成功",
            data={
                "email": request.email,
                "expire": token_data.expire,
                "saved_path": saved_path,
            },
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"刷新 Token 异常: {e}")
        raise HTTPException(status_code=500, detail=f"刷新失败: {str(e)}")


__all__ = ["router"]
