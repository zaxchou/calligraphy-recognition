"""
测试 SiliconFlow AI 字体识别功能
"""
import sys
import os

# 添加 backend 到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from app.services.siliconflow_recognition_service import get_siliconflow_recognition_service


def test_recognition(image_path: str, candidates=None):
    """测试单张图片识别"""
    print(f"\n{'='*60}")
    print(f"测试图片: {image_path}")
    print(f"候选字符: {candidates}")
    print('='*60)
    
    # 读取图片
    with open(image_path, 'rb') as f:
        image_bytes = f.read()
    
    # 获取服务
    service = get_siliconflow_recognition_service()
    
    # 识别
    result = service.recognize_character(image_bytes, candidates=candidates)
    
    print(f"识别结果:")
    print(f"  成功: {result.get('success')}")
    print(f"  字符: {result.get('character')}")
    print(f"  置信度: {result.get('confidence')}")
    print(f"  理由: {result.get('reason')}")
    if result.get('error'):
        print(f"  错误: {result.get('error')}")
    
    return result


def main():
    data_dir = "data"
    
    # 测试用例
    test_cases = [
        ("大", None),
        ("三", None),
        ("乘", None),
        ("藏", None),
        ("圣", None),
        ("教", None),
    ]
    
    print("开始测试 SiliconFlow AI 字体识别...")
    print(f"使用模型: Pro/moonshotai/Kimi-K2.5")
    
    results = []
    for char, candidates in test_cases:
        image_path = os.path.join(data_dir, f"{char}.png")
        if os.path.exists(image_path):
            result = test_recognition(image_path, candidates)
            results.append({
                'expected': char,
                'recognized': result.get('character'),
                'success': result.get('success'),
                'confidence': result.get('confidence')
            })
        else:
            print(f"\n跳过 {char}: 图片不存在 {image_path}")
    
    # 统计结果
    print(f"\n{'='*60}")
    print("测试统计")
    print('='*60)
    
    correct = 0
    total = 0
    for r in results:
        total += 1
        is_correct = r['expected'] == r['recognized']
        if is_correct:
            correct += 1
        status = "✓" if is_correct else "✗"
        print(f"{status} {r['expected']} -> {r['recognized']} (置信度: {r['confidence']:.1f}%)")
    
    print(f"\n准确率: {correct}/{total} = {correct/total*100:.1f}%")


if __name__ == "__main__":
    main()
