"""直接测试API接口"""
import requests
import os

def test_api():
    """测试API接口"""
    print("="*60)
    print("直接测试API接口")
    print("="*60)
    
    api_url = "http://localhost:8000/api/v1/recognize"
    
    test_cases = [
        ("data/藏.png", "藏"),
        ("data/圣.png", "圣"),
    ]
    
    for img_path, expected_char in test_cases:
        print(f"\n{'='*60}")
        print(f"测试: {expected_char}")
        print(f"{'='*60}")
        
        if not os.path.exists(img_path):
            print(f"  ✗ 文件不存在")
            continue
        
        try:
            # 发送请求到API
            with open(img_path, 'rb') as f:
                files = {'file': (os.path.basename(img_path), f, 'image/png')}
                response = requests.post(api_url, files=files, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                if result.get('success'):
                    data = result.get('data', {})
                    recognized = data.get('recognized_character', '')
                    similarity = data.get('similarity', 0)
                    
                    print(f"  识别结果: '{recognized}' (相似度: {similarity}%)")
                    
                    if recognized == expected_char:
                        print("  ✓ 正确")
                    else:
                        print(f"  ✗ 错误 (应该是 '{expected_char}')")
                    
                    # 显示Top 5
                    top_matches = data.get('top_matches', [])
                    if top_matches:
                        print(f"\n  Top 5:")
                        for i, m in enumerate(top_matches[:5]):
                            mark = " ✓" if m['character'] == expected_char else ""
                            print(f"    {i+1}. {m['character']}: {m['similarity']:.2f}%{mark}")
                else:
                    print(f"  ✗ API返回错误: {result.get('message', '未知错误')}")
            else:
                print(f"  ✗ HTTP错误: {response.status_code}")
                print(f"     {response.text}")
                
        except Exception as e:
            print(f"  ✗ 请求失败: {e}")

if __name__ == "__main__":
    test_api()
