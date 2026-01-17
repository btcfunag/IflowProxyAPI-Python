"""存储服务模块 - 处理存储配置和操作"""
import json
import aiosqlite
from pathlib import Path
from typing import Dict, Any, Optional, List
import httpx
from .models import StoreConfig, StoreConfigUpdate
from ..logger import logger
from ..settings import DATA_DIR


# 数据库文件路径
DB_PATH = DATA_DIR / "stores.db"

# 内存存储
class MemoryStorage:
    """内存存储实现"""
    
    def __init__(self):
        self._storage: Dict[str, Any] = {}
        self._metadata: Dict[str, Dict] = {}
    
    async def get(self, key: str) -> Optional[Any]:
        return self._storage.get(key)
    
    async def set(self, key: str, value: Any, metadata: Dict = None) -> bool:
        self._storage[key] = value
        self._metadata[key] = metadata or {}
        return True
    
    async def delete(self, key: str) -> bool:
        if key in self._storage:
            del self._storage[key]
            if key in self._metadata:
                del self._metadata[key]
            return True
        return False
    
    async def list_keys(self) -> List[str]:
        return list(self._storage.keys())


# 全局内存存储实例
memory_storage = MemoryStorage()


class StoreService:
    """存储配置服务"""
    
    def __init__(self):
        self.db_path = DB_PATH
        self._http_client: Optional[httpx.AsyncClient] = None
    
    @property
    def http_client(self) -> httpx.AsyncClient:
        """获取 HTTP 客户端"""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(timeout=30.0)
        return self._http_client
    
    async def close(self):
        """关闭连接"""
        if self._http_client:
            await self._http_client.aclose()
    
    async def init_db(self):
        """初始化数据库表"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS stores (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    store_type TEXT NOT NULL,
                    config TEXT NOT NULL,
                    enabled INTEGER DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT
                )
            """)
            await db.commit()
            logger.info(f"存储数据库初始化完成: {self.db_path}")
    
    async def create_store(self, store: StoreConfig) -> Dict[str, Any]:
        """创建存储配置"""
        async with aiosqlite.connect(self.db_path) as db:
            try:
                cursor = await db.execute(
                    """
                    INSERT INTO stores (name, store_type, config, enabled, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        store.name,
                        store.store_type,
                        json.dumps(store.config),
                        1 if store.enabled else 0,
                        store.created_at.isoformat(),
                        store.updated_at.isoformat() if store.updated_at else None
                    )
                )
                await db.commit()
                store_id = cursor.lastrowid
                logger.info(f"创建存储配置: {store.name} (ID: {store_id})")
                return {"id": store_id, "name": store.name, "success": True}
            except aiosqlite.IntegrityError:
                logger.warning(f"存储配置已存在: {store.name}")
                return {"success": False, "error": "存储配置名称已存在"}
    
    async def get_store(self, name: str) -> Optional[Dict[str, Any]]:
        """获取存储配置"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM stores WHERE name = ?",
                (name,)
            )
            row = await cursor.fetchone()
            if row:
                return dict(row)
            return None
    
    async def list_stores(self) -> List[Dict[str, Any]]:
        """列出所有存储配置"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM stores ORDER BY id")
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    
    async def update_store(self, name: str, update: StoreConfigUpdate) -> bool:
        """更新存储配置"""
        async with aiosqlite.connect(self.db_path) as db:
            updates = []
            params = []
            
            if update.name:
                updates.append("name = ?")
                params.append(update.name)
            if update.store_type:
                updates.append("store_type = ?")
                params.append(update.store_type)
            if update.config:
                updates.append("config = ?")
                params.append(json.dumps(update.config))
            if update.enabled is not None:
                updates.append("enabled = ?")
                params.append(1 if update.enabled else 0)
            
            updates.append("updated_at = ?")
            params.append(update.updated_at.isoformat())
            params.append(name)
            
            if not updates:
                return False
                
            query = f"UPDATE stores SET {', '.join(updates)} WHERE name = ?"
            cursor = await db.execute(query, params)
            await db.commit()
            
            if cursor.rowcount > 0:
                logger.info(f"更新存储配置: {name}")
                return True
            return False
    
    async def delete_store(self, name: str) -> bool:
        """删除存储配置"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "DELETE FROM stores WHERE name = ?",
                (name,)
            )
            await db.commit()
            
            if cursor.rowcount > 0:
                logger.info(f"删除存储配置: {name}")
                return True
            return False
    
    async def read_from_store(self, store_name: str, key: str) -> Optional[Any]:
        """从存储读取数据"""
        store = await self.get_store(store_name)
        if not store:
            logger.error(f"存储不存在: {store_name}")
            return None
        
        config = json.loads(store['config'])
        
        if store['store_type'] == 'memory':
            return await memory_storage.get(key)
        
        elif store['store_type'] == 'local':
            base_path = Path(config.get('base_path', '.'))
            file_path = base_path / key
            if file_path.exists():
                return file_path.read_text()
            return None
        
        elif store['store_type'] == 'http':
            base_url = config.get('base_url', '')
            url = f"{base_url.rstrip('/')}/{key.lstrip('/')}"
            try:
                response = await self.http_client.get(url)
                if response.status_code == 200:
                    return response.text
                return None
            except Exception as e:
                logger.error(f"HTTP 读取失败: {e}")
                return None
        
        return None
    
    async def write_to_store(self, store_name: str, key: str, value: Any) -> bool:
        """向存储写入数据"""
        store = await self.get_store(store_name)
        if not store:
            logger.error(f"存储不存在: {store_name}")
            return False
        
        config = json.loads(store['config'])
        
        if store['store_type'] == 'memory':
            await memory_storage.set(key, value)
            return True
        
        elif store['store_type'] == 'local':
            base_path = Path(config.get('base_path', '.'))
            file_path = base_path / key
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(str(value))
            return True
        
        elif store['store_type'] == 'http':
            base_url = config.get('base_url', '')
            url = f"{base_url.rstrip('/')}/{key.lstrip('/')}"
            try:
                response = await self.http_client.post(url, content=str(value))
                return response.status_code in (200, 201)
            except Exception as e:
                logger.error(f"HTTP 写入失败: {e}")
                return False
        
        return False


# 全局服务实例
store_service = StoreService()

__all__ = ["StoreService", "store_service", "MemoryStorage", "memory_storage"]
