"""测试真实书法图像识别"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

import cv2
import numpy as np
from PIL import Image
from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.models.character import Character
from app.services.simple_matcher import SimpleMatcher
from app.services.feature_extractor import SimpleFeatureExtractor
from app.services.image_processor import ImageProcessor

def load_image(image_path):
    """使用PIL加载图像并转换为OpenCV格式"""
    try:
        pil_img = Image.open(image_path)
        # 转换为RGB
        if pil_img.mode != 'RGB':
            pil_img = pil_img.convert('RGB')
        # 转换为OpenCV格式 (BGR)
        cv_img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
        return cv_img
    except Exception as e:
        print(f"  加载失败: {e}")
        return None

def analyze_image(image_path, char_name):
    """分析图像特征"""
    print(f"\n{'='*60}")
    print(f"分析图像: {char_name}")
    print(f"{'='*60}")
    
    img = load_image(image_path)
    if img is None:
        return None
    
    print(f"  原始尺寸: {img.shape}")
    
    # 转换为灰度
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    print(f"  灰度范围: {gray.min()} - {gray.max()}")
    print(f"  灰度平均值: {gray.mean():.2f}")
    
    # 判断背景颜色
    if gray.mean() < 127:
        print("  背景: 深色 (黑色背景)")
    else:
        print("  背景: 浅色 (白色背景)")
    
    return img

def test_recognition(image_path, expected_char, db, matcher, image_processor, feature_extractor):
    """测试单张图片的识别"""
    print(f"\n{'='*60}")
    print(f"识别测试: 期望='{expected_char}'")
    print(f"{'='*60}")
    
    # 加载图像
    img = load_image(image_path)
    if img is None:
        return False
    
    # 编码图像
    _, img_encoded = cv2.imencode('.png', img)
    img_bytes = img_encoded.tobytes()
    
    # 处理图像
    processed_img = image_processor.process(img_bytes)
    print(f"  处理后尺寸: {processed_img.shape}")
    print(f"  处理后范围: {processed_img.min():.1f} - {processed_img.max():.1f}")
    print(f"  处理后平均值: {processed_img.mean():.2f}")
    
    # 提取特征
    feature = feature_extractor.extract(processed_img)
    print(f"  特征范数: {np.linalg.norm(feature):.4f}")
    
    # 匹配
    result = matcher.match(feature, db, top_k=5, threshold=0.0)
    
    if result.get('top_matches'):
        print(f"\n  Top 5 匹配结果:")
        for i, m in enumerate(result.get('top_matches', [])):
            mark = " ✓" if m['character'] == expected_char else ""
            print(f"    {i+1}. {m['character']}: {m['similarity']:.2f}%{mark}")
        
        best = result['top_matches'][0]
        print(f"\n  最佳匹配: '{best['character']}' (相似度: {best['similarity']:.2f}%)")
        
        if best['character'] == expected_char:
            print(f"  ✓✓✓ 识别正确!")
            return True
        else:
            print(f"  ✗✗✗ 识别错误! 应该是 '{expected_char}'")
            return False
    else:
        print(f"  ✗ 无匹配结果")
        return False

def main():
    print("="*60)
    print("测试真实书法图像识别")
    print("="*60)
    
    # 测试图片路径
    test_images = [
        ("data/大.png", "大"),
        ("data/三.png", "三"),
        ("data/乘.png", "乘"),
    ]
    
    db = SessionLocal()
    try:
        # 检查数据库中的字符
        chars = db.query(Character).all()
        print(f"\n数据库中的字符: {[c.character for c in chars]}")
        
        # 初始化服务
        matcher = SimpleMatcher()
        matcher.build_index(db)
        image_processor = ImageProcessor(target_size=(128, 128))
        feature_extractor = SimpleFeatureExtractor(feature_dim=512)
        
        # 分析每张图片
        for img_path, char in test_images:
            analyze_image(img_path, char)
        
        # 测试识别
        print(f"\n{'='*60}")
        print("开始识别测试")
        print(f"{'='*60}")
        
        correct = 0
        total = 0
        
        for img_path, char in test_images:
            total += 1
            if test_recognition(img_path, char, db, matcher, image_processor, feature_extractor):
                correct += 1
        
        # 统计结果
        print(f"\n{'='*60}")
        print("测试统计")
        print(f"{'='*60}")
        print(f"  总测试数: {total}")
        print(f"  正确识别: {correct}")
        print(f"  准确率: {correct/total*100:.1f}%")
        
    finally:
        db.close()

if __name__ == "__main__":
    main()
