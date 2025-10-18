from fastapi import APIRouter, HTTPException, Depends, status, Query, Response
from pydantic import BaseModel
from typing import Dict, Any
import logging

from app.services.task_service import get_task_service, TaskService
from app.services.socket_manager import socket_manager
from app.models.user import UserResponse
from app.core.dependencies import get_current_active_user
from app.core.database import get_supabase

# ✅ 配置日志
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tasks", tags=["任务"])

class TaskCreate(BaseModel):
    scene: str
    user_input: str

class AnswersSubmit(BaseModel):
    answers: Dict[int, str]
    intermediate_state: Dict[str, Any]

# ✅ 辅助函数：原子递增配额
async def increment_daily_used(user_id: str) -> int:
    """
    原子递增用户配额
    
    使用PostgreSQL函数确保原子性
    如果超过配额，抛出异常
    
    Returns:
        新的 daily_used 值
    """
    supabase = get_supabase()
    
    try:
        # ✅ 调用PostgreSQL函数（需要先创建）
        result = supabase.rpc("increment_daily_used", {
            "p_user_id": user_id
        }).execute()
        
        if result.data is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="今日配额已用完"
            )
        
        return result.data
    except Exception as e:
        if "quota_exceeded" in str(e):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="今日配额已用完"
            )
        raise

# ✅ 辅助函数：补偿回滚配额
async def decrement_daily_used(user_id: str):
    """补偿机制：回滚配额"""
    supabase = get_supabase()
    try:
        supabase.rpc("decrement_daily_used", {
            "p_user_id": user_id
        }).execute()
    except Exception as e:
        logger.error(f"回滚配额失败: user_id={user_id}, error={e}")

@router.post("", status_code=status.HTTP_201_CREATED)
async def create_task(
    task_data: TaskCreate,
    current_user: UserResponse = Depends(get_current_active_user),
    task_service: TaskService = Depends(get_task_service)
):
    """
    创建新任务
    
    ✅ 改进：
    - 原子递增配额（防止竞态）
    - 补偿机制（任务失败时回滚配额）
    - 结构化日志
    """
    
    # ✅ 开发环境：临时禁用配额检查
    import os
    if os.getenv("DISABLE_QUOTA_CHECK", "false").lower() == "true":
        logger.info(f"开发环境：跳过配额检查 user_id={current_user.id}")
    else:
        # ✅ 前置检查（快速失败）
        if current_user.daily_used >= current_user.daily_quota:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="今日配额已用完"
            )
    
    user_id = str(current_user.id)
    
    try:
        # ✅ 开发环境：跳过配额递增
        if os.getenv("DISABLE_QUOTA_CHECK", "false").lower() != "true":
            # ✅ 1. 先递增配额（原子操作）
            new_used = await increment_daily_used(user_id)
            logger.info(f"配额递增成功: user_id={user_id}, daily_used={new_used}")
        
        # ✅ 2. 创建任务（可能失败）
        result = await task_service.create_task(
            user_id=user_id,
            scene=task_data.scene,
            user_input=task_data.user_input
        )
        
        logger.info(
            "任务创建成功",
            extra={
                "task_id": result.get("task_id"),
                "user_id": user_id,
                "status": result.get("status")
            }
        )
        
        return result
        
    except HTTPException:
        # HTTP异常直接抛出
        raise
    except Exception as e:
        # ✅ 3. 创建失败，回滚配额
        logger.exception(
            "任务创建失败，回滚配额",
            extra={
                "user_id": user_id,
                "scene": task_data.scene,
                "error_type": type(e).__name__
            }
        )
        
        await decrement_daily_used(user_id)
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="任务创建失败，请稍后重试"
        )

@router.post("/{task_id}/answers", status_code=status.HTTP_200_OK)
async def submit_answers(
    task_id: str,
    answers_data: AnswersSubmit,
    current_user: UserResponse = Depends(get_current_active_user),
    task_service: TaskService = Depends(get_task_service)
):
    """
    提交问询答案
    
    ✅ 改进：
    - 原子状态检查（防止重复提交）
    - 结构化日志
    """
    
    # 验证任务归属
    task = task_service.get_task(task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="任务不存在"
        )
    
    if task["user_id"] != str(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问此任务"
        )
    
    if task["status"] != "inquiring":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"任务状态不正确，当前状态: {task['status']}"
        )
    
    try:
        result = await task_service.submit_answers_without_processing(
            task_id=task_id,
            answers=answers_data.answers,
            intermediate_state=answers_data.intermediate_state
        )
        
        logger.info(
            "答案提交成功",
            extra={
                "task_id": task_id,
                "user_id": str(current_user.id),
                "answers_count": len(answers_data.answers)
            }
        )
        
        return result
        
    except Exception as e:
        logger.exception(
            "答案提交失败",
            extra={
                "task_id": task_id,
                "user_id": str(current_user.id),
                "error_type": type(e).__name__
            }
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="答案提交失败，请稍后重试"
        )

@router.get("/{task_id}", status_code=status.HTTP_200_OK)
async def get_task(
    task_id: str,
    current_user: UserResponse = Depends(get_current_active_user),
    task_service: TaskService = Depends(get_task_service)
):
    """获取任务详情"""
    
    task = task_service.get_task(task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="任务不存在"
        )
    
    if task["user_id"] != str(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问此任务"
        )
    
    return task

@router.get("", status_code=status.HTTP_200_OK)
async def list_tasks(
    limit: int = Query(20, ge=1, le=100, description="每页数量"),
    offset: int = Query(0, ge=0, description="偏移量"),
    current_user: UserResponse = Depends(get_current_active_user),
    task_service: TaskService = Depends(get_task_service)
):
    """
    获取任务列表
    
    ✅ 已支持分页，返回总数
    """
    result = task_service.get_user_tasks(
        user_id=str(current_user.id),
        limit=limit,
        offset=offset
    )
    return result

@router.post("/{task_id}/start-processing", status_code=status.HTTP_200_OK)
async def start_processing(
    task_id: str,
    current_user: UserResponse = Depends(get_current_active_user),
    task_service: TaskService = Depends(get_task_service)
):
    """
    启动任务处理
    
    ✅ 改进：
    - 原子状态切换
    - 友好的错误消息
    - 结构化日志
    """
    
    # 验证任务归属
    task = task_service.get_task(task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="任务不存在"
        )
    
    if task["user_id"] != str(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问此任务"
        )
    
    # ✅ 幂等性检查
    current_status = task["status"]
    if current_status == "processing":
        return {
            "task_id": task_id,
            "status": "processing",
            "message": "任务已在处理中"
        }
    
    if current_status == "completed":
        return {
            "task_id": task_id,
            "status": "completed",
            "message": "任务已完成"
        }
    
    if current_status != "ready_for_processing":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"任务状态不正确，当前状态: {current_status}"
        )
    
    try:
        result = await task_service.start_processing(task_id)
        
        logger.info(
            "任务启动成功",
            extra={
                "task_id": task_id,
                "user_id": str(current_user.id)
            }
        )
        
        return result
        
    except Exception as e:
        logger.exception(
            "启动任务失败",
            extra={
                "task_id": task_id,
                "user_id": str(current_user.id),
                "error_type": type(e).__name__
            }
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="启动处理失败，请稍后重试"
        )

@router.get("/{task_id}/progress", status_code=status.HTTP_200_OK)
async def get_task_progress(
    task_id: str,
    response: Response,
    current_user: UserResponse = Depends(get_current_active_user),
    task_service: TaskService = Depends(get_task_service)
):
    """
    获取任务完整进度历史
    
    ✅ 改进：
    - 不缓存（实时数据）
    - 权限验证
    - 性能/缓存响应头
    """
    
    # 验证任务归属
    task = task_service.get_task(task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="任务不存在"
        )
    
    if task["user_id"] != str(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问此任务"
        )
    
    try:
        progress_history = await socket_manager.get_full_progress(task_id)
        
        # ✅ 性能/缓存响应头
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        
        return progress_history
    except Exception as e:
        logger.exception(
            "获取进度失败",
            extra={
                "task_id": task_id,
                "user_id": str(current_user.id),
                "error_type": type(e).__name__
            }
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取进度失败，请稍后重试"
        )

@router.get("/health", status_code=status.HTTP_200_OK, include_in_schema=False)
async def health_check():
    """健康检查"""
    return {"status": "ok"}
