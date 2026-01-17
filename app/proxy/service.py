"""代理服务模块 - 处理代理配置和操作"""
import json
import aiosqlite
from typing import Dict, Any, Optional, List
import httpx
from .models import ProxyConfig, ProxyConfigUpdate, ProxyTestResult
from ..logger import logger
from ..settings import DATA_DIR


# 数据库文件路径
DB_PATH = DATA_DIR / "proxies.db"


class ProxyService:
    """代理配置服务"""
    
    def __init__(self):
        self.db_path = DB_PATH
    
    async def init_db(self):
        """初始化数据库表"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS proxies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    proxy_type TEXT NOT NULL,
                    host TEXT NOT NULL,
                    port INTEGER NOT NULL,
                    username TEXT,
                    password TEXT,
                    enabled INTEGER DEFAULT 1,
                    tags TEXT,
                    timeout INTEGER DEFAULT 30,
                    created_at TEXT NOT NULL,
                    updated_at TEXT
                )
            """)
            await db.commit()
            logger.info(f"代理数据库初始化完成: {self.db_path}")
    
    async def create_proxy(self, proxy: ProxyConfig) -> Dict[str, Any]:
        """创建代理配置"""
        async with aiosqlite.connect(self.db_path) as db:
            try:
                cursor = await db.execute(
                    """
                    INSERT INTO proxies (name, proxy_type, host, port, username, password, enabled, tags, timeout, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        proxy.name,
                        proxy.proxy_type,
                        proxy.host,
                        proxy.port,
                        proxy.username,
                        proxy.password,
                        1 if proxy.enabled else 0,
                        json.dumps(proxy.tags),
                        proxy.timeout,
                        proxy.created_at.isoformat(),
                        proxy.updated_at.isoformat() if proxy.updated_at else None
                    )
                )
                await db.commit()
                proxy_id = cursor.lastrowid
                logger.info(f"创建代理配置: {proxy.name} (ID: {proxy_id})")
                return {"id": proxy_id, "name": proxy.name, "success": True}
            except aiosqlite.IntegrityError:
                logger.warning(f"代理配置已存在: {proxy.name}")
                return {"success": False, "error": "代理配置名称已存在"}
    
    async def get_proxy(self, name: str) -> Optional[Dict[str, Any]]:
        """获取代理配置"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM proxies WHERE name = ?",
                (name,)
            )
            row = await cursor.fetchone()
            if row:
                result = dict(row)
                # 解析 tags 字段
                if result['tags']:
                    result['tags'] = json.loads(result['tags'])
                else:
                    result['tags'] = []
                return result
            return None
    
    async def list_proxies(self) -> List[Dict[str, Any]]:
        """列出所有代理配置"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM proxies ORDER BY id")
            rows = await cursor.fetchall()
            proxies = []
            for row in rows:
                result = dict(row)
                if result['tags']:
                    result['tags'] = json.loads(result['tags'])
                else:
                    result['tags'] = []
                proxies.append(result)
            return proxies
    
    async def update_proxy(self, name: str, update: ProxyConfigUpdate) -> bool:
        """更新代理配置"""
        async with aiosqlite.connect(self.db_path) as db:
            updates = []
            params = []
            
            if update.name:
                updates.append("name = ?")
                params.append(update.name)
            if update.proxy_type:
                updates.append("proxy_type = ?")
                params.append(update.proxy_type)
            if update.host:
                updates.append("host = ?")
                params.append(update.host)
            if update.port:
                updates.append("port = ?")
                params.append(update.port)
            if update.username is not None:
                updates.append("username = ?")
                params.append(update.username)
            if update.password is not None:
                updates.append("password = ?")
                params.append(update.password)
            if update.enabled is not None:
                updates.append("enabled = ?")
                params.append(1 if update.enabled else 0)
            if update.tags is not None:
                updates.append("tags = ?")
                params.append(json.dumps(update.tags))
            if update.timeout is not None:
                updates.append("timeout = ?")
                params.append(update.timeout)
            
            updates.append("updated_at = ?")
            params.append(update.updated_at.isoformat())
            params.append(name)
            
            if not updates:
                return False
                
            query = f"UPDATE proxies SET {', '.join(updates)} WHERE name = ?"
            cursor = await db.execute(query, params)
            await db.commit()
            
            if cursor.rowcount > 0:
                logger.info(f"更新代理配置: {name}")
                return True
            return False
    
    async def delete_proxy(self, name: str) -> bool:
        """删除代理配置"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "DELETE FROM proxies WHERE name = ?",
                (name,)
            )
            await db.commit()
            
            if cursor.rowcount > 0:
                logger.info(f"删除代理配置: {name}")
                return True
            return False
    
    async def test_proxy(self, name: str, test_url: str = "https://httpbin.org/ip", timeout: int = 30) -> ProxyTestResult:
        """测试代理连接"""
        proxy = await self.get_proxy(name)
        if not proxy:
            return ProxyTestResult(
                proxy_name=name,
                success=False,
                error=f"代理不存在: {name}"
            )
        
        if not proxy['enabled']:
            return ProxyTestResult(
                proxy_name=name,
                success=False,
                error="代理未启用"
            )
        
        # 构建代理 URL
        auth = ""
        if proxy['username'] and proxy['password']:
            auth = f"{proxy['username']}:{proxy['password']}@"
        proxy_url = f"{proxy['proxy_type']}://{auth}{proxy['host']}:{proxy['port']}"
        
        try:
            import time
            start_time = time.time()
            
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(test_url, proxies={"http://": proxy_url, "https://": proxy_url})
                
            response_time = (time.time() - start_time) * 1000  # 转换为毫秒
            
            if response.status_code == 200:
                logger.info(f"代理测试成功: {name} ({response_time:.2f}ms)")
                return ProxyTestResult(
                    proxy_name=name,
                    success=True,
                    response_time=response_time,
                    response_data=response.json()
                )
            else:
                return ProxyTestResult(
                    proxy_name=name,
                    success=False,
                    error=f"HTTP {response.status_code}"
                )
        except Exception as e:
            logger.error(f"代理测试失败: {name} - {e}")
            return ProxyTestResult(
                proxy_name=name,
                success=False,
                error=str(e)
            )
    
    async def get_stats(self) -> Dict[str, Any]:
        """获取代理统计信息"""
        proxies = await self.list_proxies()
        
        stats = {
            "total": len(proxies),
            "enabled": sum(1 for p in proxies if p['enabled']),
            "disabled": sum(1 for p in proxies if not p['enabled']),
            "by_type": {}
        }
        
        for proxy in proxies:
            proxy_type = proxy['proxy_type']
            stats['by_type'][proxy_type] = stats['by_type'].get(proxy_type, 0) + 1
        
        return stats


# 全局服务实例
proxy_service = ProxyService()

__all__ = ["ProxyService", "proxy_service"]
