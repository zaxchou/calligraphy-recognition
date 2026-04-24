"""
简单测试册页和标签 API 的脚本
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_albums_endpoint():
    """测试获取册页列表"""
    print("\n=== 测试 GET /api/v1/tubi/albums ===")
    response = client.get("/api/v1/tubi/albums")
    print(f"状态码: {response.status_code}")
    if response.status_code == 200:
        print(f"响应: {response.json()}")
    return response.status_code == 200


def test_tags_endpoint():
    """测试获取标签列表"""
    print("\n=== 测试 GET /api/v1/tubi/tags ===")
    response = client.get("/api/v1/tubi/tags")
    print(f"状态码: {response.status_code}")
    if response.status_code == 200:
        print(f"响应: {response.json()}")
    return response.status_code == 200


def test_stats_extended_endpoint():
    """测试获取扩展统计"""
    print("\n=== 测试 GET /api/v1/tubi/stats/extended ===")
    response = client.get("/api/v1/tubi/stats/extended")
    print(f"状态码: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"成功！统计数据:")
        print(f"  - 总记录数: {data.get('data', {}).get('total')}")
        print(f"  - 册页数量: {data.get('data', {}).get('albums', {}).get('count')}")
        print(f"  - 标签数量: {data.get('data', {}).get('tags', {}).get('count')}")
    return response.status_code == 200


if __name__ == "__main__":
    print("开始测试册页和标签 API...")
    
    all_passed = True
    
    try:
        if not test_albums_endpoint():
            all_passed = False
        
        if not test_tags_endpoint():
            all_passed = False
        
        if not test_stats_extended_endpoint():
            all_passed = False
    except Exception as e:
        print(f"\n测试出错: {e}")
        import traceback
        traceback.print_exc()
        all_passed = False
    
    print(f"\n=== 测试结果 ===")
    if all_passed:
        print("[OK] 所有 API 测试通过！")
    else:
        print("[FAIL] 部分测试失败")
        sys.exit(1)
