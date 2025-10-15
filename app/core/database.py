from supabase import create_client, Client
from app.core.config import settings

# 创建Supabase客户端
supabase: Client = create_client(
    settings.SUPABASE_URL,
    settings.SUPABASE_KEY
)

# 使用service_role key的客户端（用于管理员操作）
supabase_admin: Client = create_client(
    settings.SUPABASE_URL,
    settings.SUPABASE_SERVICE_KEY
)

def get_supabase() -> Client:
    """获取Supabase客户端"""
    return supabase

def get_supabase_admin() -> Client:
    """获取管理员权限的Supabase客户端"""
    return supabase_admin