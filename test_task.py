#!/usr/bin/env python3
"""
测试任务处理流程，验证80%卡死问题是否修复
"""
import asyncio
import json
import time
from app.services.task_service import TaskService
from app.services.socket_manager import socket_manager

async def test_task_processing():
    """测试任务处理"""
    task_service = TaskService()
    
    # 创建测试任务
    print(f"[TEST] 创建测试任务...")
    import uuid
    task_id = str(uuid.uuid4())
    
    # 模拟初始状态（跳过重评估，直接开始处理）
    initial_state = {
        "task_id": task_id,
        "user_id": "test-user",
        "scene": "商业分析",
        "user_input": "请分析新能源汽车市场趋势",
        "audit_trail": [],
        "total_cost": 0.0,
        "need_inquiry": False,
        "provided_info": {"market": "新能源汽车", "focus": "市场趋势"},
        "collected_info": {"market": "新能源汽车", "focus": "市场趋势"}
    }
    
    print(f"[TEST] 启动后台任务处理...")
    
    # 模拟WebSocket连接
    socket_manager.connections[task_id] = [{"test": "connection"}]
    
    # 启动异步任务
    start_time = time.time()
    task = asyncio.create_task(task_service._process_task_async(task_id, initial_state))
    
    print(f"[TEST] 任务已启动，等待完成...")
    
    # 等待任务完成
    try:
        await asyncio.wait_for(task, timeout=30)  # 30秒超时
        end_time = time.time()
        print(f"[TEST] ✅ 任务完成！耗时: {end_time - start_time:.2f}秒")
        
        # 检查是否有100%进度和complete事件
        if hasattr(socket_manager, '_test_progress_history'):
            history = socket_manager._test_progress_history.get(task_id, [])
            print(f"[TEST] 进度历史: {history}")
            
            # 检查是否包含100%进度
            has_100_percent = any(p.get('progress') == 100 for p in history)
            has_complete = any(p.get('type') == 'complete' for p in history)
            
            print(f"[TEST] 是否到达100%: {has_100_percent}")
            print(f"[TEST] 是否有complete事件: {has_complete}")
            
            if has_100_percent and has_complete:
                print("[TEST] 🎉 修复成功！任务正常完成到100%")
            else:
                print("[TEST] ❌ 修复可能有问题，未检测到100%或complete事件")
        
    except asyncio.TimeoutError:
        print("[TEST] ❌ 任务超时，可能在80%卡住")
    except Exception as e:
        print(f"[TEST] ❌ 任务异常: {e}")
    
    print(f"[TEST] 测试完成")

if __name__ == "__main__":
    # 添加测试用的进度历史记录
    if not hasattr(socket_manager, '_test_progress_history'):
        socket_manager._test_progress_history = {}
    
    asyncio.run(test_task_processing())
