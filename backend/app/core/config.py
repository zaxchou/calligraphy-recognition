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
    TUBI_THUMBNAIL_DIR: str = os.path.join(DATA_DIR, "thumbnails")
    TUBI_ANNOTATED_DIR: str = os.path.join(DATA_DIR, "annotated")
    TUBI_DEBUG_DIR: str = os.path.join(DATA_DIR, "tubi_debug")
    TUBI_REFINE_PAINT_MASK: bool = os.getenv("TUBI_REFINE_PAINT_MASK", "false").lower() in ("1", "true", "yes", "y")
    TUBI_REFINE_INSCRIPTION_MASK: bool = os.getenv("TUBI_REFINE_INSCRIPTION_MASK", "false").lower() in ("1", "true", "yes", "y")
    TUBI_DEBUG_SAVE_IMAGES: bool = os.getenv("TUBI_DEBUG_SAVE_IMAGES", "false").lower() in ("1", "true", "yes", "y")
    TUBI_IMAGE_ID: str = os.getenv("TUBI_IMAGE_ID", "")
    
    # CV-First 新流程开关
    USE_CV_FIRST_PIPELINE: bool = os.getenv("USE_CV_FIRST_PIPELINE", "true").lower() in ("1", "true", "yes", "y")

    TUBI_PAINT_BG_SAMPLE_RATIO: float = float(os.getenv("TUBI_PAINT_BG_SAMPLE_RATIO", "0.06"))
    TUBI_PAINT_BG_DELTAE: float = float(os.getenv("TUBI_PAINT_BG_DELTAE", "12.0"))
    TUBI_PAINT_BG_GRAD_MAX: float = float(os.getenv("TUBI_PAINT_BG_GRAD_MAX", "8.0"))
    TUBI_PAINT_BG_S_MAX: float = float(os.getenv("TUBI_PAINT_BG_S_MAX", "0.0"))

    TUBI_FAN_EXPAND_PAD_X_RATIO: float = float(os.getenv("TUBI_FAN_EXPAND_PAD_X_RATIO", "0.18"))
    TUBI_FAN_EXPAND_PAD_Y_RATIO: float = float(os.getenv("TUBI_FAN_EXPAND_PAD_Y_RATIO", "0.12"))
    TUBI_FAN_EXPAND_RIGHT_EXT_RATIO: float = float(os.getenv("TUBI_FAN_EXPAND_RIGHT_EXT_RATIO", "0.42"))
    TUBI_FAN_EXPAND_X_MARGIN_RATIO: float = float(os.getenv("TUBI_FAN_EXPAND_X_MARGIN_RATIO", "0.15"))
    TUBI_FAN_EXPAND_BOTTOM_CUTOFF_RATIO: float = float(os.getenv("TUBI_FAN_EXPAND_BOTTOM_CUTOFF_RATIO", "0.10"))
    TUBI_FAN_EDGE_DILATE_K: int = int(os.getenv("TUBI_FAN_EDGE_DILATE_K", "5"))
    TUBI_FAN_EDGE_DILATE_ITER: int = int(os.getenv("TUBI_FAN_EDGE_DILATE_ITER", "2"))
    TUBI_FAN_FAN_CLOSE_K: int = int(os.getenv("TUBI_FAN_FAN_CLOSE_K", "41"))
    TUBI_FAN_FAN_CLOSE_ITER: int = int(os.getenv("TUBI_FAN_FAN_CLOSE_ITER", "2"))
    TUBI_FAN_MAX_FILL_RATIO: float = float(os.getenv("TUBI_FAN_MAX_FILL_RATIO", "0.35"))

    TUBI_INS_ROI_PAD_RATIO: float = float(os.getenv("TUBI_INS_ROI_PAD_RATIO", "0.08"))
    TUBI_INS_OTSU_MULT: float = float(os.getenv("TUBI_INS_OTSU_MULT", "0.80"))
    TUBI_INS_ADAPTIVE_BLOCK: int = int(os.getenv("TUBI_INS_ADAPTIVE_BLOCK", "21"))
    TUBI_INS_ADAPTIVE_C: int = int(os.getenv("TUBI_INS_ADAPTIVE_C", "12"))
    TUBI_INS_INK_OPEN_K: int = int(os.getenv("TUBI_INS_INK_OPEN_K", "3"))
    TUBI_INS_INK_OPEN_ITER: int = int(os.getenv("TUBI_INS_INK_OPEN_ITER", "1"))
    TUBI_INS_DILATE_KX: int = int(os.getenv("TUBI_INS_DILATE_KX", "17"))
    TUBI_INS_DILATE_KY: int = int(os.getenv("TUBI_INS_DILATE_KY", "29"))
    TUBI_INS_DILATE_ITER: int = int(os.getenv("TUBI_INS_DILATE_ITER", "1"))
    TUBI_INS_GROW_MAX_DX_RATIO: float = float(os.getenv("TUBI_INS_GROW_MAX_DX_RATIO", "0.10"))
    TUBI_INS_GROW_MAX_DY_RATIO: float = float(os.getenv("TUBI_INS_GROW_MAX_DY_RATIO", "0.15"))
    TUBI_INS_GROW_MIN_AREA: int = int(os.getenv("TUBI_INS_GROW_MIN_AREA", "150"))
    TUBI_INS_GROW_ITERS: int = int(os.getenv("TUBI_INS_GROW_ITERS", "5"))
    TUBI_INS_PAINT_OVERLAP_MAX: float = float(os.getenv("TUBI_INS_PAINT_OVERLAP_MAX", "0.25"))
    TUBI_INS_DENSITY_MIN: float = float(os.getenv("TUBI_INS_DENSITY_MIN", "0.12"))
    TUBI_INS_CLEAN_OPEN_K: int = int(os.getenv("TUBI_INS_CLEAN_OPEN_K", "7"))
    TUBI_INS_CLEAN_OPEN_ITER: int = int(os.getenv("TUBI_INS_CLEAN_OPEN_ITER", "2"))
    TUBI_INS_CLEAN_CLOSE_K: int = int(os.getenv("TUBI_INS_CLEAN_CLOSE_K", "3"))
    TUBI_INS_CLEAN_CLOSE_ITER: int = int(os.getenv("TUBI_INS_CLEAN_CLOSE_ITER", "2"))
    TUBI_SEAL_H_MAX: int = int(os.getenv("TUBI_SEAL_H_MAX", "25"))
    TUBI_SEAL_S_MIN: int = int(os.getenv("TUBI_SEAL_S_MIN", "20"))
    TUBI_SEAL_V_MIN: int = int(os.getenv("TUBI_SEAL_V_MIN", "60"))
    TUBI_SEAL_GATE_PAD_RATIO: float = float(os.getenv("TUBI_SEAL_GATE_PAD_RATIO", "0.05"))
    TUBI_SEAL_AREA_MIN: int = int(os.getenv("TUBI_SEAL_AREA_MIN", "80"))
    TUBI_SEAL_AREA_MAX: int = int(os.getenv("TUBI_SEAL_AREA_MAX", "40000"))
    TUBI_SEAL_AR_MIN: float = float(os.getenv("TUBI_SEAL_AR_MIN", "0.4"))
    TUBI_SEAL_AR_MAX: float = float(os.getenv("TUBI_SEAL_AR_MAX", "2.5"))
    TUBI_SEAL_MEAN_S_MIN: float = float(os.getenv("TUBI_SEAL_MEAN_S_MIN", "22"))
    TUBI_SEAL_MEAN_V_MAX: float = float(os.getenv("TUBI_SEAL_MEAN_V_MAX", "245"))
    
    # 模型配置
    MODEL_PATH: str = "models"
    FEATURE_DIM: int = 512
    
    # 相似度阈值
    SIMILARITY_THRESHOLD: float = 70.0
    
    # 百度 OCR 配置
    BAIDU_OCR_API_KEY: str = os.getenv("BAIDU_OCR_API_KEY", "")
    BAIDU_OCR_SECRET_KEY: str = os.getenv("BAIDU_OCR_SECRET_KEY", "")

    # DeepSeek AI 配置（已弃用，保留兼容）
    DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY", "")

    # 服务端口
    SERVER_PORT: int = int(os.getenv("SERVER_PORT", "8001"))
    DEEPSEEK_ENABLED: bool = False  # 已切换到 SiliconFlow
    
    # SiliconFlow AI 配置（题跋分析和字体识别共用）
    SILICONFLOW_API_KEY: str = os.getenv("SILICONFLOW_API_KEY", "")
    SILICONFLOW_MODEL: str = "Pro/moonshotai/Kimi-K2.5"
    SILICONFLOW_ENABLED: bool = os.getenv("SILICONFLOW_ENABLED", "true").lower() in ("1", "true", "yes", "y")

    # Aliyun DashScope Qwen（OpenAI Compatible Mode）
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

    ZHIPU_API_KEY: str = os.getenv("ZHIPU_API_KEY", "")
    ZHIPU_BASE_URL: str = os.getenv("ZHIPU_BASE_URL", "https://open.bigmodel.cn/api/paas/v4")
    ZHIPU_MODEL: str = os.getenv("ZHIPU_MODEL", "glm-5v-turbo")
    ZHIPU_ENABLED: bool = os.getenv("ZHIPU_ENABLED", "false").lower() in ("1", "true", "yes", "y")

    TUBI_LLM_PROVIDER: str = os.getenv("TUBI_LLM_PROVIDER", "").strip().lower()

    # DashScope 多模态 Embedding 开关（图像向量化用 multimodal-embedding-v1）
    DASHSCOPE_MULTIMODAL_ENABLED: bool = os.getenv("DASHSCOPE_MULTIMODAL_ENABLED", "true").lower() in ("1", "true", "yes", "y")

    COMPOSITION_LLM_MODEL: str = os.getenv("COMPOSITION_LLM_MODEL", "qwen3.5-plus")
    COMPOSITION_LLM_MAX_TOKENS: int = int(os.getenv("COMPOSITION_LLM_MAX_TOKENS", "16384"))
    
    class Config:
        env_file = ".env"


@lru_cache()
def get_settings():
    return Settings()
