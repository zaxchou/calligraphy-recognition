"""
增强版匹配器 - 使用多特征融合和关键点匹配
"""
import os
import numpy as np
import cv2
from typing import List, Dict, Optional, Tuple
from sqlalchemy.orm import Session
from app.models.character import Character
from app.core.path_utils import get_full_file_path
from app.services.image_processor import binarize_image


class EnhancedMatcher:
    """增强版书法字形匹配器"""
    
    def __init__(self):
        self.characters_data = []
        self.use_keypoints = True
        self.use_histogram = True
        self.use_structure = True
    
    def build_index(self, db: Session):
        """构建字形索引"""
        characters = db.query(Character).all()
        
        self.characters_data = []
        for char in characters:
            if char.feature_vector:
                self.characters_data.append({
                    'id': char.id,
                    'character': char.character,
                    'unicode': char.unicode,
                    'feature_vector': np.array(char.feature_vector),
                    'image_path': char.image_path,
                    'stele_id': char.stele_id
                })
        
        logger.info("增强匹配器初始化完成，包含 %d 个字符", len(self.characters_data))
    
    def match(
        self, 
        query_image: np.ndarray, 
        db: Session, 
        top_k: int = 5,
        threshold: float = 50.0
    ) -> Dict:
        """
        多特征融合匹配
        
        Args:
            query_image: 查询图像 (预处理后的图像)
            db: 数据库会话
            top_k: 返回前k个结果
            threshold: 相似度阈值
            
        Returns:
            匹配结果
        """
        if not self.characters_data:
            self.build_index(db)
        
        if not self.characters_data:
            return {
                'success': False,
                'message': '数据库中没有字形数据',
                'recognized_character': None,
                'similarity': 0,
                'best_match': None,
                'top_matches': []
            }
        
        # 提取查询图像的多重特征
        query_features = self._extract_multi_features(query_image)
        
        # 计算与每个数据库字形的相似度
        similarities = []
        for char_data in self.characters_data:
            # 获取数据库字形的图像路径并重新提取特征
            db_image = self._load_character_image(char_data['image_path'])
            if db_image is None:
                continue
            
            db_features = self._extract_multi_features(db_image)
            
            # 计算综合相似度
            similarity = self._compute_similarity(query_features, db_features)
            
            similarities.append({
                'character_id': char_data['id'],
                'character': char_data['character'],
                'unicode': char_data['unicode'],
                'similarity': similarity,
                'image_path': char_data['image_path']
            })
        
        # 按相似度排序
        similarities.sort(key=lambda x: x['similarity'], reverse=True)
        
        # 获取最佳匹配
        best_match = similarities[0] if similarities else None
        
        # 判断是否成功匹配
        is_match = best_match is not None and best_match['similarity'] >= threshold
        
        # 组装结果
        result = {
            'success': is_match,
            'message': '匹配成功' if is_match else '未找到足够相似的匹配',
            'recognized_character': best_match['character'] if best_match else None,
            'similarity': round(best_match['similarity'], 2) if best_match else 0,
            'best_match': best_match,
            'top_matches': [
                {
                    'rank': i + 1,
                    'character_id': m['character_id'],
                    'character': m['character'],
                    'unicode': m['unicode'],
                    'similarity': round(m['similarity'], 2),
                    'image_path': m['image_path']
                }
                for i, m in enumerate(similarities[:top_k])
            ]
        }
        
        return result
    
    def _load_character_image(self, image_path: str) -> Optional[np.ndarray]:
        """加载字形图像"""
        try:
            # 使用跨平台路径处理工具构建完整路径
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            full_path = get_full_file_path(image_path, os.path.join(base_dir, 'data'))

            img = cv2.imread(full_path)
            if img is None:
                return None
            
            # 预处理
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            # 确保白色笔画在黑色背景
            mean_val = np.mean(gray)
            if mean_val < 127:
                gray = 255 - gray
            
            # 二值化（使用统一函数）
            binary = binarize_image(gray, threshold=127)
            
            # 调整大小
            resized = cv2.resize(binary, (128, 128))
            
            return resized
            
        except Exception as e:
            logger.error("加载图像失败: %s", e)
            return None
    
    def _extract_multi_features(self, image: np.ndarray) -> Dict:
        """提取多重特征"""
        # 确保是灰度图
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        else:
            gray = image.copy()
        
        # 确保白色笔画在黑色背景
        mean_val = np.mean(gray)
        if mean_val < 127:
            gray = 255 - gray
        
        # 二值化（使用统一函数）
        binary = binarize_image(gray, threshold=127)
        
        # 调整大小为标准化尺寸
        binary = cv2.resize(binary, (128, 128))
        
        features = {}
        
        # 1. 结构特征
        if self.use_structure:
            features['structure'] = self._extract_structure_features(binary)
        
        # 2. 直方图特征
        if self.use_histogram:
            features['histogram'] = self._extract_histogram_features(binary)
        
        # 3. 关键点特征
        if self.use_keypoints:
            features['keypoints'] = self._extract_keypoint_features(binary)
        
        return features
    
    def _extract_structure_features(self, binary: np.ndarray) -> np.ndarray:
        """提取结构特征"""
        h, w = binary.shape
        features = []
        
        # 1. 笔画密度
        density = np.sum(binary > 0) / binary.size
        features.append(density)
        
        # 2. 九宫格密度
        grid_size = 3
        for i in range(grid_size):
            for j in range(grid_size):
                cell = binary[i*h//grid_size:(i+1)*h//grid_size, 
                             j*w//grid_size:(j+1)*w//grid_size]
                cell_density = np.sum(cell > 0) / (cell.size + 1e-7)
                features.append(cell_density)
        
        # 3. 投影特征
        h_proj = np.sum(binary, axis=1) / 255.0 / w
        w_proj = np.sum(binary, axis=0) / 255.0 / h
        
        # 采样投影
        h_samples = np.linspace(0, len(h_proj)-1, 8, dtype=int)
        w_samples = np.linspace(0, len(w_proj)-1, 8, dtype=int)
        features.extend(h_proj[h_samples])
        features.extend(w_proj[w_samples])
        
        # 4. 轮廓特征
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        features.append(len(contours))
        
        if contours:
            areas = [cv2.contourArea(c) for c in contours]
            features.append(np.mean(areas) / (h * w))
        else:
            features.append(0)
        
        return np.array(features, dtype=np.float32)
    
    def _extract_histogram_features(self, binary: np.ndarray) -> np.ndarray:
        """提取方向直方图特征"""
        # 计算梯度
        gx = cv2.Sobel(binary, cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(binary, cv2.CV_32F, 0, 1, ksize=3)
        mag, ang = cv2.cartToPolar(gx, gy)
        
        # 16个方向直方图
        hist = np.zeros(16)
        for i in range(16):
            mask = ((ang >= i * np.pi / 8) & (ang < (i + 1) * np.pi / 8))
            hist[i] = np.sum(mag[mask])
        
        # 归一化
        if np.sum(hist) > 0:
            hist = hist / np.sum(hist)
        
        return hist
    
    def _extract_keypoint_features(self, binary: np.ndarray) -> np.ndarray:
        """提取关键点特征"""
        # 使用ORB检测关键点
        orb = cv2.ORB_create(nfeatures=50)
        keypoints, descriptors = orb.detectAndCompute(binary, None)
        
        if descriptors is None or len(keypoints) == 0:
            return np.zeros(32, dtype=np.float32)
        
        # 计算关键点的统计特征
        features = []
        
        # 关键点数量
        features.append(len(keypoints) / 50.0)
        
        # 关键点位置分布
        if keypoints:
            pts = np.array([kp.pt for kp in keypoints])
            features.append(np.mean(pts[:, 0]) / 128.0)
            features.append(np.mean(pts[:, 1]) / 128.0)
            features.append(np.std(pts[:, 0]) / 128.0)
            features.append(np.std(pts[:, 1]) / 128.0)
        else:
            features.extend([0.5, 0.5, 0, 0])
        
        # 描述符的均值
        desc_mean = np.mean(descriptors, axis=0)
        features.extend(desc_mean[:27])  # 取前27维，总共32维
        
        return np.array(features, dtype=np.float32)
    
    def _compute_similarity(self, features1: Dict, features2: Dict) -> float:
        """计算综合相似度"""
        similarities = []
        weights = []
        
        # 结构特征相似度
        if 'structure' in features1 and 'structure' in features2:
            sim = self._cosine_similarity(features1['structure'], features2['structure'])
            similarities.append(sim)
            weights.append(0.4)
        
        # 直方图特征相似度
        if 'histogram' in features1 and 'histogram' in features2:
            sim = self._cosine_similarity(features1['histogram'], features2['histogram'])
            similarities.append(sim)
            weights.append(0.3)
        
        # 关键点特征相似度
        if 'keypoints' in features1 and 'keypoints' in features2:
            sim = self._cosine_similarity(features1['keypoints'], features2['keypoints'])
            similarities.append(sim)
            weights.append(0.3)
        
        # 加权平均
        if similarities:
            total_weight = sum(weights)
            weighted_sim = sum(s * w for s, w in zip(similarities, weights)) / total_weight
            return weighted_sim * 100
        
        return 0.0
    
    def _cosine_similarity(self, v1: np.ndarray, v2: np.ndarray) -> float:
        """计算余弦相似度"""
        norm1 = np.linalg.norm(v1)
        norm2 = np.linalg.norm(v2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return np.dot(v1, v2) / (norm1 * norm2)


# 全局实例
_enhanced_matcher = None

def get_enhanced_matcher() -> EnhancedMatcher:
    """获取增强匹配器实例"""
    global _enhanced_matcher
    if _enhanced_matcher is None:
        _enhanced_matcher = EnhancedMatcher()
    return _enhanced_matcher
