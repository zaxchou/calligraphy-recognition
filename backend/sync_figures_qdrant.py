"""
Sync corrected figure_metadata.json to Qdrant knowledge_images collection.
Uses same UUID generation logic as bird_flower_ingest.py (uuid5 + NAMESPACE_URL).
"""
import sys, os, json, time, uuid
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

BACKEND_DIR = Path(__file__).resolve().parent
os.chdir(BACKEND_DIR)
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv
load_dotenv(BACKEND_DIR / ".env")

import httpx
from app.modules.pantianshou_composition.qdrant_client import _get_client, _base_url, _headers

META_PATH = BACKEND_DIR / "data" / "knowledge" / "figure_metadata.json"
COLLECTION = "knowledge_images"

with open(META_PATH, "r", encoding="utf-8") as f:
    metadata = json.load(f)

print(f"[INFO] Loaded {len(metadata)} metadata items")

client = _get_client(10.0)
base = _base_url()
if not base:
    print("[ERROR] Qdrant URL not configured!")
    sys.exit(1)
print(f"[INFO] Qdrant: {base}")

# Load audit record for changed keys
audit_path = BACKEND_DIR / "data" / "knowledge" / "figure_metadata_audited.json"
changed_keys = set()
if audit_path.exists():
    with open(audit_path, "r", encoding="utf-8") as f:
        audit = json.load(f)
    for r in audit.get("results", []):
        if r.get("changed"):
            changed_keys.add(r["key"])
else:
    changed_keys = set(metadata.keys())
print(f"[INFO] Items to sync: {len(changed_keys)}")

synced = 0
failed = 0

for key in sorted(changed_keys):
    if key not in metadata:
        continue
    item = metadata[key]
    if not isinstance(item, dict):
        continue

    # Generate same UUID as bird_flower_ingest.py line 180:
    #   point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"knowledge_fig:{fm.figure_id}"))
    figure_id_raw = key  # The metadata dict key IS the figure_id (e.g., "图七")
    point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"knowledge_fig:{figure_id_raw}"))

    fn = item.get("filename", "")

    payload = {}
    if "figure_type" in item:
        payload["figure_type"] = item["figure_type"]
    payload["artist"] = item.get("artist", "") or ""
    payload["artwork_title"] = item.get("artwork_title", "") or ""
    if item.get("era"):
        payload["era"] = item["era"]
    if item.get("description"):
        payload["description"] = item["description"]

    try:
        url = f"{base}/collections/{COLLECTION}/points/payload"
        resp = client.post(
            url,
            json={"payload": payload, "points": [point_id]},
            headers=_headers(),
        )
        resp.raise_for_status()
        synced += 1
        ft = item.get("figure_type", "?")
        artist = item.get("artist", "") or "(none)"
        title = item.get("artwork_title", "") or "(none)"
        print(f"  [{synced}] {fn}: type={ft} | {artist}/{title}")
    except httpx.HTTPStatusError as e:
        failed += 1
        err_text = e.response.text[:120] if e.response else ""
        print(f"  [FAIL] {fn}: HTTP {e.response.status_code} - {err_text}")
    except Exception as e:
        failed += 1
        print(f"  [FAIL] {fn}: {e}")

    time.sleep(0.03)

print(f"\n{'='*60}")
print(f"sync complete: synced={synced}, failed={failed}")
