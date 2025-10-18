from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
import socketio

from fastapi import Request          # 新增
import time                          # 新增


# 创建FastAPI应用
app = FastAPI(
    title=settings.APP_NAME,
    description="多AI协作决策助手API",
    version="1.0.0"
)

@app.middleware("http")
async def log_every_request(request: Request, call_next):
    start = time.time()
    print(f"[DEBUG] {request.method} {request.url}  headers={dict(request.headers)}")
    response = await call_next(request)
    print(f"[DEBUG] {request.method} {request.url}  status={response.status_code}  duration={time.time()-start:.3f}s")
    return response



# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 集成Socket.IO
from app.services.socket_manager import socket_manager
sio_asgi_app = socketio.ASGIApp(
    socket_manager.sio,
    other_asgi_app=app,
    socketio_path='/socket.io'
)

@app.get("/")
async def root():
    """健康检查"""
    return {
        "app": settings.APP_NAME,
        "status": "running",
        "environment": settings.ENVIRONMENT
    }

@app.get("/health")
async def health_check():
    """健康检查端点"""
    return {"status": "ok"}

# 导入路由
from app.api import test, auth, users, ai_test, workflow_test, tasks

# 注册路由
app.include_router(test.router, prefix="/api")
app.include_router(auth.router, prefix="/api")
app.include_router(users.router, prefix="/api")
app.include_router(ai_test.router, prefix="/api")
app.include_router(workflow_test.router, prefix="/api")
app.include_router(tasks.router, prefix="/api")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        sio_asgi_app,  # 使用包装后的应用
        host="0.0.0.0",
        port=8000,
        reload=True
    )