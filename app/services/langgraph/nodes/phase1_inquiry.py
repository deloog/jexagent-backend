from typing import Dict, Any, List
from app.services.langgraph.state import JexAgentState
from app.services.ai_manager import get_ai_manager
import json
import re

async def phase1_generate_inquiry(state: JexAgentState) -> Dict[str, Any]:
    """
    Phase 1: 动态问询生成节点
    
    功能：
    1. 基于评估结果生成针对性问题
    2. 问题数量：3-5个
    3. 问题必须清晰、具体、易回答
    """
    
    ai_manager = get_ai_manager()
    
    # 构建问询生成Prompt
    inquiry_prompt = f"""你是一个元认知AI，负责生成问询问题。

**任务场景：** {state['scene']}

**用户原始输入：**
{state['user_input']}

**已提供的信息：**
{json.dumps(state.get('provided_info', {}), ensure_ascii=False, indent=2)}

**缺失的关键信息：**
{json.dumps(state.get('missing_info', []), ensure_ascii=False, indent=2)}

**你的任务：**
生成3-5个问题，收集这些缺失的关键信息。

**问题要求：**
1. 必须清晰、具体、易于回答
2. 避免过于宽泛或抽象的问题
3. 每个问题聚焦一个主题
4. 优先问"必须知道"的信息，而非"最好知道"的信息
5. 提供示例答案，帮助用户理解

**请以JSON格式返回：**
{{
  "questions": [
    {{
      "id": 1,
      "question": "问题文本？",
      "placeholder": "例如：...",
      "required": true
    }},
    {{
      "id": 2,
      "question": "问题文本？",
      "placeholder": "例如：...",
      "required": true
    }}
  ]
}}

只返回JSON，不要其他内容。
"""
    
    messages = [{"role": "user", "content": inquiry_prompt}]
    
    try:
        # 调用元认知AI
        result = await ai_manager.call_meta_ai(messages, temperature=0.5)
        
        # 解析JSON响应
        content = result["content"].strip()
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            inquiry_data = json.loads(json_match.group())
        else:
            inquiry_data = json.loads(content)
        
        questions = inquiry_data.get("questions", [])
        
        # 审查：确保问题数量在3-5之间
        if len(questions) < 3:
            # 如果问题太少，补充一个通用问题
            questions.append({
                "id": len(questions) + 1,
                "question": "还有其他需要说明的背景信息吗？",
                "placeholder": "例如：时间限制、预算、特殊要求等...",
                "required": False
            })
        elif len(questions) > 5:
            # 如果问题太多，只保留前5个
            questions = questions[:5]
        
        # 记录审计轨迹
        audit_entry = {
            "step": len(state.get("audit_trail", [])),
            "phase": "问询",
            "actor": "元认知AI",
            "action": "生成问询问题",
            "input": f"缺失信息: {state.get('missing_info', [])}",
            "output": f"生成了{len(questions)}个问题",
            "reasoning": f"针对缺失信息生成针对性问题",
            "tokens_used": result["tokens"]["total"],
            "cost": result["cost"]
        }
        
        # 提取问题文本列表
        inquiry_questions = [q["question"] for q in questions]
        
        state["inquiry_details"] = questions

        return {
            # === 状态机必需字段 ===
            'task_id': state.get('task_id') or '',
            'user_id': state.get('user_id') or '',
            'scene': state.get('scene') or '',
            'user_input': state.get('user_input') or '',
            'need_inquiry': True,
            'provided_info': state.get('provided_info') or {},
            'missing_info': state.get('missing_info') or [],
            'info_sufficiency': state.get('info_sufficiency') or 0.3,
            'collected_info': state.get('collected_info') or {},
            'task_type': state.get('task_type') or 'topic-analysis',
            'collaboration_mode': 'inquiry',
            'ai_a_role': state.get('ai_a_role') or '',
            'ai_b_role': state.get('ai_b_role') or '',
            'ai_a_output': state.get('ai_a_output') or '',
            'ai_b_output': state.get('ai_b_output') or '',
            'debate_rounds': state.get('debate_rounds') or 0,
            'current_round': state.get('current_round') or 0,
            'max_rounds': state.get('max_rounds') or 3,
            'should_stop': state.get('should_stop') or False,
            'stop_reason': state.get('stop_reason') or '',
            'final_output': state.get('final_output') or '',
            'audit_trail': (state.get("audit_trail") or []) + [audit_entry],
            'total_cost': (state.get("total_cost") or 0.0) + result["cost"],
            'error': state.get('error') or '',

            # === 业务数据 ===
            'inquiry_questions': inquiry_questions,
            'inquiry_details': questions,  # 保存完整问题信息（包含placeholder等）
        }
        
    except Exception as e:
        return {
            "error": f"Phase 1问询生成失败: {str(e)}",
            "inquiry_questions": ["请补充更多信息以便我们提供准确建议"]
        }


async def phase1_process_answers(state: JexAgentState, answers: Dict[int, str]) -> Dict[str, Any]:
    """
    Phase 1: 处理用户答案
    
    功能：
    1. 理解用户的自然语言回答
    2. 提取结构化信息
    3. 整合到collected_info中
    4. 处理跳过问询的情况（空的answers）
    """
    
    # 检查是否跳过问询（空的answers）
    if not answers:
        print(f"[DEBUG] 检测到跳过问询，answers为空")
        # 跳过问询，直接返回状态，不调用AI处理
        audit_entry = {
            "step": len(state.get("audit_trail", [])),
            "phase": "问询",
            "actor": "用户",
            "action": "跳过问询",
            "input": "用户选择跳过问询",
            "output": "使用现有信息继续处理",
            "reasoning": "用户选择跳过问询，使用现有信息继续AI协作",
            "tokens_used": 0,
            "cost": 0.0
        }
        
        return {
            # === 状态机必需字段 ===
            'task_id': state.get('task_id') or '',
            'user_id': state.get('user_id') or '',
            'scene': state.get('scene') or '',
            'user_input': state.get('user_input') or '',
            'need_inquiry': False,  # 不再需要问询
            'provided_info': state.get('provided_info') or {},
            'missing_info': state.get('missing_info') or [],  # 保留缺失信息，因为用户跳过了
            'info_sufficiency': state.get('info_sufficiency') or 0.3,  # 保持原来的信息充足度
            'collected_info': state.get('collected_info') or {},  # 没有收集新信息
            'task_type': state.get('task_type') or 'topic-analysis',
            'collaboration_mode': 'inquiry_skipped',
            'ai_a_role': state.get('ai_a_role') or '',
            'ai_b_role': state.get('ai_b_role') or '',
            'ai_a_output': state.get('ai_a_output') or '',
            'ai_b_output': state.get('ai_b_output') or '',
            'debate_rounds': state.get('debate_rounds') or 0,
            'current_round': state.get('current_round') or 0,
            'max_rounds': state.get('max_rounds') or 3,
            'should_stop': state.get('should_stop') or False,
            'stop_reason': state.get('stop_reason') or '',
            'final_output': state.get('final_output') or '',
            'audit_trail': (state.get("audit_trail") or []) + [audit_entry],
            'total_cost': state.get("total_cost") or 0.0,
            'error': state.get('error') or '',

            # === 业务数据 ===
            'collected_info': state.get("collected_info") or {}
        }
    
    ai_manager = get_ai_manager()
    
    # 构建答案理解Prompt
    understanding_prompt = f"""你是一个元认知AI，负责理解用户的回答并提取结构化信息。

**任务场景：** {state['scene']}

**问题和回答：**
{json.dumps({f"问题{k}": v for k, v in answers.items()}, ensure_ascii=False, indent=2)}

**你的任务：**
理解这些回答，提取关键信息，转换成结构化数据。

**请以JSON格式返回：**
{{
  "extracted_info": {{
    "关键1": "提取的信息",
    "关键2": "提取的信息"
  }},
  "summary": "简短总结用户提供的信息"
}}

只返回JSON，不要其他内容。
"""
    
    messages = [{"role": "user", "content": understanding_prompt}]
    
    try:
        # 调用元认知AI
        result = await ai_manager.call_meta_ai(messages, temperature=0.3)
        
        # 解析JSON响应
        content = result["content"].strip()
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            understanding_data = json.loads(json_match.group())
        else:
            understanding_data = json.loads(content)
        
        extracted_info = understanding_data.get("extracted_info", {})
        
        # 记录审计轨迹
        audit_entry = {
            "step": len(state.get("audit_trail", [])),
            "phase": "问询",
            "actor": "元认知AI",
            "action": "理解用户回答",
            "input": f"收到{len(answers)}个回答",
            "output": json.dumps(extracted_info, ensure_ascii=False),
            "reasoning": understanding_data.get("summary", ""),
            "tokens_used": result["tokens"]["total"],
            "cost": result["cost"]
        }
        
        # 合并到collected_info
        collected_info = {**state.get("collected_info", {}), **extracted_info}
        
        return {
            # === 状态机必需字段 ===
            'task_id': state.get('task_id') or '',
            'user_id': state.get('user_id') or '',
            'scene': state.get('scene') or '',
            'user_input': state.get('user_input') or '',
            'need_inquiry': False,  # 答案处理完成，不再需要问询
            'provided_info': state.get('provided_info') or {},
            'missing_info': [],  # 清空缺失信息，因为已经收集了
            'info_sufficiency': 1.0,  # 信息充足度设为最高
            'collected_info': collected_info,
            'task_type': state.get('task_type') or 'topic-analysis',
            'collaboration_mode': 'inquiry_completed',
            'ai_a_role': state.get('ai_a_role') or '',
            'ai_b_role': state.get('ai_b_role') or '',
            'ai_a_output': state.get('ai_a_output') or '',
            'ai_b_output': state.get('ai_b_output') or '',
            'debate_rounds': state.get('debate_rounds') or 0,
            'current_round': state.get('current_round') or 0,
            'max_rounds': state.get('max_rounds') or 3,
            'should_stop': state.get('should_stop') or False,
            'stop_reason': state.get('stop_reason') or '',
            'final_output': state.get('final_output') or '',
            'audit_trail': (state.get("audit_trail") or []) + [audit_entry],
            'total_cost': (state.get("total_cost") or 0.0) + result["cost"],
            'error': state.get('error') or '',

            # === 业务数据 ===
            'collected_info': collected_info,
        }
        
    except Exception as e:
        return {
            # === 状态机必需字段 ===
            'task_id': state.get('task_id') or '',
            'user_id': state.get('user_id') or '',
            'scene': state.get('scene') or '',
            'user_input': state.get('user_input') or '',
            'need_inquiry': False,
            'provided_info': state.get('provided_info') or {},
            'missing_info': state.get('missing_info') or [],
            'info_sufficiency': state.get('info_sufficiency') or 0.3,
            'collected_info': state.get('collected_info') or {},
            'task_type': state.get('task_type') or 'topic-analysis',
            'collaboration_mode': 'inquiry_failed',
            'ai_a_role': state.get('ai_a_role') or '',
            'ai_b_role': state.get('ai_b_role') or '',
            'ai_a_output': state.get('ai_a_output') or '',
            'ai_b_output': state.get('ai_b_output') or '',
            'debate_rounds': state.get('debate_rounds') or 0,
            'current_round': state.get('current_round') or 0,
            'max_rounds': state.get('max_rounds') or 3,
            'should_stop': True,
            'stop_reason': f"Phase 1答案处理失败: {str(e)}",
            'final_output': state.get('final_output') or '',
            'audit_trail': state.get("audit_trail") or [],
            'total_cost': state.get("total_cost") or 0.0,
            'error': f"Phase 1答案处理失败: {str(e)}",

            # === 业务数据 ===
            'collected_info': state.get("collected_info") or {}
        }
