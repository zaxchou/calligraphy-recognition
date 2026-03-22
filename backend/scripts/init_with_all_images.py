"""
使用所有真实书法图像初始化数据库
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session
from app.core.database import SessionLocal, engine, Base
from app.models.stele import Stele
from app.models.character import Character
from app.services.image_processor import ImageProcessor
from app.services.feature_extractor import SimpleFeatureExtractor
import cv2
import numpy as np
from PIL import Image

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

def init_database():
    """初始化数据库"""
    # 创建表
    Base.metadata.create_all(bind=engine)
    print("✓ 数据库表创建完成")
    
    db = SessionLocal()
    try:
        print("\n开始初始化数据库数据...")
        
        # 创建碑帖
        stele_name = "雁塔圣教序"
        existing = db.query(Stele).filter(Stele.name == stele_name).first()
        if existing:
            print(f"{stele_name}碑帖已存在，使用现有ID: {existing.id}")
            stele_id = existing.id
        else:
            stele = Stele(
                name=stele_name,
                dynasty="唐",
                calligrapher="褚遂良",
                style="楷书",
                description="《雁塔圣教序》是唐代书法家褚遂良的代表作，书于永徽四年（653年）。",
                meta_info={"year": "653", "location": "西安大雁塔"}
            )
            db.add(stele)
            db.commit()
            stele_id = stele.id
            print(f"✓ 创建碑帖: {stele_name} (ID: {stele_id})")
        
        # 删除旧的字形数据
        old_chars = db.query(Character).filter(Character.stele_id == stele_id).all()
        if old_chars:
            for char in old_chars:
                db.delete(char)
            db.commit()
            print(f"删除旧的 {len(old_chars)} 个字形数据")
        
        # 扫描data文件夹中的所有图片
        data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data")
        
        # 获取所有png文件
        image_files = [f for f in os.listdir(data_dir) if f.endswith('.png')]
        
        # 解析文件名（假设文件名就是汉字）
        real_images = []
        for img_file in image_files:
            # 去掉.png后缀获取字符名
            char_name = img_file.replace('.png', '')
            img_path = os.path.join(data_dir, img_file)
            
            # 获取Unicode
            try:
                unicode_val = f"U+{ord(char_name):04X}"
            except:
                unicode_val = f"U+{hash(char_name) % 0xFFFF:04X}"
            
            real_images.append((img_path, char_name, unicode_val))
        
        print(f"\n找到 {len(real_images)} 个真实图像:")
        for img_path, char, unicode_val in real_images:
            print(f"  - {char}: {os.path.basename(img_path)}")
        
        image_processor = ImageProcessor(target_size=(128, 128))
        feature_extractor = SimpleFeatureExtractor(feature_dim=512)
        
        # 创建字形目录
        backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        chars_dir = os.path.join(backend_dir, "data", "static", "characters", f"stele_{stele_id}")
        os.makedirs(chars_dir, exist_ok=True)
        print(f"\n字形目录: {chars_dir}")
        
        success_count = 0
        for img_path, char, unicode_val in real_images:
            try:
                if not os.path.exists(img_path):
                    print(f"  ✗ 图像不存在: {img_path}")
                    continue
                
                # 加载图像
                img = load_image(img_path)
                if img is None:
                    print(f"  ✗ 无法加载图像: {img_path}")
                    continue
                
                # 保存图像
                safe_unicode = unicode_val.replace('+', '_')
                image_filename = f"{safe_unicode}.png"
                image_path = os.path.join(chars_dir, image_filename)
                cv2.imwrite(image_path, img)
                
                # 使用图像处理器处理
                _, img_encoded = cv2.imencode('.png', img)
                img_bytes = img_encoded.tobytes()
                processed_img = image_processor.process(img_bytes)
                
                # 提取特征
                feature_vector = feature_extractor.extract(processed_img).tolist()
                
                # 创建字符记录
                character = Character(
                    stele_id=stele_id,
                    character=char,
                    unicode=unicode_val,
                    image_path=f"/static/characters/stele_{stele_id}/{image_filename}",
                    feature_vector=feature_vector,
                    stroke_count=len(char),
                    bounding_box={"x": 0, "y": 0, "w": 128, "h": 128},
                    meta_info={"source": "real_image"}
                )
                
                db.add(character)
                print(f"  ✓ 创建字形: {char}")
                success_count += 1
                
            except Exception as e:
                print(f"  ✗ 创建字形 {char} 失败: {e}")
        
        db.commit()
        print(f"\n字形数据创建完成: {success_count}/{len(real_images)} 个成功")
        
        # 统计
        char_count = db.query(Character).filter(Character.stele_id == stele_id).count()
        print(f"\n数据初始化完成！")
        print(f"碑帖: {stele_name}")
        print(f"字形数量: {char_count}")
        
    finally:
        db.close()

if __name__ == "__main__":
    init_database()
