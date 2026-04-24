"""检查缩略图目录"""
import os

thumb_dir = r"z:\BaiduSync\BaiduSyncdisk\calligraphy-recognition\backend\data\thumbnails"
files = sorted(os.listdir(thumb_dir))
print(f"Total files: {len(files)}")
for f in files:
    size = os.path.getsize(os.path.join(thumb_dir, f)) // 1024
    print(f"  {f} ({size} KB)")