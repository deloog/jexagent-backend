# Supabase 迁移执行指南

## 需要执行的 SQL 迁移

您需要在 Supabase 中执行 `migrations/create_quota_functions.sql` 文件中的 SQL 语句。

## 执行步骤

### 方法1：通过 Supabase Dashboard
1. 登录到您的 Supabase 项目
2. 进入 **SQL Editor** 页面
3. 复制 `migrations/create_quota_functions.sql` 文件中的全部内容
4. 粘贴到 SQL 编辑器中
5. 点击 **Run** 执行

### 方法2：通过 Supabase CLI（如果已安装）
```bash
# 连接到您的 Supabase 项目
supabase db push
```

### 方法3：通过 psql 命令行
```bash
# 连接到您的 Supabase 数据库
psql "postgresql://postgres:[your-password]@db.[your-project-ref].supabase.co:5432/postgres"

# 执行迁移文件
\i migrations/create_quota_functions.sql
```

## 验证执行结果

执行成功后，您可以通过以下 SQL 验证函数是否创建成功：

```sql
-- 检查函数是否存在
SELECT proname, prosrc 
FROM pg_proc 
WHERE proname IN ('increment_daily_used', 'decrement_daily_used');

-- 检查索引是否存在
SELECT indexname, indexdef 
FROM pg_indexes 
WHERE indexname = 'idx_users_id_quota';
```

## 函数说明

### `increment_daily_used(p_user_id UUID)`
- **功能**：原子递增用户每日使用配额
- **参数**：用户 ID
- **返回值**：递增后的使用量
- **异常**：如果超过配额，抛出 `quota_exceeded` 异常

### `decrement_daily_used(p_user_id UUID)`
- **功能**：原子递减用户每日使用配额（用于补偿回滚）
- **参数**：用户 ID
- **返回值**：递减后的使用量

### 索引 `idx_users_id_quota`
- **功能**：优化配额查询性能
- **字段**：`id`, `daily_used`, `daily_quota`

## 重要提示

1. **执行顺序**：确保在创建函数之前，`users` 表已经存在且包含 `daily_used` 和 `daily_quota` 字段
2. **权限**：确保数据库用户有执行存储过程的权限
3. **测试**：执行后建议测试函数是否正常工作

## 测试函数

```sql
-- 测试递增函数（假设用户ID为 '123e4567-e89b-12d3-a456-426614174000'）
SELECT increment_daily_used('123e4567-e89b-12d3-a456-426614174000');

-- 测试递减函数
SELECT decrement_daily_used('123e4567-e89b-12d3-a456-426614174000');
```

执行成功后，您的应用就可以使用这些原子操作来安全地管理用户配额了。
