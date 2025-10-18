# 配额系统临时禁用方案

## 问题描述
前端报403错误："今日配额已用完"，影响开发调试。

## 解决方案
已添加环境变量控制，可在开发环境临时禁用配额检查。

## 使用方法

### 方案1：设置环境变量（推荐）
在 `.env` 文件中添加：
```env
DISABLE_QUOTA_CHECK=true
```

### 方案2：直接修改代码（临时）
如果不想设置环境变量，可以直接修改 `app/api/tasks.py` 中的逻辑：

```python
# 临时强制禁用配额检查
DISABLE_QUOTA_CHECK = True  # 开发环境设为 True

# 在 create_task 函数中：
if DISABLE_QUOTA_CHECK:
    logger.info(f"开发环境：跳过配额检查 user_id={current_user.id}")
else:
    # 原有的配额检查逻辑...
```

## 代码修改详情

### 修改的文件
- `jexagent-backend/app/api/tasks.py`

### 修改内容
1. 在 `create_task` 路由中添加了环境变量检查
2. 当 `DISABLE_QUOTA_CHECK=true` 时，跳过：
   - 前置配额检查
   - 配额递增操作

### 生产环境恢复
部署到生产环境时：
1. 确保 `DISABLE_QUOTA_CHECK=false` 或未设置
2. 配额系统将正常工作

## 注意事项
- 此修改仅影响任务创建时的配额检查
- 其他功能（如用户认证、任务状态等）不受影响
- 生产环境务必启用配额检查，防止滥用
