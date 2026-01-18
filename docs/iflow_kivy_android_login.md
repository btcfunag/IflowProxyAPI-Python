---
AIGC:
    ContentProducer: Minimax Agent AI
    ContentPropagator: Minimax Agent AI
    Label: AIGC
    ProduceID: "00000000000000000000000000000000"
    PropagateID: "00000000000000000000000000000000"
    ReservedCode1: 3045022100e9eee938c2d180166bf5d24ff8decb27b944bffcf1e7b96c2ba40c0b1368fc7302207740eabd339014327be94f0ceaeeacf85d68fc46570788d8b8561e9dffdf84bc
    ReservedCode2: 3045022005653d321eb74d8e1a4d6e40de3dbaf4f09f99afa1066acb3066ad4565364329022100f896f7abd39acc732e8e350977e1112aa4d78d8836d46970a9569b4cc592dc87
---

# iFlow Kivy 安卓端登录方案

## 场景分析

Kivy 应用在安卓上运行时面临以下限制：

1. **无法绑定 localhost 端口**：OAuth 回调需要本地服务器接收授权码，但安卓应用无法绑定 127.0.0.1 端口
2. **应用生命周期限制**：安卓应用可能在前台/后台切换，影响回调服务器的稳定性
3. **网络权限限制**：需要正确的网络配置才能接收回调

当前 Kivy 代码的登录逻辑：
```python
# 现有实现依赖本地服务器
redirect_uri = f"http://localhost:{port}/oauth2callback"
webbrowser.open(auth_url)  # 打开浏览器
await oauth_server.wait_for_callback()  # 等待回调
```

## 推荐方案

### 方案一：公网回调服务 + 轮询（推荐）

通过第三方回调服务或自己部署的公网服务，将 OAuth 回调转发给 Kivy 应用。

**架构图：**
```
┌─────────────┐     1. 打开浏览器      ┌─────────────┐
│  Kivy App   │ ───────────────────▶  │   浏览器     │
│  (安卓端)   │                       │             │
└─────────────┘                       └─────────────┘
       │                                     │
       │ 4. 轮询获取授权码                     │ 2. 用户登录
       │◀────────────────────────────────────│
       │                                     ▼
       │                       ┌─────────────────────┐
       │                       │   iFlow OAuth       │
       │                       │   服务器            │
       │◀──────────────────────│                     │
       │ 3. 回调到公网服务      └─────────────────────┘
       │
       ▼
┌─────────────┐
│ 公网回调服务 │ ◀─── 2. 回调携带授权码
│ (如 ngrok)  │
└─────────────┘
```

**步骤 1：使用 Ngrok 内网穿透**

```python
# Kivy 应用中启动本地服务器并暴露到公网
import asyncio
import uvicorn
from fastapi import FastAPI
import threading

app = FastAPI()

oauth_results = {}

@app.get("/oauth2callback")
async def oauth_callback(code: str, state: str):
    oauth_results[state] = {"code": code, "completed": True}
    return {"status": "success", "message": "请切换回应用"}

def run_server():
    uvicorn.run(app, host="127.0.0.1", port=11451)

# 在 Kivy 应用启动时
def start_oauth_server():
    # 启动本地服务器线程
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    
    # 使用 ngrok 暴露端口
    from pyngrok import ngrok
    public_url = ngrok.connect(11451, "http")
    print(f"OAuth 回调地址: {public_url}")
    return public_url
```

**步骤 2：修改登录流程**

```python
# 新的 Kivy 登录流程
class IFlowLoginManager:
    
    def __init__(self):
        self.http_client = httpx.AsyncClient()
        self.state = None
        self.public_url = None
    
    async def start_login(self):
        """启动 OAuth 登录流程"""
        import secrets
        
        # 1. 启动本地服务器并获取公网 URL
        self.public_url = start_oauth_server()
        self.state = secrets.token_urlsafe(16)
        
        # 2. 生成授权 URL
        auth_url = self._build_auth_url()
        
        # 3. 打开浏览器
        import webbrowser
        webbrowser.open(auth_url)
        
        # 4. 轮询等待授权码
        result = await self._poll_for_result(timeout=300)
        return result
    
    def _build_auth_url(self):
        """构建授权 URL"""
        params = {
            "loginMethod": "phone",
            "type": "phone",
            "redirect": f"{self.public_url}/oauth2callback",
            "state": self.state,
            "client_id": IFLOW_OAUTH_CLIENT_ID,
        }
        from urllib.parse import urlencode
        return f"{IFLOW_OAUTH_AUTHORIZE_ENDPOINT}?{urlencode(params)}"
    
    async def _poll_for_result(self, timeout=300):
        """轮询获取授权结果"""
        import time
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            if self.state in oauth_results:
                result = oauth_results.pop(self.state)
                return result
            
            await asyncio.sleep(2)  # 每 2 秒轮询一次
        
        return None
```

**步骤 3：Kivy 界面集成**

```python
# main.py - Kivy 应用主文件
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.clock import mainthread
import asyncio

class IFlowLoginScreen(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'vertical'
        
        self.status_label = Label(text='准备登录 iFlow')
        self.add_widget(self.status_label)
        
        login_btn = Button(text='登录 iFlow', on_press=self.start_login)
        self.add_widget(login_btn)
    
    async def start_login(self, instance):
        self.status_label.text = '正在启动登录...'
        
        # 在后台线程运行异步登录
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, asyncio.run, self.do_login())
        
        if result:
            self.status_label.text = f'登录成功！'
        else:
            self.status_label.text = '登录失败或超时'
    
    async def do_login(self):
        login_manager = IFlowLoginManager()
        result = await login_manager.start_login()
        return result is not None

class IFlowApp(App):
    def build(self):
        return IFlowLoginScreen()

IFlowApp().run()
```

### 方案二：简化版 - 手动 Cookie 输入（无需服务器改动）

如果无法部署公网服务，可以让用户手动获取 Cookie 后输入。

**步骤 1：在 iFlow 服务器添加 Cookie 登录接口（已存在）**

当前项目已有 Cookie 登录接口：
```python
POST /api/iflow/login/cookie
```

**步骤 2：Kivy 界面提供 Cookie 输入框**

```python
# kivy_ui.py
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout

class CookieLoginScreen(ScrollView):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        layout = GridLayout(cols=1, spacing=20, size_hint_y=None)
        layout.bind(minimum_height=layout.setter('height'))
        
        # 标题
        title = Label(
            text='iFlow Cookie 登录',
            size_hint_y=None,
            height=50,
            font_size='24sp'
        )
        layout.add_widget(title)
        
        # 说明
        instructions = Label(
            text='请按以下步骤获取 Cookie：\n'
                 '1. 在浏览器中访问 https://iflow.cn\n'
                 '2. 登录你的账号\n'
                 '3. 按 F12 打开开发者工具\n'
                 '4. 复制完整的 Cookie 内容\n'
                 '5. 粘贴到下方输入框',
            size_hint_y=None,
            height=200,
            text_size=(400, None),
            halign='left'
        )
        layout.add_widget(instructions)
        
        # Cookie 输入框
        self.cookie_input = TextInput(
            hint_text='在此粘贴 Cookie',
            multiline=True,
            size_hint_y=None,
            height=150
        )
        layout.add_widget(self.cookie_input)
        
        # 登录按钮
        login_btn = Button(
            text='确认登录',
            size_hint_y=None,
            height=50,
            on_press=self.submit_cookie
        )
        layout.add_widget(login_btn)
        
        # 状态显示
        self.status_label = Label(
            text='',
            size_hint_y=None,
            height=50,
            color=[1, 0, 0, 1]  # 红色
        )
        layout.add_widget(self.status_label)
        
        self.add_widget(layout)
        self.login_manager = IFlowLoginManager()
    
    def submit_cookie(self, instance):
        cookie = self.cookie_input.text.strip()
        
        if not cookie:
            self.status_label.text = '请输入 Cookie'
            return
        
        if 'BXAuth=' not in cookie:
            self.status_label.text = 'Cookie 必须包含 BXAuth 字段'
            return
        
        # 发送登录请求到后端
        import threading
        
        def do_login():
            import httpx
            try:
                response = httpx.post(
                    'http://your-server:8000/api/iflow/login/cookie',
                    json={"cookie": cookie},
                    timeout=30.0
                )
                
                if response.json().get('success'):
                    self.status_label.text = '登录成功！'
                    self.status_label.color = [0, 1, 0, 1]  # 绿色
                else:
                    self.status_label.text = '登录失败：' + response.json().get('detail', '未知错误')
            except Exception as e:
                self.status_label.text = f'连接失败：{str(e)}'
        
        threading.Thread(target=do_login).start()
```

**步骤 3：提供 Cookie 获取教程界面**

```python
class CookieTutorialScreen(BoxLayout):
    """Cookie 获取教程界面"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'vertical'
        
        # 使用 Markdown 或 Rich Text 显示教程
        tutorial = Label(
            text=self.get_tutorial_text(),
            text_size=(400, None),
            halign='left',
            valign='top'
        )
        self.add_widget(tutorial)
    
    def get_tutorial_text(self):
        return '''
Cookie 获取教程（Chrome 浏览器）

步骤 1：登录 iFlow
  - 打开 Chrome 浏览器
  - 访问 https://iflow.cn
  - 使用手机号登录

步骤 2：打开开发者工具
  - 在页面任意位置右键点击
  - 选择"检查"或按 F12

步骤 3：获取 Cookie
  - 切换到 Network（网络）标签
  - 刷新页面
  - 点击任意请求
  - 在 Headers（请求头）中找到 Cookie
  - 复制完整的 Cookie 值

步骤 4：粘贴到应用
  - 返回本应用
  - 将 Cookie 粘贴到输入框
  - 点击"确认登录"
        '''
```

### 方案三：使用 Intent 机制（高级方案）

在安卓上，可以使用 Intent 机制让浏览器将结果返回给应用。

```python
# android_oauth.py - 安卓特定实现
from kivy.utils import platform
from jnius import autoclass, cast

if platform == 'android':
    from android import activity
    from jnius import JavaException
    from android.content import Intent
    from android.net import Uri

class AndroidOAuth:
    
    def __init__(self):
        self.PythonActivity = autoclass('org.kivy.android.PythonActivity')
        self.Intent = autoclass('android.content.Intent')
        self.Uri = autoclass('android.net.Uri')
    
    def open_browser(self, url):
        """打开系统浏览器"""
        intent = Intent(Intent.ACTION_VIEW, Uri.parse(url))
        current_activity = cast('android.app.Activity', self.PythonActivity.mActivity)
        current_activity.startActivity(intent)
    
    def start_activity_for_result(self, intent, request_code):
        """启动活动并等待结果"""
        current_activity = cast('android.app.Activity', self.PythonActivity.mActivity)
        current_activity.startActivityForResult(intent, request_code)
    
    def generate_deep_link_callback(self, scheme='iflowapp', host='oauth'):
        """生成 Deep Link 回调 URL"""
        return f"{scheme}://{host}/callback"
```

### 方案四：URL Scheme 回调（需要 iFlow 服务器配合）

如果 iFlow 服务器支持自定义回调 URL scheme，可以直接回调到应用。

```python
# 需要 iFlow 服务器支持以下格式的回调 URL
callback_url = "iflowapp://oauth/callback"

# 在 AndroidManifest.xml 中添加 Intent Filter
INTENT_FILTER = """
<activity android:name=".MainActivity">
    <intent-filter>
        <action android:name="android.intent.action.VIEW" />
        <category android:name="android.intent.category.DEFAULT" />
        <category android:name="android.intent.category.BROWSABLE" />
        <data android:scheme="iflowapp" />
    </intent-filter>
</activity>
"""
```

## 完整 Kivy 登录模块实现

```python
# iflow_kivy_login.py - 完整的 Kivy 登录模块

import asyncio
import httpx
import threading
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.clock import mainthread
from kivy.properties import StringProperty

# 导入 iFlow 认证模块
import sys
sys.path.insert(0, '/path/to/your/project')
from app.iflow.auth import IFLOW_OAUTH_CLIENT_ID, IFLOW_OAUTH_AUTHORIZE_ENDPOINT


class LoginScreen(Screen):
    """登录方式选择界面"""
    status = StringProperty('')
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        layout = BoxLayout(orientation='vertical', padding=50, spacing=20)
        
        title = Label(text='iFlow 登录', font_size='32sp', size_hint_y=None, height=60)
        layout.add_widget(title)
        
        # 浏览器登录按钮
        browser_btn = Button(
            text='浏览器登录',
            size_hint_y=None,
            height=60,
            on_press=self.browser_login
        )
        layout.add_widget(browser_btn)
        
        # Cookie 登录按钮
        cookie_btn = Button(
            text='Cookie 登录',
            size_hint_y=None,
            height=60,
            on_press=self.go_to_cookie_login
        )
        layout.add_widget(cookie_btn)
        
        # 状态标签
        self.status_label = Label(text='', size_hint_y=None, height=40)
        layout.add_widget(self.status_label)
        
        self.add_widget(layout)
    
    def browser_login(self, instance):
        self.status_label.text = '请选择登录方式：'
        # 导航到浏览器登录界面
        App.get_running_app().root.current = 'browser_login'
    
    def go_to_cookie_login(self, instance):
        App.get_running_app().root.current = 'cookie_login'


class BrowserLoginScreen(Screen):
    """浏览器登录界面"""
    status = StringProperty('')
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        layout = BoxLayout(orientation='vertical', padding=50, spacing=20)
        
        title = Label(text='浏览器登录', font_size='24sp', size_hint_y=None, height=50)
        layout.add_widget(title)
        
        instructions = Label(
            text='点击下方按钮打开浏览器完成登录\n'
                 '登录成功后会自动返回',
            size_hint_y=None,
            height=100
        )
        layout.add_widget(instructions)
        
        start_btn = Button(
            text='打开浏览器登录',
            size_hint_y=None,
            height=60,
            on_press=self.start_browser_login
        )
        layout.add_widget(start_btn)
        
        self.status_label = Label(text='', size_hint_y=None, height=40, color=[1, 0, 0, 1])
        layout.add_widget(self.status_label)
        
        # 返回按钮
        back_btn = Button(
            text='返回',
            size_hint_y=None,
            height=50,
            on_press=self.go_back
        )
        layout.add_widget(back_btn)
        
        self.add_widget(layout)
    
    def start_browser_login(self, instance):
        self.status_label.text = '正在启动登录流程...'
        self.status_label.color = [1, 1, 0, 1]  # 黄色
        
        # 在后台线程运行登录流程
        threading.Thread(target=self._do_login, daemon=True).start()
    
    def _do_login(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(self.login())
        loop.close()
        
        @mainthread
        def update_ui():
            if result:
                self.status_label.text = '登录成功！'
                self.status_label.color = [0, 1, 0, 1]  # 绿色
            else:
                self.status_label.text = '登录失败或超时'
        
        update_ui()
    
    async def login(self):
        """执行浏览器登录流程"""
        try:
            # 方案 A：使用 ngrok（推荐）
            from pyngrok import ngrok
            
            # 启动本地服务器
            public_url = ngrok.connect(11451, "http")
            state = self._generate_state()
            
            # 生成授权 URL
            auth_url = self._build_auth_url(public_url, state)
            
            # 打开浏览器
            import webbrowser
            webbrowser.open(auth_url)
            
            # 轮询等待结果
            return await self._poll_result(state, timeout=300)
            
        except ImportError:
            # 方案 B：使用简化登录
            return await self.simplified_login()
    
    def _generate_state(self):
        import secrets
        return secrets.token_urlsafe(16)
    
    def _build_auth_url(self, public_url, state):
        from urllib.parse import urlencode
        params = {
            'loginMethod': 'phone',
            'type': 'phone',
            'redirect': f'{public_url}/oauth2callback',
            'state': state,
            'client_id': IFLOW_OAUTH_CLIENT_ID,
        }
        return f"{IFLOW_OAUTH_AUTHORIZE_ENDPOINT}?{urlencode(params)}"
    
    async def _poll_result(self, state, timeout):
        import time
        oauth_results = {}
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            if state in oauth_results:
                result = oauth_results.pop(state)
                return result is not None
            
            await asyncio.sleep(2)
        
        return False
    
    async def simplified_login(self):
        """简化登录：生成授权 URL 让用户手动完成"""
        import webbrowser
        
        state = self._generate_state()
        # 使用 localhost 回调（可能不工作，仅作演示）
        auth_url = self._build_auth_url(
            f"http://localhost:11451", state
        )
        
        @mainthread
        def show_message():
            self.status_label.text = '请在浏览器中完成登录\n然后返回输入 Cookie'
        
        show_message()
        webbrowser.open(auth_url)
        return False
    
    def go_back(self, instance):
        App.get_running_app().root.current = 'login'


class CookieLoginScreen(Screen):
    """Cookie 登录界面"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        layout = BoxLayout(orientation='vertical', padding=30, spacing=15)
        
        title = Label(text='Cookie 登录', font_size='24sp', size_hint_y=None, height=50)
        layout.add_widget(title)
        
        # 使用说明
        instructions = Label(
            text='获取 Cookie 方法：\n'
                 '1. 浏览器访问 iflow.cn 并登录\n'
                 '2. F12 打开开发者工具\n'
                 '3. 复制完整 Cookie 到下方\n'
                 '4. 必须包含 BXAuth 字段',
            size_hint_y=None,
            height=180,
            text_size=(400, None),
            halign='left'
        )
        layout.add_widget(instructions)
        
        # Cookie 输入框
        self.cookie_input = TextInput(
            hint_text='Cookie',
            multiline=True,
            size_hint_y=None,
            height=120
        )
        layout.add_widget(self.cookie_input)
        
        # 登录按钮
        login_btn = Button(
            text='登录',
            size_hint_y=None,
            height=50,
            on_press=self.submit_cookie
        )
        layout.add_widget(login_btn)
        
        # 状态标签
        self.status_label = Label(text='', size_hint_y=None, height=40)
        layout.add_widget(self.status_label)
        
        # 返回按钮
        back_btn = Button(
            text='返回',
            size_hint_y=None,
            height=50,
            on_press=self.go_back
        )
        layout.add_widget(back_btn)
        
        self.add_widget(layout)
    
    def submit_cookie(self, instance):
        cookie = self.cookie_input.text.strip()
        
        if not cookie:
            self.status_label.text = '请输入 Cookie'
            self.status_label.color = [1, 0, 0, 1]
            return
        
        if 'BXAuth=' not in cookie:
            self.status_label.text = 'Cookie 必须包含 BXAuth 字段'
            self.status_label.color = [1, 0, 0, 1]
            return
        
        self.status_label.text = '正在登录...'
        self.status_label.color = [1, 1, 0, 1]
        
        # 后台线程发送请求
        threading.Thread(target=self._do_cookie_login, args=(cookie,), daemon=True).start()
    
    def _do_cookie_login(self, cookie):
        try:
            # 连接到你的 iFlow API 服务器
            response = httpx.post(
                'http://your-server:8000/api/iflow/login/cookie',
                json={"cookie": cookie},
                timeout=30.0
            )
            
            result = response.json()
            
            @mainthread
            def update_ui():
                if result.get('success'):
                    self.status_label.text = f"登录成功！\n账号：{result['data']['email']}"
                    self.status_label.color = [0, 1, 0, 1]
                else:
                    self.status_label.text = f"登录失败：{result.get('detail', '未知错误')}"
                    self.status_label.color = [1, 0, 0, 1]
            
            update_ui()
            
        except Exception as e:
            @mainthread
            def show_error():
                self.status_label.text = f'连接失败：{str(e)}'
                self.status_label.color = [1, 0, 0, 1]
            
            show_error()
    
    def go_back(self, instance):
        App.get_running_app().root.current = 'login'


class IFlowApp(App):
    def build(self):
        # 创建屏幕管理
        sm = ScreenManager()
        
        # 添加各个屏幕
        sm.add_widget(LoginScreen(name='login'))
        sm.add_widget(BrowserLoginScreen(name='browser_login'))
        sm.add_widget(CookieLoginScreen(name='cookie_login'))
        
        return sm


if __name__ == '__main__':
    IFlowApp().run()
```

## 运行配置

**buildozer.spec 配置：**

```spec
[app]
title = iFlow Login
package.name = iflowlogin
package.domain = com.example
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json
version = 1.0.0
requirements = python3,kivy,httpx,asyncio
orientation = portrait
fullscreen = 0

[dependencies]
# 如果使用 ngrok
pyngrok = 6.1.3
```

**requirements.txt：**

```
kivy>=2.2.0
httpx>=0.25.0
asyncio
# pyngrok>=6.1.3  # 可选，用于公网回调
```

## 方案对比

| 方案 | 优点 | 缺点 | 适用场景 |
|------|------|------|----------|
| **Ngrok + 轮询** | 自动化程度高 | 需要网络穿透服务 | 生产环境首选 |
| **手动 Cookie** | 稳定可靠 | 需要用户手动操作 | 开发/测试阶段 |
| **Intent 机制** | 原生体验 | 需要安卓原生代码 | 高端应用 |
| **URL Scheme** | 快速集成 | 依赖服务器支持 | 服务器可控时 |

## 实施建议

1. **开发阶段**：使用手动 Cookie 输入，简单可靠
2. **测试阶段**：使用 Ngrok 验证完整流程
3. **生产阶段**：
   - 方案 A：部署自己的回调服务（更可控）
   - 方案 B：使用 Ngrok 付费版（更稳定）
   - 方案 C：与 iFlow 服务器团队协商支持自定义回调 URL

4. **Kivy 特有注意事项**：
   - 在安卓上需要正确配置网络权限
   - 后台线程中使用 `mainthread` 装饰器更新 UI
   - 使用 `threading` 避免阻塞 UI 线程
   - 考虑应用生命周期（按 HOME 键后可能失去焦点）

## 文件结构

```
项目目录/
├── main.py              # Kivy 应用入口
├── iflow_kivy_login.py  # 登录模块
├── buildozer.spec       # 构建配置
└── requirements.txt     # Python 依赖
```
