"""
简化匹配器 - 直接使用特征向量余弦相似度
"""
import logging
import numpy as np
from typing import List, Dict
from sqlalchemy.orm import Session
from app.models.character import Character
from app.models.stele import Stele

logger = logging.getLogger(__name__)


class SimpleMatcher:
    """基于余弦相似度的简单匹配器"""
    
    def __init__(self):
        self.characters_data = []
        self.is_initialized = False
    
    def build_index(self, db: Session):
        """从数据库加载特征向量"""
        characters = db.query(Character).all()
        
        self.characters_data = []
        for char in characters:
            if char.feature_vector:
                self.characters_data.append({
                    'id': char.id,
                    'character': char.character,
                    'stele_id': char.stele_id,
                    'image_path': char.image_path,
                    'unicode': char.unicode,
                    'feature_vector': np.array(char.feature_vector)
                })
        
        self.is_initialized = len(self.characters_data) > 0
        logger.info("简单匹配器初始化完成，包含 %d 个字符", len(self.characters_data))
    
    def match(self, query_feature: np.ndarray, db: Session, top_k: int = 5, threshold: float = 50.0) -> Dict:
        """
        匹配特征向量
        
        Args:
            query_feature: 查询特征向量
            db: 数据库会话
            top_k: 返回前K个结果
            threshold: 相似度阈值
            
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
        
        # 计算余弦相似度
        similarities = []
        query_norm = np.linalg.norm(query_feature)
        
        if query_norm == 0:
            return {
                'success': False,
                'message': '查询特征向量为零'
            }
        
        query_normalized = query_feature / query_norm
        
        for char_data in self.characters_data:
            ref_feature = char_data['feature_vector']
            ref_norm = np.linalg.norm(ref_feature)
            
            if ref_norm > 0:
                ref_normalized = ref_feature / ref_norm
                # 余弦相似度 (-1 到 1)
                cosine_sim = np.dot(query_normalized, ref_normalized)
                # 转换为 0-100 的相似度，使用sigmoid函数使分布更合理
                # 将余弦相似度映射到 50-100 范围，避免所有结果都接近100%
                similarity = 50 + 50 * cosine_sim
                similarities.append({
                    'character': char_data['character'],
                    'similarity': similarity,
                    'data': char_data
                })
        
        # 排序
        similarities.sort(key=lambda x: x['similarity'], reverse=True)
        
        # 只保留相似度 >= 40% 的候选
        min_similarity_threshold = 40.0
        filtered_similarities = [s for s in similarities if s['similarity'] >= min_similarity_threshold]
        
        # 取前top_k个
        top_matches = filtered_similarities[:top_k]
        
        if not top_matches:
            return {
                'success': False,
                'message': '未找到相似度足够的匹配结果',
                'top_matches': []
            }
        
        # 获取最佳匹配
        best_match = top_matches[0]
        
        # 检查是否超过阈值
        if best_match['similarity'] < threshold:
            return {
                'success': False,
                'message': f'相似度低于阈值 ({best_match["similarity"]:.1f}% < {threshold}%)',
                'top_matches': [
                    {
                        'rank': i + 1,
                        'character_id': m['data']['id'],
                        'character': m['character'],
                        'similarity': round(m['similarity'], 1),
                        'stele_id': m['data']['stele_id'],
                        'image_path': m['data']['image_path'],
                        'unicode': m['data']['unicode']
                    }
                    for i, m in enumerate(top_matches)
                ]
            }
        
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
            'similarity': round(best_match['similarity'], 1),
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
                    'similarity': round(m['similarity'], 1),
                    'stele_id': m['data']['stele_id'],
                    'image_path': m['data']['image_path'],
                    'unicode': m['data']['unicode']
                }
                for i, m in enumerate(top_matches)
            ]
        }
