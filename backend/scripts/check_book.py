import sqlite3

conn = sqlite3.connect('data/knowledge.db')
cursor = conn.cursor()

cursor.execute("SELECT id, file_name, title FROM pdf_books WHERE file_name LIKE '%899591682ff741588ba7017d69188ef1%'")
books = cursor.fetchall()
for book in books:
    book_id = book[0]
    file_name = book[1]
    title = book[2]
    
    print(f"ID: {book_id}")
    print(f"File Name: {file_name}")
    print(f"Title bytes: {title.encode('utf-8') if title else None}")
    
    # Decode to verify
    if title:
        decoded = title.encode('latin-1').decode('utf-8', errors='replace')
        print(f"Title decoded: {decoded}")

conn.close()
