#!/usr/bin/env python3
"""
Enriched DB entity indexer — Phase 1.1 + 1.2

Indexes to Qdrant knowledge_db:
- Artworks: with content_analysis (sentiment, themes, objects, inscription)
- Artists: with representative works + active years
- Seals: basic metadata
- Artist rules: emotion baselines + sentiment/theme notes
"""
import sqlite3, uuid, json, sys, os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, BACKEND_DIR)

# Override QDRANT_URL for host-side execution (Docker uses 'qdrant' hostname)
os.environ["QDRANT_URL"] = "http://localhost:6333"

from app.core.config import get_settings
get_settings.cache_clear()  # Force reload with new env var

from app.modules.pantianshou_composition.embedding_service import EmbeddingService
from app.modules.pantianshou_composition import qdrant_client as qc

# Force the qdrant client to use localhost
qc.settings.QDRANT_URL = "http://localhost:6333"

es = EmbeddingService()
db_path = os.path.join(BACKEND_DIR, 'data', 'calligraphy.db')
db = sqlite3.connect(db_path)
db.row_factory = sqlite3.Row

entities = []


def safe_json(val):
    if not val:
        return {}
    if isinstance(val, dict):
        return val
    try:
        return json.loads(val)
    except Exception:
        return {}


# ── 1. Artists (enriched with stats) ──
rows = db.execute("SELECT * FROM artists ORDER BY id").fetchall()
print(f"Artists: {len(rows)}")
for row in rows:
    parts = [f"# {row['name']}"]
    if row['dynasty']: parts.append(f"朝代: {row['dynasty']}")
    if row['alias']: parts.append(f"字号: {row['alias']}")
    if row['hometown']: parts.append(f"籍贯: {row['hometown']}")
    if row['art_school']: parts.append(f"画派: {row['art_school']}")
    if row['summary']: parts.append(f"概述: {row['summary']}")
    if row['biography']: parts.append(f"生平: {row['biography'][:500]}")
    if row['art_style']: parts.append(f"艺术特色: {row['art_style']}")
    if row['main_achievements']: parts.append(f"主要成就: {row['main_achievements']}")
    if row['influence']: parts.append(f"后世影响: {row['influence']}")
    if row['historical_evaluation']: parts.append(f"历史评价: {row['historical_evaluation']}")
    if row['representative_works_text']: parts.append(f"代表作: {row['representative_works_text']}")
    if row['tags']:
        try:
            tags = json.loads(row['tags'])
            if tags: parts.append(f"标签: {', '.join(tags)}")
        except Exception:
            pass

    # Aggregate stats from tubi_analyses
    artist_name = row['name']
    stats = db.execute(
        "SELECT COUNT(*), MIN(year), MAX(year) FROM tubi_analyses WHERE artist = ? AND year IS NOT NULL",
        (artist_name,)
    ).fetchone()
    if stats and stats[0] > 0:
        parts.append(f"作品数量: {stats[0]}幅，创作年份: {stats[1]}-{stats[2]}")

    text = "\n".join(parts)
    if text.strip():
        entities.append(("artist", f"artist-{row['id']}", {
            "type": "artist", "entity_id": f"artist-{row['id']}",
            "name": artist_name, "url": f"/artist/{artist_name}",
            "content": text, "source": "database",
        }, text))


# ── 2. Artworks (enriched with content_analysis) ──
rows = db.execute("SELECT * FROM tubi_analyses WHERE status IN ('analyzed','uploaded') ORDER BY id").fetchall()
print(f"Artworks: {len(rows)}")
for row in rows:
    d = dict(row)
    title = d.get("title") or "未命名"
    artist = d.get("artist") or ""
    parts = [f"# {title} — {artist}" if artist else f"# {title}"]

    # Basic metadata
    if d.get("year"): parts.append(f"创作年份: {d['year']}年")
    if d.get("period"): parts.append(f"艺术时期: {d['period']}")
    if d.get("period_phase"): parts.append(f"分期: {d['period_phase']}")
    if d.get("material"): parts.append(f"材质: {d['material']}")
    if d.get("mounting_format"): parts.append(f"装裱: {d['mounting_format']}")
    w, h = d.get("artwork_width_cm"), d.get("artwork_height_cm")
    if w and h: parts.append(f"尺寸: {w}x{h} cm")
    if d.get("current_location"): parts.append(f"现藏: {d['current_location']}")
    if d.get("work_type"): parts.append(f"类型: {d['work_type']}")

    # Tags (all 5 fields)
    for tag_field in ['style_tags', 'subject_tags', 'technique_tags', 'theme_tags', 'free_tags']:
        if d.get(tag_field): parts.append(f"{tag_field.replace('_tags','')}: {d[tag_field]}")

    # Inscription (full text — key for emotional analysis)
    if d.get("inscription_content"):
        parts.append(f"题跋全文: {d['inscription_content']}")
    if d.get("inscription_modern"):
        parts.append(f"题跋译文: {d['inscription_modern'][:500]}")
    if d.get("inscription_author"): parts.append(f"款识作者: {d['inscription_author']}")

    # AI analysis
    if d.get("analysis_note"):
        parts.append(f"AI分析: {d['analysis_note']}")

    # ── content_analysis JSON (the richest data) ──
    ca = safe_json(d.get("content_analysis"))
    if ca:
        # Combined sentiment
        cs = safe_json(ca.get("combined_sentiment"))
        if cs:
            polarity = cs.get("polarity", "")
            reasoning = cs.get("reasoning", "")
            if polarity: parts.append(f"情感倾向: {polarity}")
            if reasoning: parts.append(f"情感分析: {reasoning[:300]}")

        # Sentiment score
        sent = safe_json(ca.get("sentiment"))
        if sent:
            score = sent.get("emotion_score")
            if score is not None:
                parts.append(f"情感分数: {score}")
            reasoning = sent.get("reasoning", "")
            if reasoning: parts.append(f"情感依据: {reasoning[:200]}")

        # Themes
        themes = ca.get("themes", [])
        if themes:
            theme_names = [t.get("name", "") for t in themes if t.get("name")]
            if theme_names:
                parts.append(f"主题: {', '.join(theme_names)}")

        # Objects mentioned (竹/梅/兰/菊 etc.)
        objects = ca.get("objects_mentioned", [])
        if objects:
            parts.append(f"画面意象: {', '.join(objects)}")

        # Spatial emotion
        sp = safe_json(ca.get("spatial_emotion"))
        if sp:
            sigs = sp.get("signals", [])
            if sigs:
                emotions = [s.get("emotion", "") for s in sigs if s.get("emotion")]
                if emotions:
                    parts.append(f"构图情绪: {', '.join(emotions[:3])}")

    text = "\n".join(parts)
    if text.strip():
        entities.append(("artwork", f"artwork-{d['id']}", {
            "type": "artwork", "entity_id": f"artwork-{d['id']}",
            "url": f"/tiba/{d.get('image_id', '')}",
            "image_id": d.get("image_id", ""),
            "artist": artist, "title": title, "year": d.get("year"),
            "content": text, "source": "database",
        }, text))


# ── 3. Seals ──
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


# ── 4. Artist rules (Phase 1.2) ──
try:
    rules = db.execute("SELECT * FROM artist_rules ORDER BY id").fetchall()
    print(f"Artist rules: {len(rules)}")
    for row in rules:
        d = dict(row)
        artist_name = d.get("artist_name", "")
        parts = [f"# {artist_name} — 情感分析规则"]

        if d.get("emotion_baseline") is not None:
            parts.append(f"情感基线: {d['emotion_baseline']}")

        if d.get("life_stages"):
            try:
                stages = json.loads(d["life_stages"]) if isinstance(d["life_stages"], str) else d["life_stages"]
                if stages:
                    parts.append("人生阶段:")
                    for s in stages:
                        name = s.get("name", "")
                        y1 = s.get("year_start", "?")
                        y2 = s.get("year_end", "?")
                        desc = s.get("description", "")
                        mood = s.get("mood_offset", 0)
                        parts.append(f"  {name} ({y1}-{y2}): {desc} [情感偏移: {mood:+.1f}]")
            except Exception:
                pass

        if d.get("sentiment_note"):
            parts.append(f"情感判断规则: {d['sentiment_note']}")
        if d.get("theme_note"):
            parts.append(f"主题判断规则: {d['theme_note']}")
        if d.get("theme_exceptions"):
            parts.append(f"主题例外: {d['theme_exceptions']}")
        if d.get("expected_sentiment_distribution"):
            parts.append(f"预期情感分布: {d['expected_sentiment_distribution']}")
        if d.get("expected_theme_distribution"):
            parts.append(f"预期主题分布: {d['expected_theme_distribution']}")
        if d.get("seal_rules"):
            try:
                seals_data = json.loads(d["seal_rules"]) if isinstance(d["seal_rules"], str) else d["seal_rules"]
                if seals_data:
                    parts.append("印章情感规则:")
                    for seal_name, seal_info in seals_data.items():
                        desc = seal_info.get("desc", "")
                        score = seal_info.get("score", 0)
                        parts.append(f"  {seal_name}: {desc} (情感分: {score:+.1f})")
            except Exception:
                pass

        text = "\n".join(parts)
        if text.strip():
            entities.append(("artist_rule", f"rule-{artist_name}", {
                "type": "artist_rule", "entity_id": f"rule-{artist_name}",
                "name": f"{artist_name}情感规则", "url": f"/artist/{artist_name}",
                "content": text, "source": "database",
                "artist": artist_name,
            }, text))
except Exception as e:
    print(f"Artist rules error: {e}")


db.close()
print(f"Total entities: {len(entities)}")

# ── Embed and upsert ──
# Ensure collection exists (no delete — just create if missing)
qc.ensure_collection(qc.KNOWLEDGE_DB_COLLECTION, vector_size=qc.KNOWLEDGE_VECTOR_SIZE)

ok = 0
batch_size = 10
for i in range(0, len(entities), batch_size):
    batch = entities[i:i+batch_size]
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
        print(f"Batch {i//batch_size} failed: {ex}")
    if (i // batch_size + 1) % 10 == 0:
        print(f"  Progress: {ok}/{len(entities)}")

print(f"Done. Upserted {ok}/{len(entities)} to knowledge_db")
