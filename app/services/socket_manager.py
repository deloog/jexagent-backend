from typing import Dict, Set, List, Optional
import socketio
import asyncio
import time
import os
from collections import defaultdict, deque
from contextlib import suppress

# ✅ Redis配置（生产环境启用）
USE_REDIS = os.getenv("USE_REDIS_CACHE", "false").lower() == "true"

if USE_REDIS:
    import redis.asyncio as redis
    import json
    redis_client = redis.Redis(
        host=os.getenv("REDIS_HOST", "localhost"),
        port=int(os.getenv("REDIS_PORT", 6379)),
        decode_responses=True
    )
else:
    # ✅ 开发环境：进程内缓存（单进程部署）
    _progress_cache: Dict[str, deque] = {}
    _completion_cache: Dict[str, dict] = {}  # ← 新增：缓存complete事件

# ✅ 全局配置
MAX_TASKS_IN_MEMORY = 10000  # 最大缓存任务数
CACHE_CLEANUP_DELAY = 300    # 完成后5分钟清理缓存

class SocketManager:
    """WebSocket管理器 - 生产级实现"""
    
    def __init__(self):
        # ✅ CORS配置 - 生产环境收紧
        allowed_origins = os.getenv("CORS_ORIGINS", "*")
        if allowed_origins == "*":
            print("⚠️ 警告：CORS设置为 '*'，生产环境请收紧！")
        
        self.sio = socketio.AsyncServer(
            async_mode='asgi',
            cors_allowed_origins=allowed_origins.split(",") if allowed_origins != "*" else "*",
            ping_timeout=60,
            ping_interval=25
        )
        
        # ✅ 连接管理
        self.connections: Dict[str, Set[str]] = {}  # task_id -> set of sid
        self.sid_to_tasks: Dict[str, Set[str]] = {}  # ✅ 反向索引：sid -> set of task_id
        
        # ✅ 序列号管理（使用Redis或内存）
        if USE_REDIS:
            # Redis INCR 保证原子性和持久化
            self.sequence_counters = None
        else:
            self.sequence_counters: Dict[str, int] = {}
            self._seq_locks: Dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        
        # ✅ 连接事件（用于wait_for_connection）
        self._connection_events: Dict[str, asyncio.Event] = {}
        
        self._register_events()
    
    def _register_events(self):
        """注册所有Socket.IO事件"""
        
        @self.sio.event
        async def connect(sid, environ):
            print(f"[WS] Client connected: {sid}")
        
        @self.sio.event
        async def disconnect(sid):
            print(f"[WS] Client disconnected: {sid}")
            
            # ✅ O(1)清理：使用反向索引
            task_ids = self.sid_to_tasks.get(sid, set())
            for task_id in task_ids:
                if task_id in self.connections:
                    self.connections[task_id].discard(sid)
                    if not self.connections[task_id]:
                        del self.connections[task_id]
            
            # 清理反向索引
            if sid in self.sid_to_tasks:
                del self.sid_to_tasks[sid]
        
        @self.sio.event
        async def join_task(sid, data):
            """客户端加入任务房间"""
            task_id = data.get('task_id')
            if not task_id:
                return
            
            # 添加到连接映射
            if task_id not in self.connections:
                self.connections[task_id] = set()
            self.connections[task_id].add(sid)
            
            # ✅ 维护反向索引
            if sid not in self.sid_to_tasks:
                self.sid_to_tasks[sid] = set()
            self.sid_to_tasks[sid].add(task_id)
            
            print(f"[WS] Client {sid} joined task {task_id}")
            print(f"[WS] Active connections for {task_id}: {len(self.connections[task_id])}")
            
            # ✅ 触发连接事件
            if task_id not in self._connection_events:
                self._connection_events[task_id] = asyncio.Event()
            self._connection_events[task_id].set()
            
            # ✅ 发送complete事件（如果任务已完成且客户端刚连接）
            if not USE_REDIS and task_id in _completion_cache:
                print(f"[WS] 重发complete事件给新连接: {sid}")
                await self.sio.emit('complete', _completion_cache[task_id], room=sid)
            
            await self.sio.emit('joined', {'task_id': task_id}, room=sid)
        
        @self.sio.event
        async def ping(sid):
            """心跳检测"""
            await self.sio.emit('pong', room=sid)
    
    async def _get_next_sequence_id(self, task_id: str) -> int:
        """获取下一个序列号（Redis或内存）"""
        if USE_REDIS:
            # ✅ Redis INCR：原子操作 + 持久化
            return await redis_client.incr(f"seq:{task_id}")
        else:
            # ✅ 内存锁保护
            async with self._seq_locks[task_id]:
                if task_id not in self.sequence_counters:
                    self.sequence_counters[task_id] = 0
                sequence_id = self.sequence_counters[task_id]
                self.sequence_counters[task_id] += 1
                return sequence_id
    
    async def emit_progress(self, task_id: str, phase: str, progress: int, message: str):
        """推送进度更新 - 先缓存再推送"""
        
        # ✅ 获取序列号
        sequence_id = await self._get_next_sequence_id(task_id)
        
        # 构建进度项
        item = {
            "phase": phase,
            "progress": progress,
            "message": message,
            "ts": time.time(),
            "sequence_id": sequence_id,
            "task_id": task_id
        }
        
        # ✅ 缓存进度
        if USE_REDIS:
            # Redis List: LPUSH + LTRIM
            await redis_client.lpush(f"progress:{task_id}", json.dumps(item))
            await redis_client.ltrim(f"progress:{task_id}", 0, 999)
        else:
            # ✅ 内存缓存 + LRU淘汰
            if task_id not in _progress_cache:
                # 检查全局任务数上限
                if len(_progress_cache) >= MAX_TASKS_IN_MEMORY:
                    print(f"⚠️ 达到缓存上限，清理最早的任务")
                    # 删除最早的20%
                    to_remove = list(_progress_cache.keys())[:MAX_TASKS_IN_MEMORY // 5]
                    for k in to_remove:
                        del _progress_cache[k]
                
                _progress_cache[task_id] = deque(maxlen=1000)
            
            _progress_cache[task_id].append(item)
        
        print(f"[PROGRESS] task={task_id}, seq={sequence_id}, phase={phase}, progress={progress}%")
        
        # ✅ 推送实时进度（捕获任何异常，不回滚事务，仅记日志）
        if task_id in self.connections and self.connections[task_id]:
            failed_sids = []
            for sid in self.connections[task_id]:
                try:
                    await self.sio.emit('progress', item, room=sid)
                except Exception as e:
                    # ✅ 加固：仅记录日志，不影响任务流程
                    print(f"[WS] ⚠️ 推送进度失败（不影响任务）: {sid}, {e}")
                    failed_sids.append(sid)
            
            # 清理失败的连接
            for sid in failed_sids:
                self.connections[task_id].discard(sid)
                if sid in self.sid_to_tasks:
                    self.sid_to_tasks[sid].discard(task_id)
            
            if failed_sids and not self.connections[task_id]:
                del self.connections[task_id]
        else:
            print(f"[WS] ⚠️  No active connections for {task_id}, progress cached")

    async def get_full_progress(self, task_id: str) -> List[Dict]:
        """获取任务完整进度历史"""
        if USE_REDIS:
            # Redis LRANGE
            items = await redis_client.lrange(f"progress:{task_id}", 0, -1)
            return [json.loads(item) for item in reversed(items)]
        else:
            if task_id in _progress_cache:
                return list(_progress_cache[task_id])
            return []

    async def emit_ai_message(self, task_id: str, actor: str, content: str):
        """推送AI消息"""
        if task_id in self.connections and self.connections[task_id]:
            for sid in self.connections[task_id]:
                try:
                    await self.sio.emit('ai_message', {
                        'actor': actor,
                        'content': content
                    }, room=sid)
                except Exception as e:
                    print(f"[WS] ❌ Failed to emit ai_message to {sid}: {e}")
    
    async def emit_complete(self, task_id: str, output: Dict):
        """推送完成消息 + 缓存事件"""
        print(f"[WS] 📢 Emitting complete for task {task_id}")
        
        complete_data = {'output': output}
        
        # ✅ 缓存complete事件（5分钟TTL）
        if not USE_REDIS:
            _completion_cache[task_id] = complete_data
        
        # 推送给当前连接
        if task_id in self.connections and self.connections[task_id]:
            for sid in self.connections[task_id]:
                try:
                    await self.sio.emit('complete', complete_data, room=sid)
                    print(f"[WS] ✅ Emitted complete to {sid}")
                except Exception as e:
                    print(f"[WS] ❌ Failed to emit complete to {sid}: {e}")
        else:
            print(f"[WS] ⚠️  No active connections, complete event cached")
        
        # ✅ 延迟清理缓存（5分钟后）
        asyncio.create_task(self._delayed_cleanup(task_id))
    
    async def _delayed_cleanup(self, task_id: str):
        """延迟清理缓存"""
        await asyncio.sleep(CACHE_CLEANUP_DELAY)
        
        if USE_REDIS:
            await redis_client.delete(f"progress:{task_id}")
            await redis_client.delete(f"seq:{task_id}")
        else:
            _progress_cache.pop(task_id, None)
            _completion_cache.pop(task_id, None)
        
        print(f"[CLEANUP] 清理任务缓存: {task_id}")
    
    async def emit_error(self, task_id: str, error: str):
        """推送错误消息"""
        if task_id in self.connections and self.connections[task_id]:
            for sid in self.connections[task_id]:
                try:
                    await self.sio.emit('error', {'error': error}, room=sid)
                except Exception as e:
                    print(f"[WS] ❌ Failed to emit error to {sid}: {e}")
    
    def has_active_connections(self, task_id: str) -> bool:
        """检查任务是否有活跃连接"""
        return task_id in self.connections and len(self.connections[task_id]) > 0
    
    async def wait_for_connection(self, task_id: str, timeout: float = 30.0) -> bool:
        """
        等待WebSocket连接建立
        
        使用 asyncio.Event 避免轮询，更高效
        """
        print(f"[WS] ⏳ Waiting for connection to task {task_id} (timeout: {timeout}s)")
        
        # 如果已经有连接，立即返回
        if self.has_active_connections(task_id):
            print(f"[WS] ✅ Connection already active for task {task_id}")
            return True
        
        # 创建或获取事件
        if task_id not in self._connection_events:
            self._connection_events[task_id] = asyncio.Event()
        
        try:
            # 等待事件触发（带超时）
            await asyncio.wait_for(
                self._connection_events[task_id].wait(),
                timeout=timeout
            )
            print(f"[WS] ✅ Connection established for task {task_id}")
            return True
        except asyncio.TimeoutError:
            print(f"[WS] ⚠️  Connection timeout for task {task_id}")
            return False

# 创建全局实例
socket_manager = SocketManager()
