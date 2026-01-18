"""iFlow API 路由 - iFlow 接口的 API 端点"""
import asyncio
import base64
import json
import secrets
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
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


# ============ 简化版登录路由 ============

@router.post("/iflow/login/simplified", response_model=IFlowAuthResponse)
async def create_simplified_login(request: Request):
    """
    创建简化版登录会话

    生成一个一次性登录 URL，用户在浏览器中完成登录后，
    Kivy 应用通过轮询 /api/iflow/login/status/{session_id} 获取登录结果。

    适用于无法绑定本地端口的环境（如 Kivy 安卓应用）
    """
    from .simplified_login import (
        create_login_session,
        generate_authorization_url,
        LoginStatusManager,
        SessionDatabase,
    )
    import sqlite3
    from pathlib import Path

    try:
        # 获取服务器地址
        server_url = str(request.base_url).rstrip("/")
        logger.info(f"=== 开始创建简化登录会话 ===")
        logger.info(f"server_url={server_url}")
        
        # 创建登录会话
        logger.info("调用 create_login_session...")
        session_data = create_login_session(server_url)
        session_id = session_data["session_id"]
        login_url = session_data["login_url"]
        redirect_uri = session_data.get("redirect_uri", "")

        logger.info(f"简化版登录会话创建成功: {session_id}")
        logger.info(f"登录URL: {login_url}")
        logger.info(f"回调URL: {redirect_uri}")
        
        # 直接查询数据库确认会话已保存
        logger.info("验证数据库中的会话...")
        
        # 获取数据库路径
        try:
            db = SessionDatabase()
            db_path = db.db_path
        except Exception as e:
            db_path = Path("/storage/emulated/0/000CLIProxyAPI-Python/data/simplified_login_sessions.db")
            logger.warning(f"获取数据库实例失败，使用默认路径: {e}")
        
        logger.info(f"数据库路径: {db_path}")
        
        if db_path.exists():
            with sqlite3.connect(db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("SELECT * FROM login_sessions WHERE session_id = ?", (session_id,))
                row = cursor.fetchone()
                if row:
                    logger.info(f"✓ 数据库验证成功: 会话已保存")
                    logger.info(f"  - session_id: {row['session_id']}")
                    logger.info(f"  - status: {row['status']}")
                    logger.info(f"  - created_at: {row['created_at']}")
                else:
                    logger.error(f"✗ 数据库验证失败: 会话未找到!")
                    # 打印所有会话
                    cursor = conn.execute("SELECT * FROM login_sessions")
                    all_rows = cursor.fetchall()
                    logger.error(f"数据库中共有 {len(all_rows)} 个会话")
                    for r in all_rows:
                        logger.error(f"  - {r['session_id']}: {r['status']}")
        else:
            logger.error(f"✗ 数据库文件不存在: {db_path}")
        
        logger.info(f"=== 创建登录会话完成 ===")
        
        return IFlowAuthResponse(
            success=True,
            message="登录会话创建成功，请在浏览器中完成登录",
            data={
                "session_id": session_id,
                "login_url": login_url,
                "expires_in": session_data["expires_in"],
            },
        )

    except Exception as e:
        logger.error(f"创建简化登录会话异常: {e}")
        import traceback
        logger.error(f"堆栈跟踪: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"创建登录会话失败: {str(e)}")


@router.get("/iflow/login/status/{session_id}")
async def get_login_status(session_id: str):
    """
    获取简化版登录状态

    Kivy 应用轮询此接口获取登录结果。
    返回登录状态（pending/completed/failed）和认证信息。
    """
    from .simplified_login import get_login_status

    try:
        logger.debug(f"get_login_status: session_id={session_id}")
        status = get_login_status(session_id)
        logger.debug(f"get_login_status result: {status}")

        if status.get("status") == "not_found":
            logger.warning(f"会话不存在或已过期: {session_id}")
            raise HTTPException(status_code=404, detail="登录会话不存在或已过期")

        return {
            "success": True,
            "data": status,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取登录状态异常: {e}")
        import traceback
        logger.error(f"堆栈跟踪: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"获取状态失败: {str(e)}")


@router.get("/iflow/callback")
async def iflow_oauth_callback(
    request: Request,
    code: str = "",
    state: str = "",
    error: str = "",
    error_description: str = "",
):
    """
    iFlow OAuth 回调端点

    用户在 iFlow 网站完成登录后，iFlow 会重定向到此端点。
    此端点接收 OAuth code，交换 token，并保存认证信息。

    注意：此端点需要在 iFlow OAuth 配置中注册为有效的回调 URL
    """
    from .simplified_login import LoginStatusManager, complete_login_session, fail_login_session

    auth_service = get_auth_service()

    # 打印完整的请求信息用于调试
    logger.info(f"收到 OAuth 回调请求")
    logger.info(f"请求URL: {request.url}")
    logger.info(f"原始参数: code={code[:30] if code else 'none'}..., state={state}")
    
    # 解析 query string 获取原始参数
    query_params = dict(request.query_params)
    logger.info(f"Query参数: {query_params}")
    
    # 检查是否有错误
    if error:
        err_msg = error_description or error
        logger.warning(f"OAuth 回调错误: {error} - {err_msg}")
        if state:
            fail_login_session(state, err_msg)
        return {
            "success": False,
            "message": f"登录失败: {err_msg}",
        }

    # 检查是否有 code
    if not code:
        logger.warning("OAuth 回调缺少授权码")
        if state:
            fail_login_session(state, "缺少授权码")
        return {
            "success": False,
            "message": "登录失败: 缺少授权码",
        }

    # ============ 尝试获取数据库状态 ============
    # 如果 simplified_login 有 SessionDatabase，使用它；否则跳过数据库验证
    try:
        from .simplified_login import SessionDatabase as SD
        
        # 强制重新初始化数据库连接
        if hasattr(LoginStatusManager, '_db') and LoginStatusManager._db is not None:
            SD._instance = None
            LoginStatusManager._db = None
        
        if hasattr(LoginStatusManager, '_get_db'):
            db = LoginStatusManager._get_db()
            db._cleanup_expired()
            
            logger.info(f"直接查询数据库检查 state: {state}")
            with sqlite3.connect(db.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("""
                    SELECT session_id, status, created_at, expire_at 
                    FROM login_sessions 
                    ORDER BY created_at DESC
                    LIMIT 10
                """)
                all_sessions = cursor.fetchall()
                logger.info(f"数据库中直接查询到的会话数量: {len(all_sessions)}")
                
                for row in all_sessions:
                    expire_at = datetime.fromisoformat(row['expire_at'])
                    remaining = int((expire_at - datetime.now()).total_seconds())
                    logger.info(f"  DB会话: {row['session_id'][:20]}... | 状态: {row['status']} | 剩余: {remaining}秒")
                
                cursor2 = conn.execute("""
                    SELECT 1 FROM login_sessions WHERE session_id = ?
                """, (state,))
                db_exists = cursor2.fetchone() is not None
                logger.info(f"直接查询 state '{state[:20]}...' 是否存在: {db_exists}")
                
    except ImportError:
        logger.warning("simplified_login 没有 SessionDatabase，跳过数据库验证")
        logger.warning("请确保使用 simplified_login_v2.py 版本")
    except Exception as e:
        logger.error(f"数据库操作异常: {e}")
    
    # 详细的 state 对比日志
    logger.info(f"回调接收到的 state: '{state}'")
    logger.info(f"state 长度: {len(state)}")
    logger.info(f"state 类型: {type(state)}")
    
    # 检查数据库中是否存在此 state
    db_exists = LoginStatusManager.check_state_exists(state) if hasattr(LoginStatusManager, 'check_state_exists') else False
    logger.info(f"数据库中是否存在此 state: {db_exists}")
    
    # 获取会话信息
    logger.info(f"尝试查找会话: state={state}")
    session = LoginStatusManager.get_session(state)
    logger.info(f"查找结果: {session}")
    
    if not session:
        logger.warning(f"会话不存在或已过期: state={state}")
        
        # 打印所有现有的会话用于调试
        all_sessions = LoginStatusManager.get_all_sessions() if hasattr(LoginStatusManager, 'get_all_sessions') else []
        logger.warning(f"当前数据库中的会话数量: {len(all_sessions)}")
        
        # 详细对比
        logger.warning("=" * 60)
        logger.warning("详细对比:")
        logger.warning(f"回调 state: '{state}'")
        for row in all_sessions:
            db_state = row['session_id']
            logger.warning(f"数据库 state: '{db_state}'")
            logger.warning(f"是否相等: {state == db_state}")
            if state == db_state:
                logger.warning("找到匹配的会话！")
                break
        logger.warning("=" * 60)
        
        return {
            "success": False,
            "message": "登录失败: 会话已过期",
        }

    try:
        # 从请求中获取回调 URL（注意：需要加 /api 前缀）
        base_url = str(request.base_url).rstrip("/")
        redirect_uri = f"{base_url}/api/iflow/callback"
        logger.debug(f"使用 redirect_uri: {redirect_uri}")

        # 交换授权码获取 token
        logger.debug("开始交换授权码...")
        token_data = await auth_service.exchange_code_for_tokens(code, redirect_uri)

        if token_data is None:
            logger.error("交换授权码失败")
            fail_login_session(state, "交换授权码失败")
            return {
                "success": False,
                "message": "登录失败: 交换授权码失败",
            }

        # 保存认证信息
        logger.debug(f"Token交换成功，email: {token_data.email}")
        token_storage = auth_service.create_token_storage(token_data)
        saved_path = auth_service.save_auth(token_storage)

        logger.info(f"iFlow OAuth 认证成功: {token_data.email}")

        # 标记登录完成
        complete_login_session(
            state,
            token_data.email,
            token_data.api_key,
            auth_data={
                "saved_path": saved_path,
                "expire": token_data.expire,
            }
        )

        # 返回成功页面（供浏览器显示）
        return {
            "success": True,
            "message": "登录成功！请切换回应用",
            "data": {
                "email": token_data.email,
                "saved_path": saved_path,
            },
        }

    except Exception as e:
        logger.error(f"处理 OAuth 回调异常: {e}")
        import traceback
        logger.error(f"堆栈跟踪: {traceback.format_exc()}")
        fail_login_session(state, str(e))
        return {
            "success": False,
            "message": f"登录失败: {str(e)}",
        }


@router.get("/iflow/login/callback/{session_id}")
async def login_callback_page(
    session_id: str,
    email: str = "",
    api_key: str = "",
    error: str = "",
):
    """
    简化版登录回调页面（兼容旧版本）

    用户在 iFlow 网站完成登录后，会重定向到此页面。
    此接口记录登录结果，并显示提示信息。

    注意：此端点已弃用，请使用 /iflow/callback
    """
    from .simplified_login import LoginStatusManager

    try:
        if error:
            # 登录失败
            LoginStatusManager.fail_session(session_id, error)
            return {
                "success": False,
                "message": f"登录失败: {error}",
                "session_id": session_id,
            }

        if not email or not api_key:
            # 参数不完整
            logger.warning(f"登录回调参数不完整: email={email}, api_key={api_key}")

        # 完成登录会话
        if email and api_key:
            LoginStatusManager.complete_session(session_id, email, api_key)

        return {
            "success": True,
            "message": "登录成功！请切换回应用",
            "session_id": session_id,
        }

    except Exception as e:
        logger.error(f"登录回调处理异常: {e}")
        return {
            "success": False,
            "message": f"处理失败: {str(e)}",
            "session_id": session_id,
        }


__all__ = ["router"]
