"""CLI 工具入口 - 命令行接口"""
import asyncio
import sys
import argparse
import json
import signal
from pathlib import Path
from typing import Optional

from app import logger, console, settings
from app.commands import (
    APIClient,
    auth_create, auth_list, auth_get, auth_update, auth_delete,
    store_create, store_list, store_get, store_read, store_write, store_delete,
    proxy_create, proxy_list, proxy_get, proxy_test, proxy_stats, proxy_delete,
    system_status,
)


# 服务器控制
async def start_server(host: str = None, port: int = None):
    """启动 API 服务器"""
    if host:
        settings.api_host = host
    if port:
        settings.api_port = port
    
    from main import main
    console.print(f"\n[bold cyan]启动 CLIProxyAPI 服务器...[/bold cyan]")
    main()


# 认证管理
def handle_auth_command(args):
    """处理认证相关命令"""
    action = args.action
    
    if action == "create":
        config = {}
        if args.config:
            config = json.loads(args.config)
        asyncio.run(auth_create(
            name=args.name,
            auth_type=args.type,
            config=config,
            enabled=not args.disabled
        ))
    
    elif action == "list":
        asyncio.run(auth_list())
    
    elif action == "get":
        asyncio.run(auth_get(name=args.name))
    
    elif action == "update":
        updates = {}
        if args.type:
            updates["auth_type"] = args.type
        if args.config:
            updates["config"] = json.loads(args.config)
        updates["enabled"] = not args.disabled if args.disabled is not None else None
        asyncio.run(auth_update(name=args.name, **updates))
    
    elif action == "delete":
        asyncio.run(auth_delete(name=args.name))


# 存储管理
def handle_store_command(args):
    """处理存储相关命令"""
    action = args.action
    
    if action == "create":
        config = {}
        if args.config:
            config = json.loads(args.config)
        asyncio.run(store_create(
            name=args.name,
            store_type=args.type,
            config=config,
            enabled=not args.disabled
        ))
    
    elif action == "list":
        asyncio.run(store_list())
    
    elif action == "get":
        asyncio.run(store_get(name=args.name))
    
    elif action == "read":
        asyncio.run(store_read(name=args.name, key=args.key))
    
    elif action == "write":
        asyncio.run(store_write(
            name=args.name,
            key=args.key,
            value=args.value
        ))
    
    elif action == "delete":
        asyncio.run(store_delete(name=args.name))


# 代理管理
def handle_proxy_command(args):
    """处理代理相关命令"""
    action = args.action
    
    if action == "create":
        asyncio.run(proxy_create(
            name=args.name,
            proxy_type=args.type,
            host=args.host,
            port=args.port,
            username=args.username,
            password=args.password,
            enabled=not args.disabled,
            timeout=args.timeout
        ))
    
    elif action == "list":
        asyncio.run(proxy_list())
    
    elif action == "get":
        asyncio.run(proxy_get(name=args.name))
    
    elif action == "test":
        asyncio.run(proxy_test(
            name=args.name,
            test_url=args.url,
            timeout=args.timeout
        ))
    
    elif action == "stats":
        asyncio.run(proxy_stats())
    
    elif action == "delete":
        asyncio.run(proxy_delete(name=args.name))


def main():
    """主入口函数"""
    parser = argparse.ArgumentParser(
        prog="cliproxyapi",
        description="CLIProxyAPI - 命令行代理 API 管理工具"
    )
    parser.add_argument("--version", action="version", version="%(prog)s 0.1.0")
    parser.add_argument("--debug", action="store_true", help="启用调试模式")
    
    subparsers = parser.add_subparsers(dest="command", help="命令类别")
    
    # 服务器命令
    server_parser = subparsers.add_parser("server", help="服务器管理")
    server_sub = server_parser.add_subparsers(dest="server_action")
    
    start_parser = server_sub.add_parser("start", help="启动服务器")
    start_parser.add_argument("--host", help="监听地址")
    start_parser.add_argument("--port", type=int, help="监听端口")
    
    # 系统命令
    sys_parser = subparsers.add_parser("system", help="系统管理")
    sys_sub = sys_parser.add_subparsers(dest="sys_action")
    status_parser = sys_sub.add_parser("status", help="查看系统状态")
    status_parser.set_defaults(func=lambda args: asyncio.run(system_status()))
    
    # 认证命令
    auth_parser = subparsers.add_parser("auth", help="认证管理")
    auth_sub = auth_parser.add_subparsers(dest="action")
    
    auth_create_parser = auth_sub.add_parser("create", help="创建认证配置")
    auth_create_parser.add_argument("--name", required=True, help="配置名称")
    auth_create_parser.add_argument("--type", required=True, help="认证类型")
    auth_create_parser.add_argument("--config", help="配置 JSON")
    auth_create_parser.add_argument("--disabled", action="store_true", help="禁用")
    
    auth_list_parser = auth_sub.add_parser("list", help="列出认证配置")
    auth_list_parser.set_defaults(func=lambda args: asyncio.run(auth_list()))
    
    auth_get_parser = auth_sub.add_parser("get", help="获取认证配置")
    auth_get_parser.add_argument("--name", required=True, help="配置名称")
    
    auth_update_parser = auth_sub.add_parser("update", help="更新认证配置")
    auth_update_parser.add_argument("--name", required=True, help="配置名称")
    auth_update_parser.add_argument("--type", help="认证类型")
    auth_update_parser.add_argument("--config", help="配置 JSON")
    auth_update_parser.add_argument("--disabled", action="store_true", help="禁用")
    
    auth_delete_parser = auth_sub.add_parser("delete", help="删除认证配置")
    auth_delete_parser.add_argument("--name", required=True, help="配置名称")
    
    # 存储命令
    store_parser = subparsers.add_parser("store", help="存储管理")
    store_sub = store_parser.add_subparsers(dest="action")
    
    store_create_parser = store_sub.add_parser("create", help="创建存储配置")
    store_create_parser.add_argument("--name", required=True, help="配置名称")
    store_create_parser.add_argument("--type", required=True, help="存储类型")
    store_create_parser.add_argument("--config", help="配置 JSON")
    store_create_parser.add_argument("--disabled", action="store_true", help="禁用")
    
    store_list_parser = store_sub.add_parser("list", help="列出存储配置")
    store_list_parser.set_defaults(func=lambda args: asyncio.run(store_list()))
    
    store_get_parser = store_sub.add_parser("get", help="获取存储配置")
    store_get_parser.add_argument("--name", required=True, help="配置名称")
    
    store_read_parser = store_sub.add_parser("read", help="从存储读取")
    store_read_parser.add_argument("--name", required=True, help="存储名称")
    store_read_parser.add_argument("--key", required=True, help="键名")
    
    store_write_parser = store_sub.add_parser("write", help="向存储写入")
    store_write_parser.add_argument("--name", required=True, help="存储名称")
    store_write_parser.add_argument("--key", required=True, help="键名")
    store_write_parser.add_argument("--value", required=True, help="值")
    
    store_delete_parser = store_sub.add_parser("delete", help="删除存储配置")
    store_delete_parser.add_argument("--name", required=True, help="配置名称")
    
    # 代理命令
    proxy_parser = subparsers.add_parser("proxy", help="代理管理")
    proxy_sub = proxy_parser.add_subparsers(dest="action")
    
    proxy_create_parser = proxy_sub.add_parser("create", help="创建代理配置")
    proxy_create_parser.add_argument("--name", required=True, help="配置名称")
    proxy_create_parser.add_argument("--type", required=True, help="代理类型")
    proxy_create_parser.add_argument("--host", required=True, help="代理主机")
    proxy_create_parser.add_argument("--port", required=True, type=int, help="代理端口")
    proxy_create_parser.add_argument("--username", help="用户名")
    proxy_create_parser.add_argument("--password", help="密码")
    proxy_create_parser.add_argument("--disabled", action="store_true", help="禁用")
    proxy_create_parser.add_argument("--timeout", type=int, default=30, help="超时时间")
    
    proxy_list_parser = proxy_sub.add_parser("list", help="列出代理配置")
    proxy_list_parser.set_defaults(func=lambda args: asyncio.run(proxy_list()))
    
    proxy_get_parser = proxy_sub.add_parser("get", help="获取代理配置")
    proxy_get_parser.add_argument("--name", required=True, help="配置名称")
    
    proxy_test_parser = proxy_sub.add_parser("test", help="测试代理")
    proxy_test_parser.add_argument("--name", required=True, help="代理名称")
    proxy_test_parser.add_argument("--url", help="测试 URL")
    proxy_test_parser.add_argument("--timeout", type=int, default=30, help="超时时间")
    
    proxy_stats_parser = proxy_sub.add_parser("stats", help="代理统计")
    proxy_stats_parser.set_defaults(func=lambda args: asyncio.run(proxy_stats()))
    
    proxy_delete_parser = proxy_sub.add_parser("delete", help="删除代理配置")
    proxy_delete_parser.add_argument("--name", required=True, help="配置名称")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 0
    
    try:
        if args.command == "server":
            if args.server_action == "start":
                asyncio.run(start_server(host=args.host, port=args.port))
        elif args.command == "auth":
            handle_auth_command(args)
        elif args.command == "store":
            handle_store_command(args)
        elif args.command == "proxy":
            handle_proxy_command(args)
        elif args.command == "system":
            if hasattr(args, 'func'):
                args.func(args)
    except KeyboardInterrupt:
        console.print("\n[yellow]操作已取消[/yellow]")
        return 130
    except Exception as e:
        console.print(f"\n[red]错误: {e}[/red]")
        if args.debug:
            import traceback
            console.print(traceback.format_exc())
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
