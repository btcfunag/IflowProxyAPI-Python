#!/usr/bin/env python3
"""
iFlow 简化版登录测试脚本 - 简单版

使用方法：
    python test_simplified_login.py

这个脚本直接调用 API 创建登录会话，返回登录网址
"""

import httpx
import json
import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_api():
    """测试 API 端点"""
    url = "http://localhost:8000/api/iflow/login/simplified"
    
    print("=" * 60)
    print("测试 iFlow 简化登录 API")
    print("=" * 60)
    print(f"URL: {url}")
    print()
    
    try:
        print("正在请求...")
        response = httpx.post(url, timeout=30)
        print(f"状态码: {response.status_code}")
        print()
        
        if response.status_code == 200:
            data = response.json()
            print("响应数据:")
            print(json.dumps(data, indent=2, ensure_ascii=False))
            
            if data.get("success"):
                login_url = data.get("data", {}).get("login_url", "")
                session_id = data.get("data", {}).get("session_id", "")
                
                print()
                print("=" * 60)
                print("登录信息:")
                print(f"Session ID: {session_id}")
                print(f"登录网址: {login_url}")
                print("=" * 60)
                print()
                print("请在浏览器中打开登录网址完成登录")
                print("登录成功后可以轮询状态:")
                print(f"  curl http://localhost:8000/api/iflow/login/status/{session_id}")
                print()
                
                return True
        else:
            print(f"请求失败: {response.text}")
            return False
            
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    print("\n" + "=" * 60)
    print("        iFlow 简化版登录测试")
    print("=" * 60)
    print()
    
    test_api()
    
    print("\n测试完成")


if __name__ == "__main__":
    main()
