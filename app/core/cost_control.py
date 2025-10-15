from typing import Callable
from fastapi import HTTPException, status

class CostController:
    """成本控制器"""
    
    def __init__(self, max_cost_per_task: float = 1.0):
        self.max_cost_per_task = max_cost_per_task
    
    def check_budget(self, current_cost: float):
        """检查预算是否超限"""
        if current_cost >= self.max_cost_per_task:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=f"任务成本已超过限额 ¥{self.max_cost_per_task}，已终止"
            )
    
    def estimate_cost(self, input_text: str, ai_type: str = "meta") -> float:
        """估算成本（粗略估计）"""
        # 粗略估算：1个中文字符约等于2个token
        estimated_tokens = len(input_text) * 2 * 2  # 输入+输出
        
        if ai_type == "meta":
            return (estimated_tokens / 1000) * 0.0015
        elif ai_type == "ai_a":
            return (estimated_tokens / 1000) * 0.012
        elif ai_type == "ai_b":
            return (estimated_tokens / 1000) * 0.0018
        
        return 0.0


# 创建全局成本控制器
cost_controller = CostController(max_cost_per_task=1.0)

def get_cost_controller() -> CostController:
    """获取成本控制器"""
    return cost_controller