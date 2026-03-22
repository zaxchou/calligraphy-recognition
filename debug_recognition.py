"""调试识别问题"""
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
    """使用PIL加载图像"""
    try:
        pil_img = Image.open(image_path)
        if pil_img.mode != 'RGB':
            pil_img = pil_img.convert('RGB')
        cv_img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
        return cv_img
    except Exception as e:
        print(f"  加载失败: {e}")
        return None

def debug_recognition():
    """调试识别过程"""
    print("="*60)
    print("调试识别问题")
    print("="*60)
    
    db = SessionLocal()
    try:
        # 检查数据库中的字符和特征
        chars = db.query(Character).all()
        print(f"\n数据库中的字符:")
        for c in chars:
            vec = np.array(c.feature_vector)
            print(f"  {c.character}: 特征范数={np.linalg.norm(vec):.4f}, 前5维={vec[:5]}")
        
        # 初始化服务
        matcher = SimpleMatcher()
        matcher.build_index(db)
        image_processor = ImageProcessor(target_size=(128, 128))
        feature_extractor = SimpleFeatureExtractor(feature_dim=512)
        
        # 测试图片
        test_images = [
            ("data/大.png", "大"),
            ("data/三.png", "三"),
            ("data/乘.png", "乘"),
        ]
        
        for img_path, expected_char in test_images:
            print(f"\n{'='*60}")
            print(f"测试: {expected_char}")
            print(f"{'='*60}")
            
            # 加载图像
            img = load_image(img_path)
            if img is None:
                continue
            
            # 编码并处理
            _, img_encoded = cv2.imencode('.png', img)
            img_bytes = img_encoded.tobytes()
            processed_img = image_processor.process(img_bytes)
            
            print(f"处理后图像: 形状={processed_img.shape}, 平均值={processed_img.mean():.2f}")
            
            # 提取特征
            feature = feature_extractor.extract(processed_img)
            print(f"查询特征: 范数={np.linalg.norm(feature):.4f}, 前5维={feature[:5]}")
            
            # 与数据库中每个字符对比
            print(f"\n与数据库对比:")
            for char_data in matcher.characters_data:
                db_feature = char_data['feature_vector']
                
                # 计算余弦相似度
                dot = np.dot(feature, db_feature)
                norm_q = np.linalg.norm(feature)
                norm_db = np.linalg.norm(db_feature)
                similarity = dot / (norm_q * norm_db) * 100
                
                print(f"  {char_data['character']}: {similarity:.2f}%")
            
            # 获取匹配结果
            result = matcher.match(feature, db, top_k=3, threshold=0.0)
            if result.get('top_matches'):
                best = result['top_matches'][0]
                print(f"\n识别结果: '{best['character']}' (相似度: {best['similarity']:.2f}%)")
                if best['character'] == expected_char:
                    print("  ✓ 正确")
                else:
                    print(f"  ✗ 错误 (应该是 '{expected_char}')")
        
    finally:
        db.close()

if __name__ == "__main__":
    debug_recognition()
