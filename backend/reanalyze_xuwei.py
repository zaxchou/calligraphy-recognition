"""
批量重新分析 analysis_note 中包含"徐渭"的记录
使用 analyze_text_summary_only 重新生成，传入正确的 artist 参数
"""
import sqlite3
import sys
import os
import time

# 添加 backend 到 path
sys.path.insert(0, os.path.dirname(__file__))

from app.services.siliconflow_service import analyze_text_summary_only

def main():
    conn = sqlite3.connect('data/calligraphy.db')
    conn.row_factory = sqlite3.Row

    # 查找所有 analysis_note 包含"徐渭"的记录
    rows = conn.execute('''
        SELECT id, image_id, title, artist, year, filepath,
               substr(analysis_note, 1, 200) as note_preview
        FROM tubi_analyses
        WHERE analysis_note LIKE '%徐渭%'
        ORDER BY id DESC
    ''').fetchall()

    print('找到 %d 条需要重新分析的记录' % len(rows))
    print()

    success_count = 0
    fail_count = 0

    for i, row in enumerate(rows):
        rec_id = row['id']
        title = row['title'] or '未命名'
        artist = row['artist'] or '李鱓'
        filepath = row['filepath']

        print('[%d/%d] id=%d title=[%s] artist=[%s]' % (i+1, len(rows), rec_id, title, artist))

        if not filepath or not os.path.exists(filepath):
            print('  SKIP: 文件不存在 %s' % filepath)
            fail_count += 1
            continue

        try:
            result = analyze_text_summary_only(filepath, artist=artist)
            if result and result.get('success'):
                new_note = result.get('analysis_note', '')
                if new_note:
                    # 检查新分析是否还包含徐渭
                    has_xw = '徐渭' in new_note
                    status = 'WARNING 仍含徐渭' if has_xw else 'OK'

                    # 更新数据库
                    conn.execute(
                        'UPDATE tubi_analyses SET analysis_note = ?, updated_at = datetime("now") WHERE id = ?',
                        (new_note, rec_id)
                    )
                    conn.commit()
                    print('  %s: %s...' % (status, new_note[:80]))
                    success_count += 1
                else:
                    print('  SKIP: 返回空 analysis_note')
                    fail_count += 1
            else:
                error = result.get('error', '未知错误') if result else '无返回'
                print('  FAIL: %s' % error)
                fail_count += 1
        except Exception as e:
            print('  ERROR: %s' % str(e))
            fail_count += 1

        # 避免 API 限流
        if i < len(rows) - 1:
            time.sleep(1)

    print()
    print('=== 完成 ===')
    print('成功: %d, 失败: %d, 总计: %d' % (success_count, fail_count, len(rows)))
    conn.close()

if __name__ == '__main__':
    main()
