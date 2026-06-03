#!/usr/bin/env python3
"""Index DB entities (artists/artworks/seals) into Qdrant knowledge_db."""
import sqlite3, uuid, json, sys, os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, BACKEND_DIR)

# Override QDRANT_URL for host-side execution (Docker uses 'qdrant' hostname)
os.environ.setdefault("QDRANT_URL", "http://localhost:6333")

from app.modules.pantianshou_composition.embedding_service import EmbeddingService
from app.modules.pantianshou_composition import qdrant_client as qc

es = EmbeddingService()
db_path = os.path.join(BACKEND_DIR, 'data', 'calligraphy.db')
db = sqlite3.connect(db_path)
db.row_factory = sqlite3.Row

entities = []

# Artists
rows = db.execute("SELECT * FROM artists ORDER BY id").fetchall()
print(f"Artists: {len(rows)}")
for row in rows:
    parts = [f"# {row['name']}"]
    if row['dynasty']: parts.append(f"朝代: {row['dynasty']}")
    if row['alias']: parts.append(f"字号: {row['alias']}")
    if row['hometown']: parts.append(f"籍贯: {row['hometown']}")
    if row['art_school']: parts.append(f"画派: {row['art_school']}")
    if row['summary']: parts.append(f"概述: {row['summary']}")
    if row['biography']: parts.append(f"生平: {row['biography'][:300]}")
    if row['art_style']: parts.append(f"艺术特色: {row['art_style']}")
    text = "\n".join(parts)
    if text.strip():
        entities.append(("artist", f"artist-{row['id']}", {
            "type": "artist", "entity_id": f"artist-{row['id']}",
            "name": row['name'], "url": f"/artist/{row['name']}",
            "content": text, "source": "database",
        }, text))

# Artworks — enriched with sentiment, analysis, inscription
rows = db.execute("SELECT * FROM tubi_analyses WHERE status IN ('analyzed','uploaded') ORDER BY id").fetchall()
print(f"Artworks: {len(rows)}")
for row in rows:
    d = dict(row)
    title = d.get("title") or "未命名"
    artist = d.get("artist") or ""
    parts = [f"# {title} — {artist}" if artist else f"# {title}"]
    if d.get("year"): parts.append(f"创作年份: {d['year']}年")
    if d.get("period"): parts.append(f"艺术时期: {d['period']}")
    if d.get("material"): parts.append(f"材质: {d['material']}")
    if d.get("mounting_format"): parts.append(f"装裱: {d['mounting_format']}")
    w = d.get("artwork_width_cm")
    h = d.get("artwork_height_cm")
    if w and h: parts.append(f"尺寸: {w}x{h} cm")
    if d.get("current_location"): parts.append(f"现藏: {d['current_location']}")
    if d.get("style_tags"): parts.append(f"风格: {d['style_tags']}")
    if d.get("subject_tags"): parts.append(f"题材: {d['subject_tags']}")
    if d.get("technique_tags"): parts.append(f"技法: {d['technique_tags']}")
    if d.get("theme_tags"): parts.append(f"主题: {d['theme_tags']}")
    # 题跋内容（关键：包含画家自述、情感表达）
    if d.get("inscription_content"): parts.append(f"题跋: {d['inscription_content'][:500]}")
    if d.get("inscription_modern"): parts.append(f"题跋译文: {d['inscription_modern'][:300]}")
    if d.get("inscription_author"): parts.append(f"款识作者: {d['inscription_author']}")
    # AI 分析（包含情绪、意境等判断）
    if d.get("analysis_note"): parts.append(f"AI分析: {d['analysis_note'][:500]}")
    # 情感分析数据
    cs = d.get("combined_sentiment")
    if cs:
        try:
            import json as _json
            sentiment = _json.loads(cs) if isinstance(cs, str) else cs
            if isinstance(sentiment, dict):
                vs = sentiment.get("vader_normalized", 0)
                dims = sentiment.get("dimensions", {})
                if vs:
                    polarity = "正面" if vs > 0.1 else "负面" if vs < -0.1 else "中性"
                    parts.append(f"情感倾向: {polarity} (分数: {vs:.2f})")
                if dims:
                    for dim_name, dim_val in dims.items():
                        if isinstance(dim_val, dict) and dim_val.get("score"):
                            parts.append(f"情感维度-{dim_name}: {dim_val['score']:.1f}")
        except Exception:
            pass
    text = "\n".join(parts)
    if text.strip():
        entities.append(("artwork", f"artwork-{d['id']}", {
            "type": "artwork", "entity_id": f"artwork-{d['id']}",
            "url": f"/tiba/{d.get('image_id', '')}",
            "image_id": d.get("image_id", ""),
            "artist": artist, "title": title, "year": d.get("year"),
            "content": text, "source": "database",
        }, text))

# Seals
rows = db.execute("SELECT * FROM seals ORDER BY id").fetchall()
print(f"Seals: {len(rows)}")
for row in rows:
    d = dict(row)
    name = d.get("name") or "未命名"
    artist = d.get("artist_name") or ""
    parts = [f"# {name} — {artist}" if artist else f"# {name}"]
    if d.get("seal_type"): parts.append(f"类型: {d['seal_type']}")
    if d.get("description"): parts.append(f"描述: {d['description']}")
    text = "\n".join(parts)
    if text.strip():
        entities.append(("seal", f"seal-{d['id']}", {
            "type": "seal", "entity_id": f"seal-{d['id']}",
            "name": name, "url": "/admin/seals",
            "content": text, "source": "database",
        }, text))

db.close()
print(f"Total entities: {len(entities)}")

# Embed and upsert in batches
ok = 0
for i in range(0, len(entities), 10):
    batch = entities[i:i+10]
    texts = [e[3] for e in batch]
    try:
        results = es.embed_texts_sync(texts, batch_size=len(texts))
        points = []
        for ent, emb in zip(batch, results):
            if emb and emb.embedding:
                points.append({
                    "id": str(uuid.uuid5(uuid.NAMESPACE_DNS, ent[1])),
                    "vector": emb.embedding,
                    "payload": ent[2],
                })
        if points and qc.upsert_db_entities(points):
            ok += len(points)
    except Exception as ex:
        print(f"Batch {i//10} failed: {ex}")
    if (i // 10 + 1) % 5 == 0:
        print(f"  Progress: {ok}/{len(entities)}")

print(f"Done. Upserted {ok}/{len(entities)} to knowledge_db")
