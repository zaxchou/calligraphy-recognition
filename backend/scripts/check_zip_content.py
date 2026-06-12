"""检查 MinerU zip 的 full.md 内容"""
import zipfile
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

zip_path = 'data/uploads/mineru_result.zip'
with zipfile.ZipFile(zip_path, 'r') as z:
    with z.open('full.md') as f:
        content = f.read().decode('utf-8')
        # Show first 500 chars
        print('=== First 500 chars of full.md ===')
        print(content[:500])
        print('\n...')
        # Show last 500 chars
        print('\n=== Last 500 chars of full.md ===')
        print(content[-500:])
