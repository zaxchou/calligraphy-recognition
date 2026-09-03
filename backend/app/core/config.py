import os
from pydantic import Field
from pydantic_settings import BaseSettings
from functools import lru_cache
from dotenv import load_dotenv

# 获取项目根目录
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# 确保DATA_DIR是绝对路径
# v2.0: 支持环境变量覆盖（测试隔离/多实例），未设置时保持原行为
DATA_DIR = os.path.abspath(os.getenv("DATA_DIR", os.path.join(BASE_DIR, "data")))
os.makedirs(DATA_DIR, exist_ok=True)

# 加载 .env 文件
env_path = os.path.join(BASE_DIR, ".env")
load_dotenv(env_path)


class Settings(BaseSettings):
    PROJECT_NAME: str = "书法碑帖字体认证系统"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"

    CORS_ALLOW_ORIGINS: str = Field(default="*")
    
    # 数据库配置 (使用SQLite，无需安装PostgreSQL)
    DATABASE_URL: str = f"sqlite:///{os.path.join(DATA_DIR, 'calligraphy.db')}"
    
    # Redis配置
    REDIS_URL: str = "redis://localhost:6379/0"

    COMPOSITION_API_KEY: str = Field(default="")
    COMPOSITION_REQUIRE_API_KEY: bool = False

    QDRANT_URL: str = Field(default="")
    QDRANT_API_KEY: str = Field(default="")
    
    # 文件存储配置
    UPLOAD_DIR: str = os.path.join(DATA_DIR, "uploads")
    STATIC_DIR: str = os.path.join(DATA_DIR, "static")
    TIBA_THUMBNAIL_DIR: str = os.path.join(DATA_DIR, "thumbnails")
    TIBA_ANNOTATED_DIR: str = os.path.join(DATA_DIR, "annotated")
    TIBA_DEBUG_DIR: str = os.path.join(DATA_DIR, "tubi_debug")
    TIBA_REFINE_PAINT_MASK: bool = Field(default=False)
    TIBA_REFINE_INSCRIPTION_MASK: bool = Field(default=False)
    TIBA_DEBUG_SAVE_IMAGES: bool = Field(default=False)
    TIBA_IMAGE_ID: str = Field(default="")
    
    # CV-First 新流程开关
    USE_CV_FIRST_PIPELINE: bool = Field(default=False)

    # 站点只读模式（true 时隐藏登录/注册/互动功能）
    SITE_READONLY: bool = Field(default=False)

    TIBA_PAINT_BG_SAMPLE_RATIO: float = Field(default=0.06)
    TIBA_PAINT_BG_DELTAE: float = Field(default=12.0)
    TIBA_PAINT_BG_GRAD_MAX: float = Field(default=8.0)
    TIBA_PAINT_BG_S_MAX: float = Field(default=0.0)

    TIBA_FAN_EXPAND_PAD_X_RATIO: float = Field(default=0.18)
    TIBA_FAN_EXPAND_PAD_Y_RATIO: float = Field(default=0.12)
    TIBA_FAN_EXPAND_RIGHT_EXT_RATIO: float = Field(default=0.42)
    TIBA_FAN_EXPAND_X_MARGIN_RATIO: float = Field(default=0.15)
    TIBA_FAN_EXPAND_BOTTOM_CUTOFF_RATIO: float = Field(default=0.10)
    TIBA_FAN_EDGE_DILATE_K: int = Field(default=5)
    TIBA_FAN_EDGE_DILATE_ITER: int = Field(default=2)
    TIBA_FAN_FAN_CLOSE_K: int = Field(default=41)
    TIBA_FAN_FAN_CLOSE_ITER: int = Field(default=2)
    TIBA_FAN_MAX_FILL_RATIO: float = Field(default=0.35)

    TIBA_FAN_RADIUS_OFFSET: int = Field(default=0)

    # DZI (Deep Zoom Image) 配置
    DZI_DIR: str = os.path.join(DATA_DIR, "dzi")
    TIBA_INS_ROI_PAD_RATIO: float = Field(default=0.08)
    TIBA_INS_OTSU_MULT: float = Field(default=0.80)
    TIBA_INS_ADAPTIVE_BLOCK: int = Field(default=21)
    TIBA_INS_ADAPTIVE_C: int = Field(default=12)
    TIBA_INS_INK_OPEN_K: int = Field(default=3)
    TIBA_INS_INK_OPEN_ITER: int = Field(default=1)
    TIBA_INS_DILATE_KX: int = Field(default=17)
    TIBA_INS_DILATE_KY: int = Field(default=29)
    TIBA_INS_DILATE_ITER: int = Field(default=1)
    TIBA_INS_GROW_MAX_DX_RATIO: float = Field(default=0.10)
    TIBA_INS_GROW_MAX_DY_RATIO: float = Field(default=0.15)
    TIBA_INS_GROW_MIN_AREA: int = Field(default=150)
    TIBA_INS_GROW_ITERS: int = Field(default=5)
    TIBA_INS_PAINT_OVERLAP_MAX: float = Field(default=0.25)
    TIBA_INS_DENSITY_MIN: float = Field(default=0.12)
    TIBA_INS_CLEAN_OPEN_K: int = Field(default=7)
    TIBA_INS_CLEAN_OPEN_ITER: int = Field(default=2)
    TIBA_INS_CLEAN_CLOSE_K: int = Field(default=3)
    TIBA_INS_CLEAN_CLOSE_ITER: int = Field(default=2)
    TIBA_SEAL_H_MAX: int = Field(default=25)
    TIBA_SEAL_S_MIN: int = Field(default=20)
    TIBA_SEAL_V_MIN: int = Field(default=60)
    TIBA_SEAL_GATE_PAD_RATIO: float = Field(default=0.05)
    TIBA_SEAL_AREA_MIN: int = Field(default=80)
    TIBA_SEAL_AREA_MAX: int = Field(default=40000)
    TIBA_SEAL_AR_MIN: float = Field(default=0.4)
    TIBA_SEAL_AR_MAX: float = Field(default=2.5)
    TIBA_SEAL_MEAN_S_MIN: float = Field(default=22)
    TIBA_SEAL_MEAN_V_MAX: float = Field(default=245)
    
    # 模型配置
    MODEL_PATH: str = "models"
    FEATURE_DIM: int = 512
    
    # 相似度阈值
    SIMILARITY_THRESHOLD: float = 70.0
    
    # 百度 OCR 配置
    BAIDU_OCR_API_KEY: str = Field(default="")
    BAIDU_OCR_SECRET_KEY: str = Field(default="")

    # 服务端口
    SERVER_PORT: int = Field(default=8001)
    DEEPSEEK_ENABLED: bool = False  # 已切换到 SiliconFlow
    
    # SiliconFlow AI 配置（题跋分析和字体识别共用）
    SILICONFLOW_API_KEY: str = Field(default="")
    SILICONFLOW_MODEL: str = "Pro/moonshotai/Kimi-K2.5"
    SILICONFLOW_ENABLED: bool = Field(default=True)

    # Aliyun DashScope Qwen（保留 — 仅图像/视觉模型使用）
    QWEN_API_KEY: str = os.getenv("QWEN_API_KEY") or os.getenv("DASHSCOPE_API_KEY", "")
    QWEN_BASE_URL: str = (
        os.getenv("QWEN_BASE_URL")
        or os.getenv("DASHSCOPE_BASE_URL")
        or os.getenv("DASHSCOPE_API_BASE")
        or "https://dashscope.aliyuncs.com/compatible-mode/v1"
    )
    QWEN_MODEL: str = Field(default="qwen3-vl-plus")
    QWEN_ENABLED: bool = Field(default=True)
    QWEN_THINKING_ENABLED: bool = Field(default=False)  # 原 os.getenv 默认 false，非流式传 true 会 400
    QWEN_TRANSLATION_MODEL: str = Field(default="qwen3.5-plus")
    QWEN_INSIGHT_MODEL: str = Field(default="qwen3.5-plus")

    # DeepSeek V4 Flash（文本 LLM 主模型）
    DEEPSEEK_API_KEY: str = Field(default="")
    DEEPSEEK_BASE_URL: str = Field(default="https://api.deepseek.com")
    DEEPSEEK_TEXT_MODEL: str = Field(default="deepseek-v4-flash")

    ZHIPU_API_KEY: str = Field(default="")
    ZHIPU_BASE_URL: str = Field(default="https://open.bigmodel.cn/api/paas/v4")
    ZHIPU_MODEL: str = Field(default="glm-5v-turbo")
    ZHIPU_ENABLED: bool = Field(default=False)

    TIBA_LLM_PROVIDER: str = os.getenv("TIBA_LLM_PROVIDER", "").strip().lower()

    # DashScope 多模态 Embedding 开关（图像向量化用 multimodal-embedding-v1）
    DASHSCOPE_MULTIMODAL_ENABLED: bool = Field(default=True)

    COMPOSITION_LLM_MODEL: str = Field(default="qwen3-vl-flash")
    COMPOSITION_LLM_MAX_TOKENS: int = Field(default=16384)

    # MinerU 云 API 配置
    MINERU_API_TOKEN: str = Field(default="")
    MINERU_API_BASE: str = Field(default="https://mineru.net")
    MINERU_MODEL_VERSION: str = Field(default="vlm")

    # ── Phase 5 配额管理 ────────────────────────────────────────────
    FREE_AI_CALLS_PER_MONTH: int = Field(default=30)
    PAID_AI_CALLS_PER_MONTH: int = Field(default=300)
    FREE_STORAGE_BYTES: int = int(os.getenv("FREE_STORAGE_BYTES", str(500 * 1024 * 1024)))       # 500 MB
    PAID_STORAGE_BYTES: int = int(os.getenv("PAID_STORAGE_BYTES", str(50 * 1024 * 1024 * 1024)))  # 50 GB
    FREE_LIBRARY_LIMIT: int = Field(default=3)

    # ── Phase 1 多用户底座 ───────────────────────────────────────────
    # JWT 配置
    JWT_SECRET_KEY: str = Field(default="calligraphy-jwt-secret-change-in-production")
    JWT_ALGORITHM: str = Field(default="HS256")
    JWT_EXPIRATION_HOURS: int = int(os.getenv("JWT_EXPIRATION_HOURS", "168"))  # 7天

    # 微信小程序配置

    # 微信开放平台网站应用配置（网页扫码登录用，与小程序是不同产品）

    # 百度百科 / 百度搜索 API Key
    BAIDU_API_KEY: str = Field(default="")
    
    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache()
def get_settings():
    return Settings()
