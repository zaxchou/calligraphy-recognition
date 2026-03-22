"""测试 DeepSeek API - 使用特征描述"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

import cv2
import numpy as np
from app.services.deepseek_service import DeepSeekService

# 创建测试图片
def create_test_image(char):
    """创建一个测试图片"""
    img = np.zeros((128, 128), dtype=np.uint8)
    cv2.putText(img, char, (35, 90), cv2.FONT_HERSHEY_SIMPLEX, 2, 255, 3)
    return img

# 测试 DeepSeek 服务
def test_deepseek():
    print("测试 DeepSeek 服务（特征描述方式）...")
    
    # 创建测试图片
    test_img = create_test_image("大")
    
    # 提取特征描述
    from app.services.feature_extractor import SimpleFeatureExtractor
    extractor = SimpleFeatureExtractor(feature_dim=512)
    
    img_rgb = cv2.cvtColor(test_img, cv2.COLOR_GRAY2RGB)
    description = extractor.extract_description(img_rgb)
    
    print(f"\n特征描述:\n{description}")
    
    # 创建服务
    try:
        service = DeepSeekService()
        print("\nDeepSeek 服务创建成功")
    except Exception as e:
        print(f"创建服务失败: {e}")
        return
    
    # 测试识别
    candidates = ["大", "唐", "三", "文"]
    print(f"\n测试识别，候选字: {candidates}")
    
    result = service.recognize_by_features(
        features_description=description,
        candidates=candidates
    )
    
    print(f"\n识别结果:")
    print(f"  成功: {result.get('success')}")
    print(f"  字符: {result.get('character')}")
    print(f"  置信度: {result.get('confidence')}")
    print(f"  理由: {result.get('reason')}")
    if result.get('error'):
        print(f"  错误: {result.get('error')}")

if __name__ == "__main__":
    test_deepseek()
