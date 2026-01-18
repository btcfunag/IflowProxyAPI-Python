---
AIGC:
    ContentProducer: Minimax Agent AI
    ContentPropagator: Minimax Agent AI
    Label: AIGC
    ProduceID: "00000000000000000000000000000000"
    PropagateID: "00000000000000000000000000000000"
    ReservedCode1: 3045022100c74c912ff0c24bc67cfb6a0ad4101b5c8201077923c7aba776a367c4d6c58969022079c177f0e71abc6b5f68f4b03b7d88cbb8061b1653c5668f938d18b187da4ee5
    ReservedCode2: 3046022100f49d970f8bb2a3e3b17e3558cc51eed7ca775afea31df6d55111638174744799022100b62373d8b2dcbaaa20e7b7bfc26d13031f4a028723b712ebd322ad0dfb0e0fa6
---

# 完整修复指南 - 会话数据库问题

## 问题分析

从你的日志中发现了**真正的问题**：

```
当前数据库中的会话数量: 0
数据库中是否存在此 state: False
```

**即使创建了会话，回调时数据库中没有任何会话！**

## 根本原因

你启动了**多个服务器进程**：
1. `simplified_login_v2_server.py`（21:58:54 启动）
2. `simplified_login_server.py`（21:59:03 启动）

**问题**：每个服务器进程都在初始化自己的 `SessionDatabase._instance`，虽然数据库文件相同，但**内存中的实例是独立的**。会话创建在一个进程中，但回调可能到达另一个进程，导致找不到会话。

## 已完成的修复

### 1. routes.py 修复

在回调处理前添加了：
- 强制清除单例模式，强制重新获取数据库实例
- 直接查询数据库，绕过缓存
- 详细的状态对比日志

### 2. 添加 sqlite3 导入

确保 routes.py 可以直接查询数据库。

## 部署步骤

### 步骤 1：停止所有服务器进程

在 Android 应用中，停止所有正在运行的服务器：
- `simplified_login_server.py`
- `simplified_login_v2_server.py`
- `main_server.py` 或 `main.py`

### 步骤 2：只启动一个服务器

**只启动你的主应用**（例如 `main.py` 或 `main_server.py`），不要同时启动多个服务器。

### 步骤 3：更新 routes.py

确保你的 `app/iflow/routes.py` 已更新（已自动更新）。

### 步骤 4：重启主应用

```bash
# 重启你的主应用
python main.py
# 或
python main_server.py
```

### 步骤 5：测试登录流程

```
a) 通过应用创建登录会话
b) 复制日志中的登录 URL
c) 在浏览器中打开并完成登录
d) 观察回调日志
```

## 预期日志输出

### 成功情况

```
2026-01-17 xx:xx:xx | INFO     | 收到 OAuth 回调请求
2026-01-17 xx:xx:xx | INFO     | 直接查询数据库检查 state: xxx
2026-01-17 xx:xx:xx | INFO     | 数据库中直接查询到的会话数量: 1
2026-01-17 xx:xx:xx | INFO     | 直接查询 state 'xxx...' 是否存在: True
2026-01-17 xx:xx:xx | INFO     | 回调接收到的 state: 'xxx'
2026-01-17 xx:xx:xx | INFO     | 数据库中是否存在此 state: True
2026-01-17 xx:xx:xx | INFO     | 查找结果: <LoginSession ...>
```

### 失败情况

如果仍然失败，日志会显示：

```
2026-01-17 xx:xx:xx | INFO     | 数据库中直接查询到的会话数量: 0
2026-01-17 xx:xx:xx | WARNING  | 数据库中没有任何会话！
2026-01-17 xx:xx:xx | WARNING  | 可能的原因：
2026-01-17 xx:xx:xx | WARNING  | 1. 之前创建的会话已过期被清理
2026-01-17 xx:xx:xx | WARNING  | 2. 数据库文件损坏或不存在
2026-01-17 xx:xx:xx | WARNING  | 3. 应用重启后内存缓存丢失
```

## 检查数据库文件

如果问题仍然存在，请检查数据库文件：

```bash
# 检查数据库文件是否存在
ls -la data/simplified_login_sessions.db

# 查看数据库内容（可选）
sqlite3 data/simplified_login_sessions.db "SELECT * FROM login_sessions;"
```

## 重要提醒

1. **只运行一个服务器进程** - 不要同时启动多个服务器
2. **使用主应用** - 使用 `main.py` 或 `main_server.py`，不要直接运行 `simplified_login_server.py`
3. **会话有效期** - 会话有效期为 30 分钟，超时后会被自动清理

## 如果仍然失败

请提供以下信息：

1. **回调失败的完整日志**（从"收到 OAuth 回调请求"开始）
2. **创建会话时的日志**（显示 session_id）
3. **确认只运行了一个服务器进程**
