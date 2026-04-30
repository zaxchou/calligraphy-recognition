"""分割 PDF 文件"""
import sys
import os
from pypdf import PdfReader, PdfWriter

def split_pdf(input_path, num_parts=4):
    """将 PDF 分割成指定数量的部分"""
    reader = PdfReader(input_path)
    total_pages = len(reader.pages)
    pages_per_part = total_pages // num_parts
    remainder = total_pages % num_parts
    
    base_name = os.path.splitext(input_path)[0]
    output_dir = os.path.dirname(input_path)
    
    start = 0
    for i in range(num_parts):
        # 计算当前部分的页数
        end = start + pages_per_part + (1 if i < remainder else 0)
        
        # 创建新的 PDF
        writer = PdfWriter()
        for page_num in range(start, end):
            writer.add_page(reader.pages[page_num])
        
        # 保存文件
        output_path = f"{base_name}_part{i+1}.pdf"
        with open(output_path, 'wb') as f:
            writer.write(f)
        
        print(f"Part {i+1}: pages {start+1}-{end} -> {os.path.basename(output_path)}")
        start = end
    
    print(f"\nDone! Split {total_pages} pages into {num_parts} parts.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python split_pdf.py <input.pdf> [num_parts]")
        sys.exit(1)
    
    input_path = sys.argv[1]
    num_parts = int(sys.argv[2]) if len(sys.argv) > 2 else 4
    
    split_pdf(input_path, num_parts)
