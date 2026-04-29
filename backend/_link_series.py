"""
跨文件定位辅助工具

用于将多卷PDF关联为同一系列，实现跨文件大纲跳转。

用法：
  python _link_series.py --book-id <part1_book_id> --series-id my_series
  python _link_series.py --book-id <part2_book_id> --series-id my_series --page-offset 201
  python _link_series.py --book-id <part3_book_id> --series-id my_series --page-offset 401
  python _link_series.py --book-id <part4_book_id> --series-id my_series --page-offset 601

说明：
  - series-id: 同一系列共享同一个ID（任意字符串，建议用UUID）
  - page-offset: 本卷PDF在完整书中的起始页码（part1默认1，part2从201开始）
  - 只有 part1 需要完整大纲，其他卷可以没有大纲
"""
import argparse, sqlite3, uuid

DB_PATH = 'Z:/BaiduSync/BaiduSyncdisk/calligraphy-recognition/backend/data/knowledge.db'

def main():
    parser = argparse.ArgumentParser(description='将多卷PDF关联为同一系列')
    parser.add_argument('--book-id', required=True, help='书籍ID')
    parser.add_argument('--series-id', default=str(uuid.uuid4()), help='系列ID（同一系列用同一个ID）')
    parser.add_argument('--page-offset', type=int, default=1, help='本卷在系列内的起始页码（part1=1, part2=201, ...）')
    args = parser.parse_args()

    db = sqlite3.connect(DB_PATH)
    cur = db.execute('SELECT id, title, file_name, total_pages FROM pdf_books WHERE id = ?', (args.book_id,))
    book = cur.fetchone()
    if not book:
        print(f'错误: 书籍 {args.book_id} 不存在')
        return

    db.execute('UPDATE pdf_books SET series_id = ?, page_offset = ? WHERE id = ?',
               (args.series_id, args.page_offset, args.book_id))
    db.commit()
    
    print(f'✓ 已关联: {book[1] or book[2]}')
    print(f'  系列ID: {args.series_id}')
    print(f'  页面偏移: {args.page_offset}')
    
    # 显示系列内所有书籍
    cur = db.execute('SELECT id, title, file_name, total_pages, page_offset FROM pdf_books WHERE series_id = ? ORDER BY page_offset', (args.series_id,))
    books = cur.fetchall()
    if len(books) > 1:
        print(f'\n系列内共 {len(books)} 卷:')
        for b in books:
            print(f'  {b[4]}: {b[1] or b[2]} ({b[3]}页) [{b[0][:8]}...]')
    
    db.close()

if __name__ == '__main__':
    main()
