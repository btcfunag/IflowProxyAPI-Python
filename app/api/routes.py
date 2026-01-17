"""API 路由定义"""
import json
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, status
from typing import List, Dict, Any
from ..auth.models import AuthConfig, AuthConfigUpdate, AuthResponse
from ..auth.service import auth_service
from ..stores.models import StoreConfig, StoreConfigUpdate, StoreResponse
from ..stores.service import store_service
from ..proxy.models import ProxyConfig, ProxyConfigUpdate, ProxyTestRequest, ProxyResponse, ProxyStats
from ..proxy.service import proxy_service
from ..iflow.routes import router as iflow_router
from ..logger import logger


# 创建路由器
router = APIRouter()


# ============ 认证管理路由 ============

@router.post("/auths", response_model=AuthResponse)
async def create_auth(auth: AuthConfig):
    """创建认证配置"""
    result = await auth_service.create_auth(auth)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "创建失败"))
    return AuthResponse(success=True, message="认证配置创建成功", data=result)


@router.get("/auths/{name}", response_model=AuthResponse)
async def get_auth(name: str):
    """获取认证配置"""
    auth = await auth_service.get_auth(name)
    if not auth:
        raise HTTPException(status_code=404, detail="认证配置不存在")
    return AuthResponse(success=True, message="获取成功", data=auth)


@router.get("/auths", response_model=AuthResponse)
async def list_auths():
    """列出所有认证配置"""
    auths = await auth_service.list_auths()
    return AuthResponse(success=True, message="获取成功", data={"items": auths, "total": len(auths)})


@router.put("/auths/{name}", response_model=AuthResponse)
async def update_auth(name: str, update: AuthConfigUpdate):
    """更新认证配置"""
    success = await auth_service.update_auth(name, update)
    if not success:
        raise HTTPException(status_code=404, detail="认证配置不存在或更新失败")
    return AuthResponse(success=True, message="更新成功")


@router.delete("/auths/{name}", response_model=AuthResponse)
async def delete_auth(name: str):
    """删除认证配置"""
    success = await auth_service.delete_auth(name)
    if not success:
        raise HTTPException(status_code=404, detail="认证配置不存在")
    return AuthResponse(success=True, message="删除成功")


# ============ 存储管理路由 ============

@router.post("/stores", response_model=StoreResponse)
async def create_store(store: StoreConfig):
    """创建存储配置"""
    result = await store_service.create_store(store)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "创建失败"))
    return StoreResponse(success=True, message="存储配置创建成功", data=result)


@router.get("/stores/{name}", response_model=StoreResponse)
async def get_store(name: str):
    """获取存储配置"""
    store = await store_service.get_store(name)
    if not store:
        raise HTTPException(status_code=404, detail="存储配置不存在")
    return StoreResponse(success=True, message="获取成功", data=store)


@router.get("/stores", response_model=StoreResponse)
async def list_stores():
    """列出所有存储配置"""
    stores = await store_service.list_stores()
    return StoreResponse(success=True, message="获取成功", data={"items": stores, "total": len(stores)})


@router.put("/stores/{name}", response_model=StoreResponse)
async def update_store(name: str, update: StoreConfigUpdate):
    """更新存储配置"""
    success = await store_service.update_store(name, update)
    if not success:
        raise HTTPException(status_code=404, detail="存储配置不存在或更新失败")
    return StoreResponse(success=True, message="更新成功")


@router.delete("/stores/{name}", response_model=StoreResponse)
async def delete_store(name: str):
    """删除存储配置"""
    success = await store_service.delete_store(name)
    if not success:
        raise HTTPException(status_code=404, detail="存储配置不存在")
    return StoreResponse(success=True, message="删除成功")


@router.post("/stores/{name}/read")
async def read_from_store(name: str, key: str):
    """从存储读取数据"""
    value = await store_service.read_from_store(name, key)
    if value is None:
        raise HTTPException(status_code=404, detail="数据不存在或读取失败")
    return {"success": True, "value": value}


@router.post("/stores/{name}/write")
async def write_to_store(name: str, key: str, value: str):
    """向存储写入数据"""
    success = await store_service.write_to_store(name, key, value)
    if not success:
        raise HTTPException(status_code=500, detail="写入失败")
    return {"success": True, "message": "写入成功"}


# ============ 代理管理路由 ============

@router.post("/proxies", response_model=ProxyResponse)
async def create_proxy(proxy: ProxyConfig):
    """创建代理配置"""
    result = await proxy_service.create_proxy(proxy)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "创建失败"))
    return ProxyResponse(success=True, message="代理配置创建成功", data=result)


@router.get("/proxies/{name}", response_model=ProxyResponse)
async def get_proxy(name: str):
    """获取代理配置"""
    proxy = await proxy_service.get_proxy(name)
    if not proxy:
        raise HTTPException(status_code=404, detail="代理配置不存在")
    return ProxyResponse(success=True, message="获取成功", data=proxy)


@router.get("/proxies", response_model=ProxyResponse)
async def list_proxies():
    """列出所有代理配置"""
    proxies = await proxy_service.list_proxies()
    return ProxyResponse(success=True, message="获取成功", data={"items": proxies, "total": len(proxies)})


@router.put("/proxies/{name}", response_model=ProxyResponse)
async def update_proxy(name: str, update: ProxyConfigUpdate):
    """更新代理配置"""
    success = await proxy_service.update_proxy(name, update)
    if not success:
        raise HTTPException(status_code=404, detail="代理配置不存在或更新失败")
    return ProxyResponse(success=True, message="更新成功")


@router.delete("/proxies/{name}", response_model=ProxyResponse)
async def delete_proxy(name: str):
    """删除代理配置"""
    success = await proxy_service.delete_proxy(name)
    if not success:
        raise HTTPException(status_code=404, detail="代理配置不存在")
    return ProxyResponse(success=True, message="删除成功")


@router.post("/proxies/test")
async def test_proxy(request: ProxyTestRequest):
    """测试代理连接"""
    result = await proxy_service.test_proxy(
        request.proxy_name,
        request.test_url,
        request.timeout
    )
    return result.dict()


@router.get("/proxies/stats", response_model=Dict[str, Any])
async def get_proxy_stats():
    """获取代理统计信息"""
    return await proxy_service.get_stats()


# ============ iFlow 路由 ============

router.include_router(iflow_router)


__all__ = ["router"]
