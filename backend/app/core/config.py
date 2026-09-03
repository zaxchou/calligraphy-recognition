import os
from pydantic_settings import BaseSettings
from functools import lru_cache
from dotenv import load_dotenv

# 获取项目根目录
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# 确保DATA_DIR是绝对路径
DATA_DIR = os.path.abspath(os.path.join(BASE_DIR, "data"))
os.makedirs(DATA_DIR, exist_ok=True)

# 加载 .env 文件
env_path = os.path.join(BASE_DIR, ".env")
load_dotenv(env_path)


class Settings(BaseSettings):
    PROJECT_NAME: str = "书法碑帖字体认证系统"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"

    CORS_ALLOW_ORIGINS: str = os.getenv("CORS_ALLOW_ORIGINS", "*")
    
    # 数据库配置 (使用SQLite，无需安装PostgreSQL)
    DATABASE_URL: str = f"sqlite:///{os.path.join(DATA_DIR, 'calligraphy.db')}"
    
    # Redis配置
    REDIS_URL: str = "redis://localhost:6379/0"

    COMPOSITION_API_KEY: str = os.getenv("COMPOSITION_API_KEY", "")
    COMPOSITION_REQUIRE_API_KEY: bool = False

    QDRANT_URL: str = os.getenv("QDRANT_URL", "")
    QDRANT_API_KEY: str = os.getenv("QDRANT_API_KEY", "")
    
    # 文件存储配置
    UPLOAD_DIR: str = os.path.join(DATA_DIR, "uploads")
    STATIC_DIR: str = os.path.join(DATA_DIR, "static")
    TIBA_THUMBNAIL_DIR: str = os.path.join(DATA_DIR, "thumbnails")
    TIBA_ANNOTATED_DIR: str = os.path.join(DATA_DIR, "annotated")
    TIBA_DEBUG_DIR: str = os.path.join(DATA_DIR, "tubi_debug")
    TIBA_REFINE_PAINT_MASK: bool = os.getenv("TIBA_REFINE_PAINT_MASK", "false").lower() in ("1", "true", "yes", "y")
    TIBA_REFINE_INSCRIPTION_MASK: bool = os.getenv("TIBA_REFINE_INSCRIPTION_MASK", "false").lower() in ("1", "true", "yes", "y")
    TIBA_DEBUG_SAVE_IMAGES: bool = os.getenv("TIBA_DEBUG_SAVE_IMAGES", "false").lower() in ("1", "true", "yes", "y")
    TIBA_IMAGE_ID: str = os.getenv("TIBA_IMAGE_ID", "")
    
    # CV-First 新流程开关
    USE_CV_FIRST_PIPELINE: bool = os.getenv("USE_CV_FIRST_PIPELINE", "false").lower() in ("1", "true", "yes", "y")

    # 站点只读模式（true 时隐藏登录/注册/互动功能）
    SITE_READONLY: bool = os.getenv("SITE_READONLY", "false").lower() in ("1", "true", "yes", "y")

    TIBA_PAINT_BG_SAMPLE_RATIO: float = float(os.getenv("TIBA_PAINT_BG_SAMPLE_RATIO", "0.06"))
    TIBA_PAINT_BG_DELTAE: float = float(os.getenv("TIBA_PAINT_BG_DELTAE", "12.0"))
    TIBA_PAINT_BG_GRAD_MAX: float = float(os.getenv("TIBA_PAINT_BG_GRAD_MAX", "8.0"))
    TIBA_PAINT_BG_S_MAX: float = float(os.getenv("TIBA_PAINT_BG_S_MAX", "0.0"))

    TIBA_FAN_EXPAND_PAD_X_RATIO: float = float(os.getenv("TIBA_FAN_EXPAND_PAD_X_RATIO", "0.18"))
    TIBA_FAN_EXPAND_PAD_Y_RATIO: float = float(os.getenv("TIBA_FAN_EXPAND_PAD_Y_RATIO", "0.12"))
    TIBA_FAN_EXPAND_RIGHT_EXT_RATIO: float = float(os.getenv("TIBA_FAN_EXPAND_RIGHT_EXT_RATIO", "0.42"))
    TIBA_FAN_EXPAND_X_MARGIN_RATIO: float = float(os.getenv("TIBA_FAN_EXPAND_X_MARGIN_RATIO", "0.15"))
    TIBA_FAN_EXPAND_BOTTOM_CUTOFF_RATIO: float = float(os.getenv("TIBA_FAN_EXPAND_BOTTOM_CUTOFF_RATIO", "0.10"))
    TIBA_FAN_EDGE_DILATE_K: int = int(os.getenv("TIBA_FAN_EDGE_DILATE_K", "5"))
    TIBA_FAN_EDGE_DILATE_ITER: int = int(os.getenv("TIBA_FAN_EDGE_DILATE_ITER", "2"))
    TIBA_FAN_FAN_CLOSE_K: int = int(os.getenv("TIBA_FAN_FAN_CLOSE_K", "41"))
    TIBA_FAN_FAN_CLOSE_ITER: int = int(os.getenv("TIBA_FAN_FAN_CLOSE_ITER", "2"))
    TIBA_FAN_MAX_FILL_RATIO: float = float(os.getenv("TIBA_FAN_MAX_FILL_RATIO", "0.35"))

    TIBA_FAN_RADIUS_OFFSET: int = int(os.getenv("TIBA_FAN_RADIUS_OFFSET", "0"))

    # DZI (Deep Zoom Image) 配置
    DZI_DIR: str = os.path.join(DATA_DIR, "dzi")
    TIBA_INS_ROI_PAD_RATIO: float = float(os.getenv("TIBA_INS_ROI_PAD_RATIO", "0.08"))
    TIBA_INS_OTSU_MULT: float = float(os.getenv("TIBA_INS_OTSU_MULT", "0.80"))
    TIBA_INS_ADAPTIVE_BLOCK: int = int(os.getenv("TIBA_INS_ADAPTIVE_BLOCK", "21"))
    TIBA_INS_ADAPTIVE_C: int = int(os.getenv("TIBA_INS_ADAPTIVE_C", "12"))
    TIBA_INS_INK_OPEN_K: int = int(os.getenv("TIBA_INS_INK_OPEN_K", "3"))
    TIBA_INS_INK_OPEN_ITER: int = int(os.getenv("TIBA_INS_INK_OPEN_ITER", "1"))
    TIBA_INS_DILATE_KX: int = int(os.getenv("TIBA_INS_DILATE_KX", "17"))
    TIBA_INS_DILATE_KY: int = int(os.getenv("TIBA_INS_DILATE_KY", "29"))
    TIBA_INS_DILATE_ITER: int = int(os.getenv("TIBA_INS_DILATE_ITER", "1"))
    TIBA_INS_GROW_MAX_DX_RATIO: float = float(os.getenv("TIBA_INS_GROW_MAX_DX_RATIO", "0.10"))
    TIBA_INS_GROW_MAX_DY_RATIO: float = float(os.getenv("TIBA_INS_GROW_MAX_DY_RATIO", "0.15"))
    TIBA_INS_GROW_MIN_AREA: int = int(os.getenv("TIBA_INS_GROW_MIN_AREA", "150"))
    TIBA_INS_GROW_ITERS: int = int(os.getenv("TIBA_INS_GROW_ITERS", "5"))
    TIBA_INS_PAINT_OVERLAP_MAX: float = float(os.getenv("TIBA_INS_PAINT_OVERLAP_MAX", "0.25"))
    TIBA_INS_DENSITY_MIN: float = float(os.getenv("TIBA_INS_DENSITY_MIN", "0.12"))
    TIBA_INS_CLEAN_OPEN_K: int = int(os.getenv("TIBA_INS_CLEAN_OPEN_K", "7"))
    TIBA_INS_CLEAN_OPEN_ITER: int = int(os.getenv("TIBA_INS_CLEAN_OPEN_ITER", "2"))
    TIBA_INS_CLEAN_CLOSE_K: int = int(os.getenv("TIBA_INS_CLEAN_CLOSE_K", "3"))
    TIBA_INS_CLEAN_CLOSE_ITER: int = int(os.getenv("TIBA_INS_CLEAN_CLOSE_ITER", "2"))
    TIBA_SEAL_H_MAX: int = int(os.getenv("TIBA_SEAL_H_MAX", "25"))
    TIBA_SEAL_S_MIN: int = int(os.getenv("TIBA_SEAL_S_MIN", "20"))
    TIBA_SEAL_V_MIN: int = int(os.getenv("TIBA_SEAL_V_MIN", "60"))
    TIBA_SEAL_GATE_PAD_RATIO: float = float(os.getenv("TIBA_SEAL_GATE_PAD_RATIO", "0.05"))
    TIBA_SEAL_AREA_MIN: int = int(os.getenv("TIBA_SEAL_AREA_MIN", "80"))
    TIBA_SEAL_AREA_MAX: int = int(os.getenv("TIBA_SEAL_AREA_MAX", "40000"))
    TIBA_SEAL_AR_MIN: float = float(os.getenv("TIBA_SEAL_AR_MIN", "0.4"))
    TIBA_SEAL_AR_MAX: float = float(os.getenv("TIBA_SEAL_AR_MAX", "2.5"))
    TIBA_SEAL_MEAN_S_MIN: float = float(os.getenv("TIBA_SEAL_MEAN_S_MIN", "22"))
    TIBA_SEAL_MEAN_V_MAX: float = float(os.getenv("TIBA_SEAL_MEAN_V_MAX", "245"))
    
    # 模型配置
    MODEL_PATH: str = "models"
    FEATURE_DIM: int = 512
    
    # 相似度阈值
    SIMILARITY_THRESHOLD: float = 70.0
    
    # 百度 OCR 配置
    BAIDU_OCR_API_KEY: str = os.getenv("BAIDU_OCR_API_KEY", "")
    BAIDU_OCR_SECRET_KEY: str = os.getenv("BAIDU_OCR_SECRET_KEY", "")

    # 服务端口
    SERVER_PORT: int = int(os.getenv("SERVER_PORT", "8001"))
    DEEPSEEK_ENABLED: bool = False  # 已切换到 SiliconFlow
    
    # SiliconFlow AI 配置（题跋分析和字体识别共用）
    SILICONFLOW_API_KEY: str = os.getenv("SILICONFLOW_API_KEY", "")
    SILICONFLOW_MODEL: str = "Pro/moonshotai/Kimi-K2.5"
    SILICONFLOW_ENABLED: bool = os.getenv("SILICONFLOW_ENABLED", "true").lower() in ("1", "true", "yes", "y")

    # Aliyun DashScope Qwen（保留 — 仅图像/视觉模型使用）
    QWEN_API_KEY: str = os.getenv("QWEN_API_KEY") or os.getenv("DASHSCOPE_API_KEY", "")
    QWEN_BASE_URL: str = (
        os.getenv("QWEN_BASE_URL")
        or os.getenv("DASHSCOPE_BASE_URL")
        or os.getenv("DASHSCOPE_API_BASE")
        or "https://dashscope.aliyuncs.com/compatible-mode/v1"
    )
    QWEN_MODEL: str = os.getenv("QWEN_MODEL", "qwen3-vl-plus")
    QWEN_ENABLED: bool = os.getenv("QWEN_ENABLED", "true").lower() in ("1", "true", "yes", "y")
    QWEN_THINKING_ENABLED: bool = os.getenv("QWEN_THINKING_ENABLED", "false").lower() not in ("0", "false", "no", "n", "")
    QWEN_TRANSLATION_MODEL: str = os.getenv("QWEN_TRANSLATION_MODEL", "qwen3.5-plus")
    QWEN_INSIGHT_MODEL: str = os.getenv("QWEN_INSIGHT_MODEL", "qwen3.5-plus")

    # DeepSeek V4 Flash（文本 LLM 主模型）
    DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY", "")
    DEEPSEEK_BASE_URL: str = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    DEEPSEEK_TEXT_MODEL: str = os.getenv("DEEPSEEK_TEXT_MODEL", "deepseek-v4-flash")

    ZHIPU_API_KEY: str = os.getenv("ZHIPU_API_KEY", "")
    ZHIPU_BASE_URL: str = os.getenv("ZHIPU_BASE_URL", "https://open.bigmodel.cn/api/paas/v4")
    ZHIPU_MODEL: str = os.getenv("ZHIPU_MODEL", "glm-5v-turbo")
    ZHIPU_ENABLED: bool = os.getenv("ZHIPU_ENABLED", "false").lower() in ("1", "true", "yes", "y")

    TIBA_LLM_PROVIDER: str = os.getenv("TIBA_LLM_PROVIDER", "").strip().lower()

    # DashScope 多模态 Embedding 开关（图像向量化用 multimodal-embedding-v1）
    DASHSCOPE_MULTIMODAL_ENABLED: bool = os.getenv("DASHSCOPE_MULTIMODAL_ENABLED", "true").lower() in ("1", "true", "yes", "y")

    COMPOSITION_LLM_MODEL: str = os.getenv("COMPOSITION_LLM_MODEL", "qwen3-vl-flash")
    COMPOSITION_LLM_MAX_TOKENS: int = int(os.getenv("COMPOSITION_LLM_MAX_TOKENS", "16384"))

    # MinerU 云 API 配置
    MINERU_API_TOKEN: str = os.getenv("MINERU_API_TOKEN", "")
    MINERU_API_BASE: str = os.getenv("MINERU_API_BASE", "https://mineru.net")
    MINERU_MODEL_VERSION: str = os.getenv("MINERU_MODEL_VERSION", "vlm")

    # ── Phase 5 配额管理 ────────────────────────────────────────────
    FREE_AI_CALLS_PER_MONTH: int = int(os.getenv("FREE_AI_CALLS_PER_MONTH", "30"))
    PAID_AI_CALLS_PER_MONTH: int = int(os.getenv("PAID_AI_CALLS_PER_MONTH", "300"))
    FREE_STORAGE_BYTES: int = int(os.getenv("FREE_STORAGE_BYTES", str(500 * 1024 * 1024)))       # 500 MB
    PAID_STORAGE_BYTES: int = int(os.getenv("PAID_STORAGE_BYTES", str(50 * 1024 * 1024 * 1024)))  # 50 GB
    FREE_LIBRARY_LIMIT: int = int(os.getenv("FREE_LIBRARY_LIMIT", "3"))

    # ── Phase 1 多用户底座 ───────────────────────────────────────────
    # JWT 配置
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "calligraphy-jwt-secret-change-in-production")
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    JWT_EXPIRATION_HOURS: int = int(os.getenv("JWT_EXPIRATION_HOURS", "168"))  # 7天

    # 微信小程序配置

    # 微信开放平台网站应用配置（网页扫码登录用，与小程序是不同产品）

    # 百度百科 / 百度搜索 API Key
    BAIDU_API_KEY: str = os.getenv("BAIDU_API_KEY", "")
    
    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache()
def get_settings():
    return Settings()
