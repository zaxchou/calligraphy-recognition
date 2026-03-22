"""测试像素级匹配器"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

import cv2
import numpy as np
from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.models.character import Character
from app.services.pixel_matcher import PixelMatcher
from app.services.image_processor import ImageProcessor

# 从 init_data.py 导入图像生成函数
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend', 'scripts'))
from init_data import generate_character_image

def test_pixel_match():
    print("测试像素级匹配器...")
    
    db = SessionLocal()
    try:
        # 检查数据库中的字符
        chars = db.query(Character).all()
        print(f"\n数据库中的字符: {[c.character for c in chars]}")
        
        # 初始化像素级匹配器
        pixel_matcher = PixelMatcher(target_size=(128, 128))
        pixel_matcher.build_index(db)
        
        # 测试匹配不同的字
        test_chars = ["大", "唐", "三", "文", "圣", "乘"]
        image_processor = ImageProcessor(target_size=(128, 128))
        
        for idx, test_char in enumerate(test_chars):
            print(f"\n{'='*40}")
            print(f"测试字符: {test_char}")
            print(f"{'='*40}")
            
            # 使用与数据库初始化相同的图像生成方式
            test_img = generate_character_image(test_char, seed=idx * 100)
            
            # 模拟图像处理流程
            _, img_encoded = cv2.imencode('.png', test_img)
            img_bytes = img_encoded.tobytes()
            processed_img = image_processor.process(img_bytes)
            
            # 保存处理后的图像以便查看
            cv2.imwrite(f"test_processed_{test_char}.png", 
                       cv2.cvtColor(processed_img, cv2.COLOR_RGB2BGR))
            
            # 像素级匹配
            result = pixel_matcher.match(processed_img, db, top_k=5)
            
            if result.get('success'):
                print(f"✓ 识别结果: {result.get('recognized_character')}")
                print(f"  相似度: {result.get('similarity')}%")
                top5_str = ', '.join([f"{m['character']}({m['similarity']:.1f}%)" for m in result.get('top_matches', [])])
                print(f"  Top 5: {top5_str}")
                
                # 检查是否正确
                if result.get('recognized_character') == test_char:
                    print(f"  ✓✓✓ 正确!")
                else:
                    print(f"  ✗✗✗ 错误! 应该是 {test_char}")
            else:
                print(f"✗ 匹配失败: {result.get('message')}")
        
    finally:
        db.close()

if __name__ == "__main__":
    test_pixel_match()
