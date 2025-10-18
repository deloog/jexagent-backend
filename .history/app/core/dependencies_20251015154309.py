from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
from uuid import UUID
from app.core.security import decode_access_token
from app.core.database import get_supabase
from app.models.user import UserResponse

security = HTTPBearer()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> UserResponse:
    """获取当前登录用户"""
    token = credentials.credentials
    
    # 解码token
    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证凭证",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user_id: str = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证凭证"
        )
    
    # 从数据库获取用户信息
    supabase = get_supabase()
    response = supabase.table("users").select("*").eq("id", user_id).single().execute()
    
    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在"
        )
    
    return UserResponse(**response.data)

async def get_current_active_user(
    current_user: UserResponse = Depends(get_current_user)
) -> UserResponse:
    """获取当前活跃用户（检查订阅状态）"""
    print(f"[DEBUG] user={current_user}")
    if current_user.subscription_status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="账户已被禁用或订阅已过期"
        )
    return current_user