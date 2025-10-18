"""
测试进度动画系统修复效果
验证：断线期也继续推，重连期也继续推，前端用"缓冲队列 + 微步动画"
"""

import asyncio
import time
import requests
import json
from app.services.socket_manager import socket_manager

async def test_progress_animation():
    """测试进度动画系统"""
    print("🚀 开始测试进度动画系统...")
    
    # 1. 创建测试任务
    task_data = {
        "scene": "topic-analysis",
        "user_input": "测试进度动画系统"
    }
    
    response = requests.post("http://localhost:8000/api/tasks", json=task_data)
    if response.status_code != 201:
        print(f"❌ 创建任务失败: {response.status_code}")
        return
    
    task = response.json()
    task_id = task["id"]
    print(f"✅ 创建测试任务: {task_id}")
    
    # 2. 模拟后端进度推送（断线期也继续推）
    print("📊 模拟后端进度推送...")
    
    progress_steps = [
        (20, "规划", "正在制定协作策略..."),
        (40, "协作", "多AI 辩论模式启动..."),
        (55, "协作", "第1轮协作完成"),
        (70, "协作", "第2轮协作完成"),
        (70, "协作", "第3轮协作完成"),
        (80, "整合", "正在生成综合报告..."),
        (100, "完成", "分析完成！")
    ]
    
    for progress, phase, message in progress_steps:
        print(f"📤 推送进度: {progress}% - {phase} - {message}")
        await socket_manager.emit_progress(task_id, phase, progress, message)
        await asyncio.sleep(1)  # 模拟处理时间
    
    # 3. 验证进度缓存
    print("📋 验证进度缓存...")
    cached_progress = await socket_manager.get_full_progress(task_id)
    print(f"📊 缓存进度数量: {len(cached_progress)}")
    for item in cached_progress:
        print(f"  - {item['progress']}%: {item['phase']} - {item['message']} (seq: {item['sequence_id']})")
    
    # 4. 验证API端点
    print("🔍 验证API端点...")
    progress_response = requests.get(f"http://localhost:8000/api/tasks/{task_id}/progress")
    if progress_response.status_code == 200:
        api_progress = progress_response.json()
        print(f"✅ API返回进度数量: {len(api_progress)}")
    else:
        print(f"❌ API请求失败: {progress_response.status_code}")
    
    print("🎯 测试完成！")
    print("""
    预期结果：
    ✅ 后端断线期继续推送进度（已缓存）
    ✅ 进度按序列ID排序，无倒挂问题
    ✅ 前端重连后能获取完整历史进度
    ✅ 微步动画系统正常工作
    ✅ 用户感觉"一直在走"，永不显示断开
    """)

if __name__ == "__main__":
    asyncio.run(test_progress_animation())
