import sys
sys.path.insert(0, '.')
from app.core.database import SessionLocal
from app.models.tubi_analysis import TubiAnalysis
import os

session = SessionLocal()

# Issue 1: 检查11张新图的真实文件路径和是否存在
print("=" * 60)
print("【问题1】新图文件检查")
print("=" * 60)
new_records = session.query(TubiAnalysis).filter(TubiAnalysis.id >= 57).all()
for r in new_records:
    fp = r.filepath or ""
    # 尝试多种可能的路径
    possible_paths = [
        fp,
        fp.replace("/", "\\"),
        "data/uploads/" + os.path.basename(fp),
        "z:\\BaiduSync\\BaiduSyncdisk\\calligraphy-recognition\\backend\\" + fp.replace("/", "\\"),
        "z:\\BaiduSync\\BaiduSyncdisk\\calligraphy-recognition\\backend\\data\\uploads\\" + os.path.basename(fp),
    ]
    exists = None
    for p in possible_paths:
        if os.path.exists(p):
            exists = p
            break
    print(f"  id={r.id} | filepath='{fp}' | 文件存在={exists is not None} | title={r.title}")

# Issue 2: 检查分析方法和面积数据
print("\n" + "=" * 60)
print("【问题2】新图面积分析结果 vs 老图（V9）对比")
print("=" * 60)
# 新图前5条
new5 = session.query(TubiAnalysis).filter(TubiAnalysis.id >= 57).limit(5).all()
print("新图（当前方法）:")
for r in new5:
    print(f"  {r.title}: inscription={r.inscription_percent:.1f}% painting={r.painting_percent:.1f}% blank={r.blank_percent:.1f}%")

# 老图（应该是V9）
old5 = session.query(TubiAnalysis).filter(TubiAnalysis.id <= 38, TubiAnalysis.status == 'analyzed').limit(5).all()
print("老图（V9方法）:")
for r in old5:
    print(f"  {r.title}: inscription={r.inscription_percent:.1f}% painting={r.painting_percent:.1f}% blank={r.blank_percent:.1f}%")

# Issue 3: 检查content_analysis字段是否有数据
print("\n" + "=" * 60)
print("【问题3】content_analysis字段检查")
print("=" * 60)
sample = session.query(TubiAnalysis).filter(
    TubiAnalysis.inscription_content.isnot(None),
    TubiAnalysis.id <= 38
).limit(5).all()
for r in sample:
    print(f"  id={r.id} {r.title}:")
    print(f"    char_count={r.char_count} | word_count={r.word_count}")
    print(f"    theme_tags={r.theme_tags}")
    print(f"    content_analysis (first 100 chars)={str(r.content_analysis)[:100] if r.content_analysis else 'None'}")

session.close()
