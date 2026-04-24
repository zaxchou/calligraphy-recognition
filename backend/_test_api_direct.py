import httpx
import json

try:
    response = httpx.get("http://localhost:8001/api/v1/tubi/results", timeout=10)
    print(f"状态码: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"\n返回 {len(data.get('data', []))} 条记录")
        
        items = data.get('data', [])
        if len(items) > 0:
            print("\n=== 第一条记录的完整字段 ===")
            item = items[0]
            for key in sorted(item.keys()):
                print(f"  {key}: {item[key]}")
            
            print("\n=== 找有 album_name 的记录 ===")
            found = None
            for it in items:
                if it.get('album_name'):
                    found = it
                    break
            
            if found:
                print(f"找到: {found.get('title')}")
                print(f"  album_name: {found.get('album_name')}")
                print(f"  tags: {found.get('tags')}")
                print(f"  完整 item keys: {list(found.keys())}")
            else:
                print("未找到有 album_name 的记录")
                print("\n检查所有记录的 album_name 和 tags:")
                for i, it in enumerate(items[:5]):
                    print(f"记录 {i}: title={it.get('title')}, album_name={it.get('album_name')}, tags={it.get('tags')}")
    
except Exception as e:
    print(f"错误: {e}")
    import traceback
    traceback.print_exc()
