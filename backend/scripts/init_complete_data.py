"""
使用更多真实书法图像初始化数据库
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

def generate_char_image(char, size=336):
    """生成字形图像（当没有真实图像时使用）"""
    img = np.zeros((size, size), dtype=np.uint8)
    
    # 根据字符类型绘制不同的笔画
    if char == "大":
        cv2.line(img, (size//4, size//2), (size*3//4, size//2), 200, 8)
        cv2.line(img, (size//2, size//4), (size//3, size*3//4), 200, 8)
        cv2.line(img, (size//2, size//4), (size*2//3, size*3//4), 200, 8)
    elif char == "三":
        for i, y in enumerate([size//4, size//2, size*3//4]):
            cv2.line(img, (size//4, y), (size*3//4, y), 200, 8)
    elif char == "乘":
        # 禾字旁
        cv2.line(img, (size//4, size//4), (size//4, size*3//4), 200, 6)
        cv2.line(img, (size//6, size//3), (size//3, size//3), 200, 6)
        cv2.line(img, (size//5, size//2), (size//3, size//2), 200, 6)
        # 北字旁
        cv2.line(img, (size//2, size//4), (size//2, size*3//4), 200, 6)
        cv2.line(img, (size*2//5, size//3), (size*3//5, size//3), 200, 6)
    elif char == "藏":
        # 草字头
        cv2.line(img, (size//3, size//4), (size*2//3, size//4), 200, 6)
        cv2.line(img, (size//3, size//3), (size*2//3, size//3), 200, 6)
        # 臣字旁
        cv2.line(img, (size//3, size//3), (size//3, size*3//4), 200, 6)
        cv2.line(img, (size//3, size//2), (size*2//5, size//2), 200, 6)
        cv2.line(img, (size//3, size*2//3), (size*2//5, size*2//3), 200, 6)
    elif char == "唐":
        # 广字头
        cv2.line(img, (size//2, size//4), (size//3, size*3//4), 200, 6)
        cv2.line(img, (size//2, size//4), (size*2//3, size//4), 200, 6)
        # 肀
        cv2.line(img, (size*2//5, size//2), (size*2//3, size//2), 200, 6)
        cv2.line(img, (size*3//5, size//3), (size*3//5, size*2//3), 200, 6)
    elif char == "圣":
        # 又字旁
        cv2.line(img, (size//3, size//3), (size*2//3, size//2), 200, 6)
        cv2.line(img, (size*2//3, size//3), (size//3, size//2), 200, 6)
        # 土字底
        cv2.line(img, (size//3, size*2//3), (size*2//3, size*2//3), 200, 6)
        cv2.line(img, (size//2, size//2), (size//2, size*3//4), 200, 6)
    elif char == "教":
        # 孝字旁
        cv2.line(img, (size//3, size//4), (size*2//3, size//4), 200, 6)
        cv2.line(img, (size//2, size//4), (size//2, size*3//4), 200, 6)
        # 反文旁
        cv2.line(img, (size*2//3, size//3), (size*2//3, size*2//3), 200, 6)
        cv2.line(img, (size//2, size//2), (size*3//4, size//2), 200, 6)
    elif char == "序":
        # 广字头
        cv2.line(img, (size//2, size//4), (size//3, size*3//4), 200, 6)
        cv2.line(img, (size//2, size//4), (size*2//3, size//4), 200, 6)
        # 予字
        cv2.line(img, (size*2//5, size//2), (size*2//3, size//2), 200, 6)
        cv2.line(img, (size//2, size//2), (size*2//5, size*2//3), 200, 6)
    elif char == "皇":
        # 白字旁
        cv2.line(img, (size//3, size//3), (size//3, size//2), 200, 6)
        cv2.line(img, (size//3, size//3), (size*2//5, size//3), 200, 6)
        cv2.line(img, (size//3, size//2), (size*2//5, size//2), 200, 6)
        # 王字底
        cv2.line(img, (size//3, size*2//3), (size*2//3, size*2//3), 200, 6)
        cv2.line(img, (size//2, size//2), (size//2, size*3//4), 200, 6)
    elif char == "帝":
        # 立字旁
        cv2.line(img, (size//2, size//4), (size//2, size*2//3), 200, 6)
        cv2.line(img, (size//3, size//3), (size*2//3, size//3), 200, 6)
        # 巾字底
        cv2.line(img, (size//3, size*2//3), (size*2//3, size*2//3), 200, 6)
        cv2.line(img, (size*2//5, size//2), (size*2//5, size*3//4), 200, 6)
    elif char == "文":
        # 点
        cv2.circle(img, (size//2, size//3), 5, 200, -1)
        # 横
        cv2.line(img, (size//3, size//2), (size*2//3, size//2), 200, 6)
        # 撇捺
        cv2.line(img, (size//2, size//2), (size//3, size*3//4), 200, 6)
        cv2.line(img, (size//2, size//2), (size*2//3, size*3//4), 200, 6)
    else:
        # 默认绘制一个简单图形
        cv2.putText(img, char, (size//3, size*2//3), cv2.FONT_HERSHEY_SIMPLEX, 2, 200, 3)
    
    # 添加噪声
    noise = np.random.normal(0, 10, (size, size)).astype(np.int16)
    img = np.clip(img.astype(np.int16) + noise, 0, 255).astype(np.uint8)
    
    return img

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
        
        # 定义所有字形（包括真实图像和生成的图像）
        all_chars = [
            # 真实图像
            ("data/大.png", "大", "U+5927", True),
            ("data/三.png", "三", "U+4E09", True),
            ("data/乘.png", "乘", "U+4E58", True),
            # 生成的图像
            (None, "藏", "U+85CF", False),
            (None, "唐", "U+5510", False),
            (None, "圣", "U+5723", False),
            (None, "教", "U+6559", False),
            (None, "序", "U+5E8F", False),
            (None, "皇", "U+7687", False),
            (None, "帝", "U+5E1D", False),
            (None, "文", "U+6587", False),
        ]
        
        image_processor = ImageProcessor(target_size=(128, 128))
        feature_extractor = SimpleFeatureExtractor(feature_dim=512)
        
        # 创建字形目录
        backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        chars_dir = os.path.join(backend_dir, "data", "static", "characters", f"stele_{stele_id}")
        os.makedirs(chars_dir, exist_ok=True)
        print(f"字形目录: {chars_dir}")
        
        for img_path, char, unicode_val, is_real in all_chars:
            try:
                if is_real and img_path and os.path.exists(img_path):
                    # 使用真实图像
                    img = load_image(img_path)
                    source = "real_image"
                else:
                    # 生成图像
                    img = generate_char_image(char)
                    source = "generated"
                
                if img is None:
                    continue
                
                # 保存图像
                safe_unicode = unicode_val.replace('+', '_')
                image_filename = f"{safe_unicode}.png"
                image_path = os.path.join(chars_dir, image_filename)
                cv2.imwrite(image_path, img)
                print(f"  ✓ 保存图像: {image_filename} ({source})")
                
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
                    meta_info={"source": source}
                )
                
                db.add(character)
                print(f"  ✓ 创建字形: {char}")
                
            except Exception as e:
                print(f"  ✗ 创建字形 {char} 失败: {e}")
        
        db.commit()
        print("\n字形数据创建完成")
        
        # 统计
        char_count = db.query(Character).filter(Character.stele_id == stele_id).count()
        print(f"\n数据初始化完成！")
        print(f"碑帖: {stele_name}")
        print(f"字形数量: {char_count}")
        
    finally:
        db.close()

if __name__ == "__main__":
    init_database()
