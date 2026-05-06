import sqlite3, os

conn = sqlite3.connect('/opt/calligraphy-recognition/backend/data/calligraphy.db')
c = conn.cursor()

# Check specific image
c.execute("SELECT image_id, filepath, thumbnail_path, annotated_image_path FROM tubi_analyses WHERE image_id=?", ('fe3bdeaf-5507-4881-aa68-fb64ceeedb52',))
row = c.fetchone()
print("DB record:", row)

for path_type, path in [('filepath', row[1]), ('thumbnail', row[2]), ('annotated', row[3])]:
    if path:
        norm = path.replace('\\', '/')
        full = os.path.join('/opt/calligraphy-recognition/backend', norm)
        exists = os.path.exists(full)
        size = os.path.getsize(full) if exists else 0
        print(f"{path_type}: {full} exists={exists} size={size}")

# Count total analyzed
c.execute("SELECT COUNT(*) FROM tubi_analyses WHERE status='analyzed'")
total = c.fetchone()[0]
print(f"\nTotal analyzed: {total}")

# Check ALL thumbnails
c.execute("SELECT image_id, thumbnail_path FROM tubi_analyses WHERE status='analyzed' AND thumbnail_path IS NOT NULL")
missing = []
for r in c.fetchall():
    if r[1]:
        norm = r[1].replace('\\', '/')
        full = os.path.join('/opt/calligraphy-recognition/backend', norm)
        if not os.path.exists(full):
            missing.append((r[0], r[1]))
        elif os.path.getsize(full) < 100:
            missing.append((r[0], r[1], 'tiny'))

print(f"Missing thumbnails: {len([m for m in missing if len(m)==2])}")
print(f"Tiny thumbnails: {len([m for m in missing if len(m)==3])}")
for m in missing[:20]:
    print(f"  {m[0]}: {m[1]}")

# Also check original files
c.execute("SELECT image_id, filepath FROM tubi_analyses WHERE status='analyzed'")
missing_orig = []
for r in c.fetchall():
    if r[1]:
        norm = r[1].replace('\\', '/')
        full = os.path.join('/opt/calligraphy-recognition/backend', norm)
        if not os.path.exists(full):
            missing_orig.append((r[0], r[1]))
print(f"\nMissing originals: {len(missing_orig)}")
for m in missing_orig[:10]:
    print(f"  {m[0]}: {m[1]}")

conn.close()
