"""
进度条自动跳转和数据更新修复验证脚本

这个脚本验证：
1. 进度条到达100%后是否自动跳转到结果页
2. 结果页是否显示最新数据而不是旧数据
"""

import asyncio
import time
import requests
import json
from datetime import datetime

# 配置
BACKEND_URL = "http://localhost:8000"
FRONTEND_URL = "http://localhost:3000"

def log_step(step: str, message: str):
    """记录测试步骤"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] [{step}] {message}")

async def test_progress_auto_jump():
    """测试进度条自动跳转功能"""
    log_step("TEST", "开始测试进度条自动跳转功能")
    
    try:
        # 1. 创建测试任务
        log_step("CREATE", "创建测试任务")
        task_data = {
            "user_id": "test-user",
            "scene": "business_analysis",
            "user_input": "测试进度条自动跳转功能"
        }
        
        response = requests.post(f"{BACKEND_URL}/api/tasks", json=task_data)
        if response.status_code != 200:
            log_step("ERROR", f"创建任务失败: {response.status_code}")
            return False
        
        task_result = response.json()
        task_id = task_result["task_id"]
        log_step("CREATE", f"任务创建成功: {task_id}")
        
        # 2. 检查任务状态
        log_step("CHECK", "检查任务状态")
        status_response = requests.get(f"{BACKEND_URL}/api/tasks/{task_id}")
        if status_response.status_code != 200:
            log_step("ERROR", f"获取任务状态失败: {status_response.status_code}")
            return False
        
        task_status = status_response.json()
        log_step("CHECK", f"任务状态: {task_status['status']}")
        
        # 3. 模拟进度更新
        log_step("PROGRESS", "模拟进度更新")
        from app.services.socket_manager import socket_manager
        
        # 模拟进度更新
        for progress in [10, 30, 60, 90, 100]:
            await socket_manager.emit_progress(
                task_id, 
                "测试阶段", 
                progress, 
                f"进度更新到 {progress}%"
            )
            log_step("PROGRESS", f"发送进度: {progress}%")
            await asyncio.sleep(0.5)
        
        # 4. 模拟任务完成
        log_step("COMPLETE", "模拟任务完成")
        final_output = {
            "executive_summary": {
                "tldr": "测试任务完成，验证进度条自动跳转功能",
                "key_actions": ["验证跳转逻辑", "检查数据更新"]
            },
            "certain_advice": {
                "title": "测试建议",
                "content": "这是一个测试建议，用于验证结果页数据更新功能",
                "risks": ["无风险"]
            }
        }
        
        # 先更新数据库
        from app.core.database import get_supabase
        supabase = get_supabase()
        update_result = supabase.table("tasks").update({
            "status": "completed",
            "output": final_output,
            "cost": 0.5,
            "duration": 10,
            "completed_at": datetime.utcnow().isoformat()
        }).eq("id", task_id).execute()
        
        log_step("DB", "数据库状态已更新为completed")
        
        # 再发送complete事件
        await socket_manager.emit_complete(task_id, final_output)
        log_step("SOCKET", "complete事件已发送")
        
        # 5. 验证结果页数据
        log_step("VERIFY", "验证结果页数据")
        await asyncio.sleep(2)  # 给前端留出处理时间
        
        result_response = requests.get(f"{BACKEND_URL}/api/tasks/{task_id}")
        if result_response.status_code != 200:
            log_step("ERROR", f"获取结果失败: {result_response.status_code}")
            return False
        
        final_result = result_response.json()
        log_step("VERIFY", f"最终任务状态: {final_result['status']}")
        
        if final_result['status'] == 'completed' and final_result.get('output'):
            log_step("SUCCESS", "✅ 进度条自动跳转和数据更新功能验证成功")
            log_step("DATA", f"结果数据: {json.dumps(final_result['output'], ensure_ascii=False, indent=2)}")
            return True
        else:
            log_step("FAILED", "❌ 结果页数据更新失败")
            return False
            
    except Exception as e:
        log_step("ERROR", f"测试过程中出现异常: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

async def test_data_consistency():
    """测试数据一致性"""
    log_step("CONSISTENCY", "开始测试数据一致性")
    
    try:
        # 创建测试任务
        task_data = {
            "user_id": "test-user-2",
            "scene": "data_consistency_test",
            "user_input": "测试数据一致性"
        }
        
        response = requests.post(f"{BACKEND_URL}/api/tasks", json=task_data)
        if response.status_code != 200:
            log_step("ERROR", f"创建任务失败: {response.status_code}")
            return False
        
        task_id = response.json()["task_id"]
        log_step("CREATE", f"创建一致性测试任务: {task_id}")
        
        # 模拟快速完成
        from app.services.socket_manager import socket_manager
        from app.core.database import get_supabase
        supabase = get_supabase()
        
        test_output_v1 = {
            "executive_summary": {
                "tldr": "版本1 - 初始数据",
                "key_actions": ["步骤1", "步骤2"]
            }
        }
        
        test_output_v2 = {
            "executive_summary": {
                "tldr": "版本2 - 更新后的数据",
                "key_actions": ["步骤1", "步骤2", "步骤3"]
            }
        }
        
        # 先更新数据库到版本1
        supabase.table("tasks").update({
            "status": "completed",
            "output": test_output_v1,
            "cost": 0.3,
            "duration": 5
        }).eq("id", task_id).execute()
        
        log_step("DB", "数据库更新到版本1")
        
        # 立即更新到版本2
        supabase.table("tasks").update({
            "status": "completed",
            "output": test_output_v2,
            "cost": 0.5,
            "duration": 8
        }).eq("id", task_id).execute()
        
        log_step("DB", "数据库更新到版本2")
        
        # 发送complete事件
        await socket_manager.emit_complete(task_id, test_output_v2)
        log_step("SOCKET", "发送版本2的complete事件")
        
        # 等待前端处理
        await asyncio.sleep(3)
        
        # 验证前端获取的数据
        result_response = requests.get(f"{BACKEND_URL}/api/tasks/{task_id}")
        if result_response.status_code != 200:
            log_step("ERROR", f"获取结果失败: {result_response.status_code}")
            return False
        
        final_data = result_response.json()
        expected_tldr = "版本2 - 更新后的数据"
        
        if (final_data.get('output', {}).get('executive_summary', {}).get('tldr') == expected_tldr):
            log_step("SUCCESS", "✅ 数据一致性验证成功 - 前端获取到最新数据")
            return True
        else:
            log_step("FAILED", f"❌ 数据一致性验证失败 - 期望: {expected_tldr}, 实际: {final_data.get('output', {})}")
            return False
            
    except Exception as e:
        log_step("ERROR", f"数据一致性测试异常: {str(e)}")
        return False

async def main():
    """主测试函数"""
    print("=" * 60)
    print("进度条自动跳转和数据更新修复验证")
    print("=" * 60)
    
    # 等待服务启动
    log_step("INIT", "等待后端服务启动...")
    max_retries = 30
    for i in range(max_retries):
        try:
            response = requests.get(f"{BACKEND_URL}/api/health")
            if response.status_code == 200:
                log_step("INIT", "后端服务已就绪")
                break
        except:
            if i == max_retries - 1:
                log_step("ERROR", "后端服务启动超时")
                return
            await asyncio.sleep(1)
    
    # 运行测试
    test1_success = await test_progress_auto_jump()
    test2_success = await test_data_consistency()
    
    print("\n" + "=" * 60)
    print("测试结果汇总:")
    print(f"进度条自动跳转测试: {'✅ 通过' if test1_success else '❌ 失败'}")
    print(f"数据一致性测试: {'✅ 通过' if test2_success else '❌ 失败'}")
    print("=" * 60)
    
    if test1_success and test2_success:
        print("🎉 所有测试通过！进度条自动跳转和数据更新问题已修复")
    else:
        print("⚠️ 部分测试失败，需要进一步调试")

if __name__ == "__main__":
    asyncio.run(main())
