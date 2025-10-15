from typing import Dict, List, Any
from app.services.ai_client import DeepSeekClient, MoonshotClient, QwenClient

class AIManager:
    """AI客户端管理器"""
    
    def __init__(self):
        self.meta_ai = DeepSeekClient()  # 元认知AI
        self.ai_a = MoonshotClient()     # AI-A：深度分析
        self.ai_b = QwenClient()         # AI-B：流量视角
    
    async def call_meta_ai(self, messages: List[Dict[str, str]], **kwargs) -> Dict[str, Any]:
        """调用元认知AI"""
        return await self.meta_ai.chat(messages, **kwargs)
    
    async def call_ai_a(self, messages: List[Dict[str, str]], **kwargs) -> Dict[str, Any]:
        """调用AI-A（深度分析）"""
        return await self.ai_a.chat(messages, **kwargs)
    
    async def call_ai_b(self, messages: List[Dict[str, str]], **kwargs) -> Dict[str, Any]:
        """调用AI-B（流量视角）"""
        return await self.ai_b.chat(messages, **kwargs)
    
    def get_total_cost(self) -> float:
        """获取总成本"""
        return (
            self.meta_ai.total_cost + 
            self.ai_a.total_cost + 
            self.ai_b.total_cost
        )
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "meta_ai": {
                "name": self.meta_ai.name,
                "tokens": self.meta_ai.total_tokens,
                "cost": self.meta_ai.total_cost
            },
            "ai_a": {
                "name": self.ai_a.name,
                "tokens": self.ai_a.total_tokens,
                "cost": self.ai_a.total_cost
            },
            "ai_b": {
                "name": self.ai_b.name,
                "tokens": self.ai_b.total_tokens,
                "cost": self.ai_b.total_cost
            },
            "total_cost": self.get_total_cost()
        }
    
    def reset_stats(self):
        """重置所有统计"""
        self.meta_ai.reset_stats()
        self.ai_a.reset_stats()
        self.ai_b.reset_stats()


# 创建全局AI管理器实例
ai_manager = AIManager()

def get_ai_manager() -> AIManager:
    """获取AI管理器实例"""
    return ai_manager