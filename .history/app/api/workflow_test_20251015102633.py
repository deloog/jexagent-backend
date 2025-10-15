from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.services.langgraph.workflow import get_workflow
from uuid import uuid4

router = APIRouter(prefix="/workflow-test", tags=["工作流测试"])

class EvaluateRequest(BaseModel):
    scene: str
    user_input: str

@router.post("/phase0-evaluate")
async def test_phase0_evaluate(request: EvaluateRequest):
    """测试Phase 0评估节点"""
    
    workflow = get_workflow()
    
    # 初始化状态
    initial_state = {
        "task_id": str(uuid4()),
        "user_id": "test-user",
        "scene": request.scene,
        "user_input": request.user_input,
        "audit_trail": [],
        "total_cost": 0.0
    }
    
    try:
        # 运行工作流
        result = await workflow.ainvoke(initial_state)
        
        return {
            "status": "success",
            "evaluation": {
                "need_inquiry": result.get("need_inquiry"),
                "info_sufficiency": result.get("info_sufficiency"),
                "provided_info": result.get("provided_info"),
                "missing_info": result.get("missing_info")
            },
            "audit_trail": result.get("audit_trail", []),
            "total_cost": result.get("total_cost"),
            "error": result.get("error")
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"工作流执行失败: {str(e)}")

@router.post("/quick-test")
async def quick_test():
    """快速测试：信息充足和不足的场景"""
    
    test_cases = [
        {
            "name": "信息充足场景",
            "scene": "topic-analysis",
            "user_input": "我是一个技术博主，粉丝主要是25-35岁的程序员，播放量在5-10万。我想做一期关于AI Agent的视频，之前做过3期AI相关内容效果不错。我希望通过这个选题涨粉并建立专业形象。"
        },
        {
            "name": "信息不足场景",
            "scene": "topic-analysis",
            "user_input": "我想做一期关于AI Agent的视频"
        }
    ]
    
    results = []
    workflow = get_workflow()
    
    for test in test_cases:
        initial_state = {
            "task_id": str(uuid4()),
            "user_id": "test-user",
            "scene": test["scene"],
            "user_input": test["user_input"],
            "audit_trail": [],
            "total_cost": 0.0
        }
        
        try:
            result = await workflow.ainvoke(initial_state)
            results.append({
                "test_name": test["name"],
                "need_inquiry": result.get("need_inquiry"),
                "info_sufficiency": result.get("info_sufficiency"),
                "missing_info": result.get("missing_info"),
                "cost": result.get("total_cost")
            })
        except Exception as e:
            results.append({
                "test_name": test["name"],
                "error": str(e)
            })
    
    return {
        "status": "success",
        "test_results": results
    }

@router.post("/phase1-inquiry")
async def test_phase1_inquiry(request: EvaluateRequest):
    """测试Phase 0-1完整流程（评估+生成问询）"""
    
    workflow = get_workflow()
    
    # 初始化状态
    initial_state = {
        "task_id": str(uuid4()),
        "user_id": "test-user",
        "scene": request.scene,
        "user_input": request.user_input,
        "audit_trail": [],
        "total_cost": 0.0
    }
    
    try:
        # 运行工作流（Phase 0 + Phase 1）
        result = await workflow.ainvoke(initial_state)
        
        return {
            "status": "success",
            "evaluation": {
                "need_inquiry": result.get("need_inquiry"),
                "info_sufficiency": result.get("info_sufficiency"),
                "missing_info": result.get("missing_info")
            },
            "inquiry": {
                "questions": result.get("inquiry_questions", []),
                "details": result.get("inquiry_details", [])
            },
            "audit_trail": result.get("audit_trail", []),
            "total_cost": result.get("total_cost"),
            "error": result.get("error")
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"工作流执行失败: {str(e)}")


from typing import Any
from app.services.langgraph.nodes.phase1_inquiry import phase1_process_answers

class AnswersRequest(BaseModel):
    task_id: str
    scene: str
    user_input: str
    answers: dict[int, str]  # {1: "回答1", 2: "回答2"}
    
    # 需要传递之前的状态
    provided_info: dict[str, Any]
    missing_info: list[str]
    audit_trail: list[dict[str, Any]]
    total_cost: float

@router.post("/phase1-process-answers")
async def test_phase1_process_answers(request: AnswersRequest):
    """测试处理用户答案"""
    
    # 重建状态
    state = {
        "task_id": request.task_id,
        "user_id": "test-user",
        "scene": request.scene,
        "user_input": request.user_input,
        "provided_info": request.provided_info,
        "missing_info": request.missing_info,
        "audit_trail": request.audit_trail,
        "total_cost": request.total_cost,
        "collected_info": {}
    }
    
    try:
        # 处理答案
        result = await phase1_process_answers(state, request.answers)
        
        return {
            "status": "success",
            "collected_info": result.get("collected_info"),
            "audit_trail": result.get("audit_trail", []),
            "total_cost": result.get("total_cost"),
            "error": result.get("error")
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"答案处理失败: {str(e)}")

@router.post("/phase2-planning")
async def test_phase2_planning(request: EvaluateRequest):
    """测试Phase 0-2完整流程（信息充足时直接规划）"""
    
    workflow = get_workflow()
    
    # 初始化状态（模拟信息充足的场景）
    initial_state = {
        "task_id": str(uuid4()),
        "user_id": "test-user",
        "scene": request.scene,
        "user_input": request.user_input,
        "audit_trail": [],
        "total_cost": 0.0
    }
    
    try:
        # 运行工作流
        result = await workflow.ainvoke(initial_state)
        
        return {
            "status": "success",
            "evaluation": {
                "need_inquiry": result.get("need_inquiry"),
                "info_sufficiency": result.get("info_sufficiency")
            },
            "planning": {
                "task_type": result.get("task_type"),
                "collaboration_mode": result.get("collaboration_mode"),
                "ai_a_role": result.get("ai_a_role"),
                "ai_b_role": result.get("ai_b_role"),
                "max_rounds": result.get("max_rounds")
            },
            "audit_trail": result.get("audit_trail", []),
            "total_cost": result.get("total_cost"),
            "error": result.get("error")
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"工作流执行失败: {str(e)}")


@router.post("/full-test-with-inquiry")
async def full_test_with_inquiry():
    """完整测试：从评估→问询→规划（模拟完整流程）"""
    
    # 第一步：评估并生成问询
    workflow = get_workflow()
    
    initial_state = {
        "task_id": str(uuid4()),
        "user_id": "test-user",
        "scene": "topic-analysis",
        "user_input": "我想做一期关于AI Agent的视频",
        "audit_trail": [],
        "total_cost": 0.0
    }
    
    try:
        # Phase 0-1: 评估并生成问询
        phase1_result = await workflow.ainvoke(initial_state)
        
        # 模拟用户回答问题
        mock_answers = {
            1: "我的受众是25-35岁的程序员，对新技术感兴趣",
            2: "之前做过3期AI视频，播放量5-10万",
            3: "希望涨粉并建立专业形象"
        }
        
        # Phase 1: 处理答案
        from app.services.langgraph.nodes.phase1_inquiry import phase1_process_answers
        phase1_state = dict(phase1_result)
        answer_result = await phase1_process_answers(phase1_state, mock_answers)
        
        # 合并状态
        phase1_state.update(answer_result)
        
        # Phase 2: 规划
        from app.services.langgraph.nodes.phase2_planning import phase2_planning
        planning_result = await phase2_planning(phase1_state)
        
        # 合并状态
        phase1_state.update(planning_result)
        
        return {
            "status": "success",
            "phase1_inquiry": {
                "questions": phase1_result.get("inquiry_questions", [])
            },
            "phase1_answers": {
                "collected_info": answer_result.get("collected_info")
            },
            "phase2_planning": {
                "task_type": planning_result.get("task_type"),
                "collaboration_mode": planning_result.get("collaboration_mode"),
                "ai_a_role": planning_result.get("ai_a_role"),
                "ai_b_role": planning_result.get("ai_b_role")
            },
            "audit_trail": phase1_state.get("audit_trail", []),
            "total_cost": phase1_state.get("total_cost")
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"完整流程测试失败: {str(e)}")


@router.post("/phase3-debate")
async def test_phase3_debate():
    """测试Phase 3辩论模式（完整流程）"""
    
    workflow = get_workflow()
    
    # 模拟信息充足的状态（跳过问询）
    initial_state = {
        "task_id": str(uuid4()),
        "user_id": "test-user",
        "scene": "topic-analysis",
        "user_input": "我是技术博主，粉丝是25-35岁程序员，播放量5-10万。想做AI Agent视频，之前3期AI视频效果不错。希望涨粉并建立专业形象。",
        "audit_trail": [],
        "total_cost": 0.0
    }
    
    try:
        # 运行完整工作流（Phase 0 → 2 → 3）
        result = await workflow.ainvoke(initial_state)
        
        return {
            "status": "success",
            "planning": {
                "collaboration_mode": result.get("collaboration_mode"),
                "ai_a_role": result.get("ai_a_role"),
                "ai_b_role": result.get("ai_b_role")
            },
            "collaboration": {
                "rounds": len(result.get("debate_rounds", [])),
                "stop_reason": result.get("stop_reason"),
                "final_ai_a": result.get("ai_a_output", "")[:300] + "...",
                "final_ai_b": result.get("ai_b_output", "")[:300] + "..."
            },
            "audit_trail": result.get("audit_trail", [])[-5:],  # 只返回最后5条
            "total_cost": result.get("total_cost"),
            "error": result.get("error")
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"测试失败: {str(e)}")


@router.post("/phase3-review")
async def test_phase3_review():
    """测试Phase 3审查模式（完整流程）"""
    
    workflow = get_workflow()
    
    # 模拟内容创作场景
    initial_state = {
        "task_id": str(uuid4()),
        "user_id": "test-user",
        "scene": "content-creation",
        "user_input": "帮我写一篇关于AI Agent的科普文章，面向非技术人员，要通俗易懂，举例子，大概800字",
        "audit_trail": [],
        "total_cost": 0.0
    }
    
    try:
        # 运行完整工作流
        result = await workflow.ainvoke(initial_state)
        
        return {
            "status": "success",
            "planning": {
                "collaboration_mode": result.get("collaboration_mode"),
                "ai_a_role": result.get("ai_a_role"),
                "ai_b_role": result.get("ai_b_role")
            },
            "collaboration": {
                "rounds": len(result.get("debate_rounds", [])),
                "stop_reason": result.get("stop_reason"),
                "final_content": result.get("ai_a_output", "")[:500] + "...",
                "final_review": result.get("ai_b_output", "")[:300] + "..."
            },
            "audit_trail": result.get("audit_trail", [])[-5:],
            "total_cost": result.get("total_cost"),
            "error": result.get("error")
        }
        
    except Exception as e:
        import traceback
        traceback.print_exc() 
        raise HTTPException(status_code=500, detail=f"测试失败: {str(e)}")
