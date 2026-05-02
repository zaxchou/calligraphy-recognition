"""
起承转合分析 API — 向后兼容别名
================================
前端调 /composition/arrow-demo-llm，内部转发给 qichengzhuanhe_api 的分析逻辑。
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.modules.pantianshou_composition.analyzer import decode_image_bytes
from app.modules.pantianshou_composition.qichengzhuanhe import (
    analyze_qichengzhuanhe,
    encode_preview,
)
from app.modules.pantianshou_composition.qczh_history import save_record

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/composition", tags=["起承转合 Demo (兼容)"])


@router.post("/arrow-demo-llm")
async def arrow_demo_llm(file: UploadFile = File(...)):
    """向后兼容端点，分析后保存历史记录。"""
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
        result = analyze_qichengzhuanhe(img_bgr)
    except Exception as e:
        logger.exception("起承转合分析失败")
        raise HTTPException(status_code=500, detail=f"analysis_failed: {e}")

    arrow_canvas = result["arrow_canvas"]
    preview_b64 = encode_preview(arrow_canvas)

    # ★ 保存历史记录 ★
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
        logger.info("历史记录已保存")
    except Exception as e:
        logger.warning("保存历史记录失败: %s", e)

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
        "qwen_analysis": result.get("qwen_analysis", ""),
    }
