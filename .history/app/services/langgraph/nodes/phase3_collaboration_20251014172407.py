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
async def phase3_review_mode(state: JexAgentState) -> Dict[str, Any]:
        """
    Phase 3: 审查模式协作
    
    流程：
    1. AI-A生成内容初稿
    2. AI-B审查并提出建议
    3. 元认知AI判断是否需要改进
    4. 如果需要，AI-A根据反馈改进
    5. 重复直到质量达标或达到最大轮次
    """
    
    ai_manager = get_ai_manager()
    context = _build_context(state)
    
    # 第1轮：AI-A生成初稿
    if state.get("current_round", 0) == 0:
        # AI-A生成内容
        ai_a_result = await _generate_content(context, state, ai_manager)
        
        # AI-B审查
        ai_b_result = await _review_content(
            context,
            state,
            ai_a_result["content"],
            ai_manager
        )
        
        # 判断是否需要改进
        improvement_check = await _check_need_improvement(
            ai_a_result["content"],
            ai_b_result["content"],
            ai_manager
        )
        
        # 初始化辩论记录（复用debate_rounds字段）
        debate_rounds = [{
            "round": 1,
            "ai_a_action": "生成初稿",
            "ai_a": ai_a_result["content"],
            "ai_b_action": "审查反馈",
            "ai_b": ai_b_result["content"],
            "improvement_check": improvement_check
        }]
        
        # 更新审计轨迹
        audit_trail = state.get("audit_trail", [])
        audit_trail.extend([
            {
                "step": len(audit_trail),
                "phase": "协作",
                "actor": "Kimi",
                "action": "生成内容初稿",
                "input": f"角色: {state['ai_a_role']}",
                "output": ai_a_result["content"][:200] + "...",
                "reasoning": "基于需求生成内容",
                "tokens_used": ai_a_result["tokens"]["total"],
                "cost": ai_a_result["cost"]
            },
            {
                "step": len(audit_trail) + 1,
                "phase": "协作",
                "actor": "Qwen",
                "action": "审查内容",
                "input": f"审查初稿（{len(ai_a_result['content'])}字）",
                "output": ai_b_result["content"][:200] + "...",
                "reasoning": "识别问题并提出改进建议",
                "tokens_used": ai_b_result["tokens"]["total"],
                "cost": ai_b_result["cost"]
            },
            {
                "step": len(audit_trail) + 2,
                "phase": "协作",
                "actor": "元认知AI",
                "action": "判断是否需要改进",
                "input": "分析审查反馈的严重程度",
                "output": json.dumps(improvement_check, ensure_ascii=False),
                "reasoning": improvement_check.get("reason", ""),
                "tokens_used": improvement_check.get("tokens_used", 0),
                "cost": improvement_check.get("cost", 0.0)
            }
        ])
        
        total_cost = (
            state.get("total_cost", 0.0) + 
            ai_a_result["cost"] + 
            ai_b_result["cost"] + 
            improvement_check.get("cost", 0.0)
        )
        
        # 判断是否需要改进
        if improvement_check.get("needs_improvement", False):
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
            return {
                "ai_a_output": ai_a_result["content"],
                "ai_b_output": ai_b_result["content"],
                "debate_rounds": debate_rounds,
                "current_round": 1,
                "should_stop": True,
                "stop_reason": "内容质量已达标，无需改进",
                "audit_trail": audit_trail,
                "total_cost": total_cost
            }
    
    else:
        # 改进轮次
        current_round = state.get("current_round", 1)
        
        # AI-A根据反馈改进
        ai_a_improved = await _improve_content(
            context,
            state,
            state["ai_a_output"],
            state["ai_b_output"],
            ai_manager
        )
        
        # AI-B再次审查
        ai_b_review = await _review_content(
            context,
            state,
            ai_a_improved["content"],
            ai_manager
        )
        
        # 判断质量
        improvement_check = await _check_need_improvement(
            ai_a_improved["content"],
            ai_b_review["content"],
            ai_manager
        )
        
        # 记录本轮
        debate_rounds = state.get("debate_rounds", [])
        debate_rounds.append({
            "round": current_round + 1,
            "ai_a_action": "改进内容",
            "ai_a": ai_a_improved["content"],
            "ai_b_action": "再次审查",
            "ai_b": ai_b_review["content"],
            "improvement_check": improvement_check
        })
        
        # 更新审计轨迹
        audit_trail = state.get("audit_trail", [])
        audit_trail.extend([
            {
                "step": len(audit_trail),
                "phase": "协作",
                "actor": "Kimi",
                "action": f"改进第{current_round + 1}轮",
                "input": f"基于反馈: {state['ai_b_output'][:100]}...",
                "output": ai_a_improved["content"][:200] + "...",
                "reasoning": "根据审查建议优化内容",
                "tokens_used": ai_a_improved["tokens"]["total"],
                "cost": ai_a_improved["cost"]
            },
            {
                "step": len(audit_trail) + 1,
                "phase": "协作",
                "actor": "Qwen",
                "action": f"审查第{current_round + 1}轮",
                "input": f"审查改进后的内容",
                "output": ai_b_review["content"][:200] + "...",
                "reasoning": "评估改进效果",
                "tokens_used": ai_b_review["tokens"]["total"],
                "cost": ai_b_review["cost"]
            },
            {
                "step": len(audit_trail) + 2,
                "phase": "协作",
                "actor": "元认知AI",
                "action": "质量判断",
                "input": "判断是否达标",
                "output": json.dumps(improvement_check, ensure_ascii=False),
                "reasoning": improvement_check.get("reason", ""),
                "tokens_used": improvement_check.get("tokens_used", 0),
                "cost": improvement_check.get("cost", 0.0)
            }
        ])
        
        total_cost = (
            state.get("total_cost", 0.0) + 
            ai_a_improved["cost"] + 
            ai_b_review["cost"] + 
            improvement_check.get("cost", 0.0)
        )
        
        # 判断是否应该停止
        should_stop = (
            not improvement_check.get("needs_improvement", False) or
            current_round + 1 >= state.get("max_rounds", 3)
        )
        
        stop_reason = None
        if should_stop:
            if not improvement_check.get("needs_improvement", False):
                stop_reason = "内容质量已达标"
            else:
                stop_reason = f"达到最大改进轮次({state.get('max_rounds', 3)}轮)"
        
        return {
            "ai_a_output": ai_a_improved["content"],
            "ai_b_output": ai_b_review["content"],
            "debate_rounds": debate_rounds,
            "current_round": current_round + 1,
            "should_stop": should_stop,
            "stop_reason": stop_reason,
            "audit_trail": audit_trail,
            "total_cost": total_cost
        }


# ========== 审查模式辅助函数 ==========

async def _generate_content(context: str, state: JexAgentState, ai_manager) -> Dict[str, Any]:
    """AI-A生成内容"""
    prompt = f"""{context}

**你的角色：** {state['ai_a_role']}

**你的任务：** 
基于用户需求，生成高质量的内容。

**要求：**
1. 内容完整、结构清晰
2. 符合用户的具体要求
3. 保持专业和准确

请生成内容：
"""
    
    messages = [{"role": "user", "content": prompt}]
    return await ai_manager.call_ai_a(messages, temperature=0.7, max_tokens=2000)


async def _review_content(context: str, state: JexAgentState, content: str, ai_manager) -> Dict[str, Any]:
    """AI-B审查内容"""
    prompt = f"""{context}

**你的角色：** {state['ai_b_role']}

**待审查的内容：**
{content}

**你的任务：** 
审查以上内容，找出问题和不足，提出改进建议。

**审查维度：**
1. 准确性：是否有事实错误或误导性内容
2. 完整性：是否遗漏了重要信息
3. 可读性：表达是否清晰、易懂
4. 吸引力：是否能吸引目标受众

**要求：**
- 不要重写内容，只指出问题
- 提供具体的改进建议
- 如果内容很好，也要明确指出

请开始审查：
"""
    
    messages = [{"role": "user", "content": prompt}]
    return await ai_manager.call_ai_b(messages, temperature=0.6)


async def _check_need_improvement(content: str, review: str, ai_manager) -> Dict[str, Any]:
    """判断是否需要改进"""
    prompt = f"""你是元认知AI，负责判断内容是否需要改进。

**原始内容：**
{content[:500]}...

**审查反馈：**
{review}

**你的任务：**
判断审查反馈中指出的问题是否严重，是否需要改进。

**判断标准：**
- 如果有严重问题（事实错误、重大遗漏） → 必须改进
- 如果只是小问题或优化建议 → 可以接受，无需改进
- 如果审查者认为内容已经很好 → 无需改进

**请以JSON格式返回：**
{{
  "needs_improvement": true/false,
  "severity": "严重/中等/轻微/无问题",
  "key_issues": ["问题1", "问题2"],
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
            "needs_improvement": False,
            "severity": "无法判断",
            "key_issues": [],
            "reason": "解析失败，默认接受",
            "tokens_used": result["tokens"]["total"],
            "cost": result["cost"]
        }


async def _improve_content(context: str, state: JexAgentState, original: str, feedback: str, ai_manager) -> Dict[str, Any]:
    """AI-A改进内容"""
    prompt = f"""{context}

**你的角色：** {state['ai_a_role']}

**你之前生成的内容：**
{original}

**审查反馈：**
{feedback}

**你的任务：** 
根据审查反馈，改进你的内容。

**要求：**
1. 针对性解决指出的问题
2. 保留好的部分
3. 整体保持连贯性

请提供改进后的内容：
"""
    
    messages = [{"role": "user", "content": prompt}]
    return await ai_manager.call_ai_a(messages, temperature=0.7, max_tokens=2000)