from langgraph.graph import StateGraph, END
from app.services.langgraph.state import JexAgentState
from app.services.langgraph.nodes.phase0_evaluate import phase0_evaluate
from app.services.langgraph.nodes.phase1_inquiry import phase1_generate_inquiry
from app.services.langgraph.nodes.phase2_planning import phase2_planning
from app.services.langgraph.nodes.phase3_collaboration import phase3_debate_mode, phase3_review_mode

def create_workflow():
    """创建LangGraph工作流"""
    
    # 创建状态图
    workflow = StateGraph(JexAgentState)
    
    # 添加节点
    workflow.add_node("evaluate", phase0_evaluate)
    workflow.add_node("generate_inquiry", phase1_generate_inquiry)
    workflow.add_node("planning", phase2_planning)
    workflow.add_node("debate_collaborate", phase3_debate_mode)
    workflow.add_node("review_collaborate", phase3_review_mode)
    
    # 设置入口
    workflow.set_entry_point("evaluate")
    
    # Phase 0 → Phase 1 or Phase 2
    def should_inquire(state: JexAgentState) -> str:
        if state.get("need_inquiry", False):
            return "inquire"
        else:
            return "plan"
    
    workflow.add_conditional_edges(
        "evaluate",
        should_inquire,
        {
            "inquire": "generate_inquiry",
            "plan": "planning"
        }
    )
    
    # Phase 1 → END（等待用户回答）
    workflow.add_edge("generate_inquiry", END)
    
    # Phase 2 → Phase 3（根据协作模式选择）
    def choose_collaboration_mode(state: JexAgentState) -> str:
        mode = state.get("collaboration_mode", "debate")
        if mode == "review":
            return "review"
        else:
            return "debate"
    
    workflow.add_conditional_edges(
        "planning",
        choose_collaboration_mode,
        {
            "debate": "debate_collaborate",
            "review": "review_collaborate"
        }
    )
    
    # Phase 3 → 检查是否继续协作
    def should_continue_collaboration(state: JexAgentState) -> str:
        if state.get("should_stop", False):
            return "stop"
        else:
            # 继续协作（根据模式选择）
            if state.get("collaboration_mode") == "review":
                return "review"
            else:
                return "debate"
    
    workflow.add_conditional_edges(
        "debate_collaborate",
        should_continue_collaboration,
        {
            "debate": "debate_collaborate",
            "stop": END
        }
    )
    
    workflow.add_conditional_edges(
        "review_collaborate",
        should_continue_collaboration,
        {
            "review": "review_collaborate",
            "stop": END
        }
    )
    
    return workflow.compile()


# 创建工作流实例
workflow = create_workflow()

def get_workflow():
    """获取工作流实例"""
    return workflow