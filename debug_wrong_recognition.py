"""调试错误的识别结果"""
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

def debug_recognition():
    """调试识别问题"""
    print("="*60)
    print("调试错误的识别结果")
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
        
        # 测试问题图片
        test_cases = [
            ("data/藏.png", "藏"),
            ("data/圣.png", "圣"),
        ]
        
        for img_path, expected_char in test_cases:
            print(f"\n{'='*60}")
            print(f"测试: {expected_char} ({img_path})")
            print(f"{'='*60}")
            
            if not os.path.exists(img_path):
                print(f"  ✗ 文件不存在")
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
            print(f"  预处理后: 形状={processed_image.shape}, 平均值={processed_image.mean():.2f}")
            
            # 保存处理后的图像以便查看
            debug_path = f"debug_processed_{expected_char}.png"
            cv2.imwrite(debug_path, processed_image)
            print(f"  保存处理后的图像: {debug_path}")
            
            # 提取特征
            feature_vector = feature_extractor.extract(processed_image)
            print(f"  特征范数: {np.linalg.norm(feature_vector):.4f}")
            print(f"  特征前10维: {feature_vector[:10]}")
            
            # 与数据库中每个字符对比
            print(f"\n  与数据库对比:")
            for char_data in matcher.characters_data:
                db_feature = char_data['feature_vector']
                
                # 计算余弦相似度
                dot = np.dot(feature_vector, db_feature)
                norm_q = np.linalg.norm(feature_vector)
                norm_db = np.linalg.norm(db_feature)
                similarity = dot / (norm_q * norm_db) * 100
                
                mark = " ✓" if char_data['character'] == expected_char else ""
                print(f"    {char_data['character']}: {similarity:.2f}%{mark}")
            
            # 匹配
            match_result = matcher.match(feature_vector, db, top_k=6, threshold=0.0)
            
            if match_result.get('top_matches'):
                print(f"\n  Top 6 匹配结果:")
                for i, m in enumerate(match_result['top_matches']):
                    mark = " ✓" if m['character'] == expected_char else ""
                    print(f"    {i+1}. {m['character']}: {m['similarity']:.2f}%{mark}")
                
                best = match_result['top_matches'][0]
                print(f"\n  识别结果: '{best['character']}'")
                
                if best['character'] == expected_char:
                    print("  ✓ 正确")
                else:
                    print(f"  ✗ 错误 (应该是 '{expected_char}')")
        
    finally:
        db.close()

if __name__ == "__main__":
    debug_recognition()
