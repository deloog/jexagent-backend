from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict
from app.services.ai_manager import get_ai_manager

router = APIRouter(prefix="/ai-test", tags=["AI测试"])

class ChatRequest(BaseModel):
    messages: List[Dict[str, str]]
    ai_type: str  # "meta", "ai_a", "ai_b"

@router.post("/chat")
async def test_chat(request: ChatRequest):
    """测试AI对话"""
    ai_manager = get_ai_manager()
    
    try:
        if request.ai_type == "meta":
            result = await ai_manager.call_meta_ai(request.messages)
        elif request.ai_type == "ai_a":
            result = await ai_manager.call_ai_a(request.messages)
        elif request.ai_type == "ai_b":
            result = await ai_manager.call_ai_b(request.messages)
        else:
            raise HTTPException(status_code=400, detail="无效的AI类型")
        
        return {
            "status": "success",
            "result": result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/stats")
async def get_stats():
    """获取AI使用统计"""
    ai_manager = get_ai_manager()
    return ai_manager.get_stats()

@router.post("/reset-stats")
async def reset_stats():
    """重置统计信息"""
    ai_manager = get_ai_manager()
    ai_manager.reset_stats()
    return {"message": "统计信息已重置"}

@router.post("/quick-test")
async def quick_test():
    """快速测试所有AI"""
    ai_manager = get_ai_manager()
    
    test_messages = [
        {"role": "user", "content": "你好，请简单介绍一下你自己"}
    ]
    
    results = {}
    
    try:
        # 测试元认知AI
        results["meta_ai"] = await ai_manager.call_meta_ai(test_messages)
        
        # 测试AI-A
        results["ai_a"] = await ai_manager.call_ai_a(test_messages)
        
        # 测试AI-B
        results["ai_b"] = await ai_manager.call_ai_b(test_messages)
        
        # 获取统计
        stats = ai_manager.get_stats()
        
        return {
            "status": "success",
            "results": results,
            "stats": stats
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"测试失败: {str(e)}")