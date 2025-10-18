-- ✅ 创建原子递增配额的PostgreSQL函数
CREATE OR REPLACE FUNCTION increment_daily_used(p_user_id UUID)
RETURNS INTEGER AS $$
DECLARE
    v_new_used INTEGER;
    v_quota INTEGER;
BEGIN
    -- 获取当前配额并锁行
    SELECT daily_used, daily_quota 
    INTO v_new_used, v_quota
    FROM users 
    WHERE id = p_user_id
    FOR UPDATE;
    
    -- 检查是否超过配额
    IF v_new_used >= v_quota THEN
        RAISE EXCEPTION 'quota_exceeded';
    END IF;
    
    -- 原子递增
    UPDATE users 
    SET daily_used = daily_used + 1,
        updated_at = NOW()
    WHERE id = p_user_id
    RETURNING daily_used INTO v_new_used;
    
    RETURN v_new_used;
END;
$$ LANGUAGE plpgsql;

-- ✅ 创建补偿回滚函数
CREATE OR REPLACE FUNCTION decrement_daily_used(p_user_id UUID)
RETURNS INTEGER AS $$
DECLARE
    v_new_used INTEGER;
BEGIN
    UPDATE users 
    SET daily_used = GREATEST(daily_used - 1, 0),
        updated_at = NOW()
    WHERE id = p_user_id
    RETURNING daily_used INTO v_new_used;
    
    RETURN v_new_used;
END;
$$ LANGUAGE plpgsql;

-- ✅ 创建索引（如果还没有）
CREATE INDEX IF NOT EXISTS idx_users_id_quota 
ON users(id, daily_used, daily_quota);
