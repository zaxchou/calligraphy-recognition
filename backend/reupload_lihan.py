"""
重新上传李鱓作品图片
- 从 E:\下载\0413 读取图片
- 复制到 data/uploads/ 并重命名为 UUID
- 生成缩略图到 data/thumbnails/
- 更新数据库 filepath 和 thumbnail_path
"""
import sqlite3, os, shutil, uuid, re
from PIL import Image

# 配置
SOURCE_DIR = r'E:\下载\0413'
UPLOAD_DIR = 'data/uploads'
THUMB_DIR = 'data/thumbnails'
DB_PATH = 'data/calligraphy.db'
THUMB_SIZE = (400, 400)  # 缩略图最大尺寸

# 确保目录存在
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(THUMB_DIR, exist_ok=True)

def generate_thumbnail(src_path, thumb_path):
    """生成缩略图"""
    try:
        img = Image.open(src_path)
        img.thumbnail(THUMB_SIZE, Image.Resampling.LANCZOS)
        img.save(thumb_path, 'JPEG', quality=85)
        return True
    except Exception as e:
        print(f'  缩略图生成失败: {e}')
        return False

def parse_filename(fn):
    """解析文件名: 清_李鱓_作品名_年份.jpg"""
    m = re.match(r'清_李鱓_(.+?)_(\d{4})\.jpg', fn)
    if m:
        return m.group(1), int(m.group(2))
    return None, None

# 连接数据库
conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# 获取所有文件
files = [f for f in os.listdir(SOURCE_DIR) if f.endswith('.jpg')]
print(f'找到 {len(files)} 个文件\n')

updated = 0
failed = 0

for fn in files:
    src_path = os.path.join(SOURCE_DIR, fn)
    title, year = parse_filename(fn)
    
    if not title:
        print(f'{fn} -> 无法解析文件名')
        failed += 1
        continue
    
    # 查数据库 - 精确匹配年份
    cur.execute(
        "SELECT id, title FROM tubi_analyses WHERE (title LIKE ? OR title = ?) AND year = ?",
        (f'%{title}%', title, year)
    )
    rows = cur.fetchall()
    
    if not rows:
        print(f'{fn} -> 无匹配记录 (title={title}, year={year})')
        failed += 1
        continue
    
    # 取第一个匹配（如果多个，取年份精确匹配的）
    record_id = rows[0][0]
    
    # 生成 UUID 文件名
    file_uuid = str(uuid.uuid4())
    new_filename = f'{file_uuid}.jpg'
    thumb_filename = f'{file_uuid}_thumb.jpg'
    
    dest_path = os.path.join(UPLOAD_DIR, new_filename)
    thumb_path = os.path.join(THUMB_DIR, thumb_filename)
    
    # 复制文件
    try:
        shutil.copy2(src_path, dest_path)
        print(f'{fn}')
        print(f'  -> {new_filename}')
    except Exception as e:
        print(f'{fn} -> 复制失败: {e}')
        failed += 1
        continue
    
    # 生成缩略图
    thumb_ok = generate_thumbnail(dest_path, thumb_path)
    if thumb_ok:
        print(f'  -> {thumb_filename}')
    
    # 更新数据库
    db_filepath = f'data/uploads/{new_filename}'
    db_thumbpath = f'data/thumbnails/{thumb_filename}' if thumb_ok else None
    
    cur.execute(
        "UPDATE tubi_analyses SET filepath = ?, thumbnail_path = ? WHERE id = ?",
        (db_filepath, db_thumbpath, record_id)
    )
    
    print(f'  更新数据库: id={record_id}')
    print()
    updated += 1

conn.commit()
conn.close()

print(f'\n完成: 成功 {updated} 个, 失败 {failed} 个')
