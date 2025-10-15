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

