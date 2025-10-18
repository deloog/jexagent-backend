"""
AI客户端兼容层 - 提供版本切换和灰度发布能力

设计原则：
1. 保持原有接口契约不变
2. 通过环境变量控制版本切换
3. 支持秒级回滚
4. 提供观测指标
"""

import os
from typing import List, Dict, Any, Optional
import time
import asyncio
from functools import wraps

# 版本开关配置
AI_CLIENT_VERSION = os.getenv("AI_CLIENT_VERSION", "original").lower()
ENABLE_METRICS = os.getenv("AI_CLIENT_ENABLE_METRICS", "false").lower() == "true"

# 观测指标（简化实现）
class AIMetrics:
    """AI客户端观测指标"""
    
    def __init__(self):
        self.circuit_breaker_open_total = 0
        self.request_retry_total = 0
        self.request_success_total = 0
        self.request_failure_total = 0
    
    def increment_circuit_breaker(self):
        """断路器打开计数"""
        self.circuit_breaker_open_total += 1
        print(f"[METRICS] circuit_breaker_open_total: {self.circuit_breaker_open_total}")
    
    def increment_retry(self):
        """重试计数"""
        self.request_retry_total += 1
        print(f"[METRICS] request_retry_total: {self.request_retry_total}")
    
    def increment_success(self):
        """成功计数"""
        self.request_success_total += 1
        print(f"[METRICS] request_success_total: {self.request_success_total}")
    
    def increment_failure(self):
        """失败计数"""
        self.request_failure_total += 1
        print(f"[METRICS] request_failure_total: {self.request_failure_total}")
    
    def get_metrics(self) -> Dict[str, int]:
        """获取所有指标"""
        return {
            "circuit_breaker_open_total": self.circuit_breaker_open_total,
            "request_retry_total": self.request_retry_total,
            "request_success_total": self.request_success_total,
            "request_failure_total": self.request_failure_total
        }

# 全局指标实例
metrics = AIMetrics()

def retry_on_connection_error(max_retries: int = 3, delay: float = 1.0):
    """
    连接错误重试装饰器（指数退避）
    
    Args:
        max_retries: 最大重试次数
        delay: 初始延迟（秒）
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries + 1):
                try:
                    result = await func(*args, **kwargs)
                    if attempt > 0:
                        metrics.increment_retry()
                    metrics.increment_success()
                    return result
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries:
                        wait_time = delay * (2 ** attempt)  # 指数退避
                        print(f"[RETRY] 第{attempt + 1}次重试，等待{wait_time}秒: {str(e)}")
                        await asyncio.sleep(wait_time)
                        metrics.increment_retry()
                    else:
                        metrics.increment_failure()
                        print(f"[RETRY] 达到最大重试次数{max_retries}，最终失败: {str(e)}")
            
            raise last_exception
        return wrapper
    return decorator

# 根据版本开关动态导入
if AI_CLIENT_VERSION == "fixed":
    print(f"[AI-CLIENT] 使用修复版本 (AI_CLIENT_VERSION={AI_CLIENT_VERSION})")
    from .ai_client_fixed import (
        AIClient as AIClientImpl,
        DeepSeekClient as DeepSeekClientImpl,
        MoonshotClient as MoonshotClientImpl,
        QwenClient as QwenClientImpl
    )
    from .ai_manager_fixed import (
        AIManager as AIManagerImpl,
        get_ai_manager as get_ai_manager_impl
    )
else:
    print(f"[AI-CLIENT] 使用原始版本 (AI_CLIENT_VERSION={AI_CLIENT_VERSION})")
    from .ai_client import (
        AIClient as AIClientImpl,
        DeepSeekClient as DeepSeekClientImpl,
        MoonshotClient as MoonshotClientImpl,
        QwenClient as QwenClientImpl
    )
    from .ai_manager import (
        AIManager as AIManagerImpl,
        get_ai_manager as get_ai_manager_impl
    )

# 导出兼容接口（保持原有接口契约）
AIClient = AIClientImpl
DeepSeekClient = DeepSeekClientImpl
MoonshotClient = MoonshotClientImpl
QwenClient = QwenClientImpl
AIManager = AIManagerImpl

def get_ai_manager() -> AIManager:
    """获取AI管理器实例（兼容接口）"""
    return get_ai_manager_impl()

def get_metrics() -> Dict[str, int]:
    """获取观测指标（用于监控和测试）"""
    return metrics.get_metrics()

def reset_metrics():
    """重置观测指标（用于测试）"""
    global metrics
    metrics = AIMetrics()

# 版本信息
def get_version_info() -> Dict[str, str]:
    """获取版本信息"""
    return {
        "ai_client_version": AI_CLIENT_VERSION,
        "enable_metrics": str(ENABLE_METRICS)
    }
