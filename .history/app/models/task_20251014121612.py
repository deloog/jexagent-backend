from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime
from uuid import UUID

class TaskCreate(BaseModel):
    scene: str
    user_input: str

class TaskResponse(BaseModel):
    id: UUID
    user_id: UUID
    scene: str
    user_input: str
    status: str
    cost: Optional[float] = None
    duration: Optional[int] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class TaskDetail(TaskResponse):
    collected_info: Optional[Dict[str, Any]] = None
    output: Optional[Dict[str, Any]] = None