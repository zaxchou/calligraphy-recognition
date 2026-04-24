"""
李鱓全集图片重命名脚本（Step 1 完成）
根据匹配表，为源文件加上 _p页码 后缀
"""
import os
import pandas as pd
import shutil

SRC_DIR = r"E:\李鱓全集\修改版\待确认时间"
CSV_PATH = r"E:\李鱓全集\修改版\匹配表_2026-04-15.csv"
BACKUP_DIR = r"E:\李鱓全集\修改版\待确认时间_backup_2026-04-15"

# 1. 备份
print(f"创建备份目录: {BACKUP_DIR}")
os.makedirs(BACKUP_DIR, exist_ok=True)
for fname in os.listdir(SRC_DIR):
    src = os.path.join(SRC_DIR, fname)
    dst = os.path.join(BACKUP_DIR, fname)
    shutil.copy2(src, dst)
print(f"备份完成: {len(os.listdir(BACKUP_DIR))} 个文件")

# 2. 重命名
df = pd.read_csv(CSV_PATH, encoding='utf-8-sig')
renamed = 0
skipped = 0
errors = []

for _, row in df.iterrows():
    orig = row['源文件名']
    new_name = row['新文件名']

    if pd.isna(new_name) or new_name == orig:
        skipped += 1
        continue

    src_path = os.path.join(SRC_DIR, orig)
    dst_path = os.path.join(SRC_DIR, new_name)

    if not os.path.exists(src_path):
        errors.append(f"源文件不存在: {orig}")
        continue

    # 处理重名情况
    if os.path.exists(dst_path) and dst_path != src_path:
        errors.append(f"目标文件已存在: {new_name}")
        continue

    os.rename(src_path, dst_path)
    renamed += 1
    print(f"  {orig} -> {new_name}")

print(f"\n重命名完成: {renamed} 个文件")
if skipped:
    print(f"跳过: {skipped} 个文件（无匹配或无变化）")
if errors:
    print(f"错误: {errors}")
