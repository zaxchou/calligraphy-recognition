"""
管理后台 API — /api/v1/admin

所有端点均需管理员 JWT 角色（admin / super_admin）。
不再依赖旧的 X-Admin-Key 方式。
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func as sqlfunc, text

from app.core.auth import require_admin_role, require_super_admin, get_user_permissions, ALL_PERMISSION_KEYS
from app.core.config import get_settings
from app.core.database import get_db
from app.models.user import User
from app.models.tubi_analysis import TubiAnalysis
from app.models.artist_claim import ArtistClaim
from app.models.role_permission import RolePermission

settings = get_settings()
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["管理后台"])


# ── Pydantic schemas ──

class UserOut(BaseModel):
    id: int
    nickname: Optional[str] = None
    avatar_url: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    role: str
    subscription_tier: str
    subscription_expires_at: Optional[str] = None
    storage_used_bytes: int = 0
    ai_calls_this_month: int = 0
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    class Config:
        from_attributes = True


class UserUpdateIn(BaseModel):
    nickname: Optional[str] = None
    role: Optional[str] = None
    subscription_tier: Optional[str] = None
    is_banned: Optional[bool] = None
    ai_calls_this_month: Optional[int] = None


class SubscriptionOut(BaseModel):
    user_id: int
    nickname: Optional[str] = None
    subscription_tier: str
    subscription_expires_at: Optional[str] = None
    created_at: Optional[str] = None


class SubscriptionCreateIn(BaseModel):
    user_id: int
    tier: str  # free / pro / premium
    duration_days: int = 30


class StatsOut(BaseModel):
    total_users: int
    total_artworks: int
    total_libraries: int
    total_storage_bytes: int
    ai_calls_today: int


class ConfigOut(BaseModel):
    free_ai_calls_per_month: int
    paid_ai_calls_per_month: int
    free_storage_bytes: int
    paid_storage_bytes: int
    free_library_limit: int
    ai_model: str


# ── Helper ──

def _user_to_dict(u: User) -> dict:
    return {
        "id": u.id,
        "uid": u.uid,
        "nickname": u.nickname,
        "avatar_url": u.avatar_url,
        "email": u.email,
        "phone": u.phone,
        "role": u.role,
        "subscription_tier": u.subscription_tier,
        "subscription_expires_at": u.subscription_expires_at.isoformat() if u.subscription_expires_at else None,
        "storage_used_bytes": u.storage_used_bytes or 0,
        "ai_calls_this_month": u.ai_calls_this_month or 0,
        "created_at": u.created_at.isoformat() if u.created_at else None,
        "updated_at": u.updated_at.isoformat() if u.updated_at else None,
    }


# ── 用户管理 ──

@router.get("/users")
def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None, description="按昵称/邮箱搜索"),
    role: Optional[str] = Query(None, description="按角色筛选"),
    tier: Optional[str] = Query(None, description="按订阅等级筛选"),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin_role),
):
    """用户列表（分页+搜索+筛选）"""
    q = db.query(User)

    if search:
        like = f"%{search}%"
        q = q.filter(
            (User.nickname.like(like)) | (User.email.like(like))
        )
    if role:
        q = q.filter(User.role == role)
    if tier:
        q = q.filter(User.subscription_tier == tier)

    total = q.count()
    offset = (page - 1) * page_size
    users = q.order_by(User.created_at.desc()).offset(offset).limit(page_size).all()

    return {
        "items": [_user_to_dict(u) for u in users],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.put("/users/{user_id}")
def update_user(
    user_id: int,
    body: UserUpdateIn,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin_role),
):
    """修改用户角色/订阅/封禁状态。
    不允许修改自己的角色。
    """
    if user_id == admin.id and body.role is not None:
        raise HTTPException(status_code=400, detail="不能修改自己的角色")

    u = db.query(User).filter(User.id == user_id).first()
    if not u:
        raise HTTPException(status_code=404, detail="用户不存在")

    if body.nickname is not None:
        u.nickname = body.nickname

    if body.role is not None:
        valid_roles = {"super_admin", "admin", "editor", "reader", "guest", "banned"}
        if body.role not in valid_roles:
            raise HTTPException(status_code=400, detail=f"无效角色，可选: {valid_roles}")
        # 不允许降级站长
        if user_id == 1 and body.role != "super_admin":
            raise HTTPException(status_code=400, detail="不能修改站长的角色")
        u.role = body.role

    if body.subscription_tier is not None:
        valid_tiers = {"free", "pro", "premium"}
        if body.subscription_tier not in valid_tiers:
            raise HTTPException(status_code=400, detail=f"无效订阅等级，可选: {valid_tiers}")
        u.subscription_tier = body.subscription_tier

    if body.is_banned is not None:
        if body.is_banned:
            u.role = "banned"
        elif u.role == "banned":
            u.role = "reader"  # 解封恢复为 reader

    if body.ai_calls_this_month is not None:
        u.ai_calls_this_month = body.ai_calls_this_month

    db.commit()
    db.refresh(u)
    logger.info("管理员 %d 更新了用户 %d: role=%s tier=%s", admin.id, user_id, u.role, u.subscription_tier)
    return _user_to_dict(u)


@router.delete("/users/{user_id}")
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin_role),
):
    """删除用户。禁止删除自己和站长（uid=1）。"""
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="不能删除自己的账号")
    if user_id == 1:
        raise HTTPException(status_code=400, detail="不能删除站长账号")

    u = db.query(User).filter(User.id == user_id).first()
    if not u:
        raise HTTPException(status_code=404, detail="用户不存在")

    nickname = u.nickname
    db.delete(u)
    db.commit()
    logger.info("管理员 %d 删除了用户 %d (%s)", admin.id, user_id, nickname)
    return {"ok": True, "message": f"用户「{nickname}」已删除"}


# ── 全局统计 ──

@router.get("/stats", response_model=StatsOut)
def get_stats(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin_role),
):
    """全局统计：总用户数、总作品数、今日AI调用、总存储用量"""
    total_users = db.query(sqlfunc.count(User.id)).scalar() or 0
    total_artworks = db.query(sqlfunc.count(TubiAnalysis.id)).scalar() or 0
    total_libraries = 0  # Phase 3: artwork_libraries 表已废弃
    total_storage = db.query(sqlfunc.sum(User.storage_used_bytes)).scalar() or 0
    ai_today = db.query(sqlfunc.sum(User.ai_calls_this_month)).scalar() or 0

    return StatsOut(
        total_users=total_users,
        total_artworks=total_artworks,
        total_libraries=total_libraries,
        total_storage_bytes=total_storage,
        ai_calls_today=ai_today,
    )


# ── 订阅管理 ──

@router.get("/subscriptions")
def list_subscriptions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    tier: Optional[str] = Query(None, description="按订阅等级筛选"),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin_role),
):
    """订阅列表（从 users 表查询订阅数据）"""
    q = db.query(User).filter(User.subscription_expires_at.isnot(None))

    if tier:
        q = q.filter(User.subscription_tier == tier)

    total = q.count()
    offset = (page - 1) * page_size
    users = q.order_by(User.subscription_expires_at.desc()).offset(offset).limit(page_size).all()

    items = []
    for u in users:
        items.append({
            "user_id": u.id,
            "nickname": u.nickname,
            "subscription_tier": u.subscription_tier,
            "subscription_expires_at": u.subscription_expires_at.isoformat() if u.subscription_expires_at else None,
            "created_at": u.created_at.isoformat() if u.created_at else None,
        })

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post("/subscriptions")
def create_subscription(
    body: SubscriptionCreateIn,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin_role),
):
    """手动为用户开通/续期订阅"""
    valid_tiers = {"free", "pro", "premium"}
    if body.tier not in valid_tiers:
        raise HTTPException(status_code=400, detail=f"无效订阅等级，可选: {valid_tiers}")

    u = db.query(User).filter(User.id == body.user_id).first()
    if not u:
        raise HTTPException(status_code=404, detail="用户不存在")

    now = datetime.now(timezone.utc)
    # 如果已有未过期订阅，在现有到期时间基础上叠加
    if u.subscription_expires_at and u.subscription_expires_at > now:
        new_expires = u.subscription_expires_at + timedelta(days=body.duration_days)
    else:
        new_expires = now + timedelta(days=body.duration_days)

    u.subscription_tier = body.tier
    u.subscription_expires_at = new_expires
    db.commit()
    db.refresh(u)

    logger.info(
        "管理员 %d 为用户 %d 开通订阅 tier=%s expires=%s",
        admin.id, body.user_id, body.tier, new_expires.isoformat(),
    )
    return {
        "user_id": u.id,
        "nickname": u.nickname,
        "subscription_tier": u.subscription_tier,
        "subscription_expires_at": u.subscription_expires_at.isoformat() if u.subscription_expires_at else None,
    }


# ── 系统配置 ──

@router.get("/config", response_model=ConfigOut)
def get_config(admin: User = Depends(require_admin_role)):
    """返回当前系统的配额与模型配置（供管理面板展示）"""
    return ConfigOut(
        free_ai_calls_per_month=settings.FREE_AI_CALLS_PER_MONTH,
        paid_ai_calls_per_month=settings.PAID_AI_CALLS_PER_MONTH,
        free_storage_bytes=settings.FREE_STORAGE_BYTES,
        paid_storage_bytes=settings.PAID_STORAGE_BYTES,
        free_library_limit=settings.FREE_LIBRARY_LIMIT,
        ai_model=settings.SILICONFLOW_MODEL or settings.DEEPSEEK_TEXT_MODEL or "deepseek-v4-flash",
    )


# ── 权限配置 ──

class PermissionsSaveIn(BaseModel):
    permissions: dict  # { "admin": [...], "editor": [...], "reader": [...] }


@router.get("/permissions")
def list_permissions(
    db: Session = Depends(get_db),
    admin: User = Depends(require_super_admin),
):
    """获取所有非站长角色的权限配置"""
    rows = db.query(RolePermission).all()
    result = {"admin": [], "editor": [], "reader": []}
    for r in rows:
        if r.role in result:
            result[r.role].append(r.permission_key)
    return {"permissions": result, "all_keys": ALL_PERMISSION_KEYS}


@router.put("/permissions")
def save_permissions(
    body: PermissionsSaveIn,
    db: Session = Depends(get_db),
    admin: User = Depends(require_super_admin),
):
    """批量保存权限配置（全量替换）"""
    valid_roles = {"admin", "editor", "reader"}
    for role, keys in body.permissions.items():
        if role not in valid_roles:
            raise HTTPException(status_code=400, detail=f"无效角色: {role}")
        # 删除旧权限
        db.query(RolePermission).filter(RolePermission.role == role).delete()
        # 插入新权限
        for key in keys:
            if key not in ALL_PERMISSION_KEYS:
                raise HTTPException(status_code=400, detail=f"无效权限键: {key}")
            db.add(RolePermission(role=role, permission_key=key))
    db.commit()
    logger.info("管理员 %d 更新了角色权限配置", admin.id)
    return {"ok": True, "message": "权限配置已保存"}


@router.get("/my-permissions")
def my_permissions(perms: dict = Depends(get_user_permissions)):
    """返回当前登录用户的权限列表（供前端侧边栏渲染）"""
    return perms


# ── 站点设置 ──

class SiteSettingsUpdate(BaseModel):
    settings: dict  # { "title": "墨林百科", "subtitle": "...", ... }


@router.get("/site-settings")
def get_admin_site_settings(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin_role),
):
    """管理员读取站点设置"""
    rows = db.execute(
        text("SELECT key, value FROM site_settings ORDER BY key")
    ).fetchall()
    return {"settings": {r[0]: r[1] for r in rows}}


@router.put("/site-settings")
def update_site_settings(
    body: SiteSettingsUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_super_admin),
):
    """超级管理员更新站点设置"""
    for key, value in body.settings.items():
        db.execute(
            text("INSERT INTO site_settings (key, value, updated_at) VALUES (:key, :value, CURRENT_TIMESTAMP) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = CURRENT_TIMESTAMP"),
            {"key": key, "value": value},
        )
    db.commit()
    logger.info("管理员 %d 更新了站点设置", admin.id)
    return {"ok": True, "message": "站点设置已更新"}


# ═══════════════════════════════════════════════════════════════════
# 墨林情绪引擎 v3 — 管理后台 API
# ═══════════════════════════════════════════════════════════════════

class EmotionLogQuery(BaseModel):
    page: int = 1
    page_size: int = 20
    method: Optional[str] = None   # lexicon_only / llm_corrected
    polarity: Optional[str] = None  # positive / negative / neutral
    artist: Optional[str] = None
    search: Optional[str] = None


@router.get("/emotion-logs")
def list_emotion_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    method: Optional[str] = Query(None, description="分析方法：lexicon_only / llm_corrected"),
    polarity: Optional[str] = Query(None, description="极性：positive / negative / neutral"),
    artist: Optional[str] = Query(None, description="按画家筛选"),
    search: Optional[str] = Query(None, description="按标题搜索"),
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin_role),
):
    """情绪分析日志列表（分页 + 筛选）"""
    import json as _json

    q = db.query(TubiAnalysis).filter(
        TubiAnalysis.content_analysis.isnot(None),
        TubiAnalysis.content_analysis != "",
        TubiAnalysis.content_analysis != "{}",
    )

    if artist:
        q = q.filter(TubiAnalysis.artist == artist)
    if search:
        q = q.filter(TubiAnalysis.title.contains(search))

    total = q.count()
    offset = (page - 1) * page_size
    records = q.order_by(TubiAnalysis.id.desc()).offset(offset).limit(page_size).all()

    items = []
    for r in records:
        try:
            ca = _json.loads(r.content_analysis) if r.content_analysis else {}
        except (_json.JSONDecodeError, TypeError):
            ca = {}

        am = ca.get("analysis_method", "")
        cs = ca.get("combined_sentiment", {}) if isinstance(ca.get("combined_sentiment"), dict) else {}
        ls = ca.get("lexicon_scores", {}) if isinstance(ca.get("lexicon_scores"), dict) else {}
        la = ca.get("llm_analysis", {}) if isinstance(ca.get("llm_analysis"), dict) else {}

        # Apply method filter
        if method and am != method:
            continue
        # Apply polarity filter
        item_polarity = cs.get("polarity", "")
        if polarity and item_polarity != polarity:
            continue

        items.append({
            "id": r.id,
            "image_id": r.image_id,
            "title": r.title,
            "artist": r.artist,
            "year": r.year,
            "analysis_method": am,
            "analysis_version": ca.get("analysis_version"),
            "lexicon_combined": ls.get("combined_normalized"),
            "llm_delta": la.get("combined", {}).get("delta") if isinstance(la.get("combined"), dict) else None,
            "final_score": cs.get("combined_score"),
            "vader_normalized": cs.get("vader_normalized"),
            "polarity": item_polarity,
            "reasoning": cs.get("reasoning", ""),
        })

    # Re-count after filtering
    return {
        "items": items,
        "total": len(items),  # Close enough for admin use; full count would be expensive
        "page": page,
        "page_size": page_size,
    }


@router.get("/emotion-logs/{record_id}")
def get_emotion_log_detail(
    record_id: int,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin_role),
):
    """单件作品完整情绪分析记录（逐维度详情）"""
    import json as _json

    r = db.query(TubiAnalysis).filter(TubiAnalysis.id == record_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="记录不存在")

    try:
        ca = _json.loads(r.content_analysis) if r.content_analysis else {}
    except (_json.JSONDecodeError, TypeError):
        ca = {}

    ls = ca.get("lexicon_scores", {}) if isinstance(ca.get("lexicon_scores"), dict) else {}
    la = ca.get("llm_analysis", {}) if isinstance(ca.get("llm_analysis"), dict) else {}
    cs = ca.get("combined_sentiment", {}) if isinstance(ca.get("combined_sentiment"), dict) else {}

    # Build per-dimension breakdown
    dims = ["text", "spatial", "painting", "size", "period", "seal", "theme", "brush_ink"]
    dimensions = []
    for dim in dims:
        lex = ls.get(dim, {}) if isinstance(ls, dict) else {}
        corr = la.get("corrections", {}).get(dim, {}) if isinstance(la.get("corrections"), dict) else {}
        dimensions.append({
            "key": dim,
            "lexicon_raw": lex.get("raw") if isinstance(lex, dict) else None,
            "lexicon_normalized": lex.get("normalized") if isinstance(lex, dict) else None,
            "lexicon_confidence": lex.get("confidence") if isinstance(lex, dict) else None,
            "lexicon_has_data": lex.get("has_data") if isinstance(lex, dict) else False,
            "llm_delta": corr.get("delta") if isinstance(corr, dict) else None,
            "llm_adjusted": corr.get("adjusted") if isinstance(corr, dict) else None,
            "llm_confidence": corr.get("confidence") if isinstance(corr, dict) else None,
            "llm_reasoning": corr.get("reasoning", "") if isinstance(corr, dict) else "",
            "key_phrases": corr.get("key_phrases", []) if isinstance(corr, dict) else [],
        })

    return {
        "id": r.id,
        "image_id": r.image_id,
        "title": r.title,
        "artist": r.artist,
        "year": r.year,
        "inscription_content": (r.inscription_content or "")[:500],
        "analysis_method": ca.get("analysis_method", ""),
        "analysis_version": ca.get("analysis_version"),
        "lexicon_scores": ls,
        "llm_analysis": la,
        "combined_sentiment": cs,
        "dimensions": dimensions,
        "weights": cs.get("weights") if isinstance(cs, dict) else {},
    }


@router.post("/emotion-logs/{record_id}/reanalyze")
async def reanalyze_emotion(
    record_id: int,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin_role),
):
    """手动触发单件作品的 LLM 情绪重分析"""
    import json as _json

    r = db.query(TubiAnalysis).filter(TubiAnalysis.id == record_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="记录不存在")
    if not r.inscription_content or len(r.inscription_content.strip()) < 2:
        raise HTTPException(status_code=400, detail="该记录无有效题跋内容")

    from app.services.molin_engine import analyze as molin_analyze
    from app.services.llm_emotion_corrector import judge_independently

    try:
        ca = _json.loads(r.content_analysis) if r.content_analysis else {}
    except (_json.JSONDecodeError, TypeError):
        ca = {}

    old_themes = ca.get("themes", []) if isinstance(ca, dict) else []

    # 1. Run lexicon baseline (include spatial/painting data from old analysis)
    spatial_emotion = (ca.get("spatial_emotion") if isinstance(ca, dict) else None)
    painting_matches = ((ca.get("v4_signals") or {}).get("painting", []) if isinstance(ca, dict) else [])
    if not painting_matches:
        painting_matches = ((ca.get("signals") or {}).get("painting", []) if isinstance(ca, dict) else [])

    result = molin_analyze(
        text=r.inscription_content,
        spatial_emotion=spatial_emotion,
        painting_matches=painting_matches,
        width_cm=r.artwork_width_cm,
        height_cm=r.artwork_height_cm,
        year=r.year,
        artist=r.artist,
        seal_content=r.seal_content,
        themes=old_themes,
    )

    # Build lexicon_scores dict
    lexicon_scores = {
        "version": "3.1",
        "text": {"raw": result.text.raw, "normalized": result.text.normalized, "confidence": result.text.confidence, "has_data": result.text.has_data},
        "spatial": {"raw": result.spatial.raw, "normalized": result.spatial.normalized, "confidence": result.spatial.confidence, "has_data": result.spatial.has_data},
        "painting": {"raw": result.painting.raw, "normalized": result.painting.normalized, "confidence": result.painting.confidence, "has_data": result.painting.has_data},
        "size": {"raw": result.size.raw, "normalized": result.size.normalized, "confidence": result.size.confidence, "has_data": result.size.has_data},
        "period": {"raw": result.period.raw, "normalized": result.period.normalized, "confidence": result.period.confidence, "has_data": result.period.has_data},
        "seal": {"raw": result.seal.raw, "normalized": result.seal.normalized, "confidence": result.seal.confidence, "has_data": result.seal.has_data},
        "theme": {"raw": result.theme.raw, "normalized": result.theme.normalized, "confidence": result.theme.confidence, "has_data": result.theme.has_data},
        "brush_ink": {"raw": result.brush_ink.raw, "normalized": result.brush_ink.normalized, "confidence": result.brush_ink.confidence, "has_data": result.brush_ink.has_data},
        "combined_raw": result.combined_raw,
        "combined_normalized": result.combined_normalized,
    }

    # 2. Run LLM 裁判（独立解读，不看词库分）
    from app.services.molin_engine import vader_normalize, classify_complex_polarity, compute_conflict_score, DimensionResult
    try:
        judge_result = await judge_independently(
            text=r.inscription_content,
            artist=r.artist,
            year=r.year,
            themes=old_themes,
        )
    except Exception as e:
        logger.warning("LLM judge failed for record %d: %s", record_id, e)
        judge_result = None

    # 3. 用 LLM 裁判结果覆盖词库（裁判擅长文字/时期/主题，空间/画材/尺寸/印章用词库）
    if judge_result and judge_result.get("dimension_scores"):
        jd = judge_result["dimension_scores"]
        jc = judge_result.get("combined", {})

        # 裁判擅长的维度：文字、时期、主题
        # 词库擅长的维度：空间、画材、尺寸、印章（有结构化数据支撑）
        from app.services.molin_engine import vader_normalize, classify_polarity, compute_conflict_score, DimensionResult

        # 逐维度决策：裁判有明确判断就用裁判，否则用词库
        def _best_raw(key, lexicon_raw):
            j = jd.get(key) or {}
            jr = j.get("raw", 0) or 0
            jc_val = j.get("confidence", 0) or 0
            # 裁判置信度高且非零 → 用裁判；否则用词库
            if abs(jr) > 0.1 and jc_val >= 0.5:
                return jr
            return lexicon_raw

        dim_raws = {}
        dim_pols = {}
        judge_dims = []
        dim_map = {"text": result.text, "spatial": result.spatial, "painting": result.painting,
                    "size": result.size, "period": result.period, "seal": result.seal,
                    "theme": result.theme, "brush_ink": result.brush_ink}
        for key in ["text","spatial","painting","size","period","seal","theme","brush_ink"]:
            lexicon_raw = getattr(dim_map[key], "raw", 0) or 0
            raw = _best_raw(key, lexicon_raw)
            dim_raws[key] = raw
            norm = vader_normalize(raw)
            dim_pols[key] = classify_polarity(norm)
            judge_dims.append(DimensionResult(name=key, raw=raw, normalized=norm,
                has_data=dim_map[key].has_data or abs(raw) > 0.01))

        conflict = compute_conflict_score(judge_dims)

        # 重新加权计算综合分
        w = result.weights_used
        ws, wt = 0.0, 0.0
        for key in dim_raws:
            ew = w.get(key, 0) * getattr(dim_map[key], "confidence", 0.5)
            ws += ew * dim_raws[key]
            wt += ew
        llm_combined_raw = ws / wt if wt > 0 else 0
        llm_combined_norm = vader_normalize(llm_combined_raw)
        llm_polarity = classify_complex_polarity(llm_combined_norm, dim_pols)

        analysis_method = "llm_corrected"
    else:
        # LLM 失败 → 降级到词库
        jd = {}
        jc = {"summary": "LLM裁判不可用，使用词库基线分", "polarity": result.polarity}
        llm_combined_raw = result.combined_raw
        llm_combined_norm = result.combined_normalized
        llm_polarity = result.polarity
        dim_pols = result.dimension_polarities
        conflict = result.conflict_score
        analysis_method = "lexicon_only"

    # 4. Update DB
    new_ca = dict(ca) if isinstance(ca, dict) else {}
    new_ca["lexicon_scores"] = lexicon_scores
    new_ca["llm_judge"] = judge_result  # v3.2: 存储完整裁判结果
    new_ca["llm_analysis"] = judge_result  # 兼容旧字段名
    new_ca["analysis_method"] = analysis_method
    new_ca["analysis_version"] = 3
    new_ca["combined_sentiment"] = {
        "polarity": llm_polarity,
        "reasoning": result.reasoning,
        "text_score": jd.get("text", {}).get("raw", result.text.raw) if jd else result.text.raw,
        "spatial_score": jd.get("spatial", {}).get("raw", result.spatial.raw) if jd else result.spatial.raw,
        "painting_score": jd.get("painting", {}).get("raw", result.painting.raw) if jd else result.painting.raw,
        "size_score": jd.get("size", {}).get("raw", result.size.raw) if jd else result.size.raw,
        "time_score": jd.get("period", {}).get("raw", result.period.raw) if jd else result.period.raw,
        "seal_score": jd.get("seal", {}).get("raw", result.seal.raw) if jd else result.seal.raw,
        "theme_score": jd.get("theme", {}).get("raw", result.theme.raw) if jd else result.theme.raw,
        "brush_ink_score": jd.get("brush_ink", {}).get("raw", result.brush_ink.raw) if jd else result.brush_ink.raw,
        "combined_score": round(llm_combined_raw, 2),
        "vader_normalized": round(llm_combined_norm, 3),
        "vader_alpha": 8.0,
        "weights": result.weights_used,
        "method": analysis_method,
        "dimension_polarities": dim_pols,
        "conflict_score": conflict,
        "has_data": {
            "text": result.text.has_data,
            "spatial": result.spatial.has_data,
            "painting": result.painting.has_data,
            "size": result.size.has_data,
            "period": result.period.has_data,
            "seal": result.seal.has_data,
            "theme": result.theme.has_data,
            "brush_ink": result.brush_ink.has_data,
        },
        "dimension_details": {
            "text": {"signals": result.text.signals},
            "spatial": {"signals": result.spatial.signals},
            "painting": {"signals": result.painting.signals},
            "size": {},
            "period": {},
            "seal": {"signals": result.seal.signals},
            "theme": {"signals": result.theme.signals},
        },
    }

    r.content_analysis = _json.dumps(new_ca, ensure_ascii=False)
    db.commit()

    return {
        "ok": True,
        "record_id": record_id,
        "analysis_method": analysis_method,
        "lexicon_combined": result.combined_normalized,
        "final_score": round(llm_combined_raw, 2),
        "polarity": llm_polarity,
    }


@router.get("/emotion-stats")
def get_emotion_stats(
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin_role),
):
    """情绪引擎 v3 统计：词库 vs LLM 校正量分布"""
    import json as _json

    records = db.query(TubiAnalysis).filter(
        TubiAnalysis.content_analysis.isnot(None),
        TubiAnalysis.content_analysis != "",
        TubiAnalysis.content_analysis != "{}",
    ).all()

    total = len(records)
    lexicon_count = 0
    llm_corrected_count = 0
    polarity_counts = {"positive": 0, "negative": 0, "neutral": 0, "ambiguous": 0}
    delta_distribution = {">0.5": 0, "0.2-0.5": 0, "-0.2-0.2": 0, "-0.5--0.2": 0, "<-0.5": 0}
    score_distribution = {"strong_positive": 0, "mild_positive": 0, "neutral": 0, "mild_negative": 0, "strong_negative": 0}

    for r in records:
        try:
            ca = _json.loads(r.content_analysis) if r.content_analysis else {}
        except (_json.JSONDecodeError, TypeError):
            continue

        am = ca.get("analysis_method", "")
        if am == "lexicon_only":
            lexicon_count += 1
        elif am == "llm_corrected":
            llm_corrected_count += 1

        cs = ca.get("combined_sentiment", {}) if isinstance(ca.get("combined_sentiment"), dict) else {}
        pol = cs.get("polarity", "")
        if pol in polarity_counts:
            polarity_counts[pol] += 1

        # Delta distribution
        if isinstance(ca.get("llm_analysis"), dict):
            combined_la = ca["llm_analysis"].get("combined", {})
            delta = combined_la.get("delta", 0) if isinstance(combined_la, dict) else 0
            if delta > 0.5:
                delta_distribution[">0.5"] += 1
            elif delta > 0.2:
                delta_distribution["0.2-0.5"] += 1
            elif delta >= -0.2:
                delta_distribution["-0.2-0.2"] += 1
            elif delta >= -0.5:
                delta_distribution["-0.5--0.2"] += 1
            else:
                delta_distribution["<-0.5"] += 1

        # Score distribution
        score = cs.get("combined_score", 0)
        if score > 1.5:
            score_distribution["strong_positive"] += 1
        elif score > 0:
            score_distribution["mild_positive"] += 1
        elif score == 0:
            score_distribution["neutral"] += 1
        elif score > -1.5:
            score_distribution["mild_negative"] += 1
        else:
            score_distribution["strong_negative"] += 1

    return {
        "total_analyzed": total,
        "analysis_methods": {
            "lexicon_only": lexicon_count,
            "llm_corrected": llm_corrected_count,
        },
        "polarity_distribution": polarity_counts,
        "delta_distribution": delta_distribution,
        "score_distribution": score_distribution,
    }
