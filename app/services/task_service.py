from typing import Dict, Any, Optional, List
from uuid import uuid4
from datetime import datetime
from app.core.database import get_supabase
from app.services.langgraph.workflow import get_workflow
from app.services.langgraph.nodes.phase1_inquiry import phase1_process_answers
import asyncio
import os
import hashlib
from contextlib import suppress
from pydantic import BaseModel, Field, validator
import traceback

# ✅ Redis配置（多进程安全）
USE_REDIS_LOCK = os.getenv("USE_REDIS_LOCK", "false").lower() == "true"

if USE_REDIS_LOCK:
    import redis.asyncio as redis
    redis_client = redis.Redis(
        host=os.getenv("REDIS_HOST", "localhost"),
        port=int(os.getenv("REDIS_PORT", 6379)),
        decode_responses=True
    )

# ✅ 进度计算器 - 解决硬编码问题
class ProgressCalculator:
    """集中管理进度百分比"""
    PHASES = {
        "evaluation": (0, 10),
        "inquiry": (10, 20),
        "planning": (20, 40),
        "collaboration": (40, 70),
        "integration": (70, 90),
        "finalization": (90, 100)
    }
    
    @classmethod
    def get_progress(cls, phase: str, phase_progress: float = 0.5) -> int:
        """
        计算进度百分比
        
        Args:
            phase: 阶段名称
            phase_progress: 阶段内进度 (0.0-1.0)
        
        Returns:
            整体进度百分比
        """
        if phase not in cls.PHASES:
            return 0
        
        start, end = cls.PHASES[phase]
        return int(start + (end - start) * phase_progress)

# ✅ Pydantic模型 - 防止注入攻击
class IntermediateStateSchema(BaseModel):
    """中间状态数据校验模型"""
    provided_info: dict = Field(default_factory=dict)
    missing_info: List[str] = Field(default_factory=list)
    audit_trail: List[dict] = Field(default_factory=list)
    total_cost: float = Field(default=0.0, ge=0, le=1000)
    
    @validator('total_cost')
    def validate_cost(cls, v):
        if v < 0:
            raise ValueError('成本不能为负数')
        if v > 1000:
            raise ValueError('成本超过上限')
        return v
    
    class Config:
        extra = "forbid"  # ✅ 禁止额外字段，防止注入

# ✅ UTF-8安全截断工具
def truncate_utf8(text: str, max_bytes: int) -> str:
    """
    安全截断UTF-8字符串，不会产生乱码
    
    Args:
        text: 原始文本
        max_bytes: 最大字节数
    
    Returns:
        截断后的文本
    """
    if not text:
        return ""
    
    encoded = text.encode('utf-8')
    if len(encoded) <= max_bytes:
        return text
    
    # 向前查找有效的UTF-8边界
    truncated = encoded[:max_bytes]
    while truncated:
        try:
            return truncated.decode('utf-8')
        except UnicodeDecodeError:
            truncated = truncated[:-1]
    
    return ""

class TaskService:
    """任务服务 - 生产级实现"""
    
    MAX_COLLABORATION_ROUNDS = 10
    TASK_LOCK_TTL = 3600
    
    def __init__(self):
        # ✅ 修复：延迟初始化
        self._supabase = None
        self._workflow = None
        
        # ✅ 进程内任务追踪（单进程模式）
        # 多进程模式下改用Redis
        if not USE_REDIS_LOCK:
            self._active_tasks: Dict[str, asyncio.Task] = {}
    
    # ✅ 修复：添加延迟加载属性
    @property
    def supabase(self):
        """延迟加载 Supabase 客户端"""
        if self._supabase is None:
            self._supabase = get_supabase()
        return self._supabase
    
    @property
    def workflow(self):
        """延迟加载 Workflow"""
        if self._workflow is None:
            self._workflow = get_workflow()
        return self._workflow
    
    async def _acquire_task_lock(self, task_id: str) -> bool:
        """
        获取任务锁（防止多进程重复处理）
        
        Returns:
            True if lock acquired, False otherwise
        """
        if USE_REDIS_LOCK:
            # ✅ Redis SETNX：原子操作
            is_acquired = await redis_client.set(
                f"task:lock:{task_id}",
                "1",
                ex=self.TASK_LOCK_TTL,
                nx=True  # 只在不存在时设置
            )
            return bool(is_acquired)
        else:
            # 单进程模式：检查内存
            return task_id not in self._active_tasks
    
    async def _release_task_lock(self, task_id: str):
        """释放任务锁"""
        if USE_REDIS_LOCK:
            await redis_client.delete(f"task:lock:{task_id}")
        else:
            self._active_tasks.pop(task_id, None)
    
    def _cleanup_task(self, task_id: str, task: asyncio.Task):
        """
        清理已完成的任务，并显式记录异常
        
        ✅ 修复：不会吞掉异常
        """
        # 清理任务追踪
        if not USE_REDIS_LOCK:
            self._active_tasks.pop(task_id, None)
        
        # ✅ 检查是否被取消
        if task.cancelled():
            print(f"[TASK] ⚠️ 任务被取消: {task_id}")
            return
        
        # ✅ 显式检查并记录异常
        try:
            exc = task.exception()
            if exc:
                print(f"[TASK] ❌ 任务异常退出: {task_id}")
                print(f"[TASK] 异常类型: {type(exc).__name__}")
                print(f"[TASK] 异常信息: {str(exc)}")
                traceback.print_exception(type(exc), exc, exc.__traceback__)
                
                # ✅ 可选：发送告警通知
                # asyncio.create_task(self._send_alert(task_id, exc))
        except Exception as e:
            print(f"[TASK] ❌ 检查任务异常时出错: {e}")
    
    async def create_task(self, user_id: str, scene: str, user_input: str) -> Dict[str, Any]:
        """
        创建新任务
        
        Returns:
            - 如果需要问询：返回问题列表
            - 如果信息充足：返回task_id，后台开始处理
        """
        
        task_id = str(uuid4())
        
        initial_state = {
            "task_id": task_id,
            "user_id": user_id,
            "scene": scene,
            "user_input": user_input,
            "audit_trail": [],
            "total_cost": 0.0
        }
        
        try:
            # ✅ 先插入任务（使用允许的状态）
            initial_status = "inquiring"  # 初始状态设为询问中
            self.supabase.table("tasks").insert({
                "id": task_id,
                "user_id": user_id,
                "scene": scene,
                "user_input": user_input,
                "status": initial_status,  # ✅ 使用允许的状态
                "cost": 0.0
            }).execute()
            
            # 运行Phase 0-1
            result = await self.workflow.ainvoke(initial_state)
            
            # ✅ 根据结果更新状态
            if result.get("need_inquiry"):
                # 保持 inquiring 状态
                pass
            else:
                # 更新为 processing 状态
                self.supabase.table("tasks").update({
                    "status": "processing",
                    "cost": result.get("total_cost", 0.0)
                }).eq("id", task_id).execute()
            
            if result.get("need_inquiry"):
                return {
                    "task_id": task_id,
                    "status": "inquiring",
                    "need_inquiry": True,
                    "inquiry_questions": result.get("inquiry_questions", []),
                    "inquiry_details": result.get("inquiry_details", []),
                    "info_sufficiency": result.get("info_sufficiency", 0.5),
                    "intermediate_state": IntermediateStateSchema(
                        provided_info=result.get("provided_info", {}),
                        missing_info=result.get("missing_info", []),
                        audit_trail=result.get("audit_trail", []),
                        total_cost=result.get("total_cost", 0.0)
                    ).dict()
                }
            else:
                # ✅ 信息充足，启动后台处理
                await self._start_background_task(task_id, result)
                
                return {
                    "task_id": task_id,
                    "status": "processing",
                    "need_inquiry": False,
                    "estimated_time": 60
                }
        
        except Exception as e:
            # ✅ 标记失败
            print(f"[SERVICE] ❌ 创建任务失败: {task_id}, 错误: {e}")
            self.supabase.table("tasks").update({
                "status": "failed",
                "output": {"error": str(e)}
            }).eq("id", task_id).execute()
            
            raise Exception(f"任务创建失败: {str(e)}")
    
    async def submit_answers_without_processing(
        self, 
        task_id: str, 
        answers: Dict[int, str],
        intermediate_state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        提交问询答案 - 仅更新状态，不立即启动后台任务
        
        ✅ 使用Pydantic校验，防止注入攻击
        """
        
        print(f"[SERVICE] 提交答案: task_id={task_id}")
        
        try:
            # 获取任务
            task = self.supabase.table("tasks").select("*").eq("id", task_id).single().execute()
            
            if not task.data:
                raise Exception("任务不存在")
            
            # ✅ Pydantic严格校验
            try:
                validated_state = IntermediateStateSchema(**intermediate_state)
            except Exception as e:
                raise Exception(f"中间状态数据校验失败: {str(e)}")
            
            # ✅ 重建状态（不可被覆盖的字段在外层）
            state = {
                "task_id": task_id,
                "user_id": task.data["user_id"],  # ← 不可被覆盖
                "scene": task.data["scene"],
                "user_input": task.data["user_input"],
                **validated_state.dict(),  # ← 已校验的数据
                "collected_info": {}
            }
            
            # Phase 1: 处理答案
            answer_result = await phase1_process_answers(state, answers)
            state.update(answer_result)
            
            # ✅ 原子更新（带状态检查）
            update_data = {
                "status": "ready_for_processing",
                "collected_info": state.get("collected_info", {}),
                "processing_state": state
            }
            
            result = self.supabase.table("tasks").update(
                update_data
            ).eq("id", task_id).eq("status", "inquiring").execute()
            
            if not result.data:
                raise Exception("任务状态不正确或已被处理")
            
            print(f"[SERVICE] ✅ 答案已提交: {task_id}")
            
            return {
                "task_id": task_id,
                "status": "ready_for_processing",
                "collected_info": state.get("collected_info", {}),
                "estimated_time": 60
            }
        
        except Exception as e:
            print(f"[SERVICE] ❌ 提交答案失败: {e}")
            self.supabase.table("tasks").update({
                "status": "failed",
                "output": {"error": str(e)}
            }).eq("id", task_id).execute()
            
            raise Exception(f"答案提交失败: {str(e)}")

    async def start_processing(self, task_id: str) -> Dict[str, Any]:
        """
        启动任务处理 - 由前端在WebSocket连接建立后调用
        
        ✅ 使用原子更新防止多Worker重复启动
        """
        try:
            # ✅ 原子更新：只有status='ready_for_processing'时才更新
            result = self.supabase.table("tasks").update({
                "status": "processing"
            }).eq("id", task_id).eq("status", "ready_for_processing").execute()
            
            if not result.data:
                raise Exception("任务状态不正确或已被其他实例启动")
            
            task_data = result.data[0]
            processing_state = task_data.get("processing_state", {})
            
            # ✅ 启动后台任务
            print(f"[SERVICE] 🚀 启动后台任务处理: {task_id}")
            await self._start_background_task(task_id, processing_state)
            
            return {
                "task_id": task_id,
                "status": "processing",
                "message": "后台任务已启动"
            }
        
        except Exception as e:
            print(f"[SERVICE] ❌ 启动处理失败: {e}")
            self.supabase.table("tasks").update({
                "status": "failed",
                "output": {"error": str(e)}
            }).eq("id", task_id).execute()
            
            raise Exception(f"启动处理失败: {str(e)}")
    
    async def _start_background_task(self, task_id: str, initial_state: Dict[str, Any]):
        """
        启动后台任务的统一入口
        
        ✅ 带锁保护和异常追踪
        """
        # ✅ 获取任务锁
        if not await self._acquire_task_lock(task_id):
            print(f"[SERVICE] ⚠️ 任务已在其他进程中处理: {task_id}")
            return
        
        # 创建后台任务
        bg_task = asyncio.create_task(
            self._process_task_async(task_id, initial_state)
        )
        
        # 追踪任务
        if not USE_REDIS_LOCK:
            self._active_tasks[task_id] = bg_task
        
        # ✅ 添加完成回调（显式记录异常）
        bg_task.add_done_callback(lambda t: self._cleanup_task(task_id, t))
    
    async def _process_task_async(self, task_id: str, initial_result: Dict[str, Any]):
        """
        后台异步处理任务（从Phase 2开始）
        
        ✅ 包含所有优化：
        - 等待WebSocket连接
        - UTF-8安全截断
        - 批量插入审计
        - 超时保护
        """
        print(f"[TASK-START] task_id={task_id}")
        from app.services.socket_manager import socket_manager
        
        try:
            # ✅ 等待WebSocket连接
            connection_ready = await socket_manager.wait_for_connection(task_id, timeout=10.0)
            if connection_ready:
                print(f"[TASK] ✅ WebSocket连接已就绪")
            else:
                print(f"[TASK] ⚠️ WebSocket连接超时，继续处理（进度将被缓存）")
            
            from app.services.langgraph.nodes.phase2_planning import phase2_planning
            from app.services.langgraph.nodes.phase3_collaboration import phase3_debate_mode, phase3_review_mode
            from app.services.langgraph.nodes.phase5_integration import phase5_integration
            
            state = dict(initial_result)
            state.setdefault("_last_progress", 0)
            
            # Phase 2: 规划
            progress = ProgressCalculator.get_progress("planning", 0.0)
            state["_last_progress"] = max(state["_last_progress"], progress)
            with suppress(Exception):
                await socket_manager.emit_progress(
                    task_id, "规划", state["_last_progress"], "正在制定协作策略..."
                )
            
            planning_result = await phase2_planning(state)
            state.update(planning_result)
            
            # Phase 3: 协作
            collaboration_mode = state.get("collaboration_mode", "debate")
            progress = ProgressCalculator.get_progress("collaboration", 0.0)
            state["_last_progress"] = max(state["_last_progress"], progress)
            with suppress(Exception):
                await socket_manager.emit_progress(
                    task_id,
                    "协作",
                    state["_last_progress"],
                    f"多AI {'辩论' if collaboration_mode == 'debate' else '审查'}模式启动..."
                )
            
            # ✅ 循环协作（带超时保护）
            current_round = 0
            while not state.get("should_stop", False):
                current_round += 1
                
                # ✅ 超时保护
                if current_round > self.MAX_COLLABORATION_ROUNDS:
                    print(f"[TASK] ⚠️ 达到最大轮次{self.MAX_COLLABORATION_ROUNDS}，强制停止")
                    break
                
                if collaboration_mode == "review":
                    collab_result = await phase3_review_mode(state)
                else:
                    collab_result = await phase3_debate_mode(state)
                
                state.update(collab_result)
                state["current_round"] = current_round
                
                # ✅ UTF-8安全截断
                if state.get("ai_a_output"):
                    with suppress(Exception):
                        await socket_manager.emit_ai_message(
                            task_id,
                            "Kimi",
                            truncate_utf8(state["ai_a_output"], 500) + "..."
                        )
                
                if state.get("ai_b_output"):
                    with suppress(Exception):
                        await socket_manager.emit_ai_message(
                            task_id,
                            "Qwen",
                            truncate_utf8(state["ai_b_output"], 500) + "..."
                        )
                
                # 计算协作进度
                phase_progress = min(current_round / self.MAX_COLLABORATION_ROUNDS, 1.0)
                progress = ProgressCalculator.get_progress("collaboration", phase_progress)
                state["_last_progress"] = max(state["_last_progress"], progress)
                
                with suppress(Exception):
                    await socket_manager.emit_progress(
                        task_id,
                        "协作",
                        state["_last_progress"],
                        f"第{current_round}轮协作完成"
                    )
            
            # Phase 5: 整合
            progress = ProgressCalculator.get_progress("integration", 0.5)
            state["_last_progress"] = max(state["_last_progress"], progress)
            with suppress(Exception):
                await socket_manager.emit_progress(
                    task_id, "整合", state["_last_progress"], "正在生成综合报告..."
                )
            
            integration_result = await phase5_integration(state)
            state.update(integration_result)

            # ✅ 推送100%完成进度
            with suppress(Exception):
                await socket_manager.emit_progress(task_id, "完成", 100, "分析完成！")

            # ✅ 先更新数据库，再发送complete事件（确保数据一致性）
            end_time = datetime.utcnow()
            task = self.supabase.table("tasks").select("created_at").eq("id", task_id).single().execute()
            start_time = datetime.fromisoformat(task.data["created_at"].replace("Z", "+00:00")).replace(tzinfo=None)
            duration = int((end_time - start_time).total_seconds())
            
            # 构建完整的输出数据
            final_output = {
                "executive_summary": state.get("final_output", {}).get("executive_summary"),
                "certain_advice": state.get("final_output", {}).get("certain_advice"),
                "hypothetical_advice": state.get("final_output", {}).get("hypothetical_advice"),
                "divergences": state.get("final_output", {}).get("divergences"),
                "hooks": state.get("final_output", {}).get("hooks"),
                "audit_summary": state.get("final_output", {}).get("audit_summary")
            }
            
            # 更新数据库状态
            update_result = self.supabase.table("tasks").update({
                "status": "completed",
                "output": final_output,
                "cost": state.get("total_cost", 0.0),
                "duration": duration,
                "completed_at": end_time.isoformat()
            }).eq("id", task_id).execute()
            
            print(f"[TASK] ✅ 数据库状态已更新为completed: {task_id}")
            
            # ✅ 推送完成事件（确保数据库已更新）
            try:
                await socket_manager.emit_complete(task_id, final_output)
                print(f"[TASK] ✅ complete 事件已推送: {task_id}")
            except Exception as e:
                print(f"[TASK] ❌ complete 事件失败: {task_id}, {e}")
            
            # ✅ 批量插入审计轨迹
            audit_trail = state.get("audit_trail", [])
            if audit_trail:
                audit_rows = [
                    {"task_id": task_id, **entry}
                    for entry in audit_trail
                ]
                # 一次性插入所有审计记录
                self.supabase.table("audit_trails").insert(audit_rows).execute()
                print(f"[TASK] ✅ 批量插入{len(audit_rows)}条审计记录")
            
            print(f"[TASK-END] ✅ task_id={task_id} 完成")
            
        except Exception as e:
            print(f"[TASK-END] ❌ task_id={task_id} 异常: {e}")
            traceback.print_exc()
            
            self.supabase.table("tasks").update({
                "status": "failed",
                "output": {"error": str(e)}
            }).eq("id", task_id).execute()
            
            with suppress(Exception):
                await socket_manager.emit_error(task_id, str(e))
            
            raise
        
        finally:
            # ✅ 释放任务锁
            await self._release_task_lock(task_id)
    
    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取任务详情"""
        result = self.supabase.table("tasks").select("*").eq("id", task_id).single().execute()
        return result.data if result.data else None
    
    def get_user_tasks(
        self, 
        user_id: str, 
        limit: int = 20, 
        offset: int = 0
    ) -> Dict[str, Any]:
        """
        获取用户的任务列表
        
        ✅ 支持分页
        
        Args:
            user_id: 用户ID
            limit: 每页数量
            offset: 偏移量
        
        Returns:
            包含tasks、total、limit、offset的字典
        """
        result = self.supabase.table("tasks")\
            .select("*", count="exact")\
            .eq("user_id", user_id)\
            .order("created_at", desc=True)\
            .range(offset, offset + limit - 1)\
            .execute()
        
        return {
            "tasks": result.data if result.data else [],
            "total": result.count or 0,
            "limit": limit,
            "offset": offset,
            "has_more": (result.count or 0) > (offset + limit)
        }
    
    def get_active_task_count(self) -> int:
        """
        获取活跃任务数量
        
        ✅ 单进程模式下可用
        """
        if USE_REDIS_LOCK:
            # Redis模式下无法统计（需要扫描所有key）
            return -1
        else:
            return len(self._active_tasks)


# 创建全局任务服务实例（延迟初始化）
_task_service_instance: Optional[TaskService] = None

def get_task_service() -> TaskService:
    """获取任务服务实例（延迟初始化）"""
    global _task_service_instance
    if _task_service_instance is None:
        _task_service_instance = TaskService()
    return _task_service_instance
