"""测试所有字形的识别"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

import cv2
import numpy as np
from PIL import Image
import io
from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.models.character import Character
from app.services.simple_matcher import SimpleMatcher
from app.services.feature_extractor import SimpleFeatureExtractor
from app.services.image_processor import ImageProcessor

def load_image(image_path):
    """使用PIL加载图像"""
    try:
        pil_img = Image.open(image_path)
        if pil_img.mode != 'RGB':
            pil_img = pil_img.convert('RGB')
        return pil_img
    except Exception as e:
        print(f"  加载失败: {e}")
        return None

def test_recognition():
    """测试所有字形的识别"""
    print("="*60)
    print("测试所有字形的识别")
    print("="*60)
    
    db = SessionLocal()
    try:
        # 检查数据库
        chars = db.query(Character).all()
        print(f"\n数据库中的字符: {[c.character for c in chars]}")
        
        # 初始化服务
        image_processor = ImageProcessor(target_size=(128, 128))
        feature_extractor = SimpleFeatureExtractor(feature_dim=512)
        matcher = SimpleMatcher()
        matcher.build_index(db)
        
        # 测试所有图片
        data_dir = "data"
        test_images = [
            ("data/大.png", "大"),
            ("data/三.png", "三"),
            ("data/乘.png", "乘"),
            ("data/藏.png", "藏"),
            ("data/圣.png", "圣"),
            ("data/教.png", "教"),
        ]
        
        correct = 0
        total = 0
        
        for img_path, expected_char in test_images:
            print(f"\n{'='*60}")
            print(f"测试: {expected_char}")
            print(f"{'='*60}")
            
            if not os.path.exists(img_path):
                print(f"  ✗ 文件不存在: {img_path}")
                continue
            
            # 加载图像
            pil_img = load_image(img_path)
            if pil_img is None:
                continue
            
            # 转换为字节
            img_byte_arr = io.BytesIO()
            pil_img.save(img_byte_arr, format='PNG')
            contents = img_byte_arr.getvalue()
            
            # 处理
            processed_image = image_processor.process(contents)
            print(f"  预处理后: 平均值={processed_image.mean():.2f}")
            
            # 提取特征
            feature_vector = feature_extractor.extract(processed_image)
            print(f"  特征范数: {np.linalg.norm(feature_vector):.4f}")
            
            # 匹配
            match_result = matcher.match(feature_vector, db, top_k=6, threshold=0.0)
            
            total += 1
            
            if match_result.get('top_matches'):
                print(f"\n  匹配结果:")
                for i, m in enumerate(match_result['top_matches']):
                    mark = " ✓" if m['character'] == expected_char else ""
                    print(f"    {i+1}. {m['character']}: {m['similarity']:.2f}%{mark}")
                
                best = match_result['top_matches'][0]
                print(f"\n  识别结果: '{best['character']}'")
                
                if best['character'] == expected_char:
                    print("  ✓ 正确")
                    correct += 1
                else:
                    print(f"  ✗ 错误 (应该是 '{expected_char}')")
            else:
                print("  ✗ 无匹配结果")
        
        # 统计
        print(f"\n{'='*60}")
        print("测试统计")
        print(f"{'='*60}")
        print(f"  总测试数: {total}")
        print(f"  正确识别: {correct}")
        print(f"  准确率: {correct/total*100:.1f}%")
        
    finally:
        db.close()

if __name__ == "__main__":
    test_recognition()
