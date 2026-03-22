"""测试匹配器"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

import cv2
import numpy as np
from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.models.character import Character
from app.services.feature_extractor import SimpleFeatureExtractor
from app.services.matcher import CalligraphyMatcher

# 从 init_data.py 导入图像生成函数
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend', 'scripts'))
from init_data import generate_character_image

def test_match():
    print("测试匹配器...")
    
    db = SessionLocal()
    try:
        # 检查数据库中的字符
        chars = db.query(Character).all()
        print(f"\n数据库中的字符: {[c.character for c in chars]}")
        
        # 检查特征向量
        for c in chars:
            if c.feature_vector:
                vec = np.array(c.feature_vector)
                print(f"  {c.character}: 特征维度={len(vec)}, 范数={np.linalg.norm(vec):.4f}")
        
        # 初始化匹配器
        matcher = CalligraphyMatcher(feature_dim=512, use_faiss=False)
        matcher.build_index(db)
        
        # 测试匹配不同的字 - 使用与数据库相同的图像生成方式
        test_chars = ["大", "唐", "文", "圣"]
        extractor = SimpleFeatureExtractor(feature_dim=512)
        
        for idx, test_char in enumerate(test_chars):
            print(f"\n测试字符: {test_char}")
            
            # 使用与数据库初始化相同的图像生成方式
            test_img = generate_character_image(test_char, seed=idx * 100)
            img_rgb = cv2.cvtColor(test_img, cv2.COLOR_GRAY2RGB)
            
            # 保存测试图像以便查看
            cv2.imwrite(f"test_{test_char}.png", test_img)
            
            # 提取特征
            feature = extractor.extract(img_rgb)
            print(f"  特征范数: {np.linalg.norm(feature):.4f}")
            
            # 匹配
            result = matcher.match(feature, db, top_k=5, threshold=70.0)
            
            if result.get('success'):
                print(f"  识别结果: {result.get('recognized_character')}")
                print(f"  相似度: {result.get('similarity')}")
                print(f"  Top 5: {[m['character'] for m in result.get('top_matches', [])]}")
            else:
                print(f"  匹配失败: {result.get('message')}")
        
    finally:
        db.close()

if __name__ == "__main__":
    test_match()
