import sys, os, json, numpy as np, time, sqlite3, base64, requests, argparse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app.core.config import BASE_DIR, get_settings

settings = get_settings()
API_KEY = settings.SILICONFLOW_API_KEY
SF_URL = "https://api.siliconflow.cn/v1/embeddings"
MODEL = "Qwen/Qwen3-VL-Embedding-8B"


def embed(img_path):
    with open(img_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    payload = {"model": MODEL, "input": f"data:image/jpeg;base64,{b64}", "encoding_format": "float"}
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    for attempt in range(3):
        try:
            resp = requests.post(SF_URL, json=payload, headers=headers, timeout=90)
            if resp.status_code == 200:
                return resp.json()["data"][0]["embedding"]
        except Exception:
            pass
        if attempt < 2:
            time.sleep(2 ** attempt)
    return None


def main():
    parser = argparse.ArgumentParser(description="构建图像相似度搜索索引")
    parser.add_argument("--artist", default="all")
    args = parser.parse_args()

    db_path = settings.DATABASE_URL.replace("sqlite:///", "")
    conn = sqlite3.connect(db_path, timeout=30)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    if args.artist == "all":
        cur.execute("SELECT id, thumbnail_path FROM tubi_analyses WHERE thumbnail_path IS NOT NULL AND thumbnail_path != ''")
    else:
        cur.execute("SELECT id, thumbnail_path FROM tubi_analyses WHERE artist = ? AND thumbnail_path IS NOT NULL AND thumbnail_path != ''", (args.artist,))
    rows = cur.fetchall()
    conn.close()

    print(f"Building index: {len(rows)} works (artist={args.artist})")

    import faiss
    tmp = faiss.IndexFlatIP(4096)
    id_map = []
    ok = 0
    skip = 0
    t0 = time.time()

    for i, r in enumerate(rows):
        clean = r["thumbnail_path"].replace("\\", "/").lstrip("/")
        local = os.path.normpath(os.path.join(BASE_DIR, clean))
        if not os.path.exists(local):
            skip += 1
            continue
        vec = embed(local)
        if vec and len(vec) == 4096 and any(v != 0 for v in vec):
            arr = np.array([vec], dtype=np.float32)
            faiss.normalize_L2(arr)
            tmp.add(arr)
            id_map.append(r["id"])
            ok += 1
        else:
            skip += 1
        time.sleep(0.3)
        if (i + 1) % 30 == 0:
            print(f"  {i+1}/{len(rows)} ok={ok} skip={skip} {time.time()-t0:.0f}s")

    idx_dir = os.path.join(BASE_DIR, "data", ".image_index")
    os.makedirs(idx_dir, exist_ok=True)
    faiss.write_index(tmp, os.path.join(idx_dir, "image_index.faiss"))
    with open(os.path.join(idx_dir, "image_index_idmap.json"), "w") as f:
        json.dump(id_map, f)
    print(f"DONE: {ok} indexed, {skip} skipped, {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
