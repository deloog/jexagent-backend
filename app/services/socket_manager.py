from typing import Dict, Set
import socketio
import asyncio

class SocketManager:
    """WebSocket管理器"""
    
    def __init__(self):
        self.sio = socketio.AsyncServer(
            async_mode='asgi',
            cors_allowed_origins='*'
        )
        self.connections: Dict[str, Set[str]] = {}  # task_id -> set of sid
        
        # 注册事件
        @self.sio.event
        async def connect(sid, environ):
            print(f"Client connected: {sid}")
        
        @self.sio.event
        async def disconnect(sid):
            print(f"Client disconnected: {sid}")
            # 清理连接
            for task_id in list(self.connections.keys()):
                if sid in self.connections[task_id]:
                    self.connections[task_id].remove(sid)
                    if not self.connections[task_id]:
                        del self.connections[task_id]
        
        @self.sio.event
        async def join_task(sid, data):
            """客户端加入任务房间"""
            task_id = data.get('task_id')
            if task_id:
                if task_id not in self.connections:
                    self.connections[task_id] = set()
                self.connections[task_id].add(sid)
                print(f"Client {sid} joined task {task_id}")
                await self.sio.emit('joined', {'task_id': task_id}, room=sid)
    
    async def emit_progress(self, task_id: str, phase: str, progress: int, message: str):
        """推送进度更新"""
        if task_id in self.connections:
            for sid in self.connections[task_id]:
                await self.sio.emit('progress', {
                    'phase': phase,
                    'progress': progress,
                    'message': message
                }, room=sid)
    
    async def emit_ai_message(self, task_id: str, actor: str, content: str):
        """推送AI消息"""
        if task_id in self.connections:
            for sid in self.connections[task_id]:
                await self.sio.emit('ai_message', {
                    'actor': actor,
                    'content': content
                }, room=sid)
    
    async def emit_complete(self, task_id: str, output: Dict):
        """推送完成消息"""
        if task_id in self.connections:
            for sid in self.connections[task_id]:
                await self.sio.emit('complete', {
                    'output': output
                }, room=sid)
    
    async def emit_error(self, task_id: str, error: str):
        """推送错误消息"""
        if task_id in self.connections:
            for sid in self.connections[task_id]:
                await self.sio.emit('error', {
                    'error': error
                }, room=sid)


# 创建全局实例
socket_manager = SocketManager()