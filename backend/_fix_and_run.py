"""修复11张新图的thumbnail_path，然后重新入队pending记录"""
import sys
sys.path.insert(0, '.')
from app.core.database import SessionLocal
from app.models.tubi_analysis import TubiAnalysis
from app.core.config import get_settings
import redis
import json

settings = get_settings()
r = redis.Redis(host='localhost', port=6379, decode_responses=True)

session = SessionLocal()

# 修复 thumbnail_path 前缀错误
new_records = session.query(TubiAnalysis).filter(TubiAnalysis.id >= 57).all()
fixed = 0
for rec in new_records:
    if rec.thumbnail_path and rec.thumbnail_path.startswith('static/'):
        rec.thumbnail_path = 'data/' + rec.thumbnail_path[len('static/'):]
        print(f"修复 id={rec.id}: static/ -> data/")
        fixed += 1
    # 如果 status=pending 或不是 analyzed，重新入队
    if rec.status in ('pending', 'uploaded'):
        task = {
            'record_id': rec.id,
            'image_path': rec.filepath,
            'priority': 1
        }
        r.lpush('tubi:queue:pending', json.dumps(task))
        print(f"入队 id={rec.id} title={rec.title} status={rec.status}")

session.commit()
print(f"\n共修复 {fixed} 条 thumbnail_path")

# 同时把 id=67 (长年百子富贵图) 状态改成 pending 重新入队
rec67 = session.query(TubiAnalysis).filter(TubiAnalysis.id == 67).first()
if rec67:
    rec67.status = 'pending'
    session.commit()
    task = {
        'record_id': 67,
        'image_path': rec67.filepath,
        'priority': 1
    }
    r.lpush('tubi:queue:pending', json.dumps(task))
    print(f"id=67 重新入队")

session.close()
print("完成！")
