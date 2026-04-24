import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'knowledge.db')
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Check image URLs
cursor.execute("SELECT id, file_name, stored_url, page, figure_id FROM extracted_images LIMIT 5")
images = cursor.fetchall()
print("Sample images:")
for img in images:
    print(f"  {img}")

# Check chunks with images
cursor.execute("""
    SELECT tc.id, tc.content[:50], tc.associated_images 
    FROM text_chunks tc 
    WHERE tc.associated_images IS NOT NULL AND tc.associated_images != '[]'
    LIMIT 3
""")
chunks = cursor.fetchall()
print("\nSample chunks with images:")
for chunk in chunks:
    print(f"  Chunk: {chunk[0]}")
    print(f"  Content: {chunk[1]}...")
    print(f"  Images: {chunk[2]}")
    
    # Get image details
    import json
    try:
        img_ids = json.loads(chunk[2])
        for img_id in img_ids[:2]:
            cursor.execute("SELECT file_name, stored_url FROM extracted_images WHERE id = ?", (img_id,))
            img = cursor.fetchone()
            if img:
                print(f"    -> {img[0]} @ {img[1]}")
            else:
                print(f"    -> Image {img_id} not found!")
    except:
        print(f"    -> Error parsing: {chunk[2]}")

conn.close()
