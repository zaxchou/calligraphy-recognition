"""
re_embed_images.py — 一键重入库 knowledge_images 集合

把所有图片数据重新入库到 knowledge_images，使用 DashScope multimodal-embedding-v1
获取真实 1024 维向量（替代旧零向量）。

用法：
    cd backend
    python re_embed_images.py              # 全量入库
    python re_embed_images.py --dry-run    # 预览模式，不调用 API 也不写 Qdrant
    python re_embed_images.py --source bird_flower   # 只入库花鸟画教程
    python re_embed_images.py --source pan           # 只入库潘天寿插图

数据来源：
1. 写意花鸟画教程 — bird_flower_ingest.ingest_knowledge_figures()
2. 潘天寿插图     — knowledge_ingest.ingest_illustration_images()
"""

import sys
import os
import io
import argparse
import time
import logging

# 确保 backend 在 sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Windows 控制台 UTF-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)


def check_prerequisites():
    """检查 Qdrant 是否运行、.env 是否配置"""
    from app.core.config import get_settings
    settings = get_settings()

    # 检查 Qdrant
    import requests
    try:
        r = requests.get(f"{settings.QDRANT_URL}/collections", timeout=5)
        if r.status_code != 200:
            log.error("Qdrant 返回异常: %d", r.status_code)
            return False
        log.info("✓ Qdrant 运行正常 (%s)", settings.QDRANT_URL)
    except Exception as e:
        log.error("✗ Qdrant 不可达: %s", e)
        return False

    # 检查 DashScope
    if not settings.QWEN_API_KEY:
        log.error("✗ QWEN_API_KEY 未设置，DashScope multimodal embedding 无法调用")
        return False
    log.info("✓ QWEN_API_KEY 已设置")

    if not settings.DASHSCOPE_MULTIMODAL_ENABLED:
        log.warning("⚠ DASHSCOPE_MULTIMODAL_ENABLED=false，图像 embedding 将降级为零向量")
        log.warning("  请在 .env 中设置 DASHSCOPE_MULTIMODAL_ENABLED=true")
        return False
    log.info("✓ DASHSCOPE_MULTIMODAL_ENABLED=true")

    return True


def ingest_bird_flower(dry_run=False):
    """入库写意花鸟画教程插图"""
    from app.modules.pantianshou_composition.bird_flower_ingest import ingest_knowledge_figures

    if dry_run:
        from app.modules.pantianshou_composition.bird_flower_ingest import load_figure_metadata
        meta = load_figure_metadata()
        n_with_path = sum(1 for fm in meta.values() if fm.image_path and os.path.exists(fm.image_path))
        log.info("[DRY-RUN] 写意花鸟画教程: %d 张图片有路径，%d 张无路径",
                 n_with_path, len(meta) - n_with_path)
        return {"dry_run": True, "total": len(meta), "with_path": n_with_path}

    log.info("=" * 60)
    log.info("开始入库: 写意花鸟画教程插图")
    log.info("=" * 60)
    t0 = time.time()
    result = ingest_knowledge_figures(recreate=False)
    elapsed = time.time() - t0
    log.info("写意花鸟画教程入库完成: %s (耗时 %.1f 秒)", result, elapsed)
    return result


def ingest_pan_illustrations(dry_run=False):
    """入库潘天寿插图"""
    from app.modules.pantianshou_composition.knowledge_ingest import ingest_illustration_images
    from app.core.config import get_settings
    settings = get_settings()

    # 找到 extracted 目录下的潘天寿图片
    base_data = os.path.dirname(settings.UPLOAD_DIR)
    extracted_dir = os.path.join(base_data, "knowledge", "extracted",
                                  "899591682ff741588ba7017d69188ef1")

    if not os.path.isdir(extracted_dir):
        log.warning("潘天寿插图目录不存在: %s", extracted_dir)
        return {"ok": False, "error": "dir_not_found"}

    # 找 mapping.json
    mapping_json = os.path.join(extracted_dir, "mapping.json")
    if not os.path.exists(mapping_json):
        mapping_json = None
        log.warning("潘天寿插图 mapping.json 不存在，将使用文件名作为 figure_id")

    if dry_run:
        from app.modules.pantianshou_composition.knowledge_ingest import _iter_image_files
        n_images = sum(1 for _ in _iter_image_files(extracted_dir))
        log.info("[DRY-RUN] 潘天寿插图: %d 张图片在 %s", n_images, extracted_dir)
        return {"dry_run": True, "total": n_images}

    log.info("=" * 60)
    log.info("开始入库: 潘天寿插图")
    log.info("=" * 60)
    t0 = time.time()
    result = ingest_illustration_images(
        images_dir=extracted_dir,
        mapping_json=mapping_json,
    )
    elapsed = time.time() - t0
    log.info("潘天寿插图入库完成: %s (耗时 %.1f 秒)", result, elapsed)
    return result


def verify_collection():
    """验证 knowledge_images 集合状态"""
    from app.modules.pantianshou_composition.qdrant_client import (
        count_collection, KNOWLEDGE_IMAGES_COLLECTION, scroll_collection
    )

    total = count_collection(KNOWLEDGE_IMAGES_COLLECTION)
    log.info("knowledge_images 集合: %d 条记录", total)

    if total == 0:
        log.warning("⚠ 集合为空！入库可能失败")
        return

    # 抽样检查向量质量
    result = scroll_collection(KNOWLEDGE_IMAGES_COLLECTION, limit=5, with_vector=True)
    points = result.get("points", [])

    zero_count = 0
    nonzero_count = 0
    for p in points:
        vec = p.get("vector", [])
        if all(abs(v) < 1e-8 for v in vec):
            zero_count += 1
        else:
            nonzero_count += 1
            payload = p.get("payload", {})
            fig_id = payload.get("figure_id", payload.get("caption", "unknown"))
            log.info("  ✓ 向量非零: figure_id=%s, 维度=%d, 前3值=%.4f,%.4f,%.4f",
                     fig_id, len(vec), vec[0], vec[1], vec[2])

    if zero_count > 0:
        log.warning("  ✗ 发现 %d 条零向量（DashScope API 可能未正确调用）", zero_count)
    if nonzero_count > 0:
        log.info("  ✓ 发现 %d 条非零向量（DashScope embedding 成功）", nonzero_count)


def main():
    parser = argparse.ArgumentParser(description="知识库图片重入库（DashScope multimodal embedding）")
    parser.add_argument("--dry-run", action="store_true", help="预览模式，不调用 API")
    parser.add_argument("--source", choices=["bird_flower", "pan", "all"], default="all",
                        help="数据来源: bird_flower=写意花鸟画, pan=潘天寿插图, all=全部")
    args = parser.parse_args()

    log.info("知识库图片重入库工具")
    log.info("=" * 60)

    if args.dry_run:
        log.info("※ 预览模式 -- 不调用 API，不写入 Qdrant")

    if not args.dry_run and not check_prerequisites():
        log.error("前置检查未通过，退出")
        sys.exit(1)

    results = {}

    # 入库写意花鸟画教程
    if args.source in ("bird_flower", "all"):
        results["bird_flower"] = ingest_bird_flower(dry_run=args.dry_run)

    # 入库潘天寿插图
    if args.source in ("pan", "all"):
        results["pan"] = ingest_pan_illustrations(dry_run=args.dry_run)

    # 验证
    if not args.dry_run:
        log.info("")
        log.info("=" * 60)
        log.info("验证入库结果")
        log.info("=" * 60)
        verify_collection()

    log.info("")
    log.info("=" * 60)
    log.info("全部完成！结果: %s", results)
    log.info("=" * 60)


if __name__ == "__main__":
    main()
