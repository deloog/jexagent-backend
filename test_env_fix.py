#!/usr/bin/env python3
"""
环境变量修复测试脚本
"""

print("=" * 50)
print("🔍 环境变量修复测试")
print("=" * 50)

# 步骤1：加载环境变量
from dotenv import load_dotenv
result = load_dotenv()
print(f"1. load_dotenv() 返回: {result}")
print(f"   (True=找到.env文件, False=未找到)")

# 步骤2：检查环境变量
import os
print(f"\n2. SUPABASE_URL: {os.getenv('SUPABASE_URL')}")
print(f"   SUPABASE_KEY: {os.getenv('SUPABASE_KEY')[:20] if os.getenv('SUPABASE_KEY') else None}...")

# 步骤3：测试数据库导入
try:
    from app.core.database import get_supabase
    print("\n3. ✅ database.py 导入成功")
    
    client = get_supabase()
    print("4. ✅ Supabase 客户端创建成功")
except Exception as e:
    print(f"\n3. ❌ 导入失败: {e}")

# 步骤4：测试 TaskService
try:
    from app.services.task_service import task_service
    print("5. ✅ TaskService 初始化成功")
except Exception as e:
    print(f"5. ❌ TaskService 初始化失败: {e}")

# 步骤5：测试 API 路由导入
try:
    from app.api.tasks import router
    print("6. ✅ tasks.py 路由导入成功")
except Exception as e:
    print(f"6. ❌ tasks.py 路由导入失败: {e}")

# 步骤6：测试完整应用导入
try:
    from app.main import app
    print("7. ✅ FastAPI 应用导入成功")
    print("8. ✅ 环境变量问题已修复！")
except Exception as e:
    print(f"7. ❌ FastAPI 应用导入失败: {e}")

print("=" * 50)
