from typing import Dict, Any, Optional
from uuid import uuid4
from datetime import datetime
from app.core.database import get_supabase
from app.services.langgraph.workflow import get_workflow
from app.services.langgraph.nodes.phase1_inquiry import phase1_process_answers
import asyncio
import json

class TaskService:
    """任务服务"""
    
    def __init__(self):
        self.supabase = get_supabase()
        self.workflow = get_workflow()
    
    async def create_task(self, user_id: str, scene: str, user_input: str) -> Dict[str, Any]:
        """
        创建新任务
        
        返回：
        - 如果需要问询：返回问题列表
        - 如果信息充足：返回task_id，后台开始处理
        """
        
        task_id = str(uuid4())
        
        # 初始化任务状态
        initial_state = {
            "task_id": task_id,
            "user_id": user_id,
            "scene": scene,
            "user_input": user_input,
            "audit_trail": [],
            "total_cost": 0.0
        }
        
        try:
            # 运行Phase 0-1（评估和问询生成）
            result = await self.workflow.ainvoke(initial_state)
            
            # 保存到数据库
            task_data = {
                "id": task_id,
                "user_id": user_id,
                "scene": scene,
                "user_input": user_input,
                "status": "inquiring" if result.get("need_inquiry") else "processing",
                "cost": result.get("total_cost", 0.0)
            }
            
            self.supabase.table("tasks").insert(task_data).execute()
            
            if result.get("need_inquiry"):
                # 需要问询
                return {
                    "task_id": task_id,
                    "status": "inquiring",
                    "need_inquiry": True,
                    "inquiry_questions": result.get("inquiry_questions", []),
                    "inquiry_details": result.get("inquiry_details", []),
                    "info_sufficiency": result.get("info_sufficiency", 0.5),
                    # 保存中间状态（供后续提交答案使用）
                    "intermediate_state": {
                        "provided_info": result.get("provided_info", {}),
                        "missing_info": result.get("missing_info", []),
                        "audit_trail": result.get("audit_trail", []),
                        "total_cost": result.get("total_cost", 0.0)
                    }
                }
            else:
                # 信息充足，后台处理
                # 启动异步任务处理
                asyncio.create_task(self._process_task_async(task_id, result))
                
                return {
                    "task_id": task_id,
                    "status": "processing",
                    "need_inquiry": False,
                    "estimated_time": 60  # 预计60秒
                }
        
        except Exception as e:
            # 记录错误
            self.supabase.table("tasks").update({
                "status": "failed",
                "output": {"error": str(e)}
            }).eq("id", task_id).execute()
            
            raise Exception(f"任务创建失败: {str(e)}")
    
    async def submit_answers(
        self, 
        task_id: str, 
        answers: Dict[int, str],
        intermediate_state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        提交问询答案
        """
        
        try:
            # 重建状态
            task = self.supabase.table("tasks").select("*").eq("id", task_id).single().execute()
            if not task.data:
                raise Exception("任务不存在")
            
            # 构建完整状态
            state = {
                "task_id": task_id,
                "user_id": task.data["user_id"],
                "scene": task.data["scene"],
                "user_input": task.data["user_input"],
                **intermediate_state,
                "collected_info": {}
            }
            
            # Phase 1: 处理答案
            answer_result = await phase1_process_answers(state, answers)
            state.update(answer_result)
            
            # 更新任务状态
            self.supabase.table("tasks").update({
                "status": "processing",
                "collected_info": state.get("collected_info", {})
            }).eq("id", task_id).execute()
            
            # 启动后台任务处理（从Phase 2开始）
            asyncio.create_task(self._process_task_from_phase2(task_id, state))
            
            return {
                "task_id": task_id,
                "status": "processing",
                "collected_info": state.get("collected_info", {}),
                "estimated_time": 60
            }
        
        except Exception as e:
            self.supabase.table("tasks").update({
                "status": "failed",
                "output": {"error": str(e)}
            }).eq("id", task_id).execute()
            
            raise Exception(f"答案提交失败: {str(e)}")
    
    async def _process_task_async(self, task_id: str, initial_result: Dict[str, Any]):
        """
        后台异步处理任务（从Phase 2开始）
        """
        
        from app.services.socket_manager import socket_manager
        
        try:
            # 导入Phase 2-5节点
            from app.services.langgraph.nodes.phase2_planning import phase2_planning
            from app.services.langgraph.nodes.phase3_collaboration import phase3_debate_mode, phase3_review_mode
            from app.services.langgraph.nodes.phase5_integration import phase5_integration
            
            state = dict(initial_result)
            
            # Phase 2: 规划
            await socket_manager.emit_progress(task_id, "规划", 20, "正在制定协作策略...")
            planning_result = await phase2_planning(state)
            state.update(planning_result)
            
            # Phase 3: 协作
            collaboration_mode = state.get("collaboration_mode", "debate")
            await socket_manager.emit_progress(
                task_id, 
                "协作", 
                40, 
                f"多AI {'辩论' if collaboration_mode == 'debate' else '审查'}模式启动..."
            )
            
            # 循环协作直到完成
            while not state.get("should_stop", False):
                if collaboration_mode == "review":
                    collab_result = await phase3_review_mode(state)
                else:
                    collab_result = await phase3_debate_mode(state)
                
                state.update(collab_result)
                
                # 推送AI消息
                if state.get("ai_a_output"):
                    await socket_manager.emit_ai_message(
                        task_id,
                        "Kimi",
                        state["ai_a_output"][:500] + "..."
                    )
                
                if state.get("ai_b_output"):
                    await socket_manager.emit_ai_message(
                        task_id,
                        "Qwen",
                        state["ai_b_output"][:500] + "..."
                    )
                
                progress = 40 + (state.get("current_round", 0) * 15)
                await socket_manager.emit_progress(
                    task_id,
                    "协作",
                    min(progress, 70),
                    f"第{state.get('current_round', 0)}轮协作完成"
                )
            
            # Phase 5: 整合
            await socket_manager.emit_progress(task_id, "整合", 80, "正在生成综合报告...")
            integration_result = await phase5_integration(state)
            state.update(integration_result)
            
            # 更新数据库
            end_time = datetime.utcnow()
            task = self.supabase.table("tasks").select("created_at").eq("id", task_id).single().execute()
            start_time = datetime.fromisoformat(task.data["created_at"].replace("Z", "+00:00"))
            duration = int((end_time - start_time).total_seconds())
            
            self.supabase.table("tasks").update({
                "status": "completed",
                "output": state.get("final_output", {}),
                "cost": state.get("total_cost", 0.0),
                "duration": duration,
                "completed_at": end_time.isoformat()
            }).eq("id", task_id).execute()
            
            # 保存审计轨迹
            for entry in state.get("audit_trail", []):
                entry["task_id"] = task_id
                self.supabase.table("audit_trails").insert(entry).execute()
            
            # 推送完成消息
            await socket_manager.emit_progress(task_id, "完成", 100, "分析完成！")
            await socket_manager.emit_complete(task_id, state.get("final_output", {}))
            
        except Exception as e:
            self.supabase.table("tasks").update({
                "status": "failed",
                "output": {"error": str(e)}
            }).eq("id", task_id).execute()
            
            await socket_manager.emit_error(task_id, str(e))
    
    async def _process_task_from_phase2(self, task_id: str, state: Dict[str, Any]):
        """
        从Phase 2开始处理（用于提交答案后）
        """
        await self._process_task_async(task_id, state)
    
    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取任务详情"""
        result = self.supabase.table("tasks").select("*").eq("id", task_id).single().execute()
        return result.data if result.data else None
    
    def get_user_tasks(self, user_id: str, limit: int = 20) -> list:
        """获取用户的任务列表"""
        result = self.supabase.table("tasks").select("*").eq("user_id", user_id).order("created_at", desc=True).limit(limit).execute()
        return result.data if result.data else []


# 创建全局任务服务实例
task_service = TaskService()

def get_task_service() -> TaskService:
    """获取任务服务实例"""
    return task_service