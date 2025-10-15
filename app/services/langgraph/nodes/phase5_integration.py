from typing import Dict, Any, List
from app.services.langgraph.state import JexAgentState
from app.services.ai_manager import get_ai_manager
import json
import re

async def phase5_integration(state: JexAgentState) -> Dict[str, Any]:
    """
    Phase 5: 智能整合输出节点
    
    功能：
    1. 整合多AI观点
    2. 生成执行摘要（TL;DR）
    3. 生成确定性建议
    4. 生成假设性建议
    5. 标注分歧点
    6. 生成勾子（邀请深度定制）
    7. 整理审计轨迹
    """
    
    ai_manager = get_ai_manager()
    
    # 构建完整上下文
    context = _build_integration_context(state)
    
    # 构建整合Prompt
    integration_prompt = f"""{context}

**你的任务：**
作为元认知AI，整合以上所有信息，生成一份完整的分析报告。

**输出结构（必须以JSON格式返回）：**
{{
  "executive_summary": {{
    "tldr": "一句话核心结论（50字以内）",
    "key_actions": ["行动建议1", "行动建议2", "行动建议3"]
  }},
  
  "certain_advice": {{
    "title": "基于已知信息的建议",
    "content": "详细的确定性建议（300-500字，markdown格式）",
    "risks": ["风险提示1", "风险提示2"]
  }},
  
  "hypothetical_advice": [
    {{
      "condition": "如果XXX",
      "suggestion": "则建议YYY"
    }}
  ],
  
  "divergences": [
    {{
      "issue": "分歧议题",
      "ai_a_view": "AI-A的观点",
      "ai_a_reason": "理由",
      "ai_b_view": "AI-B的观点",
      "ai_b_reason": "理由",
      "our_suggestion": "我们的综合建议"
    }}
  ],
  
  "hooks": {{
    "satisfaction_check": "如果对以上建议不满意...",
    "missing_info_hint": ["可能还需要了解的信息1", "可能还需要了解的信息2"]
  }}
}}

**要求：**
1. 执行摘要要简洁有力
2. 确定性建议要具体可操作
3. 假设性建议覆盖2-3种可能的情况
4. 只标注真正有价值的分歧点（如果没有明显分歧，divergences可以为空数组）
5. 勾子要自然，不强迫用户补充信息

**只返回JSON，不要其他内容。**
"""
    
    messages = [{"role": "user", "content": integration_prompt}]
    
    try:
        # 调用元认知AI
        result = await ai_manager.call_meta_ai(messages, temperature=0.5, max_tokens=3000)
        
        # 解析JSON响应
        content = result["content"].strip()
        
        # 提取JSON
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            output_data = json.loads(json_match.group())
        else:
            output_data = json.loads(content)
        
        # 记录审计轨迹
        audit_entry = {
            "step": len(state.get("audit_trail", [])),
            "phase": "整合",
            "actor": "元认知AI",
            "action": "生成综合报告",
            "input": f"整合{len(state.get('debate_rounds', []))}轮协作结果",
            "output": "生成了完整的结构化报告",
            "reasoning": "综合多AI观点，输出最终建议",
            "tokens_used": result["tokens"]["total"],
            "cost": result["cost"]
        }
        
        # 生成审计轨迹摘要
        audit_summary = _generate_audit_summary(state.get("audit_trail", []))
        
        return {
            "final_output": {**output_data, "audit_summary": audit_summary},
            "audit_trail": state.get("audit_trail", []) + [audit_entry],
            "total_cost": state.get("total_cost", 0.0) + result["cost"]
        }
        
    except Exception as e:
        # 出错时生成基础报告
        return {
            "error": f"Phase 5整合失败: {str(e)}",
            "final_output": _generate_fallback_output(state),
            "audit_trail": state.get("audit_trail", []),
            "total_cost": state.get("total_cost", 0.0)
        }


# ========== 辅助函数 ==========

def _build_integration_context(state: JexAgentState) -> str:
    """构建整合上下文"""
    context_parts = [
        f"**任务场景：** {state['scene']}",
        f"**用户需求：** {state['user_input']}"
    ]
    
    # 添加收集的信息
    if state.get('provided_info'):
        context_parts.append(f"**用户提供的信息：**\n{json.dumps(state['provided_info'], ensure_ascii=False, indent=2)}")
    
    if state.get('collected_info'):
        context_parts.append(f"**问询收集的信息：**\n{json.dumps(state['collected_info'], ensure_ascii=False, indent=2)}")
    
    # 添加任务规划
    context_parts.append(f"\n**协作策略：**")
    context_parts.append(f"- 任务类型：{state.get('task_type', '未知')}")
    context_parts.append(f"- 协作模式：{state.get('collaboration_mode', '未知')}")
    context_parts.append(f"- AI-A角色：{state.get('ai_a_role', '未知')}")
    context_parts.append(f"- AI-B角色：{state.get('ai_b_role', '未知')}")
    
    # 添加协作结果
    context_parts.append(f"\n**AI协作结果：**")
    
    if state.get('collaboration_mode') == 'debate':
        context_parts.append(f"\n**AI-A的最终观点：**\n{state.get('ai_a_output', '无')}")
        context_parts.append(f"\n**AI-B的最终观点：**\n{state.get('ai_b_output', '无')}")
        
        debate_rounds = state.get('debate_rounds', [])
        if len(debate_rounds) > 1:
            context_parts.append(f"\n**辩论过程：**")
            for round_data in debate_rounds:
                context_parts.append(f"第{round_data.get('round', 0)}轮：")
                if round_data.get('divergence'):
                    context_parts.append(f"  - 分歧点：{round_data['divergence'].get('divergence_points', [])}")
    
    elif state.get('collaboration_mode') == 'review':
        context_parts.append(f"\n**最终内容：**\n{state.get('ai_a_output', '无')}")
        context_parts.append(f"\n**最终审查意见：**\n{state.get('ai_b_output', '无')}")
        
        debate_rounds = state.get('debate_rounds', [])
        context_parts.append(f"\n**改进轮次：** {len(debate_rounds)}轮")
    
    # 添加停止原因
    if state.get('stop_reason'):
        context_parts.append(f"\n**协作终止原因：** {state['stop_reason']}")
    
    return "\n\n".join(context_parts)


def _generate_audit_summary(audit_trail: List[Dict[str, Any]]) -> Dict[str, Any]:
    """生成审计轨迹摘要"""
    if not audit_trail:
        return {"phases": [], "total_steps": 0}
    
    # 按阶段分组
    phases = {}
    for entry in audit_trail:
        phase = entry.get("phase", "未知")
        if phase not in phases:
            phases[phase] = []
        phases[phase].append({
            "actor": entry.get("actor"),
            "action": entry.get("action"),
            "reasoning": entry.get("reasoning", "")[:100]
        })
    
    return {
        "phases": [{"phase": k, "steps": v} for k, v in phases.items()],
        "total_steps": len(audit_trail)
    }


def _generate_fallback_output(state: JexAgentState) -> Dict[str, Any]:
    """生成备用输出（当整合失败时）"""
    return {
        "executive_summary": {
            "tldr": "由于系统错误，无法生成完整报告，但AI协作已完成",
            "key_actions": ["查看AI-A和AI-B的详细观点", "联系技术支持"]
        },
        "certain_advice": {
            "title": "AI协作结果",
            "content": f"**AI-A观点：**\n{state.get('ai_a_output', '无')}\n\n**AI-B观点：**\n{state.get('ai_b_output', '无')}",
            "risks": ["系统整合功能异常，建议人工复核"]
        },
        "hypothetical_advice": [],
        "divergences": [],
        "hooks": {
            "satisfaction_check": "如需进一步分析，请联系客服",
            "missing_info_hint": []
        }
    }
