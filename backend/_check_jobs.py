import sys
sys.path.insert(0, '.')
from app.db.database import SessionLocal
from app.models.tubi_job import TubiJob
db = SessionLocal()

print('Latest jobs:')
for j in db.query(TubiJob).order_by(TubiJob.created_at.desc()).limit(5).all():
    print(f'id={j.job_id} image={j.image_id} status={j.status} error={j.error_msg if j.error_msg else None}')
