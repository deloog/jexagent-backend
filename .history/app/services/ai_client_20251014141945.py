from typing import List, Dict, Any, Optional
from openai import OpenAI
from app.core.config import settings
import time

class AIClient:
    """AI客户端基类"""
    
    def __init__(self, api_key: str, base_url: str, model: str, name: str):
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model
        self.name = name
        self.total_tokens = 0
        self.total_cost = 0.0
    
    async def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> Dict[str, Any]:
        """发送聊天请求"""
        try:
            start_time = time.time()
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            duration = time.time() - start_time
            
            # 提取响应
            content = response.choices[0].message.content
            usage = response.usage
            
            # 计算成本
            cost = self._calculate_cost(usage.prompt_tokens, usage.completion_tokens)
            
            # 更新统计
            self.total_tokens += usage.total_tokens
            self.total_cost += cost
            
            return {
                "content": content,
                "tokens": {
                    "prompt": usage.prompt_tokens,
                    "completion": usage.completion_tokens,
                    "total": usage.total_tokens
                },
                "cost": cost,
                "duration": duration,
                "model": self.model,
                "ai_name": self.name
            }
            
        except Exception as e:
            raise Exception(f"{self.name} 调用失败: {str(e)}")
    
    def _calculate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        """计算成本（需要子类实现具体定价）"""
        raise NotImplementedError("子类必须实现此方法")
    
    def reset_stats(self):
        """重置统计信息"""
        self.total_tokens = 0
        self.total_cost = 0.0


class DeepSeekClient(AIClient):
    """DeepSeek客户端（元认知AI）"""
    
    def __init__(self):
        super().__init__(
            api_key=settings.DEEPSEEK_API_KEY,
            base_url="https://api.deepseek.com/v1",
            model="deepseek-chat",
            name="DeepSeek"
        )
    
    def _calculate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        """
        DeepSeek定价（2025年1月参考）：
        - Input: ¥0.001 / 1K tokens
        - Output: ¥0.002 / 1K tokens
        """
        input_cost = (prompt_tokens / 1000) * 0.001
        output_cost = (completion_tokens / 1000) * 0.002
        return input_cost + output_cost


class MoonshotClient(AIClient):
    """Moonshot (Kimi) 客户端（深度分析AI）"""
    
    def __init__(self):
        super().__init__(
            api_key=settings.MOONSHOT_API_KEY,
            base_url="https://api.moonshot.cn/v1",
            model="moonshot-v1-8k",
            name="Kimi"
        )
    
    def _calculate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        """
        Moonshot定价（2025年1月参考）：
        - 8K: ¥0.012 / 1K tokens
        """
        total_cost = (prompt_tokens + completion_tokens) / 1000 * 0.012
        return total_cost


class QwenClient(AIClient):
    """Qwen客户端（流量视角AI）"""
    
    def __init__(self):
        super().__init__(
            api_key=settings.QWEN_API_KEY,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            model="qwen-plus",
            name="Qwen"
        )
    
    def _calculate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        """
        Qwen定价（2025年1月参考）：
        - Input: ¥0.0008 / 1K tokens
        - Output: ¥0.002 / 1K tokens
        """
        input_cost = (prompt_tokens / 1000) * 0.0008
        output_cost = (completion_tokens / 1000) * 0.002
        return input_cost + output_cost