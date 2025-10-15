from fastapi import APIRouter, Depends, HTTPException
from app.models.user import UserResponse
from app.core.dependencies import get_current_active_user
from app.core.database import get_supabase

router = APIRouter(prefix="/users", tags=["用户"])

@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: UserResponse = Depends(get_current_active_user)
):
    """获取当前用户详细信息"""
    return current_user

@router.get("/me/quota")
async def get_user_quota(
    current_user: UserResponse = Depends(get_current_active_user)
):
    """获取用户配额信息"""
    return {
        "daily_quota": current_user.daily_quota,
        "daily_used": current_user.daily_used,
        "remaining": current_user.daily_quota - current_user.daily_used,
        "tier": current_user.tier
    }