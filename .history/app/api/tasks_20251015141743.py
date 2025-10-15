from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Dict, Any, List
from app.services.task_service import get_task_service, TaskService
from app.models.user import UserResponse
from app.core.dependencies import get_current_active_user

router = APIRouter(prefix="/tasks", tags=["任务"])

class TaskCreate(BaseModel):
    scene: str
    user_input: str

class AnswersSubmit(BaseModel):
    answers: Dict[int, str]
    intermediate_state: Dict[str, Any]

@router.post("", status_code=201)
async def create_task(
    task_data: TaskCreate,
    current_user: UserResponse = Depends(get_current_active_user),
    task_service: TaskService = Depends(get_task_service)
):
    """创建新任务"""
    
    # 检查配额
    if current_user.daily_used >= current_user.daily_quota:
        raise HTTPException(status_code=403, detail="今日配额已用完")
    
    try:
        result = await task_service.create_task(
            user_id=str(current_user.id),
            scene=task_data.scene,
            user_input=task_data.user_input
        )
        
        # 更新用户配额
        from app.core.database import get_supabase
        supabase = get_supabase()
        supabase.table("users").update({
            "daily_used": current_user.daily_used + 1
        }).eq("id", str(current_user.id)).execute()
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{task_id}/answers")
async def submit_answers(
    task_id: str,
    answers_data: AnswersSubmit,
    current_user: UserResponse = Depends(get_current_active_user),
    task_service: TaskService = Depends(get_task_service)
):
    """提交问询答案"""
    
    # 验证任务归属
    task = task_service.get_task(task_id)
    if not task or task["user_id"] != str(current_user.id):
        raise HTTPException(status_code=404, detail="任务不存在")
    
    try:
        result = await task_service.submit_answers(
            task_id=task_id,
            answers=answers_data.answers,
            intermediate_state=answers_data.intermediate_state
        )
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{task_id}")
async def get_task(
    task_id: str,
    current_user: UserResponse = Depends(get_current_active_user),
    task_service: TaskService = Depends(get_task_service)
):
    """获取任务详情"""
    
    task = task_service.get_task(task_id)
    if not task or task["user_id"] != str(current_user.id):
        raise HTTPException(status_code=404, detail="任务不存在")
    
    return task

@router.get("")
async def list_tasks(
    current_user: UserResponse = Depends(get_current_active_user),
    task_service: TaskService = Depends(get_task_service)
):
    """获取任务列表"""
    
    tasks = task_service.get_user_tasks(str(current_user.id))
    return {"tasks": tasks, "count": len(tasks)}