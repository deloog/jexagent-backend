from typing import Dict, List, Any
from app.services.ai_client_fixed import DeepSeekClient, MoonshotClient, QwenClient
import logging

logger = logging.getLogger(__name__)

class AIManager:
    """AI客户端管理器（带故障转移）"""
    
    def __init__(self):
        self.meta_ai = DeepSeekClient()  # 元认知AI
        self.ai_a = MoonshotClient()     # AI-A：深度分析
        self.ai_b = QwenClient()         # AI-B：流量视角
    
    async def call_meta_ai(self, messages: List[Dict[str, str]], **kwargs) -> Dict[str, Any]:
        """调用元认知AI（带故障转移）"""
        try:
            if self.meta_ai.is_circuit_open():
                logger.warning("DeepSeek断路器已打开，尝试使用备用AI")
                return await self._fallback_to_ai_a(messages, **kwargs)
            return await self.meta_ai.chat(messages, **kwargs)
        except Exception as e:
            logger.error(f"DeepSeek调用失败，尝试使用备用AI: {str(e)}")
            return await self._fallback_to_ai_a(messages, **kwargs)
    
    async def call_ai_a(self, messages: List[Dict[str, str]], **kwargs) -> Dict[str, Any]:
        """调用AI-A（深度分析）"""
        try:
            if self.ai_a.is_circuit_open():
                logger.warning("Moonshot断路器已打开，尝试使用备用AI")
                return await self._fallback_to_ai_b(messages, **kwargs)
            return await self.ai_a.chat(messages, **kwargs)
        except Exception as e:
            logger.error(f"Moonshot调用失败，尝试使用备用AI: {str(e)}")
            return await self._fallback_to_ai_b(messages, **kwargs)
    
    async def call_ai_b(self, messages: List[Dict[str, str]], **kwargs) -> Dict[str, Any]:
        """调用AI-B（流量视角）"""
        try:
            if self.ai_b.is_circuit_open():
                logger.warning("Qwen断路器已打开，尝试使用备用AI")
                return await self._fallback_to_meta_ai(messages, **kwargs)
            return await self.ai_b.chat(messages, **kwargs)
        except Exception as e:
            logger.error(f"Qwen调用失败，尝试使用备用AI: {str(e)}")
            return await self._fallback_to_meta_ai(messages, **kwargs)
    
    async def _fallback_to_ai_a(self, messages: List[Dict[str, str]], **kwargs) -> Dict[str, Any]:
        """故障转移到AI-A"""
        try:
            logger.info("故障转移到Moonshot (AI-A)")
            return await self.ai_a.chat(messages, **kwargs)
        except Exception as e:
            logger.error(f"所有AI服务均不可用: {str(e)}")
            raise Exception("所有AI服务暂时不可用，请稍后重试")
    
    async def _fallback_to_ai_b(self, messages: List[Dict[str, str]], **kwargs) -> Dict[str, Any]:
        """故障转移到AI-B"""
        try:
            logger.info("故障转移到Qwen (AI-B)")
            return await self.ai_b.chat(messages, **kwargs)
        except Exception as e:
            logger.error(f"所有AI服务均不可用: {str(e)}")
            raise Exception("所有AI服务暂时不可用，请稍后重试")
    
    async def _fallback_to_meta_ai(self, messages: List[Dict[str, str]], **kwargs) -> Dict[str, Any]:
        """故障转移到元认知AI"""
        try:
            logger.info("故障转移到DeepSeek (元认知AI)")
            return await self.meta_ai.chat(messages, **kwargs)
        except Exception as e:
            logger.error(f"所有AI服务均不可用: {str(e)}")
            raise Exception("所有AI服务暂时不可用，请稍后重试")
    
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
                "cost": self.meta_ai.total_cost,
                "failure_count": self.meta_ai.failure_count,
                "circuit_open": self.meta_ai.is_circuit_open()
            },
            "ai_a": {
                "name": self.ai_a.name,
                "tokens": self.ai_a.total_tokens,
                "cost": self.ai_a.total_cost,
                "failure_count": self.ai_a.failure_count,
                "circuit_open": self.ai_a.is_circuit_open()
            },
            "ai_b": {
                "name": self.ai_b.name,
                "tokens": self.ai_b.total_tokens,
                "cost": self.ai_b.total_cost,
                "failure_count": self.ai_b.failure_count,
                "circuit_open": self.ai_b.is_circuit_open()
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
