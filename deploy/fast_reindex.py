#!/usr/bin/env python3
import sys, os, json
sys.path.insert(0, "/app")
from dotenv import load_dotenv
load_dotenv("/app/.env")
import sqlite3
from app.modules.pantianshou_composition.embedding_service import EmbeddingService
from app.modules.pantianshou_composition import qdrant_client as qc

emb = EmbeddingService()
qc.ensure_collection(qc.KNOWLEDGE_TEXTS_COLLECTION, vector_size=1024, recreate=True)

conn = sqlite3.connect("/app/data/knowledge.db")
c = conn.cursor()
c.execute("SELECT id, book_id, page_start, content, meta_data, chapter_title, chunk_index FROM text_chunks ORDER BY book_id, page_start, id")
rows = c.fetchall()
conn.close()
print(f"Total: {len(rows)} chunks")

batch = []
for i, (cid, bid, ps, text, md, ch, ci) in enumerate(rows):
    if not text or len(text.strip()) < 5:
        continue
    meta = json.loads(md) if md else {}
    try:
        r = emb.embed_text_sync(text[:2000])
        if not r or not r.embedding:
            continue
        batch.append({"id": str(cid), "vector": r.embedding, "content": text,
            "chapter": ch or "", "page_start": ps or 0, "page_end": ps or 0,
            "chunk_index": ci or 0, "metadata": meta})
    except Exception as e:
        print(f"  [{i}] error: {e}")
        continue
    if len(batch) >= 50:
        qc.upsert_text_chunks(batch, bid)
        print(f"  [{i+1}/{len(rows)}] OK")
        batch = []
if batch:
    qc.upsert_text_chunks(batch, bid)
cnt = qc.count_collection(qc.KNOWLEDGE_TEXTS_COLLECTION)
print(f"DONE: {cnt} points")
