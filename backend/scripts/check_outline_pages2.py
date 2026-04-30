#!/usr/bin/env python3
"""Check outline pages"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import sqlite3
import json

conn = sqlite3.connect('data/knowledge.db')
cursor = conn.cursor()
cursor.execute("SELECT outline, total_pages FROM pdf_books WHERE id = 'b250300e-8ae4-486d-a73b-854708c048d3'")
row = cursor.fetchone()
if row and row[0]:
    outline = json.loads(row[0])
    total_pages = row[1]
    print(f"PDF total_pages: {total_pages}")
    print(f"Total outline items: {len(outline)}")
    
    # Check page ranges
    pages = [item.get('page', 0) for item in outline]
    print(f"Page range: {min(pages)} - {max(pages)}")
    
    # Show first 5 and last 5 items
    print("\nFirst 5 items:")
    for i, item in enumerate(outline[:5]):
        print(f"  {i}: page={item.get('page', 'N/A')} title={item.get('title', 'N/A')[:50]}")
    
    print("\nLast 5 items:")
    for i, item in enumerate(outline[-5:], len(outline)-5):
        print(f"  {i}: page={item.get('page', 'N/A')} title={item.get('title', 'N/A')[:50]}")
    
    # Check for any items with page > total_pages
    over_limit = [item for item in outline if item.get('page', 0) > total_pages]
    if over_limit:
        print(f"\nWARNING: {len(over_limit)} items have page > total_pages ({total_pages})")
        for item in over_limit[:3]:
            print(f"  page={item.get('page')} title={item.get('title', 'N/A')[:50]}")
    else:
        print(f"\nAll items have page <= total_pages ({total_pages})")
else:
    print("No outline found")
conn.close()
