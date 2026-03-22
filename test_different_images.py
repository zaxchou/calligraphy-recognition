"""测试不同图像的识别 - 模拟真实场景"""
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
import io

def create_different_da():
    """创建一个不同的'大'字图像（不同位置、不同粗细）"""
    # 创建黑色背景
    img = np.zeros((336, 336), dtype=np.uint8)
    
    # 绘制"大"字 - 不同位置和粗细
    # 横（位置偏上，更细）
    cv2.line(img, (50, 80), (286, 80), 200, 5)
    # 撇（位置偏左，更细）
    cv2.line(img, (168, 40), (80, 280), 200, 5)
    # 捺（位置偏右，更细）
    cv2.line(img, (168, 40), (256, 280), 200, 5)
    
    # 添加噪声
    noise = np.random.normal(0, 15, (336, 336)).astype(np.int16)
    img = np.clip(img.astype(np.int16) + noise, 0, 255).astype(np.uint8)
    
    return img

def create_different_san():
    """创建一个不同的'三'字图像"""
    img = np.zeros((336, 336), dtype=np.uint8)
    
    # 绘制"三"字 - 不同间距
    y_positions = [70, 140, 210]  # 不同的垂直位置
    for y in y_positions:
        cv2.line(img, (60, y), (276, y), 200, 6)
    
    noise = np.random.normal(0, 15, (336, 336)).astype(np.int16)
    img = np.clip(img.astype(np.int16) + noise, 0, 255).astype(np.uint8)
    
    return img

def create_different_cheng():
    """创建一个不同的'乘'字图像"""
    img = np.zeros((390, 390), dtype=np.uint8)
    
    # 简化的"乘"字 - 不同风格
    # 禾字旁
    cv2.line(img, (80, 60), (80, 280), 200, 5)  # 竖
    cv2.line(img, (40, 100), (120, 100), 200, 5)  # 横
    cv2.line(img, (50, 180), (110, 180), 200, 5)  # 横
    cv2.line(img, (60, 60), (100, 120), 200, 5)  # 撇
    cv2.line(img, (100, 60), (60, 120), 200, 5)  # 捺
    
    # 北字旁（简化）
    cv2.line(img, (200, 60), (200, 280), 200, 5)  # 竖
    cv2.line(img, (160, 100), (240, 100), 200, 5)  # 横
    cv2.line(img, (180, 280), (220, 280), 200, 5)  # 底横
    
    noise = np.random.normal(0, 15, (390, 390)).astype(np.int16)
    img = np.clip(img.astype(np.int16) + noise, 0, 255).astype(np.uint8)
    
    return img

def test_with_different_images():
    """使用不同图像测试"""
    print("="*60)
    print("测试不同图像的识别（模拟真实场景）")
    print("="*60)
    
    db = SessionLocal()
    try:
        chars = db.query(Character).all()
        print(f"\n数据库中的字符: {[c.character for c in chars]}")
        
        image_processor = ImageProcessor(target_size=(128, 128))
        feature_extractor = SimpleFeatureExtractor(feature_dim=512)
        matcher = SimpleMatcher()
        matcher.build_index(db)
        
        # 创建不同的测试图像
        test_cases = [
            ("大", create_different_da()),
            ("三", create_different_san()),
            ("乘", create_different_cheng()),
        ]
        
        for expected_char, test_img in test_cases:
            print(f"\n{'='*60}")
            print(f"测试: {expected_char} (不同风格的图像)")
            print(f"{'='*60}")
            
            # 保存测试图像
            test_path = f"test_diff_{expected_char}.png"
            cv2.imwrite(test_path, test_img)
            
            # 转换为PIL再转字节（模拟上传）
            pil_img = Image.fromarray(test_img)
            img_byte_arr = io.BytesIO()
            pil_img.save(img_byte_arr, format='PNG')
            contents = img_byte_arr.getvalue()
            
            print(f"测试图像: {test_path}")
            
            # 处理
            processed_image = image_processor.process(contents)
            print(f"预处理后: 平均值={processed_image.mean():.2f}")
            
            # 提取特征
            feature_vector = feature_extractor.extract(processed_image)
            print(f"特征范数: {np.linalg.norm(feature_vector):.4f}")
            
            # 匹配
            match_result = matcher.match(feature_vector, db, top_k=3, threshold=0.0)
            
            if match_result.get('top_matches'):
                print(f"\n匹配结果:")
                for i, m in enumerate(match_result['top_matches']):
                    mark = " ✓" if m['character'] == expected_char else ""
                    print(f"  {i+1}. {m['character']}: {m['similarity']:.2f}%{mark}")
                
                best = match_result['top_matches'][0]
                print(f"\n识别结果: '{best['character']}'")
                if best['character'] == expected_char:
                    print("  ✓ 正确")
                else:
                    print(f"  ✗ 错误 (应该是 '{expected_char}')")
            
    finally:
        db.close()

if __name__ == "__main__":
    test_with_different_images()
