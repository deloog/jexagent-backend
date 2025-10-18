from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
from app.models.user import UserResponse
from app.core.database import get_supabase
from datetime import datetime
import os

security = HTTPBearer(auto_error=False)

async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> UserResponse:
    """获取当前登录用户（开发模式下可跳过认证）"""
    
    # 开发模式：使用测试用户
    if os.getenv("ENVIRONMENT", "development") == "development":
        if not credentials or not credentials.credentials:
            # 返回测试用户
            return UserResponse(
                id="test-user-id",
                email="test@example.com",
                name="测试用户",
                avatar="",
                subscription_tier="free",
                
                daily_quota=10,
                daily_used=0,
                subscription_status="active",      # ← 补这行
                total_tasks=0,                     # ← 补这行
                total_spent=0.0,                   # ← 补这行
                created_at=datetime.utcnow(),
                last_login=datetime.utcnow()
            )
    
    # 生产模式：验证token
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未提供认证凭据",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = credentials.credentials
    
    try:
        supabase = get_supabase()
        
        # 使用Supabase验证token
        user_response = supabase.auth.get_user(token)
        if not user_response.user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="无效的认证凭据",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        user_id = user_response.user.id
        
        # 查询用户信息
        result = supabase.table("users").select("*").eq("id", user_id).single().execute()
        
        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="用户不存在"
            )
        
        return UserResponse(**result.data)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"认证失败: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )

async def get_current_active_user(
    current_user: UserResponse = Depends(get_current_user)
) -> UserResponse:
    """获取当前活跃用户"""
    return current_user