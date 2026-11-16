# Agent 配置
import os


class Config:
    # 数据库
    DATABASE_URL = os.environ.get(
        "DATABASE_URL",
        "mysql+pymysql://pdm_user:pdm_pass_2026@localhost:3306/pdm_system"
    )
    # Redis
    REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    # LLM
    LLM_API_KEY = os.environ.get("LLM_API_KEY", "")
    LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "https://api.deepseek.com/v1")
    LLM_MODEL = os.environ.get("LLM_MODEL", "deepseek-chat")
    # 行为开关
    AGENT_AUTO_ANALYZE = os.environ.get("AGENT_AUTO_ANALYZE", "true").lower() == "true"
    FEATURE_EXTRACT_INTERVAL = int(os.environ.get("FEATURE_EXTRACT_INTERVAL", "60"))


config = Config()
