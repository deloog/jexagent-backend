from typing import Dict, Any, List
from app.services.langgraph.state import JexAgentState
from app.services.ai_manager import get_ai_manager
import json
import re

async def phase3_debate_mode(state: JexAgentState) -> Dict[str, Any]:
    """
    Phase 3: 辩论模式协作
    
    流程：
    1. AI-A从视角1分析
    2. AI-B从视角2分析
    3. 元认知AI判断差异
    4. 如果差异大，启动辩论
    5. 持续辩论直到收敛或达到最大轮次
    """
    
    ai_manager = get_ai_manager()
    
    # 构建完整上下文
    context = _build_context(state)
    
    # 第1轮：AI-A和AI-B独立分析
    if state.get("current_round", 0) == 0:
        # AI-A分析
        ai_a_result = await _call_ai_a(context, state, ai_manager)
        
        # AI-B分析
        ai_b_result = await _call_ai_b(context, state, ai_manager)
        
        # 判断差异
        divergence_check = await _check_divergence(
            ai_a_result["content"],
            ai_b_result["content"],
            ai_manager
        )
        
        # 初始化辩论记录
        debate_rounds = [{
            "round": 1,
            "ai_a": ai_a_result["content"],
            "ai_b": ai_b_result["content"],
            "divergence": divergence_check
        }]
        
        # 更新审计轨迹
        audit_trail = state.get("audit_trail", [])
        audit_trail.extend([
            {
                "step": len(audit_trail),
                "phase": "协作",
                "actor": "Kimi",
                "action": "独立分析",
                "input": f"角色: {state['ai_a_role']}",
                "output": ai_a_result["content"][:200] + "...",
                "reasoning": "从深度和专业性角度分析",
                "tokens_used": ai_a_result["tokens"]["total"],
                "cost": ai_a_result["cost"]
            },
            {
                "step": len(audit_trail) + 1,
                "phase": "协作",
                "actor": "Qwen",
                "action": "独立分析",
                "input": f"角色: {state['ai_b_role']}",
                "output": ai_b_result["content"][:200] + "...",
                "reasoning": "从实用和传播角度分析",
                "tokens_used": ai_b_result["tokens"]["total"],
                "cost": ai_b_result["cost"]
            },
            {
                "step": len(audit_trail) + 2,
                "phase": "协作",
                "actor": "元认知AI",
                "action": "判断差异",
                "input": "比较AI-A和AI-B的观点",
                "output": json.dumps(divergence_check, ensure_ascii=False),
                "reasoning": divergence_check.get("reason", ""),
                "tokens_used": divergence_check.get("tokens_used", 0),
                "cost": divergence_check.get("cost", 0.0)
            }
        ])
        
        total_cost = (
            state.get("total_cost", 0.0) + 
            ai_a_result["cost"] + 
            ai_b_result["cost"] + 
            divergence_check.get("cost", 0.0)
        )
        
        # 判断是否需要辩论
        if divergence_check.get("has_significant_divergence", False):
            # 需要辩论，但不在这里继续，而是返回状态让工作流决定
            return {
                "ai_a_output": ai_a_result["content"],
                "ai_b_output": ai_b_result["content"],
                "debate_rounds": debate_rounds,
                "current_round": 1,
                "should_stop": False,
                "audit_trail": audit_trail,
                "total_cost": total_cost
            }
        else:
            # 观点一致，无需辩论，直接结束
            return {
                "ai_a_output": ai_a_result["content"],
                "ai_b_output": ai_b_result["content"],
                "debate_rounds": debate_rounds,
                "current_round": 1,
                "should_stop": True,
                "stop_reason": "观点趋于一致，无需辩论",
                "audit_trail": audit_trail,
                "total_cost": total_cost
            }
    
    else:
        # 后续辩论轮次
        current_round = state.get("current_round", 1)
        
        # AI-A针对AI-B的观点反驳
        ai_a_debate = await _debate_response(
            context,
            state,
            "ai_a",
            state["ai_b_output"],
            ai_manager
        )
        
        # AI-B针对AI-A的观点反驳
        ai_b_debate = await _debate_response(
            context,
            state,
            "ai_b",
            state["ai_a_output"],
            ai_manager
        )
        
        # 判断是否有新信息
        novelty_check = await _check_novelty(
            state.get("debate_rounds", []),
            ai_a_debate["content"],
            ai_b_debate["content"],
            ai_manager
        )
        
        # 记录本轮辩论
        debate_rounds = state.get("debate_rounds", [])
        debate_rounds.append({
            "round": current_round + 1,
            "ai_a": ai_a_debate["content"],
            "ai_b": ai_b_debate["content"],
            "novelty": novelty_check
        })
        
        # 更新审计轨迹
        audit_trail = state.get("audit_trail", [])
        audit_trail.extend([
            {
                "step": len(audit_trail),
                "phase": "协作",
                "actor": "Kimi",
                "action": f"辩论第{current_round + 1}轮",
                "input": f"针对Qwen的观点: {state['ai_b_output'][:100]}...",
                "output": ai_a_debate["content"][:200] + "...",
                "reasoning": "提出反驳或补充观点",
                "tokens_used": ai_a_debate["tokens"]["total"],
                "cost": ai_a_debate["cost"]
            },
            {
                "step": len(audit_trail) + 1,
                "phase": "协作",
                "actor": "Qwen",
                "action": f"辩论第{current_round + 1}轮",
                "input": f"针对Kimi的观点: {state['ai_a_output'][:100]}...",
                "output": ai_b_debate["content"][:200] + "...",
                "reasoning": "提出反驳或补充观点",
                "tokens_used": ai_b_debate["tokens"]["total"],
                "cost": ai_b_debate["cost"]
            },
            {
                "step": len(audit_trail) + 2,
                "phase": "协作",
                "actor": "元认知AI",
                "action": "检测信息增量",
                "input": "分析本轮辩论是否有新观点",
                "output": json.dumps(novelty_check, ensure_ascii=False),
                "reasoning": novelty_check.get("reason", ""),
                "tokens_used": novelty_check.get("tokens_used", 0),
                "cost": novelty_check.get("cost", 0.0)
            }
        ])
        
        total_cost = (
            state.get("total_cost", 0.0) + 
            ai_a_debate["cost"] + 
            ai_b_debate["cost"] + 
            novelty_check.get("cost", 0.0)
        )
        
        # 判断是否应该停止
        should_stop = (
            not novelty_check.get("has_novelty", True) or
            current_round + 1 >= state.get("max_rounds", 3)
        )
        
        stop_reason = None
        if should_stop:
            if not novelty_check.get("has_novelty", True):
                stop_reason = "无新信息增量，观点已收敛"
            else:
                stop_reason = f"达到最大轮次限制({state.get('max_rounds', 3)}轮)"
        
        return {
            "ai_a_output": ai_a_debate["content"],
            "ai_b_output": ai_b_debate["content"],
            "debate_rounds": debate_rounds,
            "current_round": current_round + 1,
            "should_stop": should_stop,
            "stop_reason": stop_reason,
            "audit_trail": audit_trail,
            "total_cost": total_cost
        }


# ========== 辅助函数 ==========

def _build_context(state: JexAgentState) -> str:
    """构建完整上下文"""
    context_parts = [
        f"**任务场景：** {state['scene']}",
        f"**用户需求：** {state['user_input']}"
    ]
    
    if state.get('provided_info'):
        context_parts.append(f"**已提供信息：** {json.dumps(state['provided_info'], ensure_ascii=False)}")
    
    if state.get('collected_info'):
        context_parts.append(f"**收集的信息：** {json.dumps(state['collected_info'], ensure_ascii=False)}")
    
    return "\n\n".join(context_parts)


async def _call_ai_a(context: str, state: JexAgentState, ai_manager) -> Dict[str, Any]:
    """调用AI-A（Kimi）"""
    prompt = f"""{context}

**你的角色：** {state['ai_a_role']}

**你的任务：** 
基于你的角色定位，从你的专业视角给出深入分析和建议。

**要求：**
1. 保持客观和专业
2. 提供具体的论据和例子
3. 长度控制在300-500字

请开始你的分析：
"""
    
    messages = [{"role": "user", "content": prompt}]
    return await ai_manager.call_ai_a(messages, temperature=0.7)


async def _call_ai_b(context: str, state: JexAgentState, ai_manager) -> Dict[str, Any]:
    """调用AI-B（Qwen）"""
    prompt = f"""{context}

**你的角色：** {state['ai_b_role']}

**你的任务：** 
基于你的角色定位，从你的专业视角给出分析和建议。

**要求：**
1. 保持客观和实用
2. 提供具体的论据和例子
3. 长度控制在300-500字

请开始你的分析：
"""
    
    messages = [{"role": "user", "content": prompt}]
    return await ai_manager.call_ai_b(messages, temperature=0.7)


async def _check_divergence(ai_a_output: str, ai_b_output: str, ai_manager) -> Dict[str, Any]:
    """检查AI-A和AI-B的观点差异"""
    prompt = f"""你是元认知AI，负责判断两个AI的观点差异。

**AI-A的观点：**
{ai_a_output}

**AI-B的观点：**
{ai_b_output}

**你的任务：**
判断这两个观点是否有显著差异，是否需要启动辩论。

**判断标准：**
- 如果观点基本一致，只是表达方式不同 → 无需辩论
- 如果有明显的分歧点、不同的建议方向 → 需要辩论

**请以JSON格式返回：**
{{
  "has_significant_divergence": true/false,
  "divergence_points": ["分歧点1", "分歧点2"],
  "reason": "判断理由"
}}

只返回JSON，不要其他内容。
"""
    
    messages = [{"role": "user", "content": prompt}]
    result = await ai_manager.call_meta_ai(messages, temperature=0.3)
    
    try:
        content = result["content"].strip()
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group())
        else:
            data = json.loads(content)
        
        data["tokens_used"] = result["tokens"]["total"]
        data["cost"] = result["cost"]
        return data
    except:
        return {
            "has_significant_divergence": True,
            "divergence_points": ["无法判断"],
            "reason": "解析失败，默认需要辩论",
            "tokens_used": result["tokens"]["total"],
            "cost": result["cost"]
        }


async def _debate_response(context: str, state: JexAgentState, ai_type: str, opponent_view: str, ai_manager) -> Dict[str, Any]:
    """生成辩论回应"""
    role = state['ai_a_role'] if ai_type == "ai_a" else state['ai_b_role']
    opponent_name = "AI-B" if ai_type == "ai_a" else "AI-A"
    
    prompt = f"""{context}

**你的角色：** {role}

**{opponent_name}的观点：**
{opponent_view}

**你的任务：**
针对{opponent_name}的观点，提出你的回应：
1. 如果你认同，说明为什么认同，并补充观点
2. 如果你不认同，说明理由，并提出你的观点
3. 保持客观和建设性

**要求：**
- 聚焦核心分歧点
- 提供新的论据或视角
- 避免重复之前的观点
- 长度控制在200-300字

请开始你的回应：
"""
    
    messages = [{"role": "user", "content": prompt}]
    
    if ai_type == "ai_a":
        return await ai_manager.call_ai_a(messages, temperature=0.7)
    else:
        return await ai_manager.call_ai_b(messages, temperature=0.7)


async def _check_novelty(debate_history: List[Dict], new_ai_a: str, new_ai_b: str, ai_manager) -> Dict[str, Any]:
    """检查本轮辩论是否有新信息"""
    prompt = f"""你是元认知AI，负责判断辩论是否产生了新信息。

**之前的辩论记录：**
{json.dumps(debate_history[-2:], ensure_ascii=False, indent=2) if len(debate_history) > 0 else "无"}

**本轮AI-A的观点：**
{new_ai_a}

**本轮AI-B的观点：**
{new_ai_b}

**你的任务：**
判断本轮辩论是否提出了新的观点、论据或视角。

**判断标准：**
- 如果只是重复之前的观点，换个说法 → 无新信息
- 如果提出了新的论据、案例、视角 → 有新信息
- 如果双方观点开始趋同 → 无新信息，可以终止

**请以JSON格式返回：**
{{
  "has_novelty": true/false,
  "new_points": ["新观点1", "新观点2"],
  "reason": "判断理由"
}}

只返回JSON，不要其他内容。
"""
    
    messages = [{"role": "user", "content": prompt}]
    result = await ai_manager.call_meta_ai(messages, temperature=0.3)
    
    try:
        content = result["content"].strip()
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group())
        else:
            data = json.loads(content)
        
        data["tokens_used"] = result["tokens"]["total"]
        data["cost"] = result["cost"]
        return data
    except:
        return {
            "has_novelty": False,
            "new_points": [],
            "reason": "解析失败，默认无新信息",
            "tokens_used": result["tokens"]["total"],
            "cost": result["cost"]
        }
    