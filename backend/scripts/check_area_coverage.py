import sqlite3
c = sqlite3.connect("data/calligraphy.db")
row = c.execute("""
    SELECT COUNT(*) as total,
           SUM(CASE WHEN inscription_percent IS NOT NULL THEN 1 ELSE 0 END) as has_area,
           SUM(CASE WHEN content_analysis IS NOT NULL AND content_analysis != '' THEN 1 ELSE 0 END) as has_content,
           SUM(CASE WHEN content_analysis IS NOT NULL AND content_analysis != '' AND inscription_percent IS NOT NULL THEN 1 ELSE 0 END) as has_both
    FROM tubi_analyses WHERE artist = '李鱓'
""").fetchone()
print(f"total={row[0]} has_area={row[1]} has_content={row[2]} has_both={row[3]}")
c.close()
