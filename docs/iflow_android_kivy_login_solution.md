---
AIGC:
    ContentProducer: Minimax Agent AI
    ContentPropagator: Minimax Agent AI
    Label: AIGC
    ProduceID: "00000000000000000000000000000000"
    PropagateID: "00000000000000000000000000000000"
    ReservedCode1: 304502207f3788eb40904c9ef8d7b5663471741797d4e83a9722ccbbc9cafb8fedb7395a022100cad4ff322bedd5261b3b4f96e061db7b8ab4ea43a952a70cbe7c64de4bea9d2c
    ReservedCode2: 304502203b87667f8d6ac13b9bb4f3b89df1bf27d68dee3390b78f66108cf055ef56e2f80221008af7ee000c2146c7ff591130523cf98dfd401eeffc11e610bd3097d3a8840b4e
---

# iFlow Android Kivy 登录解决方案

## 问题分析

通过分析 Go 版本项目的实现，发现了 Python 版本中 `simplified_login.py` 的关键问题：

### Go 版本的正确实现

1. **OAuth 服务器监听独立端口**（端口 11451），路径为 `/oauth2callback`
2. **主服务器也有回调端点** `/iflow/callback` 用于接收 OAuth 重定向
3. **回调 URL 格式**：`http://localhost:11451/oauth2callback` 或 `http://服务器地址:端口/iflow/callback`

### Python 版本的问题

原 `simplified_login.py` 使用了错误的回调 URL 格式：

```python
# 错误的格式
login_page_url = f"{base_url}/simplified/callback/{session_id}"
```

这个回调 URL **不是 iFlow OAuth 认可的重定向 URL**，因此 iFlow 服务器会返回"页面不存在"错误。

## 解决方案

根据 Go 版本的实现，我们采用以下方案：

### 使用主服务器回调端点

由于 Android Kivy 应用**无法绑定本地端口**（浏览器运行在独立进程，`localhost` 与 Kivy 应用的 `localhost` 不同），我们需要使用主服务器的 `/iflow/callback` 端点作为 OAuth 重定向目标。

### 登录流程

```
┌─────────────────────────────────────────────────────────────────────┐
│                         iFlow 登录流程                                │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  1. Kivy 应用                                                        │
│     │                                                                │
│     ▼                                                                │
│  2. 调用 /api/iflow/login/simplified 创建登录会话                      │
│     │                                                                │
│     ▼                                                                │
│  3. 服务器返回登录 URL（包含 state 参数）                               │
│     │                                                                │
│     ▼                                                                │
│  4. Kivy 应用在浏览器中打开登录 URL                                    │
│     │                                                                │
│     ▼                                                                │
│  5. 用户在 iFlow 网站登录                                             │
│     │                                                                │
│     ▼                                                                │
│  6. iFlow 重定向到 /iflow/callback?code=xxx&state=yyy                │
│     │                                                                │
│     ▼                                                                │
│  7. 服务器接收 OAuth callback，交换 token 并保存认证信息                │
│     │                                                                │
│     ▼                                                                │
│  8. Kivy 应用轮询 /api/iflow/login/status/{session_id} 获取结果       │
│     │                                                                │
│     ▼                                                                │
│  9. 登录完成，返回认证信息                                             │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

## 修改的文件

### 1. `app/iflow/simplified_login.py`

- 重写了 `generate_authorization_url` 函数，生成正确的 OAuth 授权 URL
- 重写了 `create_login_session` 函数，使用 `/iflow/callback` 作为回调端点
- 更新了 `auto_login` 函数以适应新的登录流程
- 添加了 `LoginStatusManager` 类用于管理登录状态

### 2. `app/iflow/routes.py`

- 添加了 `/iflow/callback` 端点，用于接收 iFlow OAuth 重定向
- 更新了 `/iflow/login/simplified` 端点，使用新的简化登录逻辑
- 添加了 `/iflow/login/status/{session_id}` 端点用于轮询登录状态

## 使用方法

### 在 Kivy 应用中

```python
from app.iflow.simplified_login import auto_login

# 自动完成登录
result = auto_login(server_url="http://localhost:8000")

if result["success"]:
    print(f"登录成功！账号: {result['email']}")
    print(f"API Key: {result['api_key']}")
else:
    print(f"登录失败: {result['message']}")
```

### 异步版本（适用于 Kivy）

```python
from app.iflow.simplified_login import async_auto_login

# 在后台线程中执行登录
result = async_auto_login(server_url="http://localhost:8000")
```

## 关键代码说明

### OAuth 授权 URL 生成

```python
def generate_authorization_url(state: str, server_url: str = "") -> tuple:
    """
    生成 iFlow OAuth 授权 URL
    
    回调 URL 使用主服务器的 /iflow/callback 端点
    """
    if server_url:
        redirect_uri = f"{server_url}/iflow/callback"
    else:
        redirect_uri = f"http://localhost:{IFLOW_CALLBACK_PORT}/oauth2callback"
    
    params = {
        "loginMethod": "phone",
        "type": "phone",
        "redirect": redirect_uri,
        "state": state,
        "client_id": IFLOW_OAUTH_CLIENT_ID,
    }
    
    auth_url = f"{IFLOW_OAUTH_AUTHORIZE_ENDPOINT}?{urlencode(params)}"
    return auth_url, redirect_uri
```

### OAuth 回调处理

```python
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
    
    接收 OAuth code，交换 token，并保存认证信息
    """
    # 检查错误
    if error:
        fail_login_session(state, error_description or error)
        return {"success": False, "message": f"登录失败: {error}"}
    
    # 交换授权码获取 token
    redirect_uri = str(request.base_url).rstrip("/") + "/iflow/callback"
    token_data = await auth_service.exchange_code_for_tokens(code, redirect_uri)
    
    # 保存认证信息
    token_storage = auth_service.create_token_storage(token_data)
    saved_path = auth_service.save_auth(token_storage)
    
    # 标记登录完成
    complete_login_session(state, token_data.email, token_data.api_key)
    
    return {"success": True, "message": "登录成功！"}
```

## 注意事项

1. **服务器地址**：确保 `server_url` 参数正确指向运行中的服务器地址
2. **会话过期**：登录会话默认 10 分钟后过期
3. **轮询超时**：应用应设置合理的超时时间（建议 5 分钟）
4. **回调 URL 注册**：确保 `/iflow/callback` 是 iFlow OAuth 认可的重定向 URL

## 测试方法

1. 启动 Python 服务器
2. 在 Kivy 应用或浏览器中访问：`http://localhost:8000/docs`
3. 测试 `/api/iflow/login/simplified` 端点
4. 按照返回的登录 URL 在浏览器中完成登录
5. 轮询 `/api/iflow/login/status/{session_id}` 获取登录结果

## 常见问题

### 1. 页面不存在错误

如果浏览器显示"页面不存在"，说明回调 URL 不正确。请检查：
- 服务器是否正在运行
- 回调 URL 是否与 iFlow OAuth 配置中注册的一致

### 2. 登录超时

请检查：
- 会话是否过期
- 轮询间隔是否合理（建议 2-5 秒）
- 网络连接是否正常

### 3. 状态不匹配

请确保：
- 创建会话时生成的 state 与回调中的 state 一致
- 没有多个登录会话同时进行
