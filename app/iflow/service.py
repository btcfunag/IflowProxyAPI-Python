"""iFlow 服务模块 - 核心业务逻辑实现"""
import asyncio
import base64
import hashlib
import hmac
import json
import secrets
import gzip
import time as time_module
import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any, AsyncGenerator
import httpx
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
from .models import (
    IFlowChatCompletionRequest,
    IFlowChatCompletionResponse,
)
from ..logger import logger


class IFlowOAuthServer:
    """iFlow OAuth 回调服务器"""
    
    def __init__(self, port: int = IFLOW_CALLBACK_PORT):
        self.port = port
        self._result: Optional[Dict[str, str]] = None
        self._result_event = asyncio.Event()
        self._server_task: Optional[asyncio.Task] = None
        self._shutdown_event = asyncio.Event()
        self._server = None
    
    async def start(self) -> bool:
        """启动 OAuth 回调服务器"""
        try:
            # 重置状态
            self._result = None
            self._result_event.clear()
            self._shutdown_event.clear()
            
            async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
                await self._handle_client(reader, writer)
            
            self._server = await asyncio.start_server(
                handle_client,
                host="0.0.0.0",
                port=self.port,
            )
            
            self._server_task = asyncio.create_task(self._run_server())
            logger.info(f"iFlow OAuth 服务器已启动，端口: {self.port}")
            return True
        except Exception as e:
            logger.error(f"启动 iFlow OAuth 服务器失败: {e}")
            return False
    
    async def _run_server(self):
        """运行服务器"""
        try:
            async with self._server:
                await self._server.serve_forever()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"OAuth 服务器运行异常: {e}")
    
    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """处理客户端请求"""
        try:
            data = await reader.read(4096)
            if not data:
                return
            
            request_text = data.decode('utf-8', errors='ignore')
            
            # 解析 HTTP 请求
            lines = request_text.split('\r\n')
            if not lines:
                return
            
            # 获取请求行
            request_line = lines[0]
            parts = request_line.split(' ')
            if len(parts) < 2:
                return
            
            path = parts[1]
            
            # 解析查询参数
            if '?' in path:
                path, query_string = path.split('?', 1)
            else:
                query_string = ""
            
            # 解析 OAuth 回调参数
            params = {}
            for param in query_string.split('&'):
                if '=' in param:
                    key, value = param.split('=', 1)
                    params[key] = value
            
            # 检查是否是 OAuth 回调
            if path == '/oauth2callback':
                code = params.get('code', '')
                state = params.get('state', '')
                error_param = params.get('error', '')
                
                if error_param:
                    self._result = {"error": error_param}
                    response_body = f"<html><body><h1>认证失败</h1><p>Error: {error_param}</p><script>setTimeout(function(){{window.location.href='https://iflow.cn/oauth/error';}}, 3000);</script></body></html>"
                elif not code:
                    self._result = {"error": "missing_code"}
                    response_body = "<html><body><h1>认证失败</h1><p>未收到授权码</p><script>setTimeout(function(){{window.location.href='https://iflow.cn/oauth/error';}}, 3000);</script></body></html>"
                else:
                    self._result = {"code": code, "state": state}
                    response_body = f"<html><body><h1>认证成功</h1><p>正在跳转...</p><script>setTimeout(function(){{window.location.href='{IFLOW_SUCCESS_REDIRECT_URL}';}}, 2000);</script></body></html>"
                    logger.info(f"收到 OAuth 回调: code={code[:20]}..., state={state}")
                
                # 发送 HTTP 响应
                response = (
                    "HTTP/1.1 200 OK\r\n"
                    "Content-Type: text/html; charset=utf-8\r\n"
                    f"Content-Length: {len(response_body)}\r\n"
                    "Connection: close\r\n"
                    "\r\n"
                ) + response_body
                writer.write(response.encode('utf-8'))
                await writer.drain()
                writer.close()
                await writer.wait_closed()
                
                # 设置事件通知结果已就绪
                self._result_event.set()
                return
            
            # 其他路径返回 404
            response_body = "Not Found"
            response = (
                "HTTP/1.1 404 Not Found\r\n"
                "Content-Type: text/plain\r\n"
                f"Content-Length: {len(response_body)}\r\n"
                "Connection: close\r\n"
                "\r\n"
            ) + response_body
            writer.write(response.encode('utf-8'))
            await writer.drain()
            writer.close()
            await writer.wait_closed()
                
        except Exception as e:
            logger.error(f"处理 OAuth 请求时出错: {e}")
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass
    
    async def wait_for_callback(self, timeout: float = 300.0) -> Optional[Dict[str, str]]:
        """等待 OAuth 回调"""
        try:
            await asyncio.wait_for(self._result_event.wait(), timeout=timeout)
            return self._result
        except asyncio.TimeoutError:
            logger.warning("等待 OAuth 回调超时")
            return None
    
    async def stop(self):
        """停止服务器"""
        self._shutdown_event.set()
        if self._server_task:
            self._server_task.cancel()
            try:
                await self._server_task
            except asyncio.CancelledError:
                pass
        if self._server:
            self._server.close()
            await self._server.wait_closed()
        logger.info("iFlow OAuth 服务器已停止")


class IFlowAuthService:
    """iFlow 认证服务"""
    
    def __init__(self):
        self.http_client: Optional[httpx.AsyncClient] = None
    
    def _get_http_client(self) -> httpx.AsyncClient:
        """获取 HTTP 客户端"""
        if self.http_client is None:
            self.http_client = httpx.AsyncClient(timeout=30.0)
        return self.http_client
    
    async def close(self):
        """关闭 HTTP 客户端"""
        if self.http_client:
            await self.http_client.aclose()
            self.http_client = None
    
    def get_authorization_url(self, state: str, port: int = IFLOW_CALLBACK_PORT) -> tuple:
        """生成授权 URL"""
        redirect_uri = f"http://localhost:{port}/oauth2callback"
        params = {
            "loginMethod": "phone",
            "type": "phone",
            "redirect": redirect_uri,
            "state": state,
            "client_id": IFLOW_OAUTH_CLIENT_ID,
        }
        
        from urllib.parse import urlencode
        auth_url = f"{IFLOW_OAUTH_AUTHORIZE_ENDPOINT}?{urlencode(params)}"
        
        return auth_url, redirect_uri
    
    async def exchange_code_for_tokens(self, code: str, redirect_uri: str) -> Optional[IFlowTokenData]:
        """使用授权码交换 Token"""
        client = self._get_http_client()
        
        # 构建 Basic Auth 头
        credentials = f"{IFLOW_OAUTH_CLIENT_ID}:{IFLOW_OAUTH_CLIENT_SECRET}"
        auth_header = base64.b64encode(credentials.encode()).decode()
        
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
        }
        
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
            "Authorization": f"Basic {auth_header}",
        }
        
        try:
            response = await client.post(
                IFLOW_OAUTH_TOKEN_ENDPOINT,
                data=data,
                headers=headers,
            )
            
            if response.status_code != 200:
                logger.error(f"Token 交换失败: {response.status_code} - {response.text}")
                return None
            
            token_resp = response.json()
            
            # 获取用户信息
            user_info = await self._fetch_user_info(token_resp.get("access_token", ""))
            if not user_info:
                logger.error("获取用户信息失败")
                return None
            
            # 检查 API Key
            api_key = user_info.get("apiKey", "")
            if not api_key:
                logger.error("用户 API Key 为空")
                return None
            
            # 获取邮箱
            email = user_info.get("email", "") or user_info.get("phone", "")
            if not email:
                logger.error("用户邮箱/手机号为空")
                return None
            
            token_data = IFlowTokenData(
                access_token=token_resp.get("access_token", ""),
                refresh_token=token_resp.get("refresh_token", ""),
                token_type=token_resp.get("token_type", "Bearer"),
                scope=token_resp.get("scope", ""),
                expire=datetime.fromtimestamp(
                    datetime.now().timestamp() + token_resp.get("expires_in", 3600),
                    tz=timezone.utc
                ).isoformat(),
                api_key=api_key,
                email=email,
            )
            
            return token_data
            
        except Exception as e:
            logger.error(f"Token 交换异常: {e}")
            return None
    
    async def refresh_tokens(self, refresh_token: str) -> Optional[IFlowTokenData]:
        """刷新访问令牌"""
        if not refresh_token:
            return None
        
        client = self._get_http_client()
        
        credentials = f"{IFLOW_OAUTH_CLIENT_ID}:{IFLOW_OAUTH_CLIENT_SECRET}"
        auth_header = base64.b64encode(credentials.encode()).decode()
        
        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        }
        
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
            "Authorization": f"Basic {auth_header}",
        }
        
        try:
            response = await client.post(
                IFLOW_OAUTH_TOKEN_ENDPOINT,
                data=data,
                headers=headers,
            )
            
            if response.status_code != 200:
                logger.error(f"Token 刷新失败: {response.status_code} - {response.text}")
                return None
            
            token_resp = response.json()
            
            token_data = IFlowTokenData(
                access_token=token_resp.get("access_token", ""),
                refresh_token=token_resp.get("refresh_token", ""),
                token_type=token_resp.get("token_type", "Bearer"),
                scope=token_resp.get("scope", ""),
                expire=datetime.fromtimestamp(
                    datetime.now().timestamp() + token_resp.get("expires_in", 3600),
                    tz=timezone.utc
                ).isoformat(),
            )
            
            return token_data
            
        except Exception as e:
            logger.error(f"Token 刷新异常: {e}")
            return None
    
    async def _fetch_user_info(self, access_token: str) -> Optional[Dict[str, Any]]:
        """获取用户信息"""
        if not access_token:
            return None
        
        client = self._get_http_client()
        
        try:
            url = f"{IFLOW_USER_INFO_ENDPOINT}?accessToken={access_token}"
            response = await client.get(url)
            
            if response.status_code != 200:
                logger.error(f"获取用户信息失败: {response.status_code} - {response.text}")
                return None
            
            resp_data = response.json()
            if not resp_data.get("success"):
                logger.error(f"获取用户信息失败: {resp_data}")
                return None
            
            return resp_data.get("data")
            
        except Exception as e:
            logger.error(f"获取用户信息异常: {e}")
            return None
    
    async def authenticate_with_cookie(self, cookie: str) -> Optional[IFlowTokenData]:
        """使用 Cookie 进行认证"""
        try:
            normalized_cookie = normalize_cookie(cookie)
        except ValueError as e:
            logger.error(f"Cookie 认证失败: {e}")
            return None
        
        client = self._get_http_client()
        
        try:
            # 获取 API Key 信息（GET 请求）
            headers = {
                "Cookie": normalized_cookie,
                "Accept": "application/json, text/plain, */*",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            }
            
            response = await client.get(IFLOW_API_KEY_ENDPOINT, headers=headers)
            
            if response.status_code != 200:
                logger.error(f"获取 API Key 失败: {response.status_code} - {response.text}")
                return None
            
            resp_data = response.json()
            if not resp_data.get("success"):
                logger.error(f"获取 API Key 失败: {resp_data}")
                return None
            
            key_data = resp_data.get("data", {})
            api_key = key_data.get("apiKey") or key_data.get("apiKeyMask", "")
            name = key_data.get("name", "")
            
            if not api_key:
                logger.error("API Key 为空")
                return None
            
            # 刷新 API Key（POST 请求）
            refresh_data = {"name": name}
            headers["Content-Type"] = "application/json"
            headers["Origin"] = "https://platform.iflow.cn"
            headers["Referer"] = "https://platform.iflow.cn/"
            
            refresh_response = await client.post(
                IFLOW_API_KEY_ENDPOINT,
                json=refresh_data,
                headers=headers,
            )
            
            if refresh_response.status_code != 200:
                logger.error(f"刷新 API Key 失败: {refresh_response.status_code}")
                return None
            
            refresh_data = refresh_response.json()
            if not refresh_data.get("success"):
                logger.error(f"刷新 API Key 失败: {refresh_data}")
                return None
            
            refreshed_key = refresh_data.get("data", {})
            
            token_data = IFlowTokenData(
                api_key=refreshed_key.get("apiKey", ""),
                email=name,
                expire=refreshed_key.get("expireTime", ""),
                cookie=normalized_cookie,
            )
            
            return token_data
            
        except Exception as e:
            logger.error(f"Cookie 认证异常: {e}")
            return None
    
    def create_token_storage(self, token_data: Optional[IFlowTokenData]) -> Optional[IFlowTokenStorage]:
        """创建 Token 存储对象"""
        if token_data is None:
            return None
        
        return IFlowTokenStorage(
            access_token=token_data.access_token,
            refresh_token=token_data.refresh_token,
            last_refresh=datetime.now(timezone.utc).isoformat(),
            expire=token_data.expire,
            api_key=token_data.api_key,
            email=token_data.email,
            token_type=token_data.token_type,
            scope=token_data.scope,
            cookie=token_data.cookie,
            auth_type="oauth" if token_data.cookie == "" else "cookie",
        )
    
    def save_auth(self, token_storage: IFlowTokenStorage) -> str:
        """保存认证信息到文件"""
        filename = generate_auth_filename(token_storage.email)
        file_path = IFLOW_AUTH_DIR / filename
        
        file_data = token_storage.to_file_dict()
        file_path.write_text(json.dumps(file_data, indent=2, ensure_ascii=False))
        
        logger.info(f"保存认证信息: {filename}")
        return str(file_path)
    
    def load_auth(self, email: str) -> Optional[IFlowTokenStorage]:
        """加载认证信息"""
        for file_path in IFLOW_AUTH_DIR.glob("iflow-*.json"):
            try:
                data = json.loads(file_path.read_text())
                if data.get("email") == email:
                    return IFlowTokenStorage.from_dict(data)
            except Exception as e:
                logger.warning(f"加载认证文件失败: {file_path} - {e}")
                continue
        
        return None
    
    def load_all_auths(self) -> list:
        """加载所有认证信息"""
        auths = []
        for file_path in IFLOW_AUTH_DIR.glob("iflow-*.json"):
            try:
                data = json.loads(file_path.read_text())
                auths.append(IFlowTokenStorage.from_dict(data))
            except Exception as e:
                logger.warning(f"加载认证文件失败: {file_path} - {e}")
                continue
        
        return auths


class IFlowExecutorService:
    """iFlow API 执行器服务"""
    
    def __init__(self):
        self.http_client: Optional[httpx.AsyncClient] = None
        self._auth_service = IFlowAuthService()
    
    def _get_http_client(self) -> httpx.AsyncClient:
        """获取 HTTP 客户端"""
        if self.http_client is None:
            self.http_client = httpx.AsyncClient(timeout=120.0)
        return self.http_client
    
    @staticmethod
    def _build_iflow_headers(api_key: str, stream: bool = False) -> dict:
        """构建 iFlow API 请求头（含签名，与 Go 项目保持一致）"""
        session_id = f"session-{uuid.uuid4()}"
        timestamp = int(time_module.time() * 1000)  # 毫秒时间戳
        user_agent = "iFlow-Cli"
        
        # HMAC-SHA256 签名: payload = "userAgent:sessionId:timestamp"
        payload = f"{user_agent}:{session_id}:{timestamp}"
        signature = hmac.new(
            api_key.encode('utf-8'),
            payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "User-Agent": user_agent,
            "session-id": session_id,
            "x-iflow-timestamp": str(timestamp),
            "x-iflow-signature": signature,
        }
        
        if stream:
            headers["Accept"] = "text/event-stream"
        else:
            headers["Accept"] = "application/json"
        
        return headers
    
    async def close(self):
        """关闭 HTTP 客户端"""
        if self.http_client:
            await self.http_client.aclose()
            self.http_client = None
        await self._auth_service.close()
    
    async def _ensure_auth_valid(self, auth_storage: IFlowTokenStorage) -> IFlowTokenStorage:
        """确保认证信息有效，必要时自动刷新（与 Go 项目 Refresh 逻辑保持一致）"""
        # 检查是否需要刷新
        needs_refresh = False
        
        if auth_storage.expire:
            try:
                expire_time = datetime.fromisoformat(auth_storage.expire.replace('Z', '+00:00'))
                now = datetime.now(timezone.utc)
                # 提前2天刷新，与 Go 项目 ShouldRefreshAPIKey 保持一致
                if expire_time <= now + __import__('datetime').timedelta(days=2):
                    needs_refresh = True
                    logger.info(f"Token 即将过期或已过期 (expire: {auth_storage.expire})，需要刷新")
            except Exception as e:
                logger.warning(f"解析过期时间失败: {e}，尝试刷新")
                needs_refresh = True
        
        if not needs_refresh:
            return auth_storage
        
        # Cookie 认证刷新
        if auth_storage.cookie and auth_storage.auth_type == "cookie":
            logger.info(f"使用 Cookie 刷新 API Key: {auth_storage.email}")
            try:
                token_data = await self._auth_service.authenticate_with_cookie(auth_storage.cookie)
                if token_data and token_data.api_key:
                    auth_storage.api_key = token_data.api_key
                    auth_storage.expire = token_data.expire
                    auth_storage.last_refresh = datetime.now(timezone.utc).isoformat()
                    # 保存更新后的认证信息
                    self._auth_service.save_auth(
                        self._auth_service.create_token_storage(token_data)
                    )
                    logger.info(f"Cookie 刷新成功，新过期时间: {token_data.expire}")
                else:
                    logger.error("Cookie 刷新失败，使用现有 token 继续")
            except Exception as e:
                logger.error(f"Cookie 刷新异常: {e}，使用现有 token 继续")
        
        # OAuth 认证刷新
        elif auth_storage.refresh_token:
            logger.info(f"使用 refresh_token 刷新 OAuth Token: {auth_storage.email}")
            try:
                token_data = await self._auth_service.refresh_tokens(auth_storage.refresh_token)
                logger.info(f"refresh_tokens 返回: token_data={token_data is not None}, access_token={bool(token_data.access_token) if token_data else 'N/A'}, refresh_token={bool(token_data.refresh_token) if token_data else 'N/A'}")
                if token_data and token_data.access_token:
                    # 刷新 token 后需要重新获取用户信息（含新的 api_key）
                    user_info = await self._auth_service._fetch_user_info(token_data.access_token)
                    if user_info and user_info.get("apiKey"):
                        auth_storage.api_key = user_info["apiKey"]
                        token_data.api_key = user_info["apiKey"]
                        token_data.email = auth_storage.email
                    
                    auth_storage.access_token = token_data.access_token
                    if token_data.refresh_token:
                        auth_storage.refresh_token = token_data.refresh_token
                    auth_storage.expire = token_data.expire
                    auth_storage.last_refresh = datetime.now(timezone.utc).isoformat()
                    
                    # 保存更新后的认证信息
                    self._auth_service.save_auth(
                        self._auth_service.create_token_storage(token_data)
                    )
                    logger.info(f"OAuth 刷新成功，新过期时间: {token_data.expire}")
                else:
                    logger.error("OAuth token 继续")
            except Exception as e:
                logger.error(f"OAuth 刷新异常: {e}，使用现有 token 继续")
        else:
            logger.warning("无可用刷新方式（无 cookie 也无 refresh_token），使用现有 token 继续")
        
        return auth_storage
    
    async def execute_chat_completion(
        self,
        auth_storage: IFlowTokenStorage,
        request: IFlowChatCompletionRequest,
    ) -> IFlowChatCompletionResponse:
        """执行 Chat Completion 请求"""
        # 执行前自动刷新过期 token
        auth_storage = await self._ensure_auth_valid(auth_storage)
        
        client = self._get_http_client()
        
        # 构建请求体
        request_body = {
            "model": request.model,
            "messages": [{"role": msg.role, "content": msg.content} for msg in request.messages],
            "stream": request.stream,
        }
        
        # 添加可选参数
        if request.max_tokens is not None:
            request_body["max_tokens"] = request.max_tokens
        if request.temperature is not None:
            request_body["temperature"] = request.temperature
        if request.top_p is not None:
            request_body["top_p"] = request.top_p
        if request.presence_penalty is not None:
            request_body["presence_penalty"] = request.presence_penalty
        if request.frequency_penalty is not None:
            request_body["frequency_penalty"] = request.frequency_penalty
        if request.reasoning_effort is not None:
            request_body["reasoning_effort"] = request.reasoning_effort
        
        headers = self._build_iflow_headers(auth_storage.api_key, stream=False)
        
        endpoint = f"{IFLOW_DEFAULT_API_BASE_URL}/chat/completions"
        
        logger.info(f"发送 Chat Completion 请求到 iFlow API - model: {request.model}, stream: {request.stream}")
        logger.debug(f"iFlow API endpoint: {endpoint}")
        logger.debug(f"消息数量: {len(request.messages)}")
        
        try:
            response = await client.post(
                endpoint,
                json=request_body,
                headers=headers,
            )
            
            if response.status_code not in (200, 201):
                logger.error(f"Chat Completion 失败: {response.status_code} - {response.text}")
                raise Exception(f"API 请求失败: {response.status_code}")
            
            resp_data = response.json()
            logger.debug(f"iFlow API 原始响应状态: {response.status_code}")
            logger.debug(f"iFlow API 原始响应: {resp_data}")
            
            # 提取 choices - 尝试多种可能的字段名
            choices = resp_data.get("choices", [])
            if not choices:
                # 尝试从 data 字段获取
                if "data" in resp_data and isinstance(resp_data["data"], dict):
                    choices = resp_data["data"].get("choices", [])
                    logger.debug(f"从 data.dict 获取 choices: {len(choices)}")
                elif "data" in resp_data and isinstance(resp_data["data"], list):
                    choices = resp_data["data"]
                    logger.debug(f"从 data.list 获取 choices: {len(choices)}")
            
            if not choices:
                logger.warning(f"响应中没有找到 choices，完整响应: {resp_data}")
                # 返回空 choices 但保持响应结构
                choices = []
            else:
                logger.info(f"成功提取 {len(choices)} 个 choices")
            
            # 标准化 choices 结构 - 确保每个 choice 有 message 字段
            standardized_choices = []
            if choices and isinstance(choices, list):
                for i, choice in enumerate(choices):
                    if not isinstance(choice, dict):
                        logger.warning(f"Choice {i} 不是字典: {choice}")
                        continue
                    
                    standardized_choice = {
                        "index": choice.get("index", i),
                        "message": choice.get("message", {}),
                        "finish_reason": choice.get("finish_reason", "stop"),
                    }
                    
                    # 如果 choice 有 delta 字段（流式响应），使用 delta
                    if "delta" in choice:
                        standardized_choice["delta"] = choice["delta"]
                        logger.debug(f"Choice {i} 包含 delta 字段（流式响应）")
                    
                    # 如果 choice 有 content 字段但没有 message，尝试提取
                    if not standardized_choice["message"] and "content" in choice:
                        standardized_choice["message"] = {
                            "role": choice.get("role", "assistant"),
                            "content": choice.get("content", ""),
                        }
                        logger.debug(f"Choice {i} 从 content 字段提取消息")
                    
                    # 确保 message 有 content 字段
                    if "content" not in standardized_choice["message"]:
                        standardized_choice["message"]["content"] = ""
                    
                    standardized_choices.append(standardized_choice)
                    logger.debug(f"Choice {i} 标准化后: {standardized_choice}")
            
            choices = standardized_choices
            
            # 提取其他字段，处理可能的嵌套结构
            response_id = resp_data.get("id", f"iflow-{datetime.now().timestamp()}")
            created = resp_data.get("created", int(datetime.now().timestamp()))
            model = resp_data.get("model", request.model)
            usage = resp_data.get("usage")
            
            logger.info(f"响应字段 - id: {response_id}, created: {created}, model: {model}")
            if usage:
                logger.info(f"Usage - prompt_tokens: {usage.get('prompt_tokens')}, completion_tokens: {usage.get('completion_tokens')}, total_tokens: {usage.get('total_tokens')}")
            
            # 转换为标准 OpenAI 格式响应
            return IFlowChatCompletionResponse(
                id=response_id,
                object="chat.completion",
                created=created,
                model=model,
                choices=choices,
                usage=usage,
            )
            
        except Exception as e:
            logger.error(f"Chat Completion 异常: {e}")
            import traceback
            logger.error(f"堆栈跟踪: {traceback.format_exc()}")
            raise
    
    async def execute_chat_completion_stream(
        self,
        auth_storage: IFlowTokenStorage,
        request: IFlowChatCompletionRequest,
    ) -> AsyncGenerator[str, None]:
        """执行流式 Chat Completion 请求"""
        # 执行前自动刷新过期 token
        auth_storage = await self._ensure_auth_valid(auth_storage)
        
        client = self._get_http_client()
        
        # 构建请求体
        request_body = {
            "model": request.model,
            "messages": [{"role": msg.role, "content": msg.content} for msg in request.messages],
            "stream": True,
        }
        
        # 添加可选参数
        if request.max_tokens is not None:
            request_body["max_tokens"] = request.max_tokens
        if request.temperature is not None:
            request_body["temperature"] = request.temperature
        if request.top_p is not None:
            request_body["top_p"] = request.top_p
        if request.presence_penalty is not None:
            request_body["presence_penalty"] = request.presence_penalty
        if request.frequency_penalty is not None:
            request_body["frequency_penalty"] = request.frequency_penalty
        if request.reasoning_effort is not None:
            request_body["reasoning_effort"] = request.reasoning_effort
        
        headers = self._build_iflow_headers(auth_storage.api_key, stream=True)
        
        endpoint = f"{IFLOW_DEFAULT_API_BASE_URL}/chat/completions"
        
        logger.info(f"发送流式请求到 iFlow API - model: {request.model}")
        logger.debug(f"iFlow endpoint: {endpoint}")
        logger.debug(f"Headers: {headers}")
        
        try:
            async with client.stream(
                "POST",
                endpoint,
                json=request_body,
                headers=headers,
            ) as response:
                logger.info(f"iFlow API 响应状态码: {response.status_code}")
                logger.debug(f"iFlow 响应头: {dict(response.headers)}")
                
                if response.status_code not in (200, 201):
                    error_text = await response.aread()
                    logger.error(f"流式 Chat Completion 失败: {response.status_code} - {error_text}")
                    raise Exception(f"API 请求失败: {response.status_code}")
                
                chunk_count = 0
                raw_chunk_count = 0
                
                async for line in response.aiter_lines():
                    raw_chunk_count += 1
                    
                    # 跳过空行
                    if not line or line.strip() == "":
                        continue
                    
                    # SSE 格式处理
                    if line.startswith("data: "):
                        data = line[6:]  # 提取 JSON 数据
                        
                        if data == "[DONE]":
                            # 发送 [DONE] 信号
                            yield "data: [DONE]\n\n"
                            break
                        
                        # 尝试解析 JSON 用于日志
                        try:
                            import json as json_module
                            data_obj = json_module.loads(data)
                            choice_content = data_obj.get("choices", [{}])[0].get("delta", {}).get("content", "") or \
                                           data_obj.get("choices", [{}])[0].get("message", {}).get("content", "")
                            logger.info(f"SSE内容: {choice_content[:30]}..." if len(choice_content) > 30 else f"SSE内容: {choice_content}")
                        except:
                            pass
                        
                        # 严格按照 SSE 格式: data: <json>\n\n
                        yield f"data: {data}\n\n"
                    elif line.startswith(":") or line.startswith("event:") or line.startswith("id:") or line.startswith("retry:"):
                        # SSE 元信息行，跳过
                        continue
                    else:
                        # 其他行，直接转发
                        yield f"{line}\n\n"
                
                logger.info(f"流式响应完成，共 {raw_chunk_count} 行")
                        
        except Exception as e:
            logger.error(f"流式 Chat Completion 异常: {e}")
            import traceback
            logger.error(f"堆栈跟踪: {traceback.format_exc()}")
            # 发送错误信息
            import json
            error_data = json.dumps({"error": {"message": str(e), "type": "server_error"}})
            yield f"data: {error_data}\n\n"
            yield "data: [DONE]\n\n"


# 全局服务实例
iflow_auth_service = IFlowAuthService()
iflow_executor_service = IFlowExecutorService()


__all__ = [
    "IFlowOAuthServer",
    "IFlowAuthService",
    "IFlowExecutorService",
    "iflow_auth_service",
    "iflow_executor_service",
]
