"""
Generate DZI tiles for existing uploaded images that don't have them yet.
Run once after deploying the DZI feature.
"""
import os
import sys
import sqlite3

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.services.dzi_generator import generate_dzi

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(BASE, 'data', 'calligraphy.db')
UPLOAD_DIR = os.path.join(BASE, 'data', 'uploads')
DZI_DIR = os.path.join(BASE, 'data', 'dzi')
os.makedirs(DZI_DIR, exist_ok=True)

conn = sqlite3.connect(DB)
rows = conn.execute("SELECT id, filepath, filename FROM tubi_analyses WHERE filepath IS NOT NULL OR filename IS NOT NULL").fetchall()

generated = 0
skipped = 0
failed = 0

for r in rows:
    aid, filepath, filename = r
    
    # Determine actual file path
    if filepath and os.path.exists(filepath):
        fp = filepath
    elif filename:
        fp = os.path.join(UPLOAD_DIR, filename)
        if not os.path.exists(fp):
            fp = None
    else:
        fp = None
    
    if not fp:
        continue
    
    # Check if DZI already exists
    base_name = os.path.splitext(os.path.basename(fp))[0]
    dzi_path = os.path.join(DZI_DIR, f"{base_name}.dzi")
    if os.path.exists(dzi_path):
        skipped += 1
        continue
    
    print(f"[{aid}] Generating DZI for: {basename(fp)}...", end=" ")
    result = generate_dzi(fp, DZI_DIR)
    if result:
        generated += 1
        print(f"OK -> {basename(result)}")
    else:
        failed += 1
        print("FAILED")

conn.close()
print(f"\nDone: {generated} generated, {skipped} skipped, {failed} failed")
