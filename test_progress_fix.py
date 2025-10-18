import asyncio
import time
from app.services.socket_manager import socket_manager

async def test_progress_with_disconnect():
    """测试进度推送和连接断开重连场景"""
    task_id = "test_task_123"
    
    print("🚀 开始测试进度推送和连接断开重连...")
    
    # 模拟进度推送
    print("📊 模拟进度推送...")
    for progress in [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]:
        await socket_manager.emit_progress(
            task_id=task_id,
            phase="testing",
            progress=progress,
            message=f"测试进度 {progress}%"
        )
        print(f"✅ 推送进度: {progress}%")
        await asyncio.sleep(0.5)  # 模拟处理间隔
    
    # 检查进度缓存
    print("📋 检查进度缓存...")
    progress_history = await socket_manager.get_full_progress(task_id)
    print(f"📊 缓存中的进度记录数: {len(progress_history)}")
    for item in progress_history:
        print(f"  - {item['progress']}%: {item['message']}")
    
    # 模拟连接表状态
    print("🔌 检查连接表状态...")
    print(f"连接表: {socket_manager.connections}")
    
    print("✅ 测试完成！")

if __name__ == "__main__":
    asyncio.run(test_progress_with_disconnect())
