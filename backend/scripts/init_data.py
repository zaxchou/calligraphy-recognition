"""
初始化数据库数据
创建雁塔圣教序碑帖和示例字形数据
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
import numpy as np
import cv2

# 创建所有表
print("创建数据库表...")
Base.metadata.create_all(bind=engine)
print("✓ 数据库表创建完成")


def init_steles(db: Session):
    """初始化碑帖数据"""
    
    # 检查是否已存在
    existing = db.query(Stele).filter(Stele.name == "雁塔圣教序").first()
    if existing:
        print("雁塔圣教序碑帖已存在，跳过创建")
        return existing
    
    stele = Stele(
        name="雁塔圣教序",
        dynasty="唐代",
        calligrapher="褚遂良",
        style="楷书",
        description="""
        《雁塔圣教序》又称《慈恩寺圣教序》，唐代褚遂良书。
        楷书，共1463字。公元653年（唐永徽四年）立。
        共二石，均在陕西西安慈恩寺大雁塔下。
        前石为序，全称《大唐三藏圣教序》，唐太宗李世民撰文；
        后石为记，全称《大唐皇帝述三藏圣教记》，唐高宗李治撰文。
        褚遂良书法的代表作，字体清丽刚劲，笔法娴熟老成。
        """
    )
    
    db.add(stele)
    db.commit()
    db.refresh(stele)
    
    print(f"创建碑帖成功: {stele.name} (ID: {stele.id})")
    return stele


def generate_character_image(char: str, seed: int = 42) -> np.ndarray:
    """
    生成更有区分度的字形图像
    每个字有不同的笔画结构和特征
    """
    np.random.seed(seed)
    
    # 创建空白画布
    img = np.zeros((128, 128), dtype=np.uint8)
    
    # 根据字符生成不同的笔画模式
    if char == "大":
        # 大：一横一撇一捺
        cv2.line(img, (40, 40), (88, 40), 255, 3)  # 横
        cv2.line(img, (64, 40), (40, 100), 255, 3)  # 撇
        cv2.line(img, (64, 40), (88, 100), 255, 3)  # 捺
    elif char == "唐":
        # 唐：广字头 + 肀
        cv2.line(img, (30, 30), (30, 100), 255, 3)  # 广左竖
        cv2.line(img, (30, 30), (98, 30), 255, 3)   # 广横
        cv2.line(img, (98, 30), (98, 50), 255, 3)   # 广右竖
        cv2.line(img, (45, 55), (85, 55), 255, 2)   # 肀横
        cv2.line(img, (45, 70), (85, 70), 255, 2)   # 肀横
        cv2.line(img, (45, 85), (85, 85), 255, 2)   # 肀横
        cv2.line(img, (65, 55), (65, 100), 255, 2)  # 肀竖
    elif char == "三":
        # 三：三横
        cv2.line(img, (35, 35), (93, 35), 255, 3)
        cv2.line(img, (35, 64), (93, 64), 255, 3)
        cv2.line(img, (35, 93), (93, 93), 255, 3)
    elif char == "藏":
        # 藏：复杂结构
        # 草字头
        cv2.line(img, (25, 25), (103, 25), 255, 2)
        cv2.line(img, (35, 15), (35, 35), 255, 2)
        cv2.line(img, (93, 15), (93, 35), 255, 2)
        # 左半部分
        cv2.line(img, (35, 40), (35, 110), 255, 2)
        cv2.line(img, (35, 55), (60, 55), 255, 2)
        cv2.line(img, (35, 75), (60, 75), 255, 2)
        # 右半部分
        cv2.line(img, (70, 40), (70, 110), 255, 2)
        cv2.line(img, (70, 55), (95, 55), 255, 2)
        cv2.line(img, (70, 75), (95, 75), 255, 2)
        cv2.line(img, (70, 95), (95, 95), 255, 2)
    elif char == "圣":
        # 圣：又 + 土
        cv2.line(img, (35, 30), (60, 60), 255, 3)  # 又撇
        cv2.line(img, (60, 30), (35, 60), 255, 3)  # 又捺
        cv2.line(img, (40, 70), (88, 70), 255, 3)  # 土横
        cv2.line(img, (64, 70), (64, 100), 255, 3) # 土竖
        cv2.line(img, (40, 100), (88, 100), 255, 3) # 土底横
    elif char == "教":
        # 教：孝 + 攵
        cv2.line(img, (25, 25), (25, 50), 255, 2)   # 孝左竖
        cv2.line(img, (25, 35), (50, 35), 255, 2)   # 孝横
        cv2.line(img, (37, 50), (37, 80), 255, 2)   # 孝竖
        cv2.line(img, (55, 20), (55, 80), 255, 2)   # 孝右竖
        cv2.line(img, (65, 30), (65, 100), 255, 2)  # 攵撇
        cv2.line(img, (85, 30), (85, 100), 255, 2)  # 攵捺
        cv2.line(img, (65, 30), (95, 30), 255, 2)   # 攵横
    elif char == "序":
        # 序：广 + 予
        cv2.line(img, (25, 25), (25, 110), 255, 3)  # 广左竖
        cv2.line(img, (25, 25), (103, 25), 255, 3)  # 广横
        cv2.line(img, (50, 45), (50, 110), 255, 2)  # 予竖
        cv2.line(img, (50, 60), (85, 60), 255, 2)   # 予横
        cv2.line(img, (70, 45), (95, 80), 255, 2)   # 予撇
    elif char == "皇":
        # 皇：白 + 王
        cv2.rectangle(img, (35, 20), (65, 50), 255, 2)  # 白外框
        cv2.line(img, (35, 35), (65, 35), 255, 2)       # 白横
        cv2.line(img, (40, 60), (88, 60), 255, 3)       # 王上横
        cv2.line(img, (40, 80), (88, 80), 255, 3)       # 王中横
        cv2.line(img, (40, 100), (88, 100), 255, 3)     # 王下横
        cv2.line(img, (64, 60), (64, 100), 255, 3)      # 王竖
    elif char == "帝":
        # 帝：亠 + 冖 + 巾
        cv2.line(img, (40, 20), (88, 20), 255, 3)       # 亠横
        cv2.line(img, (64, 20), (50, 40), 255, 3)       # 亠点
        cv2.line(img, (30, 40), (98, 40), 255, 3)       # 冖横
        cv2.line(img, (30, 40), (30, 55), 255, 2)       # 冖左竖
        cv2.line(img, (98, 40), (98, 55), 255, 2)       # 冖右竖
        cv2.line(img, (50, 55), (78, 55), 255, 2)       # 巾上横
        cv2.line(img, (64, 55), (64, 110), 255, 3)      # 巾竖
        cv2.line(img, (50, 110), (78, 110), 255, 2)     # 巾底横
    elif char == "文":
        # 文：亠 + 乂
        cv2.line(img, (40, 25), (88, 25), 255, 3)       # 亠横
        cv2.line(img, (64, 25), (50, 45), 255, 3)       # 亠点
        cv2.line(img, (40, 45), (88, 100), 255, 3)      # 乂撇
        cv2.line(img, (88, 45), (40, 100), 255, 3)      # 乂捺
    else:
        # 默认：使用文字渲染
        cv2.putText(img, char, (35, 90), cv2.FONT_HERSHEY_SIMPLEX, 2, 255, 3)
    
    # 添加轻微的随机扰动使图像更自然
    noise = np.random.normal(0, 5, img.shape).astype(np.uint8)
    img = cv2.add(img, noise)
    
    # 添加轻微的模糊模拟真实书法
    img = cv2.GaussianBlur(img, (3, 3), 0.5)
    
    return img


def create_sample_characters(db: Session, stele_id: int):
    """创建示例字形数据（用于演示）"""
    
    # 删除旧数据
    deleted = db.query(Character).filter(Character.stele_id == stele_id).delete()
    if deleted > 0:
        print(f"删除旧的 {deleted} 个字形数据")
    db.commit()
    
    # 示例汉字
    sample_chars = [
        ("大", "U+5927"),
        ("唐", "U+5510"),
        ("三", "U+4E09"),
        ("藏", "U+85CF"),
        ("圣", "U+5723"),
        ("教", "U+6559"),
        ("序", "U+5E8F"),
        ("皇", "U+7687"),
        ("帝", "U+5E1D"),
        ("文", "U+6587"),
    ]
    
    image_processor = ImageProcessor(target_size=(128, 128))
    feature_extractor = SimpleFeatureExtractor(feature_dim=512)
    
    # 创建字形目录 - 使用绝对路径
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    chars_dir = os.path.join(backend_dir, "data", "static", "characters", f"stele_{stele_id}")
    os.makedirs(chars_dir, exist_ok=True)
    print(f"字形目录: {chars_dir}")
    
    for idx, (char, unicode_val) in enumerate(sample_chars):
        # 使用不同的种子生成不同的图像特征
        img = generate_character_image(char, seed=idx * 100)
        
        # 保存图像 - 使用安全的文件名（只使用Unicode码点）
        safe_unicode = unicode_val.replace('+', '_')
        image_filename = f"{safe_unicode}.png"
        image_path = os.path.join(chars_dir, image_filename)
        success = cv2.imwrite(image_path, img)
        if not success:
            print(f"  ✗ 保存图像失败: {image_path}")
        else:
            print(f"  ✓ 保存图像成功: {image_path}")
        
        # 使用与识别流程相同的图像处理方式
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
            image_path=f"/static/characters/stele_{stele_id}/{safe_unicode}.png",
            feature_vector=feature_vector,
            stroke_count=len(char),
            bounding_box={"x": 0, "y": 0, "w": 128, "h": 128},
            meta_info={"source": "sample", "note": "示例数据"}
        )
        
        db.add(character)
        print(f"创建字形: {char}")
    
    db.commit()
    print(f"示例字形数据创建完成")


def main():
    """主函数"""
    print("开始初始化数据库数据...")
    
    db = SessionLocal()
    try:
        # 创建碑帖
        stele = init_steles(db)
        
        # 创建示例字形
        create_sample_characters(db, stele.id)
        
        print("\n数据初始化完成！")
        print(f"碑帖: {stele.name}")
        print(f"字形数量: {db.query(Character).filter(Character.stele_id == stele.id).count()}")
        
    except Exception as e:
        print(f"初始化失败: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
