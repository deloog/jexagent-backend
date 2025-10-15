from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime
from uuid import UUID

class UserBase(BaseModel):
    email: EmailStr
    name: Optional[str] = None

class UserCreate(UserBase):
    pass

class UserResponse(UserBase):
    id: UUID
    tier: str
    subscription_status: str
    daily_quota: int
    daily_used: int
    total_tasks: int
    total_spent: float
    created_at: datetime
    
    class Config:
        from_attributes = True