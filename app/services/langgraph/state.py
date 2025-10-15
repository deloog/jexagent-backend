from typing import TypedDict, List, Dict, Any, Optional
from uuid import UUID

class JexAgentState(TypedDict):
    """JexAgent工作流状态"""
    
    # ========== 输入信息 ==========
    task_id: str
    user_id: str
    scene: str
    user_input: str
    
    # ========== Phase 0: 评估 ==========
    need_inquiry: bool  # 是否需要问询
    provided_info: Dict[str, Any]  # 用户已提供的信息
    missing_info: List[str]  # 缺失的关键信息
    info_sufficiency: float  # 信息充足度 0-1
    
    # ========== Phase 1: 问询 ==========
    inquiry_questions: List[str]  # AI生成的问题列表
    inquiry_details: list[dict[str, any]]
    collected_info: Dict[str, Any]  # 收集到的结构化信息
    
    # ========== Phase 2: 规划 ==========
    task_type: str  # 任务类型
    collaboration_mode: str  # 协作模式: 'debate' | 'review'
    ai_a_role: str  # AI-A的角色定义
    ai_b_role: str  # AI-B的角色定义
    
    # ========== Phase 3: 协作 ==========
    ai_a_output: str  # AI-A的输出
    ai_b_output: str  # AI-B的输出
    debate_rounds: List[Dict[str, Any]]  # 辩论轮次记录
    
    # ========== Phase 4: 监控 ==========
    current_round: int  # 当前轮次
    max_rounds: int  # 最大轮次
    should_stop: bool  # 是否应该停止
    stop_reason: Optional[str]  # 停止原因
    
    # ========== Phase 5: 输出 ==========
    final_output: Dict[str, Any]  # 最终输出
    
    # ========== 通用 ==========
    audit_trail: List[Dict[str, Any]]  # 审计轨迹
    total_cost: float  # 总成本
    error: Optional[str]  # 错误信息