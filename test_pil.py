from PIL import Image
import os
import cv2
import numpy as np

files = ['data/大.png', 'data/三.png', 'data/乘.png']

for f in files:
    print(f"\n{f}:")
    try:
        # 使用PIL读取
        pil_img = Image.open(f)
        print(f"  PIL: {pil_img.size}, mode={pil_img.mode}")
        
        # 转换为OpenCV格式
        cv_img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
        print(f"  OpenCV转换: {cv_img.shape}")
        
        # 保存为新的文件
        new_path = f.replace('.png', '_new.png')
        cv2.imwrite(new_path, cv_img)
        print(f"  保存到: {new_path}")
        
    except Exception as e:
        print(f"  错误: {e}")
