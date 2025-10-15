from typing import Dict, Any
from app.services.langgraph.state import JexAgentState
from app.services.ai_manager import get_ai_manager
import json
import re

async def phase0_evaluate(state: JexAgentState) -> Dict[str, Any]:
    """
    Phase 0: 智能评估节点
    
    功能：
    1. 分析用户输入
    2. 评估信息充足度
    3. 判断是否需要问询
    4. 识别缺失的关键信息
    """
    
    ai_manager = get_ai_manager()
    
    # 构建评估Prompt
    evaluation_prompt = f"""你是一个元认知AI，负责评估用户提供的信息是否充足。

**任务场景：** {state['scene']}

**用户输入：**
{state['user_input']}

**你的任务：**
1. 分析用户已经提供了哪些信息
2. 评估对于"{state['scene']}"这个场景，还缺少哪些**关键**信息
3. 判断是否需要向用户提问

**评估标准：**
- 如果缺少的信息会导致建议"完全错误"或"毫无价值" → 必须问询
- 如果缺少的信息只是让建议"不够精准" → 可以用假设处理，不必问询
- 优先考虑用户体验，不要过度问询

**请以JSON格式返回评估结果：**
{{
  "provided_info": {{
    "关键1": "用户提供的内容",
    "关键2": "用户提供的内容"
  }},
  "missing_critical_info": ["缺失的关键信息1", "缺失的关键信息2"],
  "info_sufficiency": 0.7,
  "need_inquiry": true/false,
  "reason": "判断理由"
}}

只返回JSON，不要其他内容。
"""
    
    messages = [{"role": "user", "content": evaluation_prompt}]
    
    try:
        # 调用元认知AI
        result = await ai_manager.call_meta_ai(messages, temperature=0.3)
        
        # 解析JSON响应
        content = result["content"].strip()
        
        # 提取JSON（如果AI返回了额外文本）
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            evaluation_data = json.loads(json_match.group())
        else:
            evaluation_data = json.loads(content)
        
        # 记录审计轨迹
        audit_entry = {
            "step": 0,
            "phase": "评估",
            "actor": "元认知AI",
            "action": "评估信息充足度",
            "input": state['user_input'][:200] + "...",
            "output": json.dumps(evaluation_data, ensure_ascii=False),
            "reasoning": evaluation_data.get("reason", ""),
            "tokens_used": result["tokens"]["total"],
            "cost": result["cost"]
        }
        
        # 更新状态
        return {
            "need_inquiry": evaluation_data.get("need_inquiry", False),
            "provided_info": evaluation_data.get("provided_info", {}),
            "missing_info": evaluation_data.get("missing_critical_info", []),
            "info_sufficiency": evaluation_data.get("info_sufficiency", 0.5),
            "audit_trail": state.get("audit_trail", []) + [audit_entry],
            "total_cost": state.get("total_cost", 0.0) + result["cost"]
        }
        
    except Exception as e:
        # 错误处理
        return {
            "error": f"Phase 0评估失败: {str(e)}",
            "need_inquiry": True,  # 出错时默认需要问询
            "missing_info": ["无法自动评估，需要补充信息"]
        }