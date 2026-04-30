"""检查 MinerU 输出 zip 中的 content_list_v2.json 结构"""
import zipfile
import json
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

zip_path = 'data/uploads/mineru_result.zip'
with zipfile.ZipFile(zip_path, 'r') as z:
    with z.open('content_list_v2.json') as f:
        content_list = json.load(f)
        print(f'Type: {type(content_list)}')
        if isinstance(content_list, list):
            print(f'Length: {len(content_list)}')
            if content_list:
                first = content_list[0]
                print(f'First item type: {type(first)}')
                if isinstance(first, list):
                    print(f'First item length: {len(first)}')
                    if first:
                        print(f'First sub-item: {json.dumps(first[0], ensure_ascii=False)[:300]}')
                elif isinstance(first, dict):
                    print(f'First item keys: {list(first.keys())}')
                    print(f'First item: {json.dumps(first, ensure_ascii=False)[:300]}')
        elif isinstance(content_list, dict):
            print(f'Keys: {list(content_list.keys())}')
