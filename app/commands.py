"""CLI 命令处理模块"""
import json
import asyncio
from typing import Optional
from pathlib import Path
import httpx

from .settings import API_HOST, API_PORT, settings
from .logger import logger, console


class APIClient:
    """HTTP API 客户端"""
    
    def __init__(self, base_url: str = None):
        self.base_url = base_url or f"http://{API_HOST}:{API_PORT}/api"
    
    async def get(self, path: str, **kwargs) -> dict:
        """GET 请求"""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{self.base_url}{path}", **kwargs)
            response.raise_for_status()
            return response.json()
    
    async def post(self, path: str, data: dict = None, **kwargs) -> dict:
        """POST 请求"""
        async with httpx.AsyncClient() as client:
            response = await client.post(f"{self.base_url}{path}", json=data, **kwargs)
            response.raise_for_status()
            return response.json()
    
    async def put(self, path: str, data: dict = None, **kwargs) -> dict:
        """PUT 请求"""
        async with httpx.AsyncClient() as client:
            response = await client.put(f"{self.base_url}{path}", json=data, **kwargs)
            response.raise_for_status()
            return response.json()
    
    async def delete(self, path: str, **kwargs) -> dict:
        """DELETE 请求"""
        async with httpx.AsyncClient() as client:
            response = await client.delete(f"{self.base_url}{path}", **kwargs)
            response.raise_for_status()
            return response.json()


# ============ 认证管理命令 ============

async def auth_create(name: str, auth_type: str, config: dict, enabled: bool = True):
    """创建认证配置"""
    client = APIClient()
    data = {
        "name": name,
        "auth_type": auth_type,
        "config": config,
        "enabled": enabled
    }
    result = await client.post("/auths", data)
    console.print(f"[green]✓[/green] 创建成功: {result}")


async def auth_list():
    """列出所有认证配置"""
    client = APIClient()
    result = await client.get("/auths")
    
    if not result.get("items"):
        console.print("[yellow]暂无认证配置[/yellow]")
        return
    
    console.print(f"\n[bold]认证配置列表 ({result['total']})[/bold]:")
    for item in result["items"]:
        status = "[green]启用[/green]" if item["enabled"] else "[red]禁用[/red]"
        console.print(f"  • {item['name']} ({item['auth_type']}) - {status}")


async def auth_get(name: str):
    """获取认证配置详情"""
    client = APIClient()
    result = await client.get(f"/auths/{name}")
    console.print(f"\n[bold]认证配置详情[/bold]:")
    console.print(json.dumps(result, indent=2, ensure_ascii=False))


async def auth_update(name: str, **kwargs):
    """更新认证配置"""
    client = APIClient()
    result = await client.put(f"/auths/{name}", kwargs)
    console.print(f"[green]✓[/green] 更新成功")


async def auth_delete(name: str):
    """删除认证配置"""
    client = APIClient()
    result = await client.delete(f"/auths/{name}")
    console.print(f"[green]✓[/green] 删除成功")


# ============ 存储管理命令 ============

async def store_create(name: str, store_type: str, config: dict, enabled: bool = True):
    """创建存储配置"""
    client = APIClient()
    data = {
        "name": name,
        "store_type": store_type,
        "config": config,
        "enabled": enabled
    }
    result = await client.post("/stores", data)
    console.print(f"[green]✓[/green] 创建成功: {result}")


async def store_list():
    """列出所有存储配置"""
    client = APIClient()
    result = await client.get("/stores")
    
    if not result.get("items"):
        console.print("[yellow]暂无存储配置[/yellow]")
        return
    
    console.print(f"\n[bold]存储配置列表 ({result['total']})[/bold]:")
    for item in result["items"]:
        status = "[green]启用[/green]" if item["enabled"] else "[red]禁用[/red]"
        console.print(f"  • {item['name']} ({item['store_type']}) - {status}")


async def store_get(name: str):
    """获取存储配置详情"""
    client = APIClient()
    result = await client.get(f"/stores/{name}")
    console.print(f"\n[bold]存储配置详情[/bold]:")
    console.print(json.dumps(result, indent=2, ensure_ascii=False))


async def store_read(name: str, key: str):
    """从存储读取数据"""
    client = APIClient()
    result = await client.post(f"/stores/{name}/read", params={"key": key})
    console.print(f"[green]✓[/green] 读取成功: {result}")


async def store_write(name: str, key: str, value: str):
    """向存储写入数据"""
    client = APIClient()
    result = await client.post(f"/stores/{name}/write", params={"key": key, "value": value})
    console.print(f"[green]✓[/green] 写入成功")


async def store_delete(name: str):
    """删除存储配置"""
    client = APIClient()
    result = await client.delete(f"/stores/{name}")
    console.print(f"[green]✓[/green] 删除成功")


# ============ 代理管理命令 ============

async def proxy_create(name: str, proxy_type: str, host: str, port: int, **kwargs):
    """创建代理配置"""
    client = APIClient()
    data = {
        "name": name,
        "proxy_type": proxy_type,
        "host": host,
        "port": port,
        **kwargs
    }
    result = await client.post("/proxies", data)
    console.print(f"[green]✓[/green] 创建成功: {result}")


async def proxy_list():
    """列出所有代理配置"""
    client = APIClient()
    result = await client.get("/proxies")
    
    if not result.get("items"):
        console.print("[yellow]暂无代理配置[/yellow]")
        return
    
    console.print(f"\n[bold]代理配置列表 ({result['total']})[/bold]:")
    for item in result["items"]:
        status = "[green]启用[/green]" if item["enabled"] else "[red]禁用[/red]"
        console.print(f"  • {item['name']} ({item['proxy_type']}) - {item['host']}:{item['port']} - {status}")


async def proxy_get(name: str):
    """获取代理配置详情"""
    client = APIClient()
    result = await client.get(f"/proxies/{name}")
    console.print(f"\n[bold]代理配置详情[/bold]:")
    console.print(json.dumps(result, indent=2, ensure_ascii=False))


async def proxy_test(name: str, test_url: str = None, timeout: int = 30):
    """测试代理连接"""
    client = APIClient()
    data = {
        "proxy_name": name,
        "test_url": test_url or "https://httpbin.org/ip",
        "timeout": timeout
    }
    result = await client.post("/proxies/test", data)
    
    if result.get("success"):
        response_time = result.get("response_time", 0)
        console.print(f"[green]✓[/green] 代理测试成功 ({response_time:.2f}ms)")
    else:
        console.print(f"[red]✗[/red] 代理测试失败: {result.get('error')}")


async def proxy_stats():
    """获取代理统计信息"""
    client = APIClient()
    result = await client.get("/proxies/stats")
    console.print(f"\n[bold]代理统计信息[/bold]:")
    console.print(f"  总数: {result['total']}")
    console.print(f"  启用: {result['enabled']}")
    console.print(f"  禁用: {result['disabled']}")
    console.print(f"  按类型分布:")
    for ptype, count in result['by_type'].items():
        console.print(f"    {ptype}: {count}")


async def proxy_delete(name: str):
    """删除代理配置"""
    client = APIClient()
    result = await client.delete(f"/proxies/{name}")
    console.print(f"[green]✓[/green] 删除成功")


# ============ 系统命令 ============

async def system_status():
    """获取系统状态"""
    client = APIClient()
    
    console.print(f"\n[bold]CLIProxyAPI 系统状态[/bold]:")
    console.print(f"  API 地址: {client.base_url}")
    
    # 获取各模块统计
    try:
        auths = await client.get("/auths")
        stores = await client.get("/stores")
        proxies = await client.get("/proxies")
        
        console.print(f"  认证配置: {auths['total']}")
        console.print(f"  存储配置: {stores['total']}")
        console.print(f"  代理配置: {proxies['total']}")
    except Exception as e:
        console.print(f"  [red]无法连接到服务器: {e}[/red]")


__all__ = [
    "APIClient",
    "auth_create", "auth_list", "auth_get", "auth_update", "auth_delete",
    "store_create", "store_list", "store_get", "store_read", "store_write", "store_delete",
    "proxy_create", "proxy_list", "proxy_get", "proxy_test", "proxy_stats", "proxy_delete",
    "system_status",
]
