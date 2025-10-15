from fastapi import APIRouter, HTTPException
from app.core.database import get_supabase

router = APIRouter(prefix="/test", tags=["测试"])

@router.get("/db-connection")
async def test_db_connection():
    """测试数据库连接"""
    try:
        supabase = get_supabase()
        
        # 查询templates表
        response = supabase.table("templates").select("*").limit(1).execute()
        
        return {
            "status": "success",
            "message": "数据库连接正常",
            "data": response.data
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"数据库连接失败: {str(e)}")

@router.get("/tables")
async def list_tables():
    """列出所有场景模板"""
    try:
        supabase = get_supabase()
        response = supabase.table("templates").select("name, scene, description").execute()
        
        return {
            "status": "success",
            "count": len(response.data),
            "templates": response.data
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))