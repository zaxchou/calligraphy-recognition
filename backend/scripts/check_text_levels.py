"""检查 MinerU content_list 中的 text_level 值"""
import zipfile
import json
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

zip_path = 'data/uploads/mineru_result.zip'
with zipfile.ZipFile(zip_path, 'r') as z:
    for name in z.namelist():
        if 'content_list' in name and name != 'content_list_v2.json':
            with z.open(name) as f:
                cl = json.load(f)
                
                # Check text_level values
                levels = {}
                for item in cl:
                    level = item.get('text_level', 0)
                    levels[level] = levels.get(level, 0) + 1
                print(f'text_level distribution: {levels}')
                
                # Show items with text_level <= 2 (likely headings)
                print('\nItems with text_level <= 2:')
                for item in cl:
                    level = item.get('text_level', 0)
                    if level and level <= 2:
                        page_idx = item.get('page_idx', 0)
                        text = item.get('text', '')[:60]
                        print(f'  level={level}, page_idx={page_idx}, page_1based={page_idx+1}, text={text}')
