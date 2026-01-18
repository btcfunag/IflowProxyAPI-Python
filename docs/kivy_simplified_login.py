# Kivy 简化版登录示例
# 文件名: kivy_simplified_login.py

import asyncio
import threading
import httpx
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.clock import mainthread
from kivy.properties import StringProperty


class KivyLoginHelper:
    """Kivy 登录助手"""
    
    def __init__(self, server_url: str = "http://localhost:8000"):
        self.server_url = server_url.rstrip("/")
        self.session_id = None
        self.login_url = None
    
    def start_login(self) -> str:
        """启动登录流程"""
        try:
            response = httpx.post(
                f"{self.server_url}/api/iflow/login/simplified",
                timeout=30.0,
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    self.session_id = data["data"]["session_id"]
                    self.login_url = data["data"]["login_url"]
                    return self.login_url
            
            return None
        except Exception as e:
            print(f"启动登录失败: {e}")
            return None
    
    def check_status(self) -> dict:
        """检查登录状态"""
        if not self.session_id:
            return {"status": "not_started"}
        
        try:
            response = httpx.get(
                f"{self.server_url}/api/iflow/login/status/{self.session_id}",
                timeout=10.0,
            )
            
            if response.status_code == 200:
                return response.json().get("data", {})
            elif response.status_code == 404:
                return {"status": "expired"}
            
            return {"status": "error"}
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    def wait_for_login(self, timeout: float = 300) -> dict:
        """等待登录完成（阻塞）"""
        import time
        start = time.time()
        
        while time.time() - start < timeout:
            status = self.check_status()
            st = status.get("status", "")
            
            if st == "completed":
                return {"success": True, "email": status.get("email"), "api_key": status.get("api_key")}
            if st in ("failed", "expired"):
                return {"success": False, "message": status.get("message", "登录失败")}
            
            time.sleep(2)
        
        return {"success": False, "message": "登录超时"}
    
    def open_browser(self):
        """打开浏览器"""
        if self.login_url:
            import webbrowser
            webbrowser.open(self.login_url)


class LoginScreen(Screen):
    status = StringProperty('')
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.helper = KivyLoginHelper()
        
        layout = BoxLayout(orientation='vertical', padding=40, spacing=20)
        
        title = Label(text='iFlow 登录', font_size='28sp', size_hint_y=None, height=50)
        layout.add_widget(title)
        
        info = Label(
            text='点击下方按钮打开浏览器\n完成登录后自动返回',
            size_hint_y=None,
            height=80
        )
        layout.add_widget(info)
        
        self.login_btn = Button(
            text='打开浏览器登录',
            size_hint_y=None,
            height=60,
            on_press=self.start_login
        )
        layout.add_widget(self.login_btn)
        
        self.status_label = Label(text='', size_hint_y=None, height=40)
        layout.add_widget(self.status_label)
        
        self.add_widget(layout)
    
    def start_login(self, instance):
        self.status_label.text = '正在创建登录会话...'
        self.status_label.color = (1, 1, 0, 1)
        
        threading.Thread(target=self._do_login, daemon=True).start()
    
    def _do_login(self):
        url = self.helper.start_login()
        
        @mainthread
        def on_url_ready():
            if url:
                self.status_label.text = '请在浏览器中完成登录'
                self.status_label.color = (0, 0.5, 1, 1)
                self.helper.open_browser()
                self._start_polling()
            else:
                self.status_label.text = '创建登录会话失败'
                self.status_label.color = (1, 0, 0, 1)
        
        on_url_ready()
    
    def _start_polling(self):
        """开始轮询登录状态"""
        self.status_label.text = '等待登录中...（请在浏览器中完成登录）'
        self.status_label.color = (1, 1, 0, 1)
        
        threading.Thread(target=self._poll_login, daemon=True).start()
    
    def _poll_login(self):
        result = self.helper.wait_for_login(timeout=300)
        
        @mainthread
        def on_complete():
            if result.get("success"):
                self.status_label.text = f'登录成功！\n账号: {result.get("email")}'
                self.status_label.color = (0, 1, 0, 1)
            else:
                self.status_label.text = result.get("message", "登录失败")
                self.status_label.color = (1, 0, 0, 1)
        
        on_complete()


class IFlowApp(App):
    def build(self):
        sm = ScreenManager()
        sm.add_widget(LoginScreen(name='login'))
        return sm


if __name__ == '__main__':
    IFlowApp().run()
