"""检查 MinerU 输出 zip 中的 content_list.json"""
import zipfile
import json
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

zip_path = 'data/uploads/mineru_result.zip'
with zipfile.ZipFile(zip_path, 'r') as z:
    print('Files in zip:')
    for name in z.namelist():
        print(f'  {name}')
    
    # Check content_list.json
    if 'content_list.json' in z.namelist():
        with z.open('content_list.json') as f:
            content_list = json.load(f)
            print(f'\ncontent_list items: {len(content_list)}')
            # Check for title items
            title_items = [item for item in content_list if item.get('type') == 'title']
            print(f'Title items: {len(title_items)}')
            for item in title_items[:5]:
                page_idx = item.get('page_idx', 0)
                text = item.get('text', '')[:50]
                print(f'  page_idx={page_idx}, text={text}')
            
            # Check all types
            types = {}
            for item in content_list:
                t = item.get('type', 'unknown')
                types[t] = types.get(t, 0) + 1
            print(f'\nItem types: {types}')
    else:
        print('content_list.json not found in zip')
