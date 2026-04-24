"""
李鱓全集图片匹配脚本
- 源目录：E:\李鱓全集\修改版\待确认时间（86张，已裁剪画芯）
- 参考目录：E:\李鱓全集\（提取图片）扬州画派书画全集  李鳝_12772971（376张PDF书页）
- 任务：对每张源图，用pHash在参考页中找到最相似的那个，输出匹配表并重命名
"""

import os
import re
import imagehash
from PIL import Image
from glob import glob
from tqdm import tqdm
import pandas as pd

# ============ 路径配置 ============
SRC_DIR = r"E:\李鱓全集\修改版\待确认时间"
REF_DIR = r"E:\李鱓全集\（提取图片）扬州画派书画全集  李鳝_12772971"
OUTPUT_CSV = r"E:\李鱓全集\修改版\匹配表_2026-04-15.csv"

# ============ 1. 加载文件列表 ============
src_files = sorted([f for f in os.listdir(SRC_DIR) if f.lower().endswith(('.jpg', '.jpeg', '.png'))])
ref_files = sorted([f for f in os.listdir(REF_DIR) if f.lower().endswith(('.jpg', '.jpeg', '.png'))])

print(f"源文件数: {len(src_files)}")
print(f"参考文件数: {len(ref_files)}")

# 从参考文件名提取页码
def extract_page_num(filename):
    m = re.search(r'第(\d+)页', filename)
    return int(m.group(1)) if m else None

ref_page_map = {extract_page_num(f): f for f in ref_files}
all_ref_pages = sorted(ref_page_map.keys())
print(f"参考页码范围: {min(all_ref_pages)} - {max(all_ref_pages)}")

# ============ 2. 从源文件名提取已有页码标注 ============
def extract_embedded_page(fname):
    """从源文件名中提取 _pXXX 形式的页码"""
    m = re.search(r'_p(\d+)', fname)
    return int(m.group(1)) if m else None

# ============ 3. 计算参考页哈希（只计算一次） ============
print("\n正在计算参考页感知哈希...")
ref_hashes = {}
for fname in tqdm(ref_files, desc="参考页"):
    path = os.path.join(REF_DIR, fname)
    try:
        img = Image.open(path).convert('RGB')
        h = imagehash.phash(img)
        ref_hashes[fname] = h
    except Exception as e:
        print(f"  参考页读取失败 {fname}: {e}")

print(f"成功计算 {len(ref_hashes)} 个参考页哈希")

# ============ 4. 对每张源图做匹配 ============
results = []

# 已通过文件名中_pXXX确认的
confirmed = []
# 需要pHash匹配的
need_hash_match = []

for fname in src_files:
    embedded_page = extract_embedded_page(fname)
    row = {
        '源文件名': fname,
        '嵌入式页码': embedded_page,
        '匹配方式': '文件名_pXXX' if embedded_page else 'pHash匹配',
        '匹配页码': embedded_page,
        '匹配文件名': ref_page_map.get(embedded_page, 'N/A') if embedded_page else '',
        'pHash距离': '' if embedded_page else '',
        '汉明距离': '' if embedded_page else '',
        '新文件名': ''
    }

    if embedded_page:
        if embedded_page in ref_page_map:
            row['匹配文件名'] = ref_page_map[embedded_page]
            row['匹配页码'] = embedded_page
        confirmed.append(row)
    else:
        need_hash_match.append((fname, row))

# ============ 5. pHash 匹配 ============
print(f"\n已确认（文件名含_pXXX）: {len(confirmed)} 张")
print(f"需pHash匹配: {len(need_hash_match)} 张")

hash_matched = []
for fname, row in tqdm(need_hash_match, desc="pHash匹配"):
    src_path = os.path.join(SRC_DIR, fname)
    try:
        src_img = Image.open(src_path).convert('RGB')
        src_hash = imagehash.phash(src_img)

        # 找最近邻
        best_fname = None
        best_dist = 999
        for ref_fname, ref_hash in ref_hashes.items():
            dist = src_hash - ref_hash  # 汉明距离
            if dist < best_dist:
                best_dist = dist
                best_fname = ref_fname

        page_num = extract_page_num(best_fname) if best_fname else None
        row['匹配文件名'] = best_fname or ''
        row['匹配页码'] = page_num
        row['pHash距离'] = best_dist
        hash_matched.append(row)

    except Exception as e:
        row['匹配文件名'] = f'ERROR: {e}'
        hash_matched.append(row)

# ============ 6. 生成新文件名 ============
all_results = confirmed + hash_matched

def make_new_name(orig, page):
    """
    从原始文件名生成新文件名。
    策略：去掉旧的页码标注(_p数字)，保留年份部分，追加新页码。
    例: 松藤图_0000.jpg + p17 -> 松藤图_0000_p17.jpg
        百龄图_p123_0000.jpg + p123 -> 百龄图_0000_p123.jpg
        平山堂...藏_0000.jpg + p281 -> 平山堂...藏_0000_p281.jpg
    """
    # 去掉已有的 _p数字（页码标注），保留分隔下划线
    # _pXXX_0000 -> _0000 (保留 trailing _), _pXXX.jpg -> 空 (无 trailing _)
    base = re.sub(r'_p\d+(_?)', r'\1', orig, count=1)
    # 分离扩展名（取最后一个 . 之后的内容）
    parts = base.rsplit('.', 1)
    base_no_ext = parts[0]
    ext = parts[1] if len(parts) > 1 else ''
    return f"{base_no_ext}_p{page}.{ext}"

for row in all_results:
    orig = row['源文件名']
    page = row['匹配页码']

    if page:
        row['新文件名'] = make_new_name(orig, page)
    else:
        row['新文件名'] = orig  # 无法匹配，保留原名

# ============ 7. 保存匹配表 ============
df = pd.DataFrame(all_results)
df = df.sort_values(['匹配方式', '匹配页码'])
df.to_csv(OUTPUT_CSV, index=False, encoding='utf-8-sig')
print(f"\n匹配表已保存: {OUTPUT_CSV}")

# ============ 8. 打印摘要 ============
matched = df[df['匹配页码'].notna() & (df['匹配页码'] != '')]
unmatched = df[df['匹配页码'].isna() | (df['匹配页码'] == '')]
hash_distances = df[df['匹配方式'] == 'pHash匹配']['pHash距离']

print(f"\n{'='*60}")
print(f"匹配结果摘要")
print(f"{'='*60}")
print(f"总源文件: {len(df)}")
print(f"已匹配（含文件名确认+pHash）: {len(matched)}")
print(f"未匹配: {len(unmatched)}")
if len(hash_distances) > 0:
    print(f"\npHash匹配汉明距离统计:")
    print(f"  最小: {hash_distances.min()}")
    print(f"  最大: {hash_distances.max()}")
    print(f"  平均: {hash_distances.mean():.1f}")
print(f"\n前20条记录预览:")
print(df[['源文件名', '匹配方式', '匹配页码', 'pHash距离', '新文件名']].head(20).to_string(index=False))
