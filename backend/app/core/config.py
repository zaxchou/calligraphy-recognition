import os
from pydantic_settings import BaseSettings
from functools import lru_cache
from dotenv import load_dotenv

# 获取项目根目录
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

# 加载 .env 文件
env_path = os.path.join(BASE_DIR, ".env")
load_dotenv(env_path)


class Settings(BaseSettings):
    PROJECT_NAME: str = "书法碑帖字体认证系统"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    
    # 数据库配置 (使用SQLite，无需安装PostgreSQL)
    DATABASE_URL: str = f"sqlite:///{os.path.join(DATA_DIR, 'calligraphy.db')}"
    
    # Redis配置
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # 文件存储配置
    UPLOAD_DIR: str = os.path.join(DATA_DIR, "uploads")
    STATIC_DIR: str = os.path.join(DATA_DIR, "static")
    
    # 模型配置
    MODEL_PATH: str = "models"
    FEATURE_DIM: int = 512
    
    # 相似度阈值
    SIMILARITY_THRESHOLD: float = 70.0
    
    # DeepSeek AI 配置（已弃用，保留兼容）
    DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY", "")
    DEEPSEEK_ENABLED: bool = False  # 已切换到 SiliconFlow
    
    # SiliconFlow AI 配置（题跋分析和字体识别共用）
    SILICONFLOW_API_KEY: str = os.getenv("SILICONFLOW_API_KEY", "")
    SILICONFLOW_MODEL: str = "Pro/moonshotai/Kimi-K2.5"
    SILICONFLOW_ENABLED: bool = True  # 是否启用 SiliconFlow AI 识别
    
    class Config:
        env_file = ".env"


@lru_cache()
def get_settings():
    return Settings()
