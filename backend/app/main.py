"""
应用入口（v2.0 重构）：
- 启动副作用（建表/迁移/索引/Qdrant/缓存清理/嵌入 Worker）全部收进 lifespan，
  import app.main 不再有副作用（测试可隔离）
- 路由注册表驱动；可选重依赖路由集中降级管理
"""
import json
import logging
import os
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from app.services.ai_translation import translate_json
from sqlalchemy import text
from sqlalchemy.orm import Session

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(os.path.dirname(os.path.dirname(__file__)), "app.log"), encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

from app.core.config import DATA_DIR, get_settings
settings = get_settings()

# 启动前检查：生产环境禁止默认 JWT Secret / 允许的 mock 状态
if os.getenv("ENVIRONMENT") == "production":
    if settings.JWT_SECRET_KEY == "calligraphy-jwt-secret-change-in-production":
        raise RuntimeError("生产环境禁止使用默认 JWT_SECRET_KEY，请在 .env 中设置自定义值")
elif settings.JWT_SECRET_KEY == "calligraphy-jwt-secret-change-in-production":
    logger.warning("⚠️  JWT_SECRET_KEY 使用默认值，生产环境请在 .env 中修改！")

from app.core.database import engine, Base, get_db, run_migrations
from app.api import (
    recognition, steles, tiba, seals, artists, artist_rules, auth,
    artist_claims, revisions, notifications, libraries, artist_changes,
    artwork_artists, artworks,
)


# ════════════════════════════════════════════════════════════════
# 可选路由（重依赖缺失时降级禁用，不拖垮整体启动）
# ════════════════════════════════════════════════════════════════
def _try_import_router(module_path: str, attr: str = "router"):
    try:
        module = __import__(module_path, fromlist=[attr])
        return getattr(module, attr)
    except Exception:
        logger.exception("Failed to import %s; 相关路由已禁用", module_path)
        return None


composition_router = _try_import_router("app.api.composition")
knowledge_router = _try_import_router(
    "app.modules.pantianshou_composition.knowledge_api") if composition_router else None
chat_router = _try_import_router(
    "app.modules.pantianshou_composition.chat_api") if composition_router else None
arrow_demo_router = _try_import_router(
    "app.modules.pantianshou_composition.arrow_demo_api")
qczh_router = _try_import_router(
    "app.modules.pantianshou_composition.qichengzhuanhe_api")
content_analysis_router = _try_import_router("app.api.content_analysis")
emotion_engine_router = _try_import_router("app.api.emotion_engine")
image_search_router = _try_import_router("app.api.image_search")
admin_router = _try_import_router("app.api.admin")


# ════════════════════════════════════════════════════════════════
# 启动副作用（lifespan 管理）
# ════════════════════════════════════════════════════════════════
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


def _ensure_indexes():
    try:
        with engine.connect() as conn:
            for stmt in _INDEX_SQL.strip().split(";"):
                stmt = stmt.strip()
                if stmt:
                    conn.execute(text(stmt))
            conn.commit()
        logger.info("数据库索引已确保")
    except Exception as e:
        logger.warning(f"创建索引失败（非致命）: {e}")


def _init_knowledge_collections():
    try:
        from app.modules.pantianshou_composition.qdrant_client import ensure_knowledge_collections
        ensure_knowledge_collections()
    except Exception as e:
        logger.warning(f"知识库集合初始化失败: {e}")


def _clear_results_cache_safe():
    try:
        from app.api.tiba import _clear_results_cache
        _clear_results_cache()
        logger.info("已清除作品列表缓存")
    except Exception:
        pass


# ── 嵌入式 AI 识图 Worker（后台线程；Phase 3 将拆为独立进程） ──
_stop_event = threading.Event()


def _recover_stale_jobs(log):
    """启动时恢复：把卡在 processing 超过 2 分钟的任务重置为 queued"""
    from app.core.database import SessionLocal
    db = SessionLocal()
    try:
        from datetime import datetime as _dt, timedelta as _td
        cutoff = (_dt.now() - _td(minutes=2)).strftime("%Y-%m-%d %H:%M:%S")
        db.execute(text(
            "UPDATE tubi_jobs SET status='queued', last_error='recovered' WHERE status='processing' AND updated_at < :cutoff"
        ), {"cutoff": cutoff})
        stuck = db.execute(text(
            "UPDATE tubi_analyses SET status='uploaded' WHERE status='analyzing' AND updated_at < :cutoff"
        ), {"cutoff": cutoff})
        db.commit()
        if stuck.rowcount:
            log.info(f"恢复卡住任务: {stuck.rowcount} analyses")
    except Exception as e:
        log.warning(f"恢复任务失败: {e}")
    finally:
        db.close()


def _embedded_worker_loop():
    """DB 轮询模式：直接查 tubi_jobs 表，不需要 Redis"""
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from app.core.database import SessionLocal
    from app.models.tiba_job import TibaJob

    log = logging.getLogger("embedded_worker")
    log.info("嵌入式 Worker 已启动（DB 轮询模式）")
    _recover_stale_jobs(log)

    import time as _time
    while not _stop_event.is_set():
        db = SessionLocal()
        image_id = None
        try:
            job = db.query(TibaJob).filter(TibaJob.status == "queued").order_by(
                TibaJob.created_at.asc()).first()
            if not job:
                _time.sleep(2)
                continue
            image_id = job.image_id
            job.status = "processing"
            db.commit()
        except Exception as e:
            log.error(f"取任务失败: {e}")
            _time.sleep(3)
            continue
        finally:
            db.close()

        if not image_id:
            continue

        try:
            from tiba_worker import process_one
            process_one(None, image_id)
        except Exception as e:
            log.error(f"处理失败 {image_id}: {e}")

    log.info("嵌入式 Worker 已停止")


@asynccontextmanager
async def lifespan(app: FastAPI):
    _stop_event.clear()  # 复位停止信号（防二次进入 lifespan 时 Worker 静默失效）
    Base.metadata.create_all(bind=engine)
    run_migrations()
    _ensure_indexes()
    _init_knowledge_collections()
    _clear_results_cache_safe()
    # v2.0 §2.3: 生产用独立 worker 进程（app/worker_main.py + compose service）时，
    # 设 TIBA_EMBEDDED_WORKER=false 关闭内嵌线程；本地开发默认 true 保持一键启动
    if os.getenv("TIBA_EMBEDDED_WORKER", "true").lower() in ("1", "true", "yes", "y"):
        worker = threading.Thread(target=_embedded_worker_loop, daemon=True, name="tiba-worker")
        worker.start()
    else:
        logger.info("TIBA_EMBEDDED_WORKER=false，内嵌 Worker 未启动（由独立进程消费队列）")
    yield
    # ── shutdown ──
    _stop_event.set()


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    docs_url="/docs",
    description="书法碑帖字体认证系统 API",
    lifespan=lifespan,
)


# 报错信息国际化：Accept-Language: en 时 HTTPException 的中文 detail 翻译为英文
@app.exception_handler(StarletteHTTPException)
async def _i18n_http_exception_handler(request: Request, exc: StarletteHTTPException):
    from fastapi.responses import JSONResponse
    from app.core.error_i18n import translate_detail
    headers = getattr(exc, "headers", None)
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": translate_detail(exc.detail, request)},
        headers=headers,
    )


@app.middleware("http")
async def redirect_root(request: Request, call_next):
    if request.url.path == "/" and request.method == "GET":
        return RedirectResponse(url="http://localhost:8080")
    return await call_next(request)


# ── AI 分析内容读时英文化：EN 请求把 tiba/content-analysis 响应里的中文换成缓存译文 ──
@app.middleware("http")
async def ai_content_i18n(request: Request, call_next):
    response = await call_next(request)
    try:
        path = request.url.path
        lang = (request.headers.get("accept-language") or "").lower()
        if (request.method == "GET" and lang.startswith("en")
                and (path.startswith("/api/v1/tiba/") or path.startswith("/api/v1/content-analysis"))
                and "application/json" in response.headers.get("content-type", "")):
            body = b""
            async for chunk in response.body_iterator:
                body += chunk
            data = json.loads(body)
            from app.core.database import SessionLocal
            db = SessionLocal()
            try:
                data = translate_json(data, db)
            finally:
                db.close()
            new_body = json.dumps(data, ensure_ascii=False).encode()
            headers = {k: v for k, v in response.headers.items() if k.lower() != "content-length"}
            from starlette.responses import Response as StarletteResponse
            return StarletteResponse(content=new_body, status_code=response.status_code,
                                     headers=headers, media_type="application/json")
    except Exception:  # noqa: BLE001 — 翻译层故障必须降级为原响应
        logger.exception("ai_content_i18n failed; serving original response")
    return response


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
app.mount("/static", StaticFiles(directory=DATA_DIR), name="static")  # v2.0: 配置驱动，支持测试隔离
app.mount("/dzi", StaticFiles(directory=settings.DZI_DIR), name="dzi")


# ════════════════════════════════════════════════════════════════
# 路由注册（表驱动）
# ════════════════════════════════════════════════════════════════
_V1 = settings.API_V1_STR
_ROUTER_TABLE = [
    (recognition.router, _V1, ["识别"]),
    (steles.router, _V1, ["碑帖"]),
    (tiba.router, _V1, ["题跋分析"]),
    (seals.router, _V1, ["印章管理"]),
    (artists.router, _V1, ["画家管理"]),
    (artist_rules.router, _V1, ["画家规则"]),
    (artist_changes.router, _V1, ["画家编辑审核"]),
    (artwork_artists.router, _V1, ["作品-画家关联"]),
    (artworks.router, _V1, ["作品管理"]),
    (auth.router, _V1 + "/auth", ["认证"]),
    (artist_claims.router, _V1, ["画家认领"]),
    (revisions.router, _V1, ["版本历史"]),
    (notifications.router, _V1, ["通知"]),
    (libraries.router, _V1, ["作品库"]),
]

for _router, _prefix, _tags in _ROUTER_TABLE:
    app.include_router(_router, prefix=_prefix, tags=_tags)

if admin_router is not None:
    app.include_router(admin_router, prefix=_V1, tags=["管理后台"])
if composition_router is not None:
    app.include_router(composition_router, prefix=_V1, tags=["潘天寿教你构图"])
if knowledge_router is not None:
    app.include_router(knowledge_router, prefix=_V1 + "/knowledge", tags=["知识库"])
if chat_router is not None:
    app.include_router(chat_router, prefix=_V1 + "/knowledge", tags=["聊天会话"])
if arrow_demo_router is not None:
    app.include_router(arrow_demo_router, prefix=_V1, tags=["起承转合 Demo"])
if qczh_router is not None:
    app.include_router(qczh_router, prefix=_V1, tags=["起承转合分析"])
if content_analysis_router is not None:
    app.include_router(content_analysis_router, prefix=_V1, tags=["题跋内容分析"])
if emotion_engine_router is not None:
    app.include_router(emotion_engine_router, prefix=_V1, tags=["墨林情绪引擎"])
if image_search_router is not None:
    app.include_router(image_search_router, prefix=_V1 + "/image-search", tags=["图像相似搜索"])


@app.get("/")
def root():
    return {
        "message": "书法碑帖字体认证系统 API",
        "version": settings.VERSION,
        "docs_url": "/docs"
    }


@app.get(f"{_V1}/site-settings")
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
