# Socket.IO 403 问题修复总结

## 问题现象
- 前端每1~2秒尝试连接 `ws://localhost:8000/socket.io/` 都被403拒绝
- WebSocket握手阶段就被拒绝，导致前端从未真正连上房间
- 所有进度只能落盘缓存，无法实时推送

## 根因分析
1. **Socket.IO挂载不正确** - 使用`ASGIApp`包装但路由处理不当
2. **CORS配置不完整** - 后端只允许`localhost:3000`，前端可能运行在其他端口
3. **启动方式错误** - 日志显示使用`uvicorn app.main:app`，但应该使用包装后的应用

## 修复方案

### 1. 正确挂载Socket.IO到FastAPI
**文件：** `app/main.py`

```python
# 创建Socket.IO的ASGI子应用
sio_app = ASGIApp(socket_manager.sio, socketio_path="/socket.io")

# 用mount把/socket.io交给sio_app处理
app.mount("/socket.io", sio_app)

# 主ASGI应用 - 用于uvicorn启动
main_asgi_app = app
```

### 2. 扩展CORS白名单
**文件：** `app/core/config.py`

```python
# CORS配置
ALLOWED_ORIGINS: List[str] = [
    "http://localhost:3000",
    "http://localhost:5173", 
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173"
]
```

### 3. 修正启动命令
**正确启动方式：**
```bash
# 使用包装后的应用
python -m uvicorn app.main:main_asgi_app --reload --host 0.0.0.0 --port 8000
```

## 验证方法

### 1. 启动后端服务
```bash
cd jexagent-backend
python -m uvicorn app.main:main_asgi_app --reload --host 0.0.0.0 --port 8000
```

### 2. 运行测试脚本
```bash
python test_socketio_fix.py
```

### 3. 观察日志
**成功连接时应该看到：**
```
INFO:     Client connected: [sid]
INFO:     Client [sid] joined task [task_id]
```

**浏览器WebSocket状态：**
- 状态码从403变为101 Switching Protocols
- 连接状态变为Connected

## 预期效果
- ✅ WebSocket握手成功，不再出现403错误
- ✅ 前端能实时接收进度推送
- ✅ 缓存日志不再出现（因为实时推送成功）
- ✅ 任务完成后前端能立即收到完成事件

## 技术原理
1. **路由匹配**：`app.mount("/socket.io", sio_app)` 确保所有 `/socket.io/*` 请求被正确路由到Socket.IO处理器
2. **CORS预检**：扩展的CORS白名单确保前端不同端口的请求都能通过预检检查
3. **ASGI兼容**：正确的应用包装确保uvicorn能正确处理WebSocket升级请求

## 注意事项
- 开发阶段可以使用 `cors_allowed_origins='*'` 简化调试
- 生产环境需要收紧CORS配置
- 如果使用JWT鉴权，需要在connect事件中手动处理token验证
