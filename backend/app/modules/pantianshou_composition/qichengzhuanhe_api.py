"""
起承转合分析 API（独立页面）
============================
调用 qichengzhuanhe.py 共享模块。
"""
from __future__ import annotations

import asyncio
import logging
from typing import List

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from app.modules.pantianshou_composition.analyzer import decode_image_bytes
from app.modules.pantianshou_composition.qichengzhuanhe import (
    analyze_qichengzhuanhe,
    encode_preview,
)
from app.modules.pantianshou_composition.qczh_history import (
    delete_record,
    delete_records,
    get_record,
    list_records,
    save_record,
    clear_all,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/composition", tags=["起承转合分析"])


# -----------------------------------------------------------------------
# 分析接口
# -----------------------------------------------------------------------
@router.post("/qichengzhuanhe-analyze")
async def qichengzhuanhe_analyze(file: UploadFile = File(...)):
    """
    使用 Qwen VL 视觉模型分析起承转合。
    分析完成后自动保存到历史记录。
    """
    MAX_SIZE = 10 * 1024 * 1024
    content = await file.read(MAX_SIZE + 1)
    if len(content) > MAX_SIZE:
        raise HTTPException(status_code=413, detail="file_too_large")
    if not content:
        raise HTTPException(status_code=400, detail="empty_file")

    try:
        img_bgr = decode_image_bytes(content)
    except Exception:
        raise HTTPException(status_code=400, detail="invalid_image")

    h, w = img_bgr.shape[:2]

    try:
        # analyze_qichengzhuanhe 是同步函数（含 CV + LLM 调用，耗时 30-120s），
        # 用 asyncio.to_thread 避免阻塞事件循环
        result = await asyncio.to_thread(analyze_qichengzhuanhe, img_bgr)
    except Exception as e:
        logger.exception("起承转合分析失败")
        raise HTTPException(status_code=500, detail=f"analysis_failed: {e}")

    arrow_canvas = result["arrow_canvas"]
    preview_b64 = encode_preview(arrow_canvas)

    # 自动保存到历史记录
    try:
        save_record(
            preview_image=preview_b64,
            arrows=result["arrows"],
            arrow_labels=result["arrow_labels"],
            llm_analysis=result["llm_analysis"],
            path_type=result["path_type"],
            points=result["points"],
            model=result["model"],
            width=w,
            height=h,
            material_type=result.get("material_type", ""),
            growth_direction=result.get("growth_direction", ""),
            has_inscription=result.get("has_inscription", True),
            inscription_edge=result.get("inscription_edge", ""),
            seal_positions=result.get("seal_positions", []),
            image_file_name=file.filename or "",
        )
    except Exception as e:
        logger.warning("保存历史记录失败（不影响分析结果）: %s", e)

    return {
        "width": w,
        "height": h,
        "preview_image": preview_b64,
        "arrows": result["arrows"],
        "arrow_labels": result["arrow_labels"],
        "llm_analysis": result["llm_analysis"],
        "path_type": result["path_type"],
        "points": result["points"],
        "model": result["model"],
        "material_type": result.get("material_type", ""),
        "growth_direction": result.get("growth_direction", ""),
        "has_inscription": result.get("has_inscription", True),
        "inscription_edge": result.get("inscription_edge", ""),
        "seal_positions": result.get("seal_positions", []),
        # CV+AI 融合数据（v2）
        "cv_preprocess": result.get("cv_preprocess", {}),
    }


# -----------------------------------------------------------------------
# 历史记录接口
# -----------------------------------------------------------------------
class DeleteBatchRequest(BaseModel):
    ids: List[str]


@router.get("/qczh-history")
def get_history(limit: int = 50, offset: int = 0):
    """获取历史记录列表（不含图片数据，仅缩略信息）"""
    return list_records(limit=limit, offset=offset)


@router.get("/qczh-history/{record_id}")
def get_history_detail(record_id: str):
    """获取单条历史记录详情（含图片数据）"""
    record = get_record(record_id)
    if not record:
        raise HTTPException(status_code=404, detail="记录不存在")
    return record


@router.delete("/qczh-history/{record_id}")
def delete_single(record_id: str):
    """删除单条历史记录"""
    ok = delete_record(record_id)
    if not ok:
        raise HTTPException(status_code=404, detail="记录不存在")
    return {"ok": True, "message": "已删除"}


@router.post("/qczh-history/batch-delete")
def delete_batch(req: DeleteBatchRequest):
    """批量删除历史记录"""
    deleted = delete_records(req.ids)
    return {"ok": True, "deleted": deleted}


@router.post("/qczh-history/clear-all")
def clear_history():
    """清空所有历史记录"""
    deleted = clear_all()
    return {"ok": True, "deleted": deleted}
