import sys
sys.path.insert(0, '.')
from app.core.database import SessionLocal
from app.models.tubi_analysis import TubiAnalysis
from app.core.config import get_settings
import os

settings = get_settings()
session = SessionLocal()

UPLOAD_DIR = settings.UPLOAD_DIR
THUMBNAIL_DIR = settings.TUBI_THUMBNAIL_DIR

print(f"UPLOAD_DIR: {UPLOAD_DIR}")
print(f"THUMBNAIL_DIR: {THUMBNAIL_DIR}")
print()

new_records = session.query(TubiAnalysis).filter(TubiAnalysis.id >= 57).all()
for r in new_records:
    print(f"id={r.id} | title={r.title}")
    print(f"  filepath db value:     '{r.filepath}'")
    print(f"  thumbnail_path db val: '{r.thumbnail_path}'")

    # Simulate _to_local_path logic
    def to_local_path(p):
        if not p:
            return ""
        p2 = p.replace("/", os.sep)
        if os.path.isabs(p2) or (len(p2) >= 2 and p2[1] == ":"):
            return os.path.normpath(p2)
        p2 = p2.lstrip("\\/")
        proj = os.environ.get('PROJECT_ROOT', 'Z:\\BaiduSync\\BaiduSyncdisk\\calligraphy-recognition\\backend')
        return os.path.normpath(os.path.join(proj, p2))

    tp_local = to_local_path(r.thumbnail_path) if r.thumbnail_path else None
    fp_local = to_local_path(r.filepath) if r.filepath else None
    print(f"  resolved thumb local:  '{tp_local}'")
    print(f"  thumb exists:          {os.path.exists(tp_local) if tp_local else 'N/A'}")
    print(f"  resolved upload local:  '{fp_local}'")
    print(f"  upload exists:          {os.path.exists(fp_local) if fp_local else 'N/A'}")
    print()

session.close()
