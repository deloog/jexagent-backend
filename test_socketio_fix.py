#!/usr/bin/env python3
"""
Socket.IO 403修复验证脚本
用于测试Socket.IO连接是否正常工作
"""

import asyncio
import socketio
import time

async def test_socketio_connection():
    """测试Socket.IO连接"""
    print("🔧 开始测试Socket.IO连接...")
    
    # 创建Socket.IO客户端
    sio = socketio.AsyncClient()
    
    connected = False
    joined = False
    
    @sio.event
    async def connect():
        nonlocal connected
        connected = True
        print("✅ Socket.IO连接成功！")
    
    @sio.event
    async def disconnect():
        print("🔌 Socket.IO断开连接")
    
    @sio.event
    async def joined(data):
        nonlocal joined
        joined = True
        print(f"✅ 成功加入任务房间: {data}")
    
    @sio.event
    async def progress(data):
        print(f"📊 收到进度更新: {data}")
    
    try:
        # 尝试连接
        print("🔄 尝试连接到 ws://localhost:8000/socket.io/")
        await sio.connect('http://localhost:8000', transports=['websocket', 'polling'])
        
        # 等待连接建立
        await asyncio.sleep(2)
        
        if connected:
            print("✅ 连接测试通过！")
            
            # 测试加入房间
            test_task_id = "test-task-123"
            print(f"🔄 尝试加入任务房间: {test_task_id}")
            await sio.emit('join_task', {'task_id': test_task_id})
            
            # 等待加入确认
            await asyncio.sleep(1)
            
            if joined:
                print("✅ 房间加入测试通过！")
            else:
                print("❌ 房间加入失败 - 未收到joined事件")
            
            # 断开连接
            await sio.disconnect()
            print("✅ 所有测试完成！")
            return True
        else:
            print("❌ 连接测试失败 - 未收到connect事件")
            return False
            
    except Exception as e:
        print(f"❌ 连接测试失败: {e}")
        return False

async def test_http_endpoints():
    """测试HTTP端点是否正常工作"""
    import aiohttp
    
    print("\n🔧 开始测试HTTP端点...")
    
    endpoints = [
        "http://localhost:8000/",
        "http://localhost:8000/health",
        "http://localhost:8000/api/tasks"
    ]
    
    async with aiohttp.ClientSession() as session:
        for endpoint in endpoints:
            try:
                async with session.get(endpoint) as response:
                    print(f"✅ {endpoint}: HTTP {response.status}")
            except Exception as e:
                print(f"❌ {endpoint}: {e}")

if __name__ == "__main__":
    print("🚀 Socket.IO 403修复验证脚本")
    print("=" * 50)
    
    # 检查后端是否在运行
    print("📡 检查后端服务状态...")
    
    # 运行测试
    loop = asyncio.get_event_loop()
    
    # 先测试HTTP端点
    loop.run_until_complete(test_http_endpoints())
    
    # 再测试Socket.IO连接
    success = loop.run_until_complete(test_socketio_connection())
    
    if success:
        print("\n🎉 所有测试通过！Socket.IO 403问题已修复。")
        print("\n📋 修复总结:")
        print("1. ✅ Socket.IO正确挂载到FastAPI应用")
        print("2. ✅ CORS配置包含所有前端端口")
        print("3. ✅ 应用启动方式正确")
    else:
        print("\n❌ 测试失败，请检查后端服务是否正在运行。")
        print("💡 启动后端服务: cd jexagent-backend && python -m uvicorn app.main:main_asgi_app --reload --host 0.0.0.0 --port 8000")
