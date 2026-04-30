#!/usr/bin/env python3
"""Validate PDF file"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import os

pdf_path = r"Z:\BaiduSync\BaiduSyncdisk\calligraphy-recognition\backend\data\uploads\028b83c2-56a1-4a85-b1c8-58ae17d84ce5_中国画传习文献汇编_part1.pdf"

print(f"PDF path: {pdf_path}")
print(f"File exists: {os.path.exists(pdf_path)}")
print(f"File size: {os.path.getsize(pdf_path)} bytes")

# Check PDF header
with open(pdf_path, 'rb') as f:
    header = f.read(10)
    print(f"PDF header: {header}")
    if header[:5] == b'%PDF-':
        print("Valid PDF header")
    else:
        print("Invalid PDF header!")

# Try to read with PyMuPDF if available
try:
    import fitz  # PyMuPDF
    doc = fitz.open(pdf_path)
    print(f"\nPyMuPDF info:")
    print(f"  Pages: {doc.page_count}")
    print(f"  Metadata: {doc.metadata}")
    
    # Try to render first page
    page = doc[0]
    pix = page.get_pixmap(matrix=fitz.Matrix(0.5, 0.5))
    print(f"  First page rendered: {pix.width}x{pix.height}")
    
    doc.close()
    print("\nPDF is valid and renderable!")
except ImportError:
    print("\nPyMuPDF not installed, skipping detailed validation")
except Exception as e:
    print(f"\nError reading PDF: {e}")
