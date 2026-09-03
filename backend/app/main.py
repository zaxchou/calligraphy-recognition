from fastapi import FastAPI, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
import logging
import os

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(os.path.dirname(os.path.dirname(__file__)), "app.log"), encoding="utf-8"),
        logging.StreamHandler(),
    ],
)

from app.core.config import get_settings
settings = get_settings()

# 启动时检查：生产环境禁止默认 JWT Secret
if os.getenv("ENVIRONMENT") == "production":
    if settings.JWT_SECRET_KEY == "calligraphy-jwt-secret-change-in-production":
        raise RuntimeError("生产环境禁止使用默认 JWT_SECRET_KEY，请在 .env 中设置自定义值")
elif settings.JWT_SECRET_KEY == "calligraphy-jwt-secret-change-in-production":
    logging.getLogger(__name__).warning(
        "⚠️  JWT_SECRET_KEY 使用默认值，生产环境请在 .env 中修改！"
    )

from app.core.database import engine, Base, get_db
from sqlalchemy import text
from app.api import recognition, steles, tiba, seals, artists, artist_rules, auth, artist_claims, revisions, notifications, libraries, artist_changes, artwork_artists, artworks

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

# 创建数据库表
Base.metadata.create_all(bind=engine)

# 执行增量迁移（幂等）
from app.core.database import run_migrations
run_migrations()

# 确保常用查询字段有索引（给已有表加索引）
_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS ix_tubi_analyses_created_at ON tubi_analyses(created_at);
CREATE INDEX IF NOT EXISTS ix_tubi_analyses_artist ON tubi_analyses(artist);
CREATE INDEX IF NOT EXISTS ix_tubi_analyses_status ON tubi_analyses(status);
CREATE INDEX IF NOT EXISTS ix_tubi_analyses_album_name ON tubi_analyses(album_name);
CREATE INDEX IF NOT EXISTS ix_tubi_analyses_owner_id ON tubi_analyses(owner_id);
CREATE INDEX IF NOT EXISTS ix_tubi_analyses_visibility ON tubi_analyses(visibility);
CREATE INDEX IF NOT EXISTS ix_change_requests_artwork_id ON change_requests(artwork_id);
CREATE INDEX IF NOT EXISTS ix_change_requests_submitter_id ON change_requests(submitter_id);
CREATE INDEX IF NOT EXISTS ix_change_requests_library_id ON change_requests(library_id);
CREATE INDEX IF NOT EXISTS ix_artist_claims_user_id ON artist_claims(user_id);
CREATE INDEX IF NOT EXISTS ix_artist_claims_artist_name ON artist_claims(artist_name);
CREATE INDEX IF NOT EXISTS ix_artist_claims_status ON artist_claims(status);
"""
try:
    with engine.connect() as conn:
        for stmt in _INDEX_SQL.strip().split(";"):
            stmt = stmt.strip()
            if stmt:
                conn.execute(text(stmt))
        conn.commit()
    logging.getLogger(__name__).info("数据库索引已确保")
except Exception as e:
    logging.getLogger(__name__).warning(f"创建索引失败（非致命）: {e}")

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
    docs_url="/docs",
    description="书法碑帖字体认证系统 API"
)


@app.middleware("http")
async def redirect_root(request: Request, call_next):
    if request.url.path == "/" and request.method == "GET":
        return RedirectResponse(url="http://localhost:8080")
    return await call_next(request)


# 健康检查
@app.get("/api/v1/health")
async def health_check():
    return {"status": "ok", "version": settings.VERSION}


# CORS配置（从环境变量读取，逗号分隔；默认 * 允许所有）
_cors = settings.CORS_ALLOW_ORIGINS
origins = [o.strip() for o in _cors.split(",") if o.strip()] if _cors != "*" else ["*"]

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
os.makedirs(settings.DZI_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=settings.DATA_DIR), name="static")  # v2.0: 配置驱动，支持测试隔离
app.mount("/dzi", StaticFiles(directory=settings.DZI_DIR), name="dzi")

# 启动时清除旧的全量作品列表缓存，确保新数据被包含
try:
    from app.api.tiba import _clear_results_cache
    _clear_results_cache()
    logging.getLogger(__name__).info("已清除作品列表缓存")
except Exception:
    pass

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
    tiba.router,
    prefix=settings.API_V1_STR,
    tags=["题跋分析"]
)

app.include_router(
    seals.router,
    prefix=settings.API_V1_STR,
    tags=["印章管理"]
)

app.include_router(
    artists.router,
    prefix=settings.API_V1_STR,
    tags=["画家管理"]
)

app.include_router(
    artist_rules.router,
    prefix=settings.API_V1_STR,
    tags=["画家规则"]
)

# 画家编辑审核
app.include_router(
    artist_changes.router,
    prefix=settings.API_V1_STR,
    tags=["画家编辑审核"]
)

# 作品-画家关联
app.include_router(
    artwork_artists.router,
    prefix=settings.API_V1_STR,
    tags=["作品-画家关联"]
)

# 作品管理（作品库内）
app.include_router(
    artworks.router,
    prefix=settings.API_V1_STR,
    tags=["作品管理"]
)

app.include_router(
    auth.router,
    prefix=settings.API_V1_STR + "/auth",
    tags=["认证"]
)

# Phase 3: 画家认领路由
app.include_router(
    artist_claims.router,
    prefix=settings.API_V1_STR,
    tags=["画家认领"]
)

# Phase 1: 版本历史
app.include_router(
    revisions.router,
    prefix=settings.API_V1_STR,
    tags=["版本历史"]
)

# Phase 4: 通知
app.include_router(
    notifications.router,
    prefix=settings.API_V1_STR,
    tags=["通知"]
)

# Phase A: 画库管理
app.include_router(
    libraries.router,
    prefix=settings.API_V1_STR,
    tags=["作品库"]
)

# Phase 5: 管理后台
try:
    from app.api import admin as admin_api  # noqa: F811
    app.include_router(
        admin_api.router,
        prefix=settings.API_V1_STR,
        tags=["管理后台"],
    )
except Exception:
    import logging
    logging.getLogger(__name__).exception("Failed to import admin module")

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
    # Chat 会话管理路由（同 prefix）
    from app.modules.pantianshou_composition.chat_api import router as chat_api_router
    app.include_router(
        chat_api_router,
        prefix=settings.API_V1_STR + "/knowledge",
        tags=["聊天会话"]
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

# 墨林情绪引擎管理路由
try:
    from app.api import emotion_engine as emotion_engine_router
    app.include_router(
        emotion_engine_router.router,
        prefix=settings.API_V1_STR,
        tags=["墨林情绪引擎"]
    )
except Exception:
    import logging
    logging.getLogger(__name__).exception("Failed to import emotion_engine module")

# 图像相似搜索路由
try:
    from app.api import image_search as image_search_router
    app.include_router(
        image_search_router.router,
        prefix=settings.API_V1_STR + "/image-search",
        tags=["图像相似搜索"]
    )
except Exception:
    import logging
    logging.getLogger(__name__).exception("Failed to import image_search module")


@app.get("/")
def root():
    return {
        "message": "书法碑帖字体认证系统 API",
        "version": settings.VERSION,
        "docs_url": "/docs"
    }


@app.get(f"{settings.API_V1_STR}/site-settings")
def get_public_site_settings(db: Session = Depends(get_db)):
    """公开接口：获取站点全局设置（标题、副标题等），无需登录"""
    rows = db.execute(
        text("SELECT key, value FROM site_settings ORDER BY key")
    ).fetchall()
    result = {r[0]: r[1] for r in rows}
    result["readonly"] = "true" if settings.SITE_READONLY else "false"
    return {"settings": result}


@app.get("/health")
def health_check_root():
    return {
        "status": "healthy",
        "version": settings.VERSION
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=settings.SERVER_PORT)


# ════════════════════════════════════════════════════════════════
# 嵌入式 AI 识图 Worker（后台线程，无需单独启动进程）
# ════════════════════════════════════════════════════════════════
import threading
import time as _time

_stop_event = threading.Event()
_worker_started = False

def _recover_stale_jobs(logger):
    """启动时恢复：把卡在 processing 超过 2 分钟的任务重置为 queued"""
    from app.core.database import SessionLocal
    db = SessionLocal()
    try:
        from datetime import datetime as _dt, timedelta as _td
        cutoff = (_dt.now() - _td(minutes=2)).strftime("%Y-%m-%d %H:%M:%S")
        # Reset stuck jobs
        stuck_jobs = db.execute(
            text(
                "UPDATE tubi_jobs SET status='queued', last_error='recovered' WHERE status='processing' AND updated_at < :cutoff"
            ), {"cutoff": cutoff}
        )
        # Reset stuck analyses
        stuck_analyses = db.execute(
            text(
                "UPDATE tubi_analyses SET status='uploaded' WHERE status='analyzing' AND updated_at < :cutoff"
            ), {"cutoff": cutoff}
        )
        db.commit()
        if stuck_jobs.rowcount or stuck_analyses.rowcount:
            logger.info(f"恢复卡住任务: {stuck_jobs.rowcount} jobs + {stuck_analyses.rowcount} analyses")
    except Exception as e:
        logger.warning(f"恢复任务失败: {e}")
    finally:
        db.close()

def _embedded_worker_loop():
    """DB 轮询模式：直接查 tubi_jobs 表，不需要 Redis"""
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    from app.core.database import SessionLocal
    from app.models.tiba_analysis import TibaAnalysis
    from app.models.tiba_job import TibaJob

    logger = logging.getLogger("embedded_worker")
    logger.info("嵌入式 Worker 已启动（DB 轮询模式）")

    # 启动时恢复：把卡在 processing 超过 2 分钟的任务重置为 queued
    _recover_stale_jobs(logger)

    while not _stop_event.is_set():
        db = SessionLocal()
        image_id = None
        try:
            job = db.query(TibaJob).filter(TibaJob.status == "queued").order_by(TibaJob.created_at.asc()).first()
            if not job:
                _time.sleep(2)
                continue

            image_id = job.image_id
            job.status = "processing"
            db.commit()
        except Exception as e:
            logger.error(f"取任务失败: {e}")
            _time.sleep(3)
            continue
        finally:
            db.close()

        if not image_id:
            continue

        # process_one 内部自己管理 DB session
        try:
            from tiba_worker import process_one
            process_one(None, image_id)
        except Exception as e:
            logger.error(f"处理失败 {image_id}: {e}")

    logger.info("嵌入式 Worker 已停止")


@app.on_event("startup")
def _start_embedded_worker():
    global _worker_started
    if _worker_started:
        return
    _worker_started = True
    _stop_event.clear()
    t = threading.Thread(target=_embedded_worker_loop, daemon=True, name="tiba-worker")
    t.start()


@app.on_event("shutdown")
def _stop_embedded_worker():
    _stop_event.set()
