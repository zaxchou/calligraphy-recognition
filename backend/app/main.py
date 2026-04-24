from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

from app.core.config import get_settings
from app.core.database import engine, Base
from app.api import recognition, steles, tubi

try:
    from app.api import composition
except Exception:
    import logging

    logging.getLogger(__name__).exception("Failed to import composition module; composition routes will be disabled")
    composition = None

try:
    from app.modules.pantianshou_composition.arrow_demo_api import router as arrow_demo_router
    _arrow_demo_router = arrow_demo_router
except Exception:
    _arrow_demo_router = None

try:
    from app.modules.pantianshou_composition.qichengzhuanhe_api import router as qczh_router
    _qczh_router = qczh_router
except Exception:
    _qczh_router = None

settings = get_settings()

# 创建数据库表
Base.metadata.create_all(bind=engine)

# 初始化知识库 Qdrant 集合
try:
    from app.modules.pantianshou_composition.qdrant_client import ensure_knowledge_collections
    ensure_knowledge_collections()
except Exception as e:
    import logging
    logging.getLogger(__name__).warning(f"知识库集合初始化失败: {e}")

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="书法碑帖字体认证系统 API"
)

# CORS配置
origins = ["http://localhost:3000"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载静态文件目录
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
os.makedirs(settings.STATIC_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory="data"), name="static")

# 注册路由
app.include_router(
    recognition.router,
    prefix=settings.API_V1_STR,
    tags=["识别"]
)

app.include_router(
    steles.router,
    prefix=settings.API_V1_STR,
    tags=["碑帖"]
)

app.include_router(
    tubi.router,
    prefix=settings.API_V1_STR,
    tags=["题跋分析"]
)

if composition is not None:
    app.include_router(
        composition.router,
        prefix=settings.API_V1_STR,
        tags=["潘天寿教你构图"]
    )
    # 知识库路由（平级）
    from app.modules.pantianshou_composition.knowledge_api import router as knowledge_router
    app.include_router(
        knowledge_router,
        prefix=settings.API_V1_STR + "/knowledge",
        tags=["知识库"]
    )

if _arrow_demo_router is not None:
    app.include_router(
        _arrow_demo_router,
        prefix=settings.API_V1_STR,
        tags=["起承转合 Demo"]
    )

if _qczh_router is not None:
    app.include_router(
        _qczh_router,
        prefix=settings.API_V1_STR,
        tags=["起承转合分析"]
    )

# 题跋内容学术分析路由
try:
    from app.api import content_analysis as content_analysis_router
    app.include_router(
        content_analysis_router.router,
        prefix=settings.API_V1_STR,
        tags=["题跋内容分析"]
    )
except Exception:
    import logging
    logging.getLogger(__name__).exception("Failed to import content_analysis module")


@app.get("/")
def root():
    return {
        "message": "书法碑帖字体认证系统 API",
        "version": settings.VERSION,
        "docs_url": "/docs"
    }


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "version": settings.VERSION
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=settings.SERVER_PORT)
