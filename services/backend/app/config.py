# 后端配置
import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # 数据库
    database_url: str = os.environ.get(
        "DATABASE_URL",
        "mysql+pymysql://pdm_user:pdm_pass_2026@localhost:3306/pdm_system"
    )
    
    # Redis
    redis_url: str = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    
    # MinIO
    minio_endpoint: str = os.environ.get("MINIO_ENDPOINT", "localhost:9000")
    minio_access_key: str = os.environ.get("MINIO_ACCESS_KEY", "minioadmin")
    minio_secret_key: str = os.environ.get("MINIO_SECRET_KEY", "minioadmin")
    minio_bucket: str = os.environ.get("MINIO_BUCKET", "pdm-manuals")
    
    # LLM（后端转发给 Agent 用）
    llm_api_key: str = os.environ.get("LLM_API_KEY", "")
    llm_base_url: str = os.environ.get("LLM_BASE_URL", "https://api.deepseek.com/v1")
    llm_model: str = os.environ.get("LLM_MODEL", "deepseek-chat")
    
    class Config:
        env_file = ".env"


settings = Settings()
