from langgraph.graph import StateGraph, END
from app.services.langgraph.state import JexAgentState
from app.services.langgraph.nodes.phase0_evaluate import phase0_evaluate
from app.services.langgraph.nodes.phase1_inquiry import phase1_generate_inquiry
from app.services.langgraph.nodes.phase2_planning import phase2_planning

def create_workflow():
    """创建LangGraph工作流"""
    
    # 创建状态图
    workflow = StateGraph(JexAgentState)
    
    # 添加节点
    workflow.add_node("evaluate", phase0_evaluate)
    workflow.add_node("generate_inquiry", phase1_generate_inquiry)
    workflow.add_node("planning", phase2_planning)
    
    # 设置入口
    workflow.set_entry_point("evaluate")
    
    # Phase 0 → Phase 1 or Phase 2
    def should_inquire(state: JexAgentState) -> str:
        """判断是否需要问询"""
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
    
    # Phase 2 → END（下一步是Phase 3协作）
    workflow.add_edge("planning", END)
    
    return workflow.compile()


# 创建工作流实例
workflow = create_workflow()

def get_workflow():
    """获取工作流实例"""
    return workflow