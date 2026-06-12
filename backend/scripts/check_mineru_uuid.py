"""检查 MinerU 输出 zip 中的 UUID-named content_list"""
import zipfile
import json
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

zip_path = 'data/uploads/mineru_result.zip'
with zipfile.ZipFile(zip_path, 'r') as z:
    for name in z.namelist():
        if 'content_list' in name and name != 'content_list_v2.json':
            print(f'Checking: {name}')
            with z.open(name) as f:
                cl = json.load(f)
                print(f'  Type: {type(cl)}')
                if isinstance(cl, list):
                    print(f'  Length: {len(cl)}')
                    if cl:
                        first = cl[0]
                        print(f'  First item type: {type(first)}')
                        if isinstance(first, dict):
                            print(f'  First item keys: {list(first.keys())}')
                            print(f'  First item: {json.dumps(first, ensure_ascii=False)[:400]}')
                            
                            # Check for title items
                            title_items = [item for item in cl if item.get('type') == 'title']
                            print(f'\n  Title items: {len(title_items)}')
                            for item in title_items[:10]:
                                page_idx = item.get('page_idx', 0)
                                text = item.get('text', '')[:60]
                                print(f'    page_idx={page_idx}, page_1based={page_idx+1}, text={text}')
                            
                            # Check all types
                            types = {}
                            for item in cl:
                                t = item.get('type', 'unknown')
                                types[t] = types.get(t, 0) + 1
                            print(f'\n  Item types: {types}')
