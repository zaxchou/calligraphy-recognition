"""
E:\李鱓全集\修改版\已校对第二批 目录图片 pHash 匹配
结果直接写到 txt，不改文件名
"""
import os, sys, imagehash
from PIL import Image
from tqdm import tqdm

SRC_DIR = r"E:\李鱓全集\修改版\已校对第二批"
REF_DIR = r"E:\李鱓全集\（提取图片）扬州画派书画全集  李鳝_12772971"
OUT_TXT = r"E:\李鱓全集\修改版\已校对第二批_匹配结果.txt"

# 只取无括号的版本（标准页）
ref_files = [f for f in os.listdir(REF_DIR) if not "(1)" in f and f.lower().endswith((".jpg", ".jpeg", ".png"))]
print(f"源文件: {len(os.listdir(SRC_DIR))} | 参考书: {len(ref_files)}")

print("正在计算参考书 pHash ...")
ref_hashes = {}
for fname in tqdm(ref_files):
    fpath = os.path.join(REF_DIR, fname)
    try:
        h = imagehash.phash(Image.open(fpath))
        ref_hashes[fname] = h
    except Exception as e:
        print(f"  跳过（损坏）: {fname} -> {e}")

src_files = [f for f in os.listdir(SRC_DIR) if f.lower().endswith((".jpg", ".jpeg", ".png"))]
print(f"正在匹配 {len(src_files)} 张源图 ...")

lines = []
for fname in tqdm(src_files):
    fpath = os.path.join(SRC_DIR, fname)
    try:
        src_h = imagehash.phash(Image.open(fpath))
    except Exception as e:
        lines.append(f"{fname} -> 读取失败: {e}")
        continue

    best_name, best_dist = None, 999
    for rname, rh in ref_hashes.items():
        d = src_h - rh
        if d < best_dist:
            best_dist = d
            best_name = rname

    page_num = best_name.replace("第", "").replace("页-", "p").replace(".JPG", "").replace(".jpg", "") if best_name else "未匹配"
    lines.append(f"{fname} -> {best_name} (距{best_dist}) -> {page_num}")

lines.sort()
with open(OUT_TXT, "w", encoding="utf-8") as f:
    f.write("\n".join(lines))

print(f"\n完成，结果已写入: {OUT_TXT}")
