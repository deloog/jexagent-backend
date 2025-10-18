"""
数据库连接模块
支持同步和异步Supabase客户端
"""
import os
from supabase import create_client, Client

# ✅ 配置
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("缺少 SUPABASE_URL 或 SUPABASE_KEY 环境变量")

# 同步客户端（默认）
_supabase_client: Client = None

def get_supabase() -> Client:
    """
    获取Supabase客户端（同步版本）
    
    ⚠️ 注意：supabase-py 的默认 Client 内部使用 httpx.Client（同步）
    在异步环境中大量使用会阻塞事件循环
    
    建议：
    - 短期方案：在线程池中运行（见下方）
    - 长期方案：等待官方 AsyncClient 或使用 PostgREST 直接调用
    """
    global _supabase_client
    if _supabase_client is None:
        _supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _supabase_client

# ✅ 异步包装器（短期方案）
import asyncio
from concurrent.futures import ThreadPoolExecutor
from functools import wraps

# 线程池
_executor = ThreadPoolExecutor(max_workers=10)

def run_in_executor(func):
    """
    装饰器：在线程池中运行同步函数
    
    使用示例：
    @run_in_executor
    def sync_db_operation():
        return get_supabase().table("tasks").select("*").execute()
    
    # 异步调用：
    result = await sync_db_operation()
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(_executor, func, *args, **kwargs)
    return wrapper

# ✅ 使用示例（如果需要在task_service中使用）
"""
from app.core.database import get_supabase, run_in_executor

@run_in_executor
def get_task_sync(task_id: str):
    return get_supabase().table("tasks").select("*").eq("id", task_id).execute()

# 在异步函数中：
async def some_async_function():
    result = await get_task_sync(task_id)
"""
