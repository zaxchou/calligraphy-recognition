"""
全量数据审计+修复脚本
1. 列出所有疑似非画家（演员、导演等）
2. 列出所有生卒年缺失的人物
3. 潘天寿已有照片生成缩略图
4. 百度CDN头像下载到本地
"""
import sqlite3, os, json, urllib.request, io, hashlib, shutil, ssl

BASE = r'Z:\BaiduSync\BaiduSyncdisk\calligraphy-recognition\backend'
DB = os.path.join(BASE, 'data', 'calligraphy.db')
UPLOAD_DIR = os.path.join(BASE, 'uploads')
os.makedirs(UPLOAD_DIR, exist_ok=True)

conn = sqlite3.connect(DB)
conn.execute("PRAGMA journal_mode=WAL")

def get_static_url(filename):
    return f"/static/uploads/{filename}"

# ===== 1. 列出疑似非画家 =====
print("=" * 60)
print("1. 疑似非画家（演员/导演/歌手/主持人/制片）")
print("=" * 60)
NON_ARTIST_KW = ['演员', '歌手', '导演', '主持人', '编剧', '制片', '模特']
suspicious = set()
for kw in NON_ARTIST_KW:
    rows = conn.execute(
        f"SELECT id, name, occupation, dynasty, birth_year, death_year, substr(biography,1,100) FROM artists WHERE (occupation LIKE '%{kw}%' OR biography LIKE '%{kw}%') AND occupation NOT LIKE '%画家%' AND occupation NOT LIKE '%书法%'"
    ).fetchall()
    for r in rows:
        suspicious.add(r[0])
        print(f'  [{kw}] id={r[0]} {r[1]}: {r[2][:30]}, {r[3]}, {r[4]}-{r[5]}')

print(f"\n共 {len(suspicious)} 个疑似非画家")

# ===== 2. 生卒年缺失全量 =====
print("\n" + "=" * 60)
print("2. 生卒年全部缺失的人物")
print("=" * 60)
missing = conn.execute("""
    SELECT id, name, dynasty, birth_year, death_year
    FROM artists 
    WHERE (birth_year IS NULL OR birth_year = 0) AND (death_year IS NULL OR death_year = 0)
    AND name != '' AND name IS NOT NULL
    ORDER BY name
""").fetchall()
print(f"共 {len(missing)} 人:\n")
for r in missing:
    print(f'  id={r[0]:4d} | {r[1]:10s} [{r[2]:10s}] b={r[3]} d={r[4]}')

# 分开统计：真正的生卒年不详 vs 需要AI补的
# 唐代及以前的大多是确实不详（如张僧繇、周昉等）
# 明清之后的很多是有资料可查的

# ===== 3. 潘天寿照片生成缩略图 =====
print("\n" + "=" * 60)
print("3. 潘天寿照片缩略图生成")
print("=" * 60)
try:
    from PIL import Image
    has_pil = True
except ImportError:
    has_pil = False
    print("PIL未安装，跳过缩略图生成")

if has_pil:
    r = conn.execute("SELECT id, name, photos FROM artists WHERE name='潘天寿'").fetchone()
    if r and r[2]:
        photos = json.loads(r[2])
        print(f"潘天寿 photos原始数据: {photos}")
        updated = False
        for i, p in enumerate(photos):
            if isinstance(p, dict):
                url = p.get('url', '')
                thumb_url = p.get('thumb_url', '')
            else:
                url = p
                thumb_url = ''
            
            if thumb_url and thumb_url != url:
                print(f'  [{i}] 已有缩略图: {thumb_url}')
                continue
            
            # Extract filename from URL
            fname = url.replace('/static/uploads/', '') if '/static/uploads/' in url else None
            if not fname:
                print(f'  [{i}] URL不是本地路径: {url}')
                continue
            
            filepath = os.path.join(UPLOAD_DIR, fname)
            if not os.path.exists(filepath):
                print(f'  [{i}] 文件不存在: {filepath}')
                continue
            
            try:
                img = Image.open(filepath)
                img.thumbnail((200, 200), Image.LANCZOS)
                # Generate thumb filename
                base, ext = os.path.splitext(fname)
                thumb_name = f"{base}_thumb.jpg"
                thumb_path = os.path.join(UPLOAD_DIR, thumb_name)
                img.save(thumb_path, "JPEG", quality=75)
                thumb_url = get_static_url(thumb_name)
                
                if isinstance(photos[i], dict):
                    photos[i]['thumb_url'] = thumb_url
                else:
                    photos[i] = {'url': url, 'thumb_url': thumb_url}
                print(f'  [{i}] 缩略图已生成: {thumb_url}')
                updated = True
            except Exception as e:
                print(f'  [{i}] 生成失败: {e}')
        
        if updated:
            conn.execute("UPDATE artists SET photos=? WHERE id=?", (json.dumps(photos, ensure_ascii=False), r[0]))
            conn.commit()
            print("  已保存更新后的photos字段")
    else:
        print("  潘天寿无照片数据")

# ===== 4. 百度CDN头像下载到本地 =====
print("\n" + "=" * 60)
print("4. 百度CDN头像下载到本地")
print("=" * 60)
cdn_rows = conn.execute(
    "SELECT id, name, avatar_url FROM artists WHERE avatar_url LIKE '%bcebos.com%' OR avatar_url LIKE '%baidu.com%'"
).fetchall()
print(f"共 {len(cdn_rows)} 个百度CDN头像\n")

ssl_ctx = ssl.create_default_context()
ssl_ctx.check_hostname = False
ssl_ctx.verify_mode = ssl.CERT_NONE

fixed_count = 0
for r in cdn_rows:
    aid, name, url = r
    if not url:
        continue
    try:
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://baike.baidu.com/'
        })
        resp = urllib.request.urlopen(req, context=ssl_ctx, timeout=10)
        data = resp.read()
        if len(data) < 500:
            print(f'  SKIP {name}: 图片过小({len(data)}B)')
            continue
        # Determine extension
        ext = '.jpg'
        content_type = resp.headers.get('Content-Type', '')
        if 'png' in content_type:
            ext = '.png'
        elif 'webp' in content_type:
            ext = '.webp'
        elif 'gif' in content_type:
            ext = '.gif'
        
        fname = f"avatar_cdn_{aid}{ext}"
        fpath = os.path.join(UPLOAD_DIR, fname)
        with open(fpath, 'wb') as f:
            f.write(data)
        new_url = get_static_url(fname)
        conn.execute("UPDATE artists SET avatar_url=? WHERE id=?", (new_url, aid))
        fixed_count += 1
        if fixed_count <= 10 or fixed_count % 50 == 0:
            print(f'  OK {name}: {new_url}')
    except Exception as e:
        print(f'  FAIL {name}: {e}')

conn.commit()
print(f"\n下载成功: {fixed_count}/{len(cdn_rows)}")

# ===== Summary =====
print("\n" + "=" * 60)
print("修复概要")
print("=" * 60)
print(f"  非画家待处理: {len(suspicious)}人")
print(f"  生卒年缺失: {len(missing)}人")
print(f"  CDN头像已下载: {fixed_count}人")

conn.close()
