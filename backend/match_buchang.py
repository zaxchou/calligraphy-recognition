"""补漏目录图片 pHash 匹配并移动到待确认时间目录"""
import os, re, shutil
import imagehash
from PIL import Image
import pandas as pd
from tqdm import tqdm

src_dir = r"E:\李鱓全集\修改版\待确认补漏"
ref_dir = r"E:\李鱓全集\（提取图片）扬州画派书画全集  李鳝_12772971"
dest_dir = r"E:\李鱓全集\修改版\待确认时间"

src_files = sorted([f for f in os.listdir(src_dir) if f.lower().endswith(('.jpg', '.jpeg', '.png'))])
ref_files = sorted([f for f in os.listdir(ref_dir) if f.lower().endswith(('.jpg', '.jpeg', '.png'))])

print(f"源文件: {len(src_files)} | 参考书: {len(ref_files)}")

# 预计算参考书所有 pHash
print("正在计算参考书 pHash ...")
ref_hashes = {}
for rf in tqdm(ref_files):
    try:
        h = imagehash.phash(Image.open(os.path.join(ref_dir, rf)))
        ref_hashes[rf] = h
    except Exception as e:
        print(f"  skip {rf}: {e}")

# 逐个匹配源文件
results = []
for sf in tqdm(src_files, desc="匹配中"):
    src_path = os.path.join(src_dir, sf)
    src_h = imagehash.phash(Image.open(src_path))

    best_dist = 999
    best_ref = None
    for rf, rh in ref_hashes.items():
        d = src_h - rh
        if d < best_dist:
            best_dist = d
            best_ref = rf

    # 从参考文件名提取页码: "第123页-123.JPG" -> 123
    m = re.search(r'第(\d+)页', best_ref)
    page_num = int(m.group(1)) if m else None

    # 构造新文件名
    name_part = sf.rsplit('.', 1)[0]
    name_part = re.sub(r'_p\d+(_?)', r'\1', name_part, count=1)
    ext = sf.rsplit('.', 1)[-1]
    new_name = f"{name_part}_p{page_num}.{ext}"

    results.append({
        "源文件": sf,
        "匹配页": best_ref,
        "页码": page_num,
        "汉明距": best_dist,
        "新文件名": new_name,
    })
    print(f"  {sf} -> {best_ref} (距{best_dist}) -> {new_name}")

# 移动文件
moved = 0
skipped = []
for r in results:
    src_path = os.path.join(src_dir, r["源文件"])
    dst_path = os.path.join(dest_dir, r["新文件名"])
    if os.path.exists(dst_path):
        print(f"  [WARN] 目标已存在，跳过: {r['新文件名']}")
        skipped.append(r)
        continue
    shutil.move(src_path, dst_path)
    moved += 1

print(f"\n完成：移动 {moved}/{len(results)} 个文件")
if skipped:
    print(f"跳过: {[r['新文件名'] for r in skipped]}")

df = pd.DataFrame(results)
csv_path = os.path.join(os.path.dirname(dest_dir), "匹配表_补漏_2026-04-16.csv")
df.to_csv(csv_path, index=False, encoding="utf-8-sig")
print(f"匹配表: {csv_path}")
