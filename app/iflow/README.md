---
AIGC:
    ContentProducer: Minimax Agent AI
    ContentPropagator: Minimax Agent AI
    Label: AIGC
    ProduceID: "00000000000000000000000000000000"
    PropagateID: "00000000000000000000000000000000"
    ReservedCode1: 3046022100eebdf9351ba6763cf8c5ff825c6fec90ede5a2267063e23a6b246d873c7c5d0f022100e29515b8a53ae679bce4db13fec0dbcb1f244e65bf3dc1854ae80b6386c76d2c
    ReservedCode2: 3046022100a93ddff0b54885d59487a43e04aa216ba686019ce25a58ff788bb978cee746b4022100b98467c964cead0be56062b74b44d3bb8dcc84a605abc308e2885a751213be1c
---

# iFlow 接口实现文档

## 概述

本文档描述了纯 Python 实现的 iFlow 接口模块，提供 OAuth2.0 认证和 OpenAI 兼容的 API 代理功能。

## 功能特性

- **OAuth2.0 认证**：支持完整的授权码流程
- **Cookie 认证**：支持使用浏览器 Cookie 进行认证
- **Token 自动刷新**：自动刷新过期的访问令牌
- **Chat Completion**：支持流式和非流式的对话补全请求
- **多账号管理**：支持多个 iFlow 账号的管理和切换

## API 端点

### 认证相关

#### 1. OAuth 登录

```
POST /api/iflow/login
```

请求体：
```json
{
    "no_browser": false,
    "callback_port": 11451
}
```

响应：
```json
{
    "success": true,
    "message": "iFlow 认证成功",
    "data": {
        "email": "user@example.com",
        "api_key": "xxx",
        "expire": "2026-01-17T20:55:20+00:00",
        "saved_path": "/path/to/auth/file.json"
    }
}
```

#### 2. Cookie 登录

```
POST /api/iflow/login/cookie
```

请求体：
```json
{
    "cookie": "BXAuth=xxx; 其他字段=值;"
}
```

响应：同 OAuth 登录

#### 3. 列出所有账号

```
GET /api/iflow/accounts
```

响应：
```json
{
    "success": true,
    "message": "获取账号列表成功",
    "data": {
        "accounts": [
            {
                "email": "user@example.com",
                "api_key": "xxx...",
                "expire": "2026-01-17T20:55:20+00:00",
                "auth_type": "oauth",
                "created_at": "2026-01-16T20:55:20+00:00"
            }
        ],
        "total": 1
    }
}
```

#### 4. 删除账号

```
DELETE /api/iflow/accounts/{email}
```

#### 5. 刷新 Token

```
POST /api/iflow/refresh
```

请求体：
```json
{
    "email": "user@example.com"
}
```

### API 调用相关

#### 6. Chat Completion

```
POST /api/iflow/chat/completions
```

请求体：
```json
{
    "model": "user@example.com-glm-4",
    "messages": [
        {"role": "system", "content": "你是一个助手"},
        {"role": "user", "content": "你好"}
    ],
    "stream": false,
    "max_tokens": 1000,
    "temperature": 0.7,
    "top_p": 0.9,
    "presence_penalty": 0,
    "frequency_penalty": 0,
    "reasoning_effort": "medium"
}
```

响应（非流式）：
```json
{
    "id": "iflow-1234567890",
    "object": "chat.completion",
    "created": 1234567890,
    "model": "glm-4",
    "choices": [
        {
            "index": 0,
            "message": {
                "role": "assistant",
                "content": "你好！有什么可以帮助你的吗？"
            },
            "finish_reason": "stop"
        }
    ],
    "usage": {
        "prompt_tokens": 10,
        "completion_tokens": 20,
        "total_tokens": 30
    }
}
```

流式响应格式（`stream: true`）：
```
data: {"id": "...", "object": "...", ...}

data: [DONE]
```

## 使用示例

### Python 示例

```python
import httpx

BASE_URL = "http://localhost:8000/api"

# 1. OAuth 登录
def oauth_login():
    response = httpx.post(f"{BASE_URL}/iflow/login", json={
        "no_browser": False
    })
    print(response.json())

# 2. Chat Completion（非流式）
def chat_completion():
    response = httpx.post(f"{BASE_URL}/iflow/chat/completions", json={
        "model": "user@example.com-glm-4",
        "messages": [
            {"role": "user", "content": "你好"}
        ],
        "stream": False
    })
    print(response.json())

# 3. Chat Completion（流式）
def chat_completion_stream():
    with httpx.stream("POST", f"{BASE_URL}/iflow/chat/completions", json={
        "model": "user@example.com-glm-4",
        "messages": [
            {"role": "user", "content": "讲个笑话"}
        ],
        "stream": True
    }) as response:
        for line in response.iter_lines():
            if line.startswith("data: "):
                print(line[6:])

# 4. 列出账号
def list_accounts():
    response = httpx.get(f"{BASE_URL}/iflow/accounts")
    print(response.json())

# 5. 删除账号
def delete_account(email):
    response = httpx.delete(f"{BASE_URL}/iflow/accounts/{email}")
    print(response.json())
```

### cURL 示例

```bash
# OAuth 登录
curl -X POST http://localhost:8000/api/iflow/login \
  -H "Content-Type: application/json" \
  -d '{"no_browser": false}'

# Chat Completion
curl -X POST http://localhost:8000/api/iflow/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "user@example.com-glm-4",
    "messages": [{"role": "user", "content": "你好"}],
    "stream": false
  }'

# 流式 Chat Completion
curl -X POST http://localhost:8000/api/iflow/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "user@example.com-glm-4",
    "messages": [{"role": "user", "content": "讲个笑话"}],
    "stream": true
  }'

# 列出账号
curl http://localhost:8000/api/iflow/accounts

# 删除账号
curl -X DELETE http://localhost:8000/api/iflow/accounts/user@example.com
```

## 模型名称格式

模型名称使用以下格式：`{email}-{model_name}`

例如：`user@example.com-glm-4`、`user@example.com-minimax-m2`

如果只提供模型名称（如 `glm-4`），系统将使用第一个配置的账号。

## 认证文件存储

认证信息存储在 `data/iflow_auths/` 目录下，文件名为 `iflow-{email}-{timestamp}.json`。

存储的认证信息包括：
- `access_token`：访问令牌
- `refresh_token`：刷新令牌
- `api_key`：API 密钥
- `email`：用户邮箱
- `expire`：过期时间
- `auth_type`：认证类型（oauth 或 cookie）

## 配置选项

### 环境变量

| 变量 | 默认值 | 描述 |
|------|--------|------|
| HOST | 0.0.0.0 | 服务绑定地址 |
| PORT | 8000 | 服务端口 |
| LOG_LEVEL | INFO | 日志级别 |

### OAuth 配置

OAuth 回调默认使用端口 11451，如需更改可在登录请求中指定 `callback_port`。

## 依赖项

```
fastapi>=0.104.0
uvicorn>=0.24.0
httpx>=0.25.0
pydantic>=2.5.0
loguru>=0.7.2
rich>=13.7.0
aiosqlite>=0.19.0
```

## 启动服务

```bash
python main.py
```

服务启动后，访问 http://localhost:8000/docs 查看完整的 API 文档。

## 注意事项

1. **OAuth 回调**：OAuth 登录需要本地能够接收回调请求，确保端口 11451 可用
2. **Cookie 格式**：Cookie 必须包含 `BXAuth` 字段
3. **Token 刷新**：OAuth 认证的 Token 会自动刷新，Cookie 认证不支持刷新
4. **多账号**：多个账号使用时，模型名称需要包含邮箱前缀
