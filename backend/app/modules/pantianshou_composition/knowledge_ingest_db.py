#!/usr/bin/env python3
"""Batch index DB entities (artists/artworks/seals) into Qdrant knowledge_db."""
import os, sys, json, uuid, sqlite3, asyncio, argparse, logging
from typing import List, Dict, Any, Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(BASE_DIR, "data", "calligraphy.db")

def get_db():
    db = sqlite3.connect(f'file:{DB_PATH}?mode=ro', uri=True)
    db.row_factory = sqlite3.Row
    return db

def build_artist_text(row):
    parts = [f"# {row['name']}"]
    if row["birth_year"] or row["death_year"]:
        parts.append(f"生卒: {row['birth_year'] or '?'}-{row['death_year'] or '?'}")
    if row["dynasty"]: parts.append(f"朝代: {row['dynasty']}")
    if row["alias"]: parts.append(f"字号: {row['alias']}")
    if row["hometown"]: parts.append(f"籍贯: {row['hometown']}")
    if row["art_school"]: parts.append(f"画派: {row['art_school']}")
    if row["nationality"]: parts.append(f"国籍: {row['nationality']}")
    if row["occupation"]: parts.append(f"职业: {row['occupation']}")
    if row["summary"]: parts.append(f"概述: {row['summary']}")
    if row["biography"]: parts.append(f"生平: {row['biography']}")
    if row["art_style"]: parts.append(f"艺术特色: {row['art_style']}")
    if row["main_achievements"]: parts.append(f"主要成就: {row['main_achievements']}")
    if row["representative_works_text"]: parts.append(f"代表作: {row['representative_works_text']}")
    if row["influence"]: parts.append(f"后世影响: {row['influence']}")
    if row["historical_evaluation"]: parts.append(f"历史评价: {row['historical_evaluation']}")
    if row["specialties"]: parts.append(f"专长: {row['specialties']}")
    if row["tags"]:
        try: parts.append(f"标签: {', '.join(json.loads(row['tags']))}")
        except: pass
    return f"artist-{row['id']}", "\n".join(parts)

def build_artwork_text(row_data):
    row = dict(row_data)
    title = row.get("title") or "未命名"
    artist = row.get("artist") or ""
    parts = [f"# {title} — {artist}" if artist else f"# {title}"]
    if row.get("year"): parts.append(f"创作年份: {row['year']}年")
    if row.get("period"): parts.append(f"艺术时期: {row['period']}")
    if row.get("period_phase"): parts.append(f"分期: {row['period_phase']}")
    if row.get("material"): parts.append(f"材质: {row['material']}")
    if row.get("mounting_format"): parts.append(f"装裱: {row['mounting_format']}")
    w = row.get("artwork_width_cm")
    h = row.get("artwork_height_cm")
    if w and h: parts.append(f"尺寸: {w}x{h} cm")
    if row.get("current_location"): parts.append(f"现藏: {row['current_location']}")
    if row.get("inscription_content"): parts.append(f"题跋: {row['inscription_content']}")
    if row.get("inscription_modern"): parts.append(f"题跋翻译: {row['inscription_modern']}")
    if row.get("inscription_author"): parts.append(f"款识作者: {row['inscription_author']}")
    if row.get("seal_content"): parts.append(f"印章: {row['seal_content']}")
    if row.get("char_count"): parts.append(f"题跋字数: {row['char_count']}")
    if row.get("theme_tags"): parts.append(f"主题标签: {row['theme_tags']}")
    if row.get("material_tags"): parts.append(f"画材标签: {row['material_tags']}")
    if row.get("style_tags"): parts.append(f"风格: {row['style_tags']}")
    if row.get("subject_tags"): parts.append(f"题材: {row['subject_tags']}")
    if row.get("technique_tags"): parts.append(f"技法: {row['technique_tags']}")
    if row.get("tags"):
        try: parts.append(f"标签: {', '.join(json.loads(row['tags']))}")
        except: pass
    if row.get("analysis_note"): parts.append(f"AI分析: {row['analysis_note']}")
    pct_i = row.get("inscription_percent") or 0
    pct_p = row.get("painting_percent") or 0
    pct_b = row.get("blank_percent") or 0
    space_tags = []
    if pct_i: space_tags.append(f"题跋占比 {pct_i:.1f}%")
    if pct_p: space_tags.append(f"绘画占比 {pct_p:.1f}%")
    if pct_b: space_tags.append(f"留白占比 {pct_b:.1f}%")
    if space_tags: parts.append("空间分析: " + ", ".join(space_tags))
    if row.get("album_name"): parts.append(f"册页: {row['album_name']}")
    return f"artwork-{row['id']}", "\n".join(parts)

def build_seal_text(row_data):
    row = dict(row_data)
    name = row.get("name") or "未命名"
    artist = row.get("artist_name") or ""
    parts = [f"# {name} — {artist}" if artist else f"# {name}"]
    if row.get("seal_type"): parts.append(f"类型: {row['seal_type']}")
    if row.get("description"): parts.append(f"描述: {row['description']}")
    if row.get("source"): parts.append(f"来源: {row['source']}")
    return f"seal-{row['id']}", "\n".join(parts)

def main():
    p = argparse.ArgumentParser(description="DB实体批量索引到Qdrant")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--clear", action="store_true")
    p.add_argument("--artists-only", action="store_true")
    p.add_argument("--artworks-only", action="store_true")
    p.add_argument("--seals-only", action="store_true")
    p.add_argument("--batch-size", type=int, default=10)
    args = p.parse_args()

    do_all = not (args.artists_only or args.artworks_only or args.seals_only)

    sys.path.insert(0, BASE_DIR)
    from app.modules.pantianshou_composition.embedding_service import EmbeddingService
    from app.modules.pantianshou_composition import qdrant_client as qc

    es = EmbeddingService()

    if args.clear:
        qc.delete_collection(qc.KNOWLEDGE_DB_COLLECTION)
    qc.ensure_collection(qc.KNOWLEDGE_DB_COLLECTION, vector_size=qc.KNOWLEDGE_VECTOR_SIZE)

    db = get_db()
    entities = []

    if do_all or args.artists_only:
        rows = db.execute("SELECT * FROM artists ORDER BY id").fetchall()
        logger.info("Reading %d artists...", len(rows))
        for row in rows:
            eid, text = build_artist_text(row)
            if text.strip():
                entities.append(("artist", eid, {
                    "type": "artist", "entity_id": eid, "name": row["name"], "url": f"/artist/{row["name"]}",
                    "content": text, "source": "database",
                }, text))

    if do_all or args.artworks_only:
        rows = db.execute("SELECT * FROM tubi_analyses WHERE status IN ('analyzed','uploaded') ORDER BY id").fetchall()
        logger.info("Reading %d artworks...", len(rows))
        for row in rows:
            eid, text = build_artwork_text(row)
            if text.strip():
                row_d = dict(row)
                entities.append(("artwork", eid, {
                    "type": "artwork", "entity_id": eid, "url": f"/tiba/{row_d.get("image_id", "")}", "image_id": row_d.get("image_id", ""),
                    "artist": row_d.get("artist", ""),
                    "title": row_d.get("title", ""), "year": row_d.get("year"),
                    "content": text, "source": "database",
                    "artwork_width_cm": row_d.get("artwork_width_cm"),
                    "artwork_height_cm": row_d.get("artwork_height_cm"),
                }, text))

    if do_all or args.seals_only:
        rows = db.execute("SELECT * FROM seals ORDER BY id").fetchall()
        logger.info("Reading %d seals...", len(rows))
        for row in rows:
            eid, text = build_seal_text(row)
            if text.strip():
                entities.append(("seal", eid, {
                    "type": "seal", "entity_id": eid, "name": row["name"], "url": f"/admin/seals",
                    "content": text, "source": "database",
                }, text))

    db.close()
    logger.info("Total entities: %d. Embedding...", len(entities))

    all_points = []
    texts = [e[3] for e in entities]
    for i in range(0, len(texts), args.batch_size):
        batch_texts = texts[i:i + args.batch_size]
        batch_entities = entities[i:i + args.batch_size]
        try:
            results = es.embed_texts_sync(batch_texts, batch_size=len(batch_texts))
            for ent, emb in zip(batch_entities, results):
                if emb and emb.embedding:
                    all_points.append({
                        "id": str(uuid.uuid5(uuid.NAMESPACE_DNS, ent[1])),
                        "vector": emb.embedding, "payload": ent[2],
                    })
        except Exception as ex:
            logger.error("Batch %d failed: %s", i // args.batch_size, ex)
        if (i // args.batch_size + 1) % 10 == 0:
            logger.info("  Batch %d/%d: %d/%d points", i // args.batch_size + 1,
                        (len(texts) - 1) // args.batch_size + 1, len(all_points), len(entities))

    logger.info("Total points to upsert: %d", len(all_points))

    if args.dry_run:
        for pt in all_points[:3]:
            logger.info("  [%s] %s: %s...", pt["payload"]["type"], pt["payload"]["entity_id"],
                       pt["payload"]["content"][:120])
        logger.info("  ... dry-run complete")
        return

    if not all_points:
        logger.warning("No points to upsert.")
        return

    ok = 0
    for i in range(0, len(all_points), 50):
        batch = all_points[i:i + 50]
        if qc.upsert_db_entities(batch):
            ok += len(batch)
        else:
            logger.error("Qdrant upsert batch %d FAILED", i // 50 + 1)

    logger.info("Done. Upserted %d/%d to %s", ok, len(all_points), qc.KNOWLEDGE_DB_COLLECTION)

if __name__ == "__main__":
    main()
