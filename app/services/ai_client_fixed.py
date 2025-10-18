from typing import List, Dict, Any, Optional
from openai import OpenAI
from app.core.config import settings
import time
import asyncio
import httpx
from functools import wraps
import logging

logger = logging.getLogger(__name__)

def retry_on_connection_error(max_retries: int = 3, delay: float = 1.0):
    """连接错误重试装饰器"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except (httpx.RemoteProtocolError, httpx.ConnectError, httpx.ReadTimeout) as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        wait_time = delay * (2 ** attempt)  # 指数退避
                        logger.warning(
                            f"AI服务连接失败，{wait_time:.1f}秒后重试 (尝试 {attempt + 1}/{max_retries}): {str(e)}"
                        )
                        await asyncio.sleep(wait_time)
                    else:
                        logger.error(f"AI服务连接失败，已达到最大重试次数: {str(e)}")
                        raise
                except Exception as e:
                    # 其他异常不重试
                    raise e
            raise last_exception
        return wrapper
    return decorator

class AIClient:
    """AI客户端基类（带重试机制）"""
    
    def __init__(self, api_key: str, base_url: str, model: str, name: str):
        # 配置超时设置
        timeout_config = httpx.Timeout(
            connect=30.0,  # 连接超时
            read=120.0,    # 读取超时
            write=30.0,    # 写入超时
            pool=30.0      # 连接池超时
        )
        
        self.client = OpenAI(
            api_key=api_key, 
            base_url=base_url,
            timeout=timeout_config,
            max_retries=0  # 禁用OpenAI内置重试，使用自定义重试
        )
        self.model = model
        self.name = name
        self.total_tokens = 0
        self.total_cost = 0.0
        self.failure_count = 0  # 失败计数器（用于断路器）
    
    @retry_on_connection_error(max_retries=3, delay=1.0)
    async def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> Dict[str, Any]:
        """发送聊天请求（带重试机制）"""
        try:
            start_time = time.time()
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            duration = time.time() - start_time
            
            # 重置失败计数器（成功调用）
            self.failure_count = 0
            
            # 提取响应
            content = response.choices[0].message.content
            usage = response.usage
            
            # 计算成本
            cost = self._calculate_cost(usage.prompt_tokens, usage.completion_tokens)
            
            # 更新统计
            self.total_tokens += usage.total_tokens
            self.total_cost += cost
            
            logger.info(
                f"{self.name} 调用成功: {usage.total_tokens} tokens, 耗时: {duration:.2f}s"
            )
            
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
            # 增加失败计数器
            self.failure_count += 1
            logger.error(f"{self.name} 调用失败 (失败次数: {self.failure_count}): {str(e)}")
            raise Exception(f"{self.name} 调用失败: {str(e)}")
    
    def is_circuit_open(self) -> bool:
        """检查断路器是否打开（连续失败次数过多）"""
        return self.failure_count >= 5  # 连续失败5次后打开断路器
    
    def _calculate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        """计算成本（需要子类实现具体定价）"""
        raise NotImplementedError("子类必须实现此方法")
    
    def reset_stats(self):
        """重置统计信息"""
        self.total_tokens = 0
        self.total_cost = 0.0
        self.failure_count = 0


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
