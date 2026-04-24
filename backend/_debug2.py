import sys
sys.path.insert(0, '.')
from app.core.database import SessionLocal
from app.models.tubi_analysis import TubiAnalysis

session = SessionLocal()

# 检查旧图 filepath 格式
old = session.query(TubiAnalysis).filter(TubiAnalysis.id <= 38).limit(3).all()
print("旧图 filepath:")
for r in old:
    print(f"  id={r.id} filepath='{r.filepath}'")

# 检查 content_analysis 是否已对新图生效
new_ca = session.query(TubiAnalysis).filter(
    TubiAnalysis.id >= 57,
    TubiAnalysis.inscription_content.isnot(None)
).count()
new_total = session.query(TubiAnalysis).filter(TubiAnalysis.id >= 57).count()
print(f"\n新图(57-67) inscription_content 有值: {new_ca}/{new_total}")

# 检查 content_analysis 是否已对新图写入
new_ca2 = session.query(TubiAnalysis).filter(
    TubiAnalysis.id >= 57,
    TubiAnalysis.content_analysis.isnot(None)
).count()
print(f"新图 content_analysis 有值: {new_ca2}/{new_total}")

# 检查 inscription_verified 字段情况
verified_counts = session.query(
    TubiAnalysis.inscription_verified
).filter(TubiAnalysis.id <= 38).all()
from collections import Counter
vc = Counter([r[0] for r in verified_counts])
print(f"\n旧图(<=38) inscription_verified: {dict(vc)}")

# 检查新版图片 inscription_percent=0 的原因
# 查一下 annotation_data 是否存在
print("\n新图 annotation_data:")
for r in session.query(TubiAnalysis).filter(TubiAnalysis.id >= 57).limit(3).all():
    ad = r.annotation_data
    print(f"  id={r.id} annotation_data exists={ad is not None}, type={type(ad).__name__}, first 80={str(ad)[:80] if ad else 'None'}")

session.close()
