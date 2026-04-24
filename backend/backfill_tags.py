"""
一次性回填脚本：为所有已分析记录补写 tags 字段
用法：python backfill_tags.py
"""
import sys, os, json
sys.stdout = __import__('io').TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, '.')
os.chdir('z:/BaiduSync/BaiduSyncdisk/calligraphy-recognition/backend')

from app.core.database import SessionLocal
from app.models.tubi_analysis import TubiAnalysis
from app.services.auto_tags import compute_tags

def main():
    db = SessionLocal()
    try:
        records = db.query(TubiAnalysis).filter(TubiAnalysis.status == 'analyzed').all()
        print(f"共 {len(records)} 条已分析记录，开始回填标签...")

        updated = 0
        skipped = 0
        for r in records:
            try:
                record_for_tags = {
                    "title": r.title,
                    "period_phase": r.period_phase,
                    "artwork_height_cm": r.artwork_height_cm,
                    "artwork_width_cm": r.artwork_width_cm,
                    "content_analysis": r.content_analysis,
                    "material_tags": r.material_tags,
                }
                auto_tags = compute_tags(record_for_tags)
                if not auto_tags:
                    skipped += 1
                    continue

                existing_tags = []
                if r.tags:
                    try:
                        existing_tags = json.loads(r.tags) if isinstance(r.tags, str) else r.tags
                    except Exception:
                        existing_tags = []
                if not isinstance(existing_tags, list):
                    existing_tags = []

                added = 0
                for tag in auto_tags:
                    if tag not in existing_tags:
                        existing_tags.append(tag)
                        added += 1

                if added > 0:
                    r.tags = json.dumps(existing_tags, ensure_ascii=False)
                    r.updated_at = __import__('datetime').datetime.now()
                    db.commit()
                    updated += 1
                    print(f"  [{r.image_id}] {r.title}: +{added}标签")
                else:
                    skipped += 1
            except Exception as e:
                print(f"  [错误] {r.image_id}: {e}")
                db.rollback()

        print(f"\n完成: 更新={updated} 跳过={skipped}")
    finally:
        db.close()

if __name__ == '__main__':
    main()
