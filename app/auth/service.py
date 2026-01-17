"""认证服务模块 - 处理认证配置的逻辑"""
import json
import aiosqlite
from pathlib import Path
from typing import List, Optional, Dict, Any
from .models import AuthConfig, AuthConfigUpdate
from ..logger import logger
from ..settings import DATA_DIR


# 数据库文件路径
DB_PATH = DATA_DIR / "auth.db"


class AuthService:
    """认证配置服务"""
    
    def __init__(self):
        self.db_path = DB_PATH
        
    async def init_db(self):
        """初始化数据库表"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS auths (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    auth_type TEXT NOT NULL,
                    config TEXT NOT NULL,
                    enabled INTEGER DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT
                )
            """)
            await db.commit()
            logger.info(f"数据库初始化完成: {self.db_path}")
    
    async def create_auth(self, auth: AuthConfig) -> Dict[str, Any]:
        """创建认证配置"""
        async with aiosqlite.connect(self.db_path) as db:
            try:
                cursor = await db.execute(
                    """
                    INSERT INTO auths (name, auth_type, config, enabled, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        auth.name,
                        auth.auth_type,
                        json.dumps(auth.config),
                        1 if auth.enabled else 0,
                        auth.created_at.isoformat(),
                        auth.updated_at.isoformat() if auth.updated_at else None
                    )
                )
                await db.commit()
                auth_id = cursor.lastrowid
                logger.info(f"创建认证配置: {auth.name} (ID: {auth_id})")
                return {"id": auth_id, "name": auth.name, "success": True}
            except aiosqlite.IntegrityError:
                logger.warning(f"认证配置已存在: {auth.name}")
                return {"success": False, "error": "认证配置名称已存在"}
    
    async def get_auth(self, name: str) -> Optional[Dict[str, Any]]:
        """获取认证配置"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM auths WHERE name = ?",
                (name,)
            )
            row = await cursor.fetchone()
            if row:
                return dict(row)
            return None
    
    async def list_auths(self) -> List[Dict[str, Any]]:
        """列出所有认证配置"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM auths ORDER BY id")
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    
    async def update_auth(self, name: str, update: AuthConfigUpdate) -> bool:
        """更新认证配置"""
        async with aiosqlite.connect(self.db_path) as db:
            updates = []
            params = []
            
            if update.name:
                updates.append("name = ?")
                params.append(update.name)
            if update.auth_type:
                updates.append("auth_type = ?")
                params.append(update.auth_type)
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
                
            query = f"UPDATE auths SET {', '.join(updates)} WHERE name = ?"
            cursor = await db.execute(query, params)
            await db.commit()
            
            if cursor.rowcount > 0:
                logger.info(f"更新认证配置: {name}")
                return True
            return False
    
    async def delete_auth(self, name: str) -> bool:
        """删除认证配置"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "DELETE FROM auths WHERE name = ?",
                (name,)
            )
            await db.commit()
            
            if cursor.rowcount > 0:
                logger.info(f"删除认证配置: {name}")
                return True
            return False


# 全局服务实例
auth_service = AuthService()

__all__ = ["AuthService", "auth_service"]
