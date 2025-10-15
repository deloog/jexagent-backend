from typing import Dict, Any
from app.services.langgraph.state import JexAgentState
from app.services.ai_manager import get_ai_manager
import json
import re

async def phase2_planning(state: JexAgentState) -> Dict[str, Any]:
    """
    Phase 2: 任务规划节点
    
    功能：
    1. 分析完整信息（用户输入 + 收集的信息）
    2. 决定任务类型
    3. 选择协作模式（辩论 or 审查）
    4. 分配AI角色
    """
    
    ai_manager = get_ai_manager()
    
    # 整合完整信息
    complete_info = {
        "用户原始输入": state['user_input'],
        "场景": state['scene'],
        "已提供信息": state.get('provided_info', {}),
        "收集的信息": state.get('collected_info', {})
    }
    
    # 构建规划Prompt
    planning_prompt = f"""你是一个元认知AI，负责规划多AI协作策略。

**完整信息：**
{json.dumps(complete_info, ensure_ascii=False, indent=2)}

**你的任务：**
基于以上信息，制定最优的协作策略。

**协作模式说明：**
1. **辩论模式（debate）**：适用于有争议性、需要权衡的决策
   - AI-A和AI-B从不同视角分析
   - 如果观点差异大，启动辩论
   - 适合：选题分析、战略决策、风险评估等

2. **审查模式（review）**：适用于内容创作、方案优化
   - AI-A生成初稿
   - AI-B审查并提出改进建议
   - AI-A根据反馈优化
   - 适合：内容创作、文案优化、代码审查等

**请以JSON格式返回规划结果：**
{{
  "task_type": "具体任务类型（如：选题可行性分析、内容创作、风险评估等）",
  "collaboration_mode": "debate 或 review",
  "ai_a_role": "AI-A的角色定义和任务（例如：从内容深度和专业性角度分析）",
  "ai_b_role": "AI-B的角色定义和任务（例如：从传播和流量角度分析）",
  "max_rounds": 3,
  "reasoning": "选择该策略的理由"
}}

**注意：**
- AI-A角色通常负责深度、专业性、长期价值
- AI-B角色通常负责实用性、传播性、短期效果
- 根据场景特点分配最合适的角色

只返回JSON，不要其他内容。
"""
    
    messages = [{"role": "user", "content": planning_prompt}]
    
    try:
        # 调用元认知AI
        result = await ai_manager.call_meta_ai(messages, temperature=0.4)
        
        # 解析JSON响应
        content = result["content"].strip()
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            planning_data = json.loads(json_match.group())
        else:
            planning_data = json.loads(content)
        
        # 记录审计轨迹
        audit_entry = {
            "step": len(state.get("audit_trail", [])),
            "phase": "规划",
            "actor": "元认知AI",
            "action": "制定协作策略",
            "input": f"场景: {state['scene']}",
            "output": json.dumps(planning_data, ensure_ascii=False),
            "reasoning": planning_data.get("reasoning", ""),
            "tokens_used": result["tokens"]["total"],
            "cost": result["cost"]
        }
        
        return {
            "task_type": planning_data.get("task_type", "未分类任务"),
            "collaboration_mode": planning_data.get("collaboration_mode", "debate"),
            "ai_a_role": planning_data.get("ai_a_role", "深度分析"),
            "ai_b_role": planning_data.get("ai_b_role", "实用建议"),
            "max_rounds": planning_data.get("max_rounds", 3),
            "current_round": 0,
            "should_stop": False,
            "audit_trail": state.get("audit_trail", []) + [audit_entry],
            "total_cost": state.get("total_cost", 0.0) + result["cost"]
        }
        
    except Exception as e:
        # 出错时使用默认策略
        return {
            "error": f"Phase 2规划失败: {str(e)}，使用默认策略",
            "task_type": "通用分析",
            "collaboration_mode": "debate",
            "ai_a_role": "从深度和专业性角度分析",
            "ai_b_role": "从实用性和可操作性角度分析",
            "max_rounds": 3,
            "current_round": 0,
            "should_stop": False
        }