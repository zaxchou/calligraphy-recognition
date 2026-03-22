import numpy as np
from typing import List, Dict, Tuple
from sqlalchemy.orm import Session
from app.models.character import Character
from app.models.stele import Stele
import json

# 尝试导入FAISS，如果失败则使用纯NumPy实现
try:
    import faiss
    HAS_FAISS = True
except ImportError:
    HAS_FAISS = False
    print("警告: FAISS未安装，使用纯NumPy实现向量检索")


class CalligraphyMatcher:
    """书法字体匹配器 - 基于FAISS向量检索"""
    
    def __init__(self, feature_dim: int = 512, use_faiss: bool = True):
        self.feature_dim = feature_dim
        self.use_faiss = use_faiss and HAS_FAISS
        self.index = None
        self.characters_data = []  # 存储字符元数据
        self.is_initialized = False
    
    def build_index(self, db: Session):
        """
        从数据库构建FAISS索引
        
        Args:
            db: 数据库会话
        """
        # 获取所有字符数据
        characters = db.query(Character).all()
        
        if not characters:
            print("警告：数据库中没有字符数据")
            return
        
        # 准备特征向量和元数据
        features_list = []
        self.characters_data = []
        
        for char in characters:
            if char.feature_vector:
                features_list.append(char.feature_vector)
                self.characters_data.append({
                    'id': char.id,
                    'character': char.character,
                    'stele_id': char.stele_id,
                    'image_path': char.image_path,
                    'unicode': char.unicode
                })
        
        if not features_list:
            print("警告：没有有效的特征向量")
            return
        
        # 转换为numpy数组
        features = np.array(features_list, dtype=np.float32)
        
        # 构建FAISS索引
        if self.use_faiss:
            # 使用内积（余弦相似度需要先归一化）
            self.index = faiss.IndexFlatIP(self.feature_dim)
            
            # 归一化特征向量（用于余弦相似度）
            faiss.normalize_L2(features)
            
            # 添加向量到索引
            self.index.add(features)
            
            print(f"FAISS索引构建完成，包含 {len(features)} 个向量")
        else:
            # 不使用FAISS，直接存储
            # 归一化特征向量
            norms = np.linalg.norm(features, axis=1, keepdims=True)
            norms[norms == 0] = 1  # 避免除零
            self.features = features / norms
            print(f"特征库构建完成，包含 {len(features)} 个向量")
        
        self.is_initialized = True
    
    def search(
        self, 
        query_feature: np.ndarray, 
        top_k: int = 5
    ) -> List[Dict]:
        """
        搜索最相似的字符
        
        Args:
            query_feature: 查询特征向量
            top_k: 返回前K个结果
            
        Returns:
            匹配结果列表
        """
        if not self.is_initialized:
            raise RuntimeError("匹配器未初始化，请先调用build_index()")
        
        # 确保特征向量是float32类型
        query_feature = np.array(query_feature, dtype=np.float32).reshape(1, -1)
        
        # 归一化查询向量
        query_norm = np.linalg.norm(query_feature)
        if query_norm > 0:
            query_feature = query_feature / query_norm
        
        if self.use_faiss and self.index is not None:
            # 使用FAISS搜索
            similarities, indices = self.index.search(query_feature, top_k)
            
            results = []
            for i, (sim, idx) in enumerate(zip(similarities[0], indices[0])):
                if idx < 0 or idx >= len(self.characters_data):
                    continue
                
                char_data = self.characters_data[idx]
                results.append({
                    'rank': i + 1,
                    'character_id': char_data['id'],
                    'character': char_data['character'],
                    'stele_id': char_data['stele_id'],
                    'image_path': char_data['image_path'],
                    'similarity': float(sim * 100),  # 转换为百分比
                    'unicode': char_data['unicode']
                })
            
            return results
        else:
            # 暴力搜索 - 使用NumPy计算余弦相似度
            similarities = np.dot(self.features, query_feature.T).flatten()
            top_indices = np.argsort(similarities)[::-1][:top_k]
            
            results = []
            for i, idx in enumerate(top_indices):
                char_data = self.characters_data[idx]
                results.append({
                    'rank': i + 1,
                    'character_id': char_data['id'],
                    'character': char_data['character'],
                    'stele_id': char_data['stele_id'],
                    'image_path': char_data['image_path'],
                    'similarity': float(similarities[idx] * 100),
                    'unicode': char_data['unicode']
                })
            
            return results
    
    def match(
        self, 
        query_feature: np.ndarray,
        db: Session,
        top_k: int = 5,
        threshold: float = 70.0
    ) -> Dict:
        """
        完整的匹配流程
        
        Args:
            query_feature: 查询特征向量
            db: 数据库会话
            top_k: 返回前K个结果
            threshold: 相似度阈值
            
        Returns:
            匹配结果字典
        """
        # 搜索相似字符
        matches = self.search(query_feature, top_k=top_k)
        
        if not matches:
            return {
                'success': False,
                'message': '未找到匹配结果',
                'matches': []
            }
        
        # 获取最佳匹配
        best_match = matches[0]
        
        # 查询碑帖信息
        stele_info = None
        if best_match['stele_id']:
            stele = db.query(Stele).filter(Stele.id == best_match['stele_id']).first()
            if stele:
                stele_info = {
                    'id': stele.id,
                    'name': stele.name,
                    'dynasty': stele.dynasty,
                    'calligrapher': stele.calligrapher,
                    'style': stele.style
                }
        
        # 判断匹配结果
        is_confident = best_match['similarity'] >= threshold
        
        result = {
            'success': True,
            'is_confident': is_confident,
            'recognized_character': best_match['character'],
            'similarity': round(best_match['similarity'], 2),
            'best_match': {
                'character_id': best_match['character_id'],
                'character': best_match['character'],
                'image_path': best_match['image_path'],
                'unicode': best_match['unicode'],
                'stele': stele_info
            },
            'top_matches': matches,
            'threshold': threshold
        }
        
        return result
    
    def add_character(self, character_data: Dict, feature_vector: np.ndarray):
        """
        添加新字符到索引
        
        Args:
            character_data: 字符元数据
            feature_vector: 特征向量
        """
        if not self.is_initialized:
            # 初始化索引
            if self.use_faiss:
                self.index = faiss.IndexFlatIP(self.feature_dim)
            else:
                self.features = np.array([]).reshape(0, self.feature_dim)
            self.is_initialized = True
        
        feature_vector = np.array(feature_vector, dtype=np.float32).reshape(1, -1)
        # 归一化
        norm = np.linalg.norm(feature_vector)
        if norm > 0:
            feature_vector = feature_vector / norm
        
        if self.use_faiss and self.index is not None:
            self.index.add(feature_vector)
        else:
            if self.features.size == 0:
                self.features = feature_vector
            else:
                self.features = np.vstack([self.features, feature_vector])
        
        self.characters_data.append(character_data)
    
    def save_index(self, filepath: str):
        """保存FAISS索引到文件"""
        if self.use_faiss and self.index is not None:
            faiss.write_index(self.index, filepath)
            # 保存元数据
            import json
            with open(filepath + '.meta', 'w', encoding='utf-8') as f:
                json.dump(self.characters_data, f, ensure_ascii=False)
            print(f"索引已保存到 {filepath}")
    
    def load_index(self, filepath: str):
        """从文件加载FAISS索引"""
        if self.use_faiss:
            self.index = faiss.read_index(filepath)
            # 加载元数据
            import json
            with open(filepath + '.meta', 'r', encoding='utf-8') as f:
                self.characters_data = json.load(f)
            self.is_initialized = True
            print(f"索引已从 {filepath} 加载")


class SimilarityCalculator:
    """相似度计算器 - 多种相似度度量方法"""
    
    @staticmethod
    def cosine_similarity(v1: np.ndarray, v2: np.ndarray) -> float:
        """余弦相似度"""
        v1_norm = v1 / (np.linalg.norm(v1) + 1e-7)
        v2_norm = v2 / (np.linalg.norm(v2) + 1e-7)
        return float(np.dot(v1_norm, v2_norm))
    
    @staticmethod
    def euclidean_distance(v1: np.ndarray, v2: np.ndarray) -> float:
        """欧氏距离（转换为相似度）"""
        dist = np.linalg.norm(v1 - v2)
        # 转换为相似度（0-1范围）
        sim = 1 / (1 + dist)
        return float(sim)
    
    @staticmethod
    def manhattan_distance(v1: np.ndarray, v2: np.ndarray) -> float:
        """曼哈顿距离（转换为相似度）"""
        dist = np.sum(np.abs(v1 - v2))
        sim = 1 / (1 + dist)
        return float(sim)
    
    @staticmethod
    def correlation_similarity(v1: np.ndarray, v2: np.ndarray) -> float:
        """相关系数相似度"""
        if len(v1) < 2:
            return 0.0
        
        v1_centered = v1 - np.mean(v1)
        v2_centered = v2 - np.mean(v2)
        
        numerator = np.sum(v1_centered * v2_centered)
        denominator = np.sqrt(np.sum(v1_centered**2) * np.sum(v2_centered**2))
        
        if denominator == 0:
            return 0.0
        
        return float(numerator / denominator)
