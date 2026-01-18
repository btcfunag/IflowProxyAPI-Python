---
AIGC:
    ContentProducer: Minimax Agent AI
    ContentPropagator: Minimax Agent AI
    Label: AIGC
    ProduceID: "00000000000000000000000000000000"
    PropagateID: "00000000000000000000000000000000"
    ReservedCode1: 3045022100e5c8b36755acab8106dc16f69965428719ca4613ffad4a76d7af6f5c84e5c0d502202c29ffda044775b0353b4d1d79863a2c13effdee3a21ebaaa11601a7396f6d87
    ReservedCode2: 3045022100fed5ab57a1235f6227a690c4128322a8ae24eb1fed504c503f291187529c2f05022057e077fe0f327930defcfc5ab1248bdd3fdc97b9d0b8b037dab399b26d43d6bf
---

# iFlow 登录问题修复指南

## 问题概述

你的 Kivy 应用在登录 iFlow 时出现两个问题：
1. **登录失败**：`{"success":false,"message":"登录失败: 会话已过期"}`
2. **日志丢失**：看不到日志输出

## 问题根因分析

### 问题 1：会话过期

从你提供的日志可以看到：
```
[WARNING] stderr: 2026-01-17 21:22:34 | WARNING | app.iflow.routes:iflow_oauth_callback:551 - 会话不存在或已过期: state=0pS5eEkWr5k7esrqzJkzCg
```

**根本原因**：`simplified_login.py` 中的 `LoginStatusManager` 使用**内存字典**存储登录会话：

```python
class LoginStatusManager:
    _sessions: Dict[str, LoginSession] = {}  # ❌ 仅内存存储
```

这会导致以下问题：
- 服务器进程重启后，所有会话丢失
- Android 应用在后台被系统杀死后重启
- 会话有效期只有 600 秒（10分钟）

### 问题 2：日志丢失

你的日志配置是正确的，使用 loguru 同时输出到：
- stderr（标准错误）
- 文件 `logs/app.log`

但在 Android 环境下：
- stderr 会被重定向到 **Android Logcat**
- 不会显示在普通控制台

## 解决方案

我已经为你创建了修复版本：`simplified_login_fixed.py`

### 主要改进

1. **持久化存储**：使用 SQLite 数据库存储会话，服务器重启后不会丢失
2. **增加超时时间**：从 600 秒（10分钟）增加到 1800 秒（30分钟）
3. **双重缓存**：SQLite 持久化 + 内存缓存（快速访问）
4. **独立日志文件**：创建专门的日志文件便于调试

## 部署步骤

### 步骤 1：备份原文件

```bash
cd /path/to/your/project
cp app/iflow/simplified_login.py app/iflow/simplified_login.py.bak
```

### 步骤 2：应用修复

```bash
cp app/iflow/simplified_login_fixed.py app/iflow/simplified_login.py
```

### 步骤 3：验证修复

运行你的应用，查看是否正确创建了会话数据库：

```bash
# 检查数据库是否创建
ls -la data/simplified_login_sessions.db

# 检查日志文件
ls -la logs/
# 应该看到：
# - app.log（主日志）
# - simplified_login.log（登录模块专用日志）
```

### 步骤 4：测试登录流程

1. 重启你的应用
2. 发起登录请求
3. 查看日志确认会话已持久化

## 日志查看方法

### 在 Android 设备上查看日志

#### 方法 1：使用 adb 查看 Logcat

```bash
# 查看所有日志
adb logcat

# 只查看应用日志（你的应用包名）
adb logcat --pid=$(adb shell pidof com.your.package.name)

# 过滤关键日志
adb logcat | grep -E "(simplified_login|会话|Login|ERROR)"

# 保存日志到文件
adb logcat > app_log.txt
```

#### 方法 2：查看应用内的日志文件

在你的 Android 设备上，访问：
```
/storage/emulated/0/000CLIProxyAPI-Python/logs/
```

应该包含：
- `app.log` - 主日志文件
- `simplified_login.log` - 登录模块专用日志

### 在开发环境中查看日志

```bash
# 实时查看日志文件
tail -f logs/app.log

# 查看登录模块日志
tail -f logs/simplified_login.log

# 搜索错误
grep -i error logs/app.log

# 搜索会话相关日志
grep -i "会话\|session" logs/app.log
```

## 增强功能

### 调试命令

在应用中添加了 `print_all_sessions()` 函数，可在调试时调用：

```python
from app.iflow.simplified_login import print_all_sessions

# 打印当前所有会话
print_all_sessions()
```

输出示例：
```
============================================================
当前会话数量: 2
  - abc123def456... | 状态: pending | 剩余: 1200秒
  - xyz789ghi012... | 状态: completed | 剩余: 0秒
============================================================
```

### 会话数据库位置

新的会话存储在：
```
data/simplified_login_sessions.db
```

数据库结构：
```sql
CREATE TABLE login_sessions (
    session_id TEXT PRIMARY KEY,
    status TEXT DEFAULT 'pending',
    email TEXT,
    api_key TEXT,
    auth_data TEXT,
    server_url TEXT,
    created_at TEXT,
    expire_at TEXT
)
```

## 预期效果

应用此修复后：

1. ✅ 服务器重启后会话不会丢失
2. ✅ 会话有效期延长到 30 分钟
3. ✅ 日志会同时写入：
   - `logs/app.log` - 主日志
   - `logs/simplified_login.log` - 登录模块日志
4. ✅ 在 Android Logcat 中可以看到日志输出

## 常见问题排查

### 问题：会话仍然过期

**可能原因**：
1. 会话超过 30 分钟
2. 数据库文件损坏

**解决方案**：
```python
# 在代码中清理过期会话
from app.iflow.simplified_login import LoginStatusManager
LoginStatusManager._cleanup()
```

### 问题：数据库创建失败

**检查权限**：
```bash
# 确保 data 目录可写
ls -la data/
chmod 755 data/
```

### 问题：日志看不到

**检查日志级别**：
在 `settings.py` 中确认：
```python
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")  # 确保不是 DEBUG 或更低
```

## 相关文件说明

- `app/iflow/simplified_login.py` - 原版本（有问题）
- `app/iflow/simplified_login_fixed.py` - 修复版本
- `app/iflow/routes.py` - API 路由（需要配合修改）
- `app/logger.py` - 日志配置
- `app/settings.py` - 应用配置

## 下一步操作

1. **备份当前文件**
2. **应用修复**：复制 `simplified_login_fixed.py` 到 `simplified_login.py`
3. **重启应用**
4. **测试登录流程**
5. **查看日志确认修复效果**

如果问题仍然存在，请提供：
- 完整的日志输出
- 操作系统环境
- 重现步骤
