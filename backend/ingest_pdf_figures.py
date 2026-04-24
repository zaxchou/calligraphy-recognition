"""
Ingest PDF extracted illustrations (潘天寿作品) into Qdrant with CLIP vectors.

Reads images from backend/data/knowledge/extracted/<hash>/ directory,
uses mapping.json to map filenames to figure_ids (图一 ~ 图一〇〇),
and upserts CLIP 512-dim vectors into composition_cases collection.
"""
import sys
import os
import json
import logging
from datetime import date

# Ensure backend is on path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────
EXTRACTED_ROOT = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "data", "knowledge", "extracted"
)
RULESET_VERSION = "2026-03-27-pdf-v1"

# ── Imports ───────────────────────────────────────────────────────────
from app.modules.pantianshou_composition.analyzer import to_feature_vector_512
from app.modules.pantianshou_composition.qdrant_client import ensure_collection, upsert_points
from app.modules.pantianshou_composition.knowledge_ingest import _load_pan_figure_index, _norm_figure_id
from app.modules.pantianshou_composition.storage import build_static_url
from app.core.config import get_settings
import cv2
import uuid

settings = get_settings()


def main():
    # 1. Ensure collection exists (do NOT recreate — preserve existing rules + uploaded_images)
    ok = ensure_collection("composition_cases", vector_size=512, recreate=False)
    if not ok:
        log.error("Qdrant unavailable — cannot ingest")
        sys.exit(1)

    # 2. Walk extracted directories, find mapping.json + images
    pan_meta = _load_pan_figure_index()
    log.info("Loaded %d pan.md figure index entries", len(pan_meta))

    base_data_dir = os.path.dirname(settings.UPLOAD_DIR)
    total_read = 0
    total_upserted = 0
    total_skipped = 0

    for root, dirs, files in os.walk(EXTRACTED_ROOT):
        if "mapping.json" not in files:
            continue

        mapping_path = os.path.join(root, "mapping.json")
        with open(mapping_path, "r", encoding="utf-8") as f:
            mapping = json.load(f) or {}

        log.info("Found mapping with %d entries in %s", len(mapping), root)

        points = []
        for file_name, figure_id_raw in mapping.items():
            if not file_name or not figure_id_raw:
                continue

            img_path = os.path.join(root, os.path.basename(str(file_name)))
            if not os.path.exists(img_path):
                log.warning("  SKIP (not found): %s", img_path)
                total_skipped += 1
                continue

            total_read += 1
            figure_id = _norm_figure_id(str(figure_id_raw))

            # Read image
            img = cv2.imread(img_path)
            if img is None:
                log.warning("  SKIP (unreadable): %s", file_name)
                total_skipped += 1
                continue

            # CLIP vector
            vec = to_feature_vector_512(img)

            # Check vector quality
            is_zero = all(abs(v) < 1e-8 for v in vec)

            # Build relative URL for serving
            rel = os.path.relpath(img_path, base_data_dir)
            image_url = build_static_url(rel)

            # Get pan.md metadata if available
            meta = pan_meta.get(figure_id)
            figure_type = meta.figure_type if meta else "unknown"
            description = meta.description if meta else ""
            score_ref = meta.score_ref if meta else None

            point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"pdf_fig:{figure_id}"))
            payload = {
                "type": "pantianshou_illustration",
                "figure_id": figure_id,
                "figure_type": figure_type,
                "score_ref": score_ref,
                "description": description,
                "ruleset_version": RULESET_VERSION,
                "source": "pdf_extracted",
                "file_name": os.path.basename(img_path),
                "image_url": image_url,
            }
            points.append({
                "id": point_id,
                "vector": vec,
                "payload": payload,
            })

            status = "CLIP" if not is_zero else "ZERO-VEC"
            if total_read <= 5 or total_read % 20 == 0:
                log.info("  [%s] %s -> %s (fig=%s)", status, os.path.basename(img_path), point_id[:12], figure_id)

        # Batch upsert
        if points:
            ok = upsert_points("composition_cases", points, wait=True)
            total_upserted += len(points)
            log.info("  Upserted %d points (batch)", len(points))

    log.info("=" * 60)
    log.info("DONE: read=%d, upserted=%d, skipped=%d", total_read, total_upserted, total_skipped)
    log.info("Ruleset version: %s", RULESET_VERSION)


if __name__ == "__main__":
    main()
