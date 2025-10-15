from langgraph.graph import StateGraph, END
from app.services.langgraph.state import JexAgentState
from app.services.langgraph.nodes.phase0_evaluate import phase0_evaluate
from app.services.langgraph.nodes.phase1_inquiry import phase1_generate_inquiry

def create_workflow():
    """创建LangGraph工作流"""
    
    # 创建状态图
    workflow = StateGraph(JexAgentState)
    
    # 添加节点
    workflow.add_node("evaluate", phase0_evaluate)
    workflow.add_node("generate_inquiry", phase1_generate_inquiry)
    
    # 设置入口
    workflow.set_entry_point("evaluate")
    
    # 添加条件边（评估后决定是否问询）
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
            "plan": END  # Phase 2会继续
        }
    )
    
    # 问询生成后结束（等待用户回答）
    workflow.add_edge("generate_inquiry", END)
    
    return workflow.compile()


# 创建工作流实例
workflow = create_workflow()

def get_workflow():
    """获取工作流实例"""
    return workflow