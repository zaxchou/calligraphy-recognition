"""
墨林情绪引擎管理 API
────────────────────────────────────────
提供词典管理、画家规则管理、校准工具的接口
"""

import json
import os
from typing import Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.core.auth import require_editor
from app.services.emotion_lexicon_loader import get_lexicon

router = APIRouter(prefix="/emotion-engine", tags=["emotion-engine"])


# ── 数据模型 ──────────────────────────────────────────────────────────

class LexiconEntry(BaseModel):
    word: str
    score: int
    category: str
    source: str = "manual"
    note: Optional[str] = None


class LexiconUpdate(BaseModel):
    score: Optional[int] = None
    category: Optional[str] = None
    note: Optional[str] = None


# ── 词典管理 ──────────────────────────────────────────────────────────

@router.get("/lexicon")
async def get_lexicon_entries(
    category: Optional[str] = Query(None, description="按分类筛选"),
    source: Optional[str] = Query(None, description="按来源筛选"),
    keyword: Optional[str] = Query(None, description="关键词搜索"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=10, le=200),
):
    """获取词典条目列表"""
    lexicon = get_lexicon()
    entries = []

    for word, data in lexicon.entries.items():
        if category and data.get("category") != category:
            continue
        if source and data.get("source") != source:
            continue
        if keyword and keyword not in word:
            continue
        entries.append({"word": word, **data})

    # 排序：按分数降序
    entries.sort(key=lambda x: x.get("score", 0), reverse=True)

    # 分页
    total = len(entries)
    start = (page - 1) * page_size
    end = start + page_size
    page_entries = entries[start:end]

    return {
        "success": True,
        "total": total,
        "page": page,
        "page_size": page_size,
        "entries": page_entries,
        "stats": lexicon.get_stats(),
    }


@router.get("/lexicon/{word}")
async def get_lexicon_word(word: str):
    """获取单个词的详情"""
    lexicon = get_lexicon()
    entry = lexicon.entries.get(word)
    if not entry:
        raise HTTPException(status_code=404, detail=f"词 '{word}' 不在词典中")
    return {"success": True, "word": word, **entry}


@router.post("/lexicon")
async def add_lexicon_entry(entry: LexiconEntry, editor=Depends(require_editor)):
    """添加词典条目"""
    lexicon = get_lexicon()

    if lexicon.has_word(entry.word):
        raise HTTPException(status_code=400, detail=f"词 '{entry.word}' 已存在，请使用 PUT 更新")

    lexicon.entries[entry.word] = {
        "score": entry.score,
        "category": entry.category,
        "source": entry.source,
        "note": entry.note,
    }
    lexicon.total_words = len(lexicon.entries)

    # 保存到文件
    _save_lexicon(lexicon)

    return {"success": True, "message": f"已添加 '{entry.word}'"}


@router.put("/lexicon/{word}")
async def update_lexicon_word(word: str, update: LexiconUpdate, editor=Depends(require_editor)):
    """更新词典条目"""
    lexicon = get_lexicon()

    if not lexicon.has_word(word):
        raise HTTPException(status_code=404, detail=f"词 '{word}' 不在词典中")

    entry = lexicon.entries[word]
    if update.score is not None:
        entry["score"] = update.score
    if update.category is not None:
        entry["category"] = update.category
    if update.note is not None:
        entry["note"] = update.note

    entry["source"] = "manual"
    entry["updated_at"] = datetime.now().isoformat()

    _save_lexicon(lexicon)

    return {"success": True, "message": f"已更新 '{word}'", "entry": entry}


@router.delete("/lexicon/{word}")
async def delete_lexicon_word(word: str, editor=Depends(require_editor)):
    """删除词典条目"""
    lexicon = get_lexicon()

    if not lexicon.has_word(word):
        raise HTTPException(status_code=404, detail=f"词 '{word}' 不在词典中")

    del lexicon.entries[word]
    lexicon.total_words = len(lexicon.entries)

    _save_lexicon(lexicon)

    return {"success": True, "message": f"已删除 '{word}'"}


# ── 统计信息 ──────────────────────────────────────────────────────────

@router.get("/stats")
async def get_engine_stats():
    """获取引擎统计信息"""
    lexicon = get_lexicon()
    stats = lexicon.get_stats()

    # 加载空间规则
    from app.services.tibi_analysis_rules import SPATIAL_EMOTION_RULES
    spatial_count = len(SPATIAL_EMOTION_RULES["form_emotion_map"])

    # 加载印章规则
    from app.services.tibi_analysis_rules import SEAL_EMOTION_RULES
    seal_count = len(SEAL_EMOTION_RULES["seal_catalog"])

    # 加载画家基线
    from app.services.tibi_analysis_rules import ARTIST_EMOTION_BASELINE
    artist_count = len(ARTIST_EMOTION_BASELINE)

    return {
        "success": True,
        "lexicon": stats,
        "spatial_types": spatial_count,
        "seal_rules": seal_count,
        "artist_baselines": artist_count,
        "engine_version": "2.0",
        "vader_alpha": 8.0,
    }


# ── 校准工具 ──────────────────────────────────────────────────────────

@router.post("/calibrate")
async def run_calibration(
    sample_size: int = Query(30, ge=10, le=100),
    artist: Optional[str] = Query(None),
    editor=Depends(require_editor),
):
    """运行校准"""
    from scripts.calibrate_scoring import calibrate

    output_path = f"backend/calibration_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    report = await calibrate(sample_size=sample_size, artist=artist, output_path=output_path)

    return {
        "success": True,
        "report": report,
    }


# ── 辅助函数 ──────────────────────────────────────────────────────────

def _save_lexicon(lexicon):
    """保存词典到文件"""
    lexicon_path = os.path.join(os.path.dirname(__file__), "..", "services", "emotion_lexicon.json")
    lexicon_path = os.path.normpath(lexicon_path)

    data = {
        "version": lexicon.version,
        "generated_at": lexicon.generated_at,
        "method": "llm_rating + manual",
        "model": "deepseek-v4-flash",
        "total_words": lexicon.total_words,
        "entries": lexicon.entries,
    }

    with open(lexicon_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
