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
    composition = None

settings = get_settings()

# 创建数据库表
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="书法碑帖字体认证系统 API"
)

# CORS配置
origins = [x.strip() for x in str(getattr(settings, "CORS_ALLOW_ORIGINS", "*") or "*").split(",") if x.strip()]
if not origins:
    origins = ["*"]
allow_credentials = False if "*" in origins else True

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=allow_credentials,
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
    uvicorn.run(app, host="0.0.0.0", port=8001)
