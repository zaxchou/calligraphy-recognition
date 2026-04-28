import json
import logging
import os
import sqlite3
import time
from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class SearchHit:
    record_id: int
    title: str
    artist: str
    score: float
    thumbnail_url: str
    year: Optional[int] = None
    album_name: Optional[str] = None
    inscription_percent: Optional[float] = None


class ImageSearchEngine:
    def __init__(self, index_dir: str = None):
        import faiss
        self.faiss = faiss

        if index_dir is None:
            from app.core.config import BASE_DIR
            index_dir = os.path.join(BASE_DIR, "data", ".image_index")
        self.index_dir = index_dir
        os.makedirs(self.index_dir, exist_ok=True)

        self.index: Optional[faiss.IndexFlatIP] = None
        self.id_map: List[int] = []
        self.embedding_dim: int = 1024

        self._load_index()

    def _index_path(self) -> str:
        return os.path.join(self.index_dir, "image_index.faiss")

    def _idmap_path(self) -> str:
        return os.path.join(self.index_dir, "image_index_idmap.json")

    def _load_index(self) -> bool:
        ipath = self._index_path()
        mpath = self._idmap_path()
        if os.path.exists(ipath) and os.path.exists(mpath):
            try:
                self.index = self.faiss.read_index(ipath)
                with open(mpath, "r") as f:
                    self.id_map = json.load(f)
                logger.info("加载图像索引: %d 条, 维度=%d", self.index.ntotal, self.index.d)
                self.embedding_dim = self.index.d
                return True
            except Exception as e:
                logger.warning("加载索引失败: %s, 将重建", e)
        return False

    def _save_index(self):
        if self.index is None:
            return
        self.faiss.write_index(self.index, self._index_path())
        with open(self._idmap_path(), "w") as f:
            json.dump(self.id_map, f)

    def _get_conn(self):
        from app.core.config import get_settings
        settings = get_settings()
        db_path = settings.DATABASE_URL.replace("sqlite:///", "")
        conn = sqlite3.connect(db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        return conn

    def _get_thumbnail_local_path(self, thumb_path: str) -> str:
        if not thumb_path:
            return ""
        from app.core.config import BASE_DIR
        clean = thumb_path.replace("\\", "/").lstrip("/")
        abs_path = os.path.normpath(os.path.join(BASE_DIR, clean))
        if os.path.exists(abs_path):
            return abs_path
        return ""

    def build_index(self, artist: str = "all") -> dict:
        conn = self._get_conn()
        cur = conn.cursor()

        if artist == "all":
            cur.execute("SELECT id, title, artist, thumbnail_path, year, album_name, inscription_percent FROM tubi_analyses WHERE thumbnail_path IS NOT NULL AND thumbnail_path != ''")
        else:
            cur.execute("SELECT id, title, artist, thumbnail_path, year, album_name, inscription_percent FROM tubi_analyses WHERE artist = ? AND thumbnail_path IS NOT NULL AND thumbnail_path != ''", (artist,))

        rows = cur.fetchall()
        conn.close()

        total = len(rows)
        if not rows:
            return {"ok": False, "error": "没有找到有缩略图的作品", "total": 0}

        from app.modules.pantianshou_composition.embedding_service import EmbeddingService
        svc = EmbeddingService()

        self.index = self.faiss.IndexFlatIP(self.embedding_dim)
        self.id_map = []

        t0 = time.time()

        indexed = 0
        skipped = 0
        for r in rows:
            local = self._get_thumbnail_local_path(r["thumbnail_path"])
            if not local:
                skipped += 1
                continue

            result = svc.embed_image_sync(local)
            if result and result.embedding and any(v != 0 for v in result.embedding):
                vec = np.array([result.embedding], dtype=np.float32)
                self.faiss.normalize_L2(vec)
                self.index.add(vec)
                self.id_map.append(r["id"])
                indexed += 1
            else:
                skipped += 1

            if indexed % 50 == 0 and indexed > 0:
                elapsed = time.time() - t0
                logger.info("索引进度: %d/%d, 耗时 %.1fs", indexed, total, elapsed)

        self._save_index()
        elapsed = time.time() - t0
        logger.info("索引构建完成: %d 条, 跳过 %d, 耗时 %.1fs", indexed, skipped, elapsed)
        return {"ok": True, "total": indexed, "skipped": skipped, "elapsed": round(elapsed, 1)}

    def search(self, image_path: str, top_k: int = 10) -> List[SearchHit]:
        if self.index is None or self.index.ntotal == 0:
            return []

        from app.modules.pantianshou_composition.embedding_service import EmbeddingService
        svc = EmbeddingService()
        result = svc.embed_image_sync(image_path)

        if not result or not result.embedding or all(v == 0 for v in result.embedding):
            return []

        query = np.array([result.embedding], dtype=np.float32)
        self.faiss.normalize_L2(query)
        distances, indices = self.index.search(query, min(top_k, self.index.ntotal))

        hits = []
        conn = self._get_conn()
        cur = conn.cursor()
        for dist, idx in zip(distances[0], indices[0]):
            if idx < 0 or idx >= len(self.id_map):
                continue
            record_id = self.id_map[idx]
            cur.execute("SELECT id, title, artist, thumbnail_path, year, album_name, inscription_percent FROM tubi_analyses WHERE id = ?", (record_id,))
            r = cur.fetchone()
            if r:
                thumb_url = ""
                if r["thumbnail_path"]:
                    fn = os.path.basename(r["thumbnail_path"].replace("\\", "/"))
                    thumb_url = f"/static/thumbnails/{fn}"
                hits.append(SearchHit(
                    record_id=r["id"],
                    title=r["title"] or "未命名",
                    artist=r["artist"] or "",
                    score=round(float(dist), 4),
                    thumbnail_url=thumb_url,
                    year=r["year"],
                    album_name=r["album_name"],
                    inscription_percent=r["inscription_percent"],
                ))
        conn.close()
        return hits

    def find_duplicates(self, threshold: float = 0.95) -> List[dict]:
        if self.index is None or self.index.ntotal < 2:
            return []

        xb = np.zeros((self.index.ntotal, self.embedding_dim), dtype=np.float32)
        self.index.reconstruct_n(0, self.index.ntotal, xb)
        self.faiss.normalize_L2(xb)

        distances, indices = self.index.search(xb, min(10, self.index.ntotal))

        conn = self._get_conn()
        cur = conn.cursor()
        pairs = []
        seen = set()
        for i in range(self.index.ntotal):
            for j_idx in range(1, len(indices[i])):
                j = indices[i][j_idx]
                if j < 0:
                    continue
                sim = float(distances[i][j_idx])
                if sim < threshold:
                    break
                a, b = self.id_map[i], self.id_map[j]
                pair_key = tuple(sorted([a, b]))
                if pair_key in seen:
                    continue
                seen.add(pair_key)

                cur.execute("SELECT id, title, artist, thumbnail_path, year FROM tubi_analyses WHERE id IN (?, ?)", (a, b))
                rows = {r["id"]: dict(r) for r in cur.fetchall()}
                ra, rb = rows.get(a), rows.get(b)
                if not ra or not rb:
                    continue

                def thumb(r):
                    if r and r.get("thumbnail_path"):
                        fn = os.path.basename(r["thumbnail_path"].replace("\\", "/"))
                        return f"/static/thumbnails/{fn}"
                    return ""

                pairs.append({
                    "score": round(sim, 4),
                    "a": {
                        "id": ra.get("id"),
                        "title": ra.get("title", "未命名"),
                        "artist": ra.get("artist", ""),
                        "thumbnail_url": thumb(ra),
                        "year": ra.get("year"),
                    },
                    "b": {
                        "id": rb.get("id"),
                        "title": rb.get("title", "未命名"),
                        "artist": rb.get("artist", ""),
                        "thumbnail_url": thumb(rb),
                        "year": rb.get("year"),
                    },
                })
        conn.close()
        pairs.sort(key=lambda x: -x["score"])
        return pairs

    def add_to_index(self, record_id: int, thumbnail_path: str) -> bool:
        if self.index is None:
            return False
        local = self._get_thumbnail_local_path(thumbnail_path)
        if not local:
            return False

        from app.modules.pantianshou_composition.embedding_service import EmbeddingService
        svc = EmbeddingService()
        result = svc.embed_image_sync(local)
        if not result or not result.embedding or all(v == 0 for v in result.embedding):
            return False

        vec = np.array([result.embedding], dtype=np.float32)
        self.faiss.normalize_L2(vec)
        self.index.add(vec)
        self.id_map.append(record_id)
        self._save_index()
        return True

    @property
    def total_indexed(self) -> int:
        return self.index.ntotal if self.index else 0


_engine: Optional[ImageSearchEngine] = None


def get_search_engine() -> ImageSearchEngine:
    global _engine
    if _engine is None:
        _engine = ImageSearchEngine()
    return _engine
