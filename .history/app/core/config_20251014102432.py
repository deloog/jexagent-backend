from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    # 应用配置
    APP_NAME: str = "JexAgent"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    
    # Supabase配置
    SUPABASE_URL: str
    SUPABASE_KEY: str
    SUPABASE_SERVICE_KEY: str
    
    # JWT配置
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # AI服务API密钥
    DEEPSEEK_API_KEY: str
    MOONSHOT_API_KEY: str
    QWEN_API_KEY: str
    
    # Redis配置
    REDIS_URL: str = "redis://localhost:6379"
    
    # CORS配置
    ALLOWED_ORIGINS: List[str] = ["http://localhost:3000"]
    
    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()