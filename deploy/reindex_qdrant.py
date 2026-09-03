#!/usr/bin/env python3
"""Reindex text_chunks from knowledge.db into Qdrant"""
import sys, os, json, time
sys.path.insert(0, '/app')

from dotenv import load_dotenv
load_dotenv("/app/.env")

import sqlite3
from app.modules.pantianshou_composition.embedding_service import EmbeddingService
from app.modules.pantianshou_composition import qdrant_client as qc

emb = EmbeddingService()
BATCH_SIZE = 10

# Ensure collection exists (1024d since using multimodal-embedding-v1)
qc.ensure_collection(qc.KNOWLEDGE_TEXTS_COLLECTION, vector_size=1024, recreate=True)

# Read chunks from DB
conn = sqlite3.connect('/app/data/knowledge.db')
c = conn.cursor()
c.execute("SELECT id, book_id, page_start, content, meta_data, chapter_title, chunk_index FROM text_chunks ORDER BY book_id, page_start, id")
rows = c.fetchall()
conn.close()

print(f"Total text_chunks: {len(rows)}")

chunks_batch = []
current_book_id = ""
for i, (cid, current_book_id, page_start, text, meta_data, chapter_title, chunk_index) in enumerate(rows):
    if not text or len(text.strip()) < 5:
        continue
    
    meta = json.loads(meta_data) if meta_data else {}
    
    try:
        result = emb.embed_text_sync(text[:2000])
        if not result or not result.embedding:
            print(f"  [{i}] embed failed for {str(cid)[:12]}")
            continue
        vec = result.embedding
    except Exception as e:
        print(f"  [{i}] embed error for {str(cid)[:12]}: {e}")
        continue
    
    chunks_batch.append({
        "id": str(cid),
        "vector": vec,
        "content": text,
        "chapter": chapter_title or "",
        "page_start": page_start or 0,
        "page_end": page_start or 0,
        "chunk_index": chunk_index or 0,
        "metadata": meta,
    })
    
    if len(chunks_batch) >= BATCH_SIZE:
        try:
            qc.upsert_text_chunks(chunks_batch, current_book_id)
            print(f"  [{i+1}/{len(rows)}] {str(current_book_id)[:12]}... {len(chunks_batch)} chunks")
        except Exception as e:
            print(f"  [{i}] upsert error: {e}")
        chunks_batch = []

if chunks_batch:
    try:
        qc.upsert_text_chunks(chunks_batch, current_book_id)
        print(f"  [{len(rows)}/{len(rows)}] final batch")
    except Exception as e:
        print(f"  Final error: {e}")

count = qc.count_collection(qc.KNOWLEDGE_TEXTS_COLLECTION)
print(f"\nQdrant total points: {count}")
print("DONE")
