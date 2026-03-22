"""测试OCR识别"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from app.services.ocr_service import get_ocr_service

def test_ocr():
    """测试OCR识别"""
    print("="*60)
    print("测试OCR识别")
    print("="*60)
    
    ocr = get_ocr_service()
    
    # 测试图片
    test_images = [
        ("data/大.png", "大"),
        ("data/三.png", "三"),
        ("data/乘.png", "乘"),
    ]
    
    for img_path, expected in test_images:
        print(f"\n测试: {expected} ({img_path})")
        
        if not os.path.exists(img_path):
            print(f"  ✗ 文件不存在")
            continue
        
        # 读取图像
        with open(img_path, 'rb') as f:
            img_bytes = f.read()
        
        # OCR识别
        result = ocr.recognize_single_char(img_bytes)
        
        if result['success']:
            print(f"  OCR结果: '{result['character']}' (置信度: {result['confidence']:.2f})")
            if result['character'] == expected:
                print("  ✓ 正确")
            else:
                print(f"  ✗ 错误 (应该是 '{expected}')")
        else:
            print(f"  ✗ 识别失败: {result['message']}")

if __name__ == "__main__":
    test_ocr()
