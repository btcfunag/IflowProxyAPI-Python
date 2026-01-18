---
AIGC:
    ContentProducer: Minimax Agent AI
    ContentPropagator: Minimax Agent AI
    Label: AIGC
    ProduceID: "00000000000000000000000000000000"
    PropagateID: "00000000000000000000000000000000"
    ReservedCode1: 304502210097fba00ffa993ea2983bea5ed968aaee6cb686f673cc491539a5bbb8ac4e02e102207706c6764d826227d0ac019f6c5d08fbbe47ff753fa2d52f7d91ac7e793d3f02
    ReservedCode2: 304502210093ef238b24e24dc9b68e73d201cfb0a5e5bd6e9f8e5e396642c2a74cd027c19302206e37677172bfb0c2845fec77bc7ffed871302d3a826bdd34c5646e71cf7e5005
---

# iFlow 安卓端登录方案

## 现状分析

当前 iFlow 的 OAuth 登录流程存在以下限制，不适合直接用于安卓端：

**现有流程的问题：**
- 依赖本地回调服务器（`localhost:11451/oauth2callback`），在安卓设备上无法使用
- 授权 URL 使用 `http://localhost:{port}/oauth2callback`，只能在开发机器上接收回调
- 登录流程需要启动本地 HTTP 服务器接收授权码，不适用于移动端场景
- 安卓应用无法绑定到 localhost 端口接收 OAuth 回调

**现有登录方式：**
```python
# 当前 OAuth 流程
redirect_uri = f"http://localhost:{port}/oauth2callback"
auth_url = f"{IFLOW_OAUTH_AUTHORIZE_ENDPOINT}?{urlencode(params)}"
```

## 推荐方案

### 方案一：OAuth 授权码模式 + PKCE（推荐）

适用于原生安卓应用，采用 Proof Key for Code Exchange（PKCE）扩展，安全性高。

**核心思路：**
1. 安卓应用生成 `code_verifier` 和 `code_challenge`
2. 用户通过系统浏览器或应用内 WebView 完成授权
3. 授权完成后，iFlow 服务器将授权码返回给回调 URL
4. 安卓应用使用授权码和 `code_verifier` 交换 Access Token

**实现步骤：**

**步骤 1：修改授权 URL 生成逻辑**

```python
# 新增 PKCE 相关函数
import hashlib
import base64
import secrets
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

def generate_pkce_pair():
    """生成 PKCE 的 code_verifier 和 code_challenge"""
    # 生成 code_verifier (43-128个字符)
    code_verifier = secrets.token_urlsafe(64)[:128]
    
    # 生成 code_challenge (S256 哈希)
    digest = hashlib.sha256(code_verifier.encode()).digest()
    code_challenge = base64.urlsafe_b64encode(digest).decode().rstrip('=')
    
    return code_verifier, code_challenge

def generate_state():
    """生成防 CSRF 攻击的 state 参数"""
    return secrets.token_urlsafe(32)
```

**步骤 2：新增移动端登录 API**

```python
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import httpx

router = APIRouter()

class MobileLoginRequest(BaseModel):
    """移动端登录请求"""
    callback_url: str  # 安卓应用的回调 URL
    state: Optional[str] = None

class MobileLoginResponse(BaseModel):
    """移动端登录响应"""
    success: bool
    auth_url: str  # 用于在浏览器中打开的授权 URL
    state: str
    expires_in: int  # 授权码有效期（秒）

@router.post("/iflow/login/mobile", response_model=MobileLoginResponse)
async def mobile_login(request: MobileLoginRequest):
    """
    移动端登录 - 生成授权 URL
    
    安卓应用调用此接口获取授权 URL，然后在系统浏览器中打开。
    用户在浏览器中完成登录后，会重定向到 callback_url，
    携带 authorization_code 和 state 参数。
    
    安卓应用需要：
    1. 拦截 callback_url 的请求，获取 authorization_code
    2. 使用 authorization_code 交换 Access Token
    """
    auth_service = get_auth_service()
    
    # 生成 PKCE 验证参数
    code_verifier, code_challenge = generate_pkce_pair()
    state = request.state or generate_state()
    
    # 生成授权 URL
    # 注意：需要 iFlow 服务器支持 PKCE 和自定义回调 URL
    params = {
        "loginMethod": "phone",
        "type": "phone",
        "redirect": request.callback_url,
        "state": state,
        "client_id": IFLOW_OAUTH_CLIENT_ID,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "response_type": "code",
    }
    
    from urllib.parse import urlencode
    auth_url = f"{IFLOW_OAUTH_AUTHORIZE_ENDPOINT}?{urlencode(params)}"
    
    # 存储 code_verifier（实际项目中应存储到数据库或 Redis）
    # 这里简化为返回给客户端，客户端需要安全存储
    logger.info(f"生成移动端授权 URL: {auth_url}")
    
    return MobileLoginResponse(
        success=True,
        auth_url=auth_url,
        state=state,
        expires_in=600,  # 10分钟有效
    )

@router.post("/iflow/token/exchange")
async def exchange_token(authorization_code: str, code_verifier: str, redirect_uri: str):
    """
    使用授权码交换 Access Token
    
    安卓应用在获取到 authorization_code 后，调用此接口交换 Token。
    """
    auth_service = get_auth_service()
    
    # 验证 code_verifier（需要从存储中获取或由客户端提供）
    # 实际项目中应验证 code_challenge 是否匹配
    
    token_data = await auth_service.exchange_code_for_tokens(
        code=authorization_code,
        redirect_uri=redirect_uri,
    )
    
    if token_data is None:
        raise HTTPException(status_code=400, detail="授权码无效或已过期")
    
    return {
        "success": True,
        "access_token": token_data.access_token,
        "refresh_token": token_data.refresh_token,
        "token_type": token_data.token_type,
        "expires_in": 3600,
        "email": token_data.email,
        "api_key": token_data.api_key,
    }
```

**步骤 3：安卓应用集成示例（伪代码）**

```kotlin
// 安卓 Kotlin 示例
class IFlowLoginManager {
    
    suspend fun startLogin(activity: Activity): Result<LoginResult> {
        // 1. 调用后端 API 获取授权 URL
        val loginResponse = apiService.getMobileLoginUrl(
            callbackUrl = "myapp://oauth/callback"
        )
        
        // 2. 在系统浏览器中打开授权页面
        val intent = Intent(Intent.ACTION_VIEW, Uri.parse(loginResponse.authUrl))
        activity.startActivity(intent)
        
        // 3. 等待用户完成授权（通过 Deep Link 回调）
        return waitForCallback()
    }
    
    suspend fun exchangeToken(authorizationCode: String): Result<TokenResult> {
        return apiService.exchangeToken(
            authorizationCode = authorizationCode,
            codeVerifier = storedCodeVerifier,
            redirectUri = "myapp://oauth/callback"
        )
    }
}

// Deep Link 处理
class OAuthCallbackActivity : Activity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        
        val uri = intent.data
        val code = uri?.getQueryParameter("code")
        val state = uri?.getQueryParameter("state")
        
        // 获取 token 并保存
        lifecycleScope.launch {
            val result = loginManager.exchangeToken(code!!)
            if (result.isSuccess) {
                // 保存 token 到本地存储
                saveToken(result.getOrNull()!!)
            }
        }
    }
}
```

### 方案二：设备授权流（Device Flow）

适用于没有浏览器或输入困难的设备，如命令行工具、智能电视等。虽然主要不是为安卓设计，但可以作为备选方案。

**流程说明：**
1. 设备向认证服务器请求设备代码和用户代码
2. 用户在另一台设备（手机/电脑）上访问验证URL，输入用户代码
3. 设备轮询认证服务器，等待用户完成授权
4. 授权完成后，设备获取 Access Token

**实现代码：**

```python
@router.post("/iflow/login/device")
async def device_login():
    """
    设备授权流 - 适用于没有浏览器的设备
    
    返回：
    - device_code: 设备用于轮询的代码
    - user_code: 用户在浏览器中输入的代码
    - verification_uri: 用户访问的验证页面
    - expires_in: 有效期
    - interval: 轮询间隔
    """
    device_code = secrets.token_urlsafe(32)
    user_code = secrets.token_urlsafe(8).upper()[:8]
    
    return {
        "success": True,
        "device_code": device_code,
        "user_code": user_code,
        "verification_uri": f"https://iflow.cn/oauth/device?code={user_code}",
        "expires_in": 1800,  # 30分钟
        "interval": 5,  # 轮询间隔 5 秒
    }

@router.post("/iflow/login/device/token")
async def device_token_request(device_code: str, grant_type: str = "urn:ietf:params:oauth:grant-type:device_code"):
    """
    设备轮询获取 Token
    
    设备定期调用此接口检查用户是否完成授权。
    """
    # 检查授权状态
    # 返回 access_token 或等待状态
```

### 方案三：简化版 URL 登录（临时方案）

如果 iFlow 服务器不支持 PKCE，可以采用简化方案：生成一次性登录链接。

**实现思路：**

```python
@router.post("/iflow/login/url")
async def generate_login_url(request: LoginUrlRequest):
    """
    生成一次性登录 URL
    
    返回一个 URL，包含一次性 token。
    用户在浏览器中打开此 URL 登录后，系统会记录登录状态。
    安卓应用通过轮询或 WebSocket 获取登录结果。
    """
    import uuid
    
    # 生成一次性登录 token
    login_token = str(uuid.uuid4())
    session_id = secrets.token_urlsafe(16)
    
    # 存储登录会话（使用 Redis 或内存）
    login_sessions[login_token] = {
        "session_id": session_id,
        "created_at": datetime.now(),
        "status": "pending",
        "callback_url": request.callback_url,
    }
    
    # 生成登录 URL
    login_url = f"https://iflow.cn/login/token/{login_token}?callback={request.callback_url}"
    
    return {
        "success": True,
        "login_url": login_url,
        "session_id": session_id,
        "expires_in": 600,  # 10分钟有效
    }

@router.get("/iflow/login/status/{session_id}")
async def check_login_status(session_id: str):
    """
    检查登录状态
    
    安卓应用轮询此接口获取登录结果。
    """
    # 查询登录会话状态
    session = login_sessions.get(session_id)
    
    if session is None:
        raise HTTPException(status_code=404, detail="登录会话不存在")
    
    if session["status"] == "completed":
        # 返回认证信息
        return {
            "success": True,
            "status": "completed",
            "email": session["email"],
            "api_key": session["api_key"],
        }
    elif session["status"] == "failed":
        raise HTTPException(status_code=401, detail="登录失败")
    else:
        return {
            "success": True,
            "status": "pending",
        }
```

### 方案四：Cookie 认证（现有方案优化）

利用现有的 Cookie 认证方式，在安卓应用中提供更好的用户体验。

**优化思路：**
1. 在安卓应用中内置一个小型 HTTP 服务器
2. 用户在浏览器中完成登录后，将 Cookie 复制到应用
3. 或通过 QR 码扫码方式传递 Cookie

```python
@router.post("/iflow/login/qr")
async def generate_qr_login():
    """
    生成二维码登录
    
    返回一个包含登录会话信息的二维码。
    用户使用手机浏览器扫描二维码，在手机浏览器中完成登录。
    登录完成后，服务器将认证信息同步到桌面应用。
    """
    import qrcode
    import io
    import base64
    
    session_id = secrets.token_urlsafe(16)
    login_url = f"https://iflow.cn/login/qr/{session_id}"
    
    # 生成二维码
    qr = qrcode.QRCode(version=1, box_size=10, border=2)
    qr.add_data(login_url)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='PNG')
    qr_base64 = base64.b64encode(img_byte_arr.getvalue()).decode()
    
    return {
        "success": True,
        "qr_code": f"data:image/png;base64,{qr_base64}",
        "session_id": session_id,
        "login_url": login_url,
    }
```

## 方案对比

| 特性 | PKCE 方案 | 设备流 | 简化 URL | Cookie 优化 |
|------|----------|--------|----------|-------------|
| **安全性** | 高 | 中 | 低 | 中 |
| **用户体验** | 好 | 一般 | 一般 | 较好 |
| **服务器改动** | 中 | 小 | 小 | 小 |
| **iFlow 兼容** | 需要服务器支持 | 需要服务器支持 | 需要服务器支持 | 无需改动 |
| **适用场景** | 原生 App | CLI/TV | 快速集成 | 跨设备登录 |
| **Token 刷新** | 支持 | 支持 | 需额外实现 | 不支持 |

## 实施建议

### 首选方案：PKCE + 移动端回调

1. **后端改动：**
   - 修改 `get_authorization_url` 方法支持 PKCE 参数
   - 新增 `POST /api/iflow/login/mobile` 接口生成授权 URL
   - 新增 `POST /api/iflow/token/exchange` 接口交换 Token
   - 实现 `code_verifier` 验证逻辑

2. **安卓端改动：**
   - 使用系统浏览器打开授权 URL（而非应用内 WebView，避免隐私问题）
   - 实现 Deep Link 接收 OAuth 回调
   - 安全存储 `code_verifier`（使用 EncryptedSharedPreferences）

3. **依赖添加：**
   ```txt
   cryptography>=41.0.0
   ```

### 快速验证方案：现有 Cookie 认证

如果短期内无法修改 iFlow 服务器，可以：

1. **在安卓应用中提供 Cookie 输入界面**
   - 用户在浏览器中复制 Cookie
   - 在应用中粘贴并提交

2. **实现 Cookie 自动获取（需要服务器配合）**
   - 用户在应用内打开 WebView
   - 登录后自动提取 Cookie
   - 使用 Android WebView 的 `WebViewClient` 监听登录完成

## 代码示例位置

在项目中创建新文件实现上述方案：

```
app/iflow/
├── auth.py              # 现有：基础认证类
├── auth_mobile.py       # 新增：移动端认证（PKCE 相关）
├── routes.py            # 现有：API 路由
├── routes_mobile.py     # 新增：移动端路由
├── service.py           # 现有：业务逻辑
└── service_mobile.py    # 新增：移动端服务
```

## 注意事项

1. **安全性：**
   - `code_verifier` 必须在安卓端安全存储
   - 回调 URL 必须使用自定义scheme（如 `myapp://`）或 https
   - 定期刷新 Access Token，避免使用长期有效的 Refresh Token

2. **用户体验：**
   - 使用系统浏览器而非应用内 WebView，获得更好的安全性感知
   - 提供清晰的登录状态提示
   - 处理用户取消登录的场景

3. **兼容性：**
   - 确保方案与现有 OAuth 流程兼容
   - 支持多账号管理
   - 处理 Token 过期和刷新逻辑

4. **部署：**
   - 回调 URL 必须可访问（公网 IP 或内网穿透）
   - 考虑使用 Ngrok 等工具进行本地测试
