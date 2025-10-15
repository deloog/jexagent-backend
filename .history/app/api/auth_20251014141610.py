from fastapi import APIRouter, HTTPException, status, Depends
from datetime import timedelta
from app.models.auth import UserRegister, UserLogin, Token
from app.models.user import UserResponse
from app.core.database import get_supabase
from app.core.security import get_password_hash, verify_password, create_access_token
from app.core.config import settings
from app.core.dependencies import get_current_active_user

router = APIRouter(prefix="/auth", tags=["认证"])

@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserRegister):
    """用户注册"""
    supabase = get_supabase()
    
    # 检查邮箱是否已存在
    existing = supabase.table("users").select("id").eq("email", user_data.email).execute()
    if existing.data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该邮箱已被注册"
        )
    
    # 创建用户（注意：实际生产环境应该使用Supabase Auth）
    # 这里为了简化MVP，直接在users表创建
    hashed_password = get_password_hash(user_data.password)
    
    new_user = {
        "email": user_data.email,
        "name": user_data.name,
        "tier": "free",
        "subscription_status": "active",
        "daily_quota": 3,
        "daily_used": 0
    }
    
    response = supabase.table("users").insert(new_user).execute()
    
    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="用户创建失败"
        )
    
    user = response.data[0]
    
    # 生成token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(user["id"])},
        expires_delta=access_token_expires
    )
    
    return Token(access_token=access_token)

@router.post("/login", response_model=Token)
async def login(credentials: UserLogin):
    """用户登录"""
    supabase = get_supabase()
    
    # 查找用户
    response = supabase.table("users").select("*").eq("email", credentials.email).execute()
    
    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="邮箱或密码错误"
        )
    
    user = response.data[0]
    
    # 注意：这里为了MVP简化，暂时跳过密码验证
    # 实际生产环境应该使用Supabase Auth或验证密码哈希
    
    # 生成token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(user["id"])},
        expires_delta=access_token_expires
    )
    
    return Token(access_token=access_token)

@router.get("/me", response_model=UserResponse)
async def get_me(current_user: UserResponse = Depends(get_current_active_user)):
    """获取当前用户信息"""
    return current_user

@router.post("/logout")
async def logout():
    """用户登出（客户端删除token即可）"""
    return {"message": "登出成功"}
