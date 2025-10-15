from langgraph.graph import StateGraph, END
from app.services.langgraph.state import JexAgentState
from app.services.langgraph.nodes.phase0_evaluate import phase0_evaluate

def create_workflow():
    """创建LangGraph工作流"""
    
    # 创建状态图
    workflow = StateGraph(JexAgentState)
    
    # 添加节点
    workflow.add_node("evaluate", phase0_evaluate)
    
    # 设置入口
    workflow.set_entry_point("evaluate")
    
    # 添加条件边（评估后决定是否问询）
    def should_inquire(state: JexAgentState) -> str:
        """判断是否需要问询"""
        if state.get("need_inquiry", False):
            return "inquire"  # 需要问询（暂时先结束，Phase 1会实现）
        else:
            return "plan"  # 信息充足，直接规划（暂时先结束，Phase 2会实现）
    
    workflow.add_conditional_edges(
        "evaluate",
        should_inquire,
        {
            "inquire": END,  # 临时终止点
            "plan": END      # 临时终止点
        }
    )
    
    return workflow.compile()


# 创建工作流实例
workflow = create_workflow()

def get_workflow():
    """获取工作流实例"""
    return workflow