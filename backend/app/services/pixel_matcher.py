"""
像素级匹配器 - 直接比较图像像素相似度
对于简单字形识别更准确
"""
import numpy as np
import cv2
from typing import List, Dict, Tuple
from sqlalchemy.orm import Session
from app.models.character import Character
from app.models.stele import Stele


class PixelMatcher:
    """基于像素相似度的匹配器"""
    
    def __init__(self, target_size: Tuple[int, int] = (128, 128)):
        self.target_size = target_size
        self.characters_data = []
        self.reference_images = {}  # 存储参考图像
        self.is_initialized = False
    
    def build_index(self, db: Session):
        """从数据库构建参考图像库"""
        characters = db.query(Character).all()
        
        if not characters:
            print("警告：数据库中没有字符数据")
            return
        
        self.characters_data = []
        self.reference_images = {}
        
        # 获取后端目录路径 (backend/app/services -> backend)
        backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        
        for char in characters:
            # 加载参考图像
            image_path = char.image_path
             
            # 构建完整路径 - 数据库路径是 /static/...，对应 backend/data/static/...
            if image_path.startswith('/static/'):
                full_path = os.path.join(backend_dir, 'data', image_path.lstrip('/'))
            elif image_path.startswith('data/'):
                full_path = os.path.join(backend_dir, image_path)
            else:
                full_path = os.path.join(backend_dir, 'data', image_path)
            
            print(f"尝试加载图像: {full_path}")
            
            if os.path.exists(full_path):
                img = cv2.imread(full_path, cv2.IMREAD_GRAYSCALE)
                if img is not None:
                    # 二值化
                    _, binary = cv2.threshold(img, 127, 255, cv2.THRESH_BINARY)
                    self.reference_images[char.character] = binary
                    self.characters_data.append({
                        'id': char.id,
                        'character': char.character,
                        'stele_id': char.stele_id,
                        'image_path': char.image_path,
                        'unicode': char.unicode
                    })
                    print(f"  ✓ 成功加载: {char.character}")
                else:
                    print(f"  ✗ 无法读取图像: {full_path}")
            else:
                print(f"  ✗ 文件不存在: {full_path}")
        
        self.is_initialized = len(self.reference_images) > 0
        print(f"像素匹配器初始化完成，包含 {len(self.reference_images)} 个参考图像")
    
    def match(self, query_image: np.ndarray, db: Session, top_k: int = 5) -> Dict:
        """
        像素级匹配
        
        Args:
            query_image: 查询图像 (RGB格式)
            db: 数据库会话
            top_k: 返回前K个结果
            
        Returns:
            匹配结果
        """
        if not self.is_initialized:
            self.build_index(db)
        
        if not self.is_initialized:
            return {
                'success': False,
                'message': '匹配器未初始化'
            }
        
        # 预处理查询图像
        query_binary = self._preprocess(query_image)
        
        # 计算与每个参考图像的相似度
        similarities = []
        for char_data in self.characters_data:
            char = char_data['character']
            if char in self.reference_images:
                ref_img = self.reference_images[char]
                sim = self._compute_similarity(query_binary, ref_img)
                similarities.append({
                    'character': char,
                    'similarity': sim,
                    'data': char_data
                })
        
        # 排序
        similarities.sort(key=lambda x: x['similarity'], reverse=True)
        top_matches = similarities[:top_k]
        
        if not top_matches:
            return {
                'success': False,
                'message': '未找到匹配结果'
            }
        
        # 获取最佳匹配
        best_match = top_matches[0]
        
        # 查询碑帖信息
        stele_info = None
        if best_match['data']['stele_id']:
            stele = db.query(Stele).filter(Stele.id == best_match['data']['stele_id']).first()
            if stele:
                stele_info = {
                    'id': stele.id,
                    'name': stele.name,
                    'dynasty': stele.dynasty,
                    'calligrapher': stele.calligrapher,
                    'style': stele.style
                }
        
        return {
            'success': True,
            'recognized_character': best_match['character'],
            'similarity': round(best_match['similarity'], 2),
            'best_match': {
                'character_id': best_match['data']['id'],
                'character': best_match['character'],
                'image_path': best_match['data']['image_path'],
                'unicode': best_match['data']['unicode'],
                'stele': stele_info
            },
            'top_matches': [
                {
                    'rank': i + 1,
                    'character_id': m['data']['id'],
                    'character': m['character'],
                    'similarity': round(m['similarity'], 2),
                    'stele_id': m['data']['stele_id'],
                    'image_path': m['data']['image_path'],
                    'unicode': m['data']['unicode']
                }
                for i, m in enumerate(top_matches)
            ]
        }
    
    def _preprocess(self, image: np.ndarray) -> np.ndarray:
        """预处理图像"""
        # 转换为灰度图
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        else:
            gray = image
        
        # 调整大小
        resized = cv2.resize(gray, self.target_size, interpolation=cv2.INTER_AREA)
        
        # 二值化
        _, binary = cv2.threshold(resized, 127, 255, cv2.THRESH_BINARY)
        
        return binary
    
    def _compute_similarity(self, img1: np.ndarray, img2: np.ndarray) -> float:
        """
        计算两幅图像的相似度
        使用多种方法取加权平均
        """
        # 确保图像大小相同
        if img1.shape != img2.shape:
            img2 = cv2.resize(img2, (img1.shape[1], img1.shape[0]))
        
        # 方法1：像素级准确率
        pixel_match = np.sum(img1 == img2) / img1.size
        
        # 方法2：结构相似度（简化版）
        # 计算笔画重叠度
        intersection = np.sum((img1 > 0) & (img2 > 0))
        union = np.sum((img1 > 0) | (img2 > 0))
        iou = intersection / (union + 1e-7)
        
        # 方法3：轮廓相似度
        contours1, _ = cv2.findContours(img1, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        contours2, _ = cv2.findContours(img2, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if contours1 and contours2:
            # 比较轮廓数量
            contour_sim = 1 - abs(len(contours1) - len(contours2)) / max(len(contours1), len(contours2))
        else:
            contour_sim = 0
        
        # 加权组合
        similarity = pixel_match * 0.4 + iou * 0.5 + contour_sim * 0.1
        
        return similarity * 100  # 转换为百分比


import os
