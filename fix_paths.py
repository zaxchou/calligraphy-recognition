"""
修复数据库中的路径分隔符问题
将 Windows 反斜杠转换为正斜杠
"""
import sqlite3
import sys
import os

# 数据库路径
db_path = os.path.join(os.path.dirname(__file__), 'backend', 'data', 'calligraphy.db')

def fix_paths():
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 修复 tubi_analyses 表
    cursor.execute("SELECT id, filepath, thumbnail_path FROM tubi_analyses")
    rows = cursor.fetchall()
    
    fixed_count = 0
    for row in rows:
        id, filepath, thumbnail_path = row
        new_filepath = filepath.replace('\\', '/') if filepath else filepath
        new_thumbnail = thumbnail_path.replace('\\', '/') if thumbnail_path else thumbnail_path
        
        if new_filepath != filepath or new_thumbnail != thumbnail_path:
            cursor.execute(
                "UPDATE tubi_analyses SET filepath = ?, thumbnail_path = ? WHERE id = ?",
                (new_filepath, new_thumbnail, id)
            )
            fixed_count += 1
    
    # 修复 recognition_logs 表
    cursor.execute("SELECT id, uploaded_image_path FROM recognition_logs")
    rows = cursor.fetchall()
    
    for row in rows:
        id, uploaded_path = row
        new_path = uploaded_path.replace('\\', '/') if uploaded_path else uploaded_path
        
        if new_path != uploaded_path:
            cursor.execute(
                "UPDATE recognition_logs SET uploaded_image_path = ? WHERE id = ?",
                (new_path, id)
            )
            fixed_count += 1
    
    conn.commit()
    conn.close()
    
    print(f"修复完成！共修复 {fixed_count} 条记录")

if __name__ == "__main__":
    fix_paths()
