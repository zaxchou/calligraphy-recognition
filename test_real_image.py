"""测试真实书法图像的识别问题"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

import cv2
import numpy as np
from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.models.character import Character
from app.services.simple_matcher import SimpleMatcher
from app.services.feature_extractor import SimpleFeatureExtractor
from app.services.image_processor import ImageProcessor

def analyze_image(image_path):
    """分析图像特征"""
    print(f"\n分析图像: {image_path}")
    
    # 读取图像
    img = cv2.imread(image_path)
    if img is None:
        print("  ✗ 无法读取图像")
        return None
    
    print(f"  原始尺寸: {img.shape}")
    print(f"  像素范围: {img.min()} - {img.max()}")
    print(f"  平均值: {img.mean():.2f}")
    
    # 转换为灰度
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    print(f"  灰度平均值: {gray.mean():.2f}")
    
    # 判断背景颜色
    if gray.mean() < 127:
        print("  背景: 深色 (黑色背景)")
        # 需要反转
        inverted = 255 - gray
        print(f"  反转后平均值: {inverted.mean():.2f}")
    else:
        print("  背景: 浅色 (白色背景)")
    
    return img

def test_with_real_image():
    """测试真实图像识别"""
    print("="*60)
    print("测试真实书法图像识别")
    print("="*60)
    
    db = SessionLocal()
    try:
        # 检查数据库中的字符
        chars = db.query(Character).all()
        print(f"\n数据库中的字符: {[c.character for c in chars]}")
        
        # 初始化匹配器
        matcher = SimpleMatcher()
        matcher.build_index(db)
        
        # 创建测试图像 - 模拟真实书法图像
        # 真实图像是：深色背景，浅色笔画
        h, w = 128, 128
        
        # 创建黑色背景
        test_img = np.zeros((h, w), dtype=np.uint8)
        
        # 绘制白色的"大"字（模拟真实书法）
        # 横
        cv2.line(test_img, (30, 50), (100, 50), 200, 8)
        # 撇
        cv2.line(test_img, (65, 30), (35, 100), 200, 8)
        # 捺
        cv2.line(test_img, (65, 30), (95, 100), 200, 8)
        
        # 添加一些噪声模拟真实图像
        noise = np.random.normal(0, 10, (h, w)).astype(np.int16)
        test_img = np.clip(test_img.astype(np.int16) + noise, 0, 255).astype(np.uint8)
        
        # 保存测试图像
        cv2.imwrite('test_real_大.png', test_img)
        print("\n创建了测试图像: test_real_大.png")
        
        # 测试识别
        image_processor = ImageProcessor(target_size=(128, 128))
        feature_extractor = SimpleFeatureExtractor(feature_dim=512)
        
        # 编码图像
        _, img_encoded = cv2.imencode('.png', test_img)
        img_bytes = img_encoded.tobytes()
        
        # 处理图像
        processed_img = image_processor.process(img_bytes)
        print(f"\n处理后图像范围: {processed_img.min()} - {processed_img.max()}")
        print(f"处理后图像平均值: {processed_img.mean():.2f}")
        
        # 提取特征
        feature = feature_extractor.extract(processed_img)
        print(f"特征范数: {np.linalg.norm(feature):.4f}")
        
        # 匹配
        result = matcher.match(feature, db, top_k=5, threshold=50.0)
        
        print(f"\n{'='*40}")
        print(f"识别结果")
        print(f"{'='*40}")
        
        if result.get('success'):
            print(f"✓ 识别结果: {result.get('recognized_character')}")
            print(f"  相似度: {result.get('similarity')}%")
            top5_str = ', '.join([f"{m['character']}({m['similarity']:.1f}%)" for m in result.get('top_matches', [])])
            print(f"  Top 5: {top5_str}")
        else:
            print(f"✗ 匹配失败: {result.get('message')}")
            if result.get('top_matches'):
                top5_str = ', '.join([f"{m['character']}({m['similarity']:.1f}%)" for m in result.get('top_matches', [])])
                print(f"  Top 5: {top5_str}")
        
        # 对比数据库中"大"字的特征
        print(f"\n{'='*40}")
        print(f"数据库中'大'字的特征对比")
        print(f"{'='*40}")
        
        da_char = db.query(Character).filter(Character.character == '大').first()
        if da_char and da_char.feature_vector:
            db_feature = np.array(da_char.feature_vector)
            print(f"数据库'大'特征范数: {np.linalg.norm(db_feature):.4f}")
            
            # 计算余弦相似度
            dot_product = np.dot(feature, db_feature)
            norm_product = np.linalg.norm(feature) * np.linalg.norm(db_feature)
            if norm_product > 0:
                cosine_sim = dot_product / norm_product
                print(f"与数据库'大'的余弦相似度: {cosine_sim * 100:.2f}%")
        
    finally:
        db.close()

if __name__ == "__main__":
    test_with_real_image()
