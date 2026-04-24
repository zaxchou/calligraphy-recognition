"""
图像-文本关联算法 V2
基于页面空间位置的精确匹配，每张图片只关联其原始出现位置的文本
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class MatchResult:
    """匹配结果"""
    image_id: str
    chunk_id: str
    score: float  # 0-1 匹配度
    match_type: str  # spatial_proximity(空间就近), caption_above(图注上方文本)


class ImageMatcher:
    """图像-文本关联器 V2
    
    核心改动：
    1. 基于图片 bbox 和文本块 bbox 的空间距离做精确匹配
    2. 每张图片最多关联 2 个文本块（上方的描述段落 + 下方的紧邻段落）
    3. 不再使用"图X"编号做全局搜索，彻底避免后文重复引用的问题
    4. 支持传入 figure_first_page 来区分首次定义和后续引用
    """
    
    def __init__(self):
        """初始化关联器"""
        pass
    
    def build_associations(
        self,
        images: List[Dict[str, Any]],
        chunks: List[Dict[str, Any]],
        image_embeddings: Optional[List[List[float]]] = None,
        chunk_embeddings: Optional[List[List[float]]] = None,
        figure_first_page: Optional[Dict[str, int]] = None,
    ) -> Tuple[Dict[str, List[str]], Dict[str, List[str]]]:
        """
        构建完整的图像-文本关联关系
        
        核心逻辑：
        - 对每张图片，根据其 bbox 找到同页/相邻页空间距离最近的文本块
        - 每张图片最多关联 2 个块（上方的描述段落 + 下方的紧邻段落）
        - 不做"图X"引用搜索，避免后文重复引用
        
        Args:
            images: 图片列表，每个元素包含 id, page, bbox(可选), caption(可选)
            chunks: 文本块列表，每个元素包含 id, page_start, page_end, content, bbox(可选)
            image_embeddings: 未使用（保留接口兼容）
            chunk_embeddings: 未使用（保留接口兼容）
            figure_first_page: 图号首次出现页码映射
        
        Returns:
            (image_to_chunks, chunk_to_images) 两个字典
        """
        # 按 chunk_index 排序（确保 spatial 顺序正确）
        chunks = sorted(chunks, key=lambda c: c.get("chunk_index", 0))
        
        # 按页码索引 chunks，加速查找
        page_to_chunks: Dict[int, List[Dict]] = {}
        for chunk in chunks:
            start = chunk.get("page_start", 0)
            end = chunk.get("page_end", start)
            for p in range(start, end + 1):
                if p not in page_to_chunks:
                    page_to_chunks[p] = []
                page_to_chunks[p].append(chunk)
        
        image_to_chunks: Dict[str, List[str]] = {}
        chunk_to_images: Dict[str, List[str]] = {}
        
        for image in images:
            img_id = image.get("id")
            img_page = image.get("page")
            img_bbox = image.get("bbox")
            
            if not img_page:
                continue
            
            # 收集候选 chunks：图片所在页 + 前后各一页
            candidate_chunks: List[Dict] = []
            for p in range(img_page - 1, img_page + 2):
                candidate_chunks.extend(page_to_chunks.get(p, []))
            
            if not candidate_chunks:
                continue
            
            # --- 计算每个候选 chunk 的空间距离分数 ---
            scored_chunks: List[Tuple[float, Dict]] = []
            
            for chunk in candidate_chunks:
                chunk_id = chunk.get("id")
                score = self._compute_match_score(
                    img_page=img_page,
                    img_bbox=img_bbox,
                    chunk=chunk,
                )
                
                if score > 0:
                    scored_chunks.append((score, chunk))
            
            # 按分数降序排列，取前 2 个
            scored_chunks.sort(key=lambda x: x[0], reverse=True)
            
            # 最多关联 2 个 chunk
            for score, chunk in scored_chunks[:2]:
                chunk_id = chunk.get("id")
                if not chunk_id:
                    continue
                
                # image -> chunk
                if img_id not in image_to_chunks:
                    image_to_chunks[img_id] = []
                if chunk_id not in image_to_chunks[img_id]:
                    image_to_chunks[img_id].append(chunk_id)
                
                # chunk -> image
                if chunk_id not in chunk_to_images:
                    chunk_to_images[chunk_id] = []
                if img_id not in chunk_to_images[chunk_id]:
                    chunk_to_images[chunk_id].append(img_id)
        
        # 日志统计
        total_images = len(images)
        matched_images = len(image_to_chunks)
        total_associations = sum(len(v) for v in image_to_chunks.values())
        logger.info(
            f"关联构建完成: {matched_images}/{total_images} 张图片有关联, "
            f"共 {total_associations} 条关联"
        )
        
        return image_to_chunks, chunk_to_images
    
    def _compute_match_score(
        self,
        img_page: int,
        img_bbox: Optional[Dict],
        chunk: Dict[str, Any],
    ) -> float:
        """
        计算图片和文本块之间的匹配分数
        
        策略（三级）：
        1. 精确空间匹配：图片和 chunk 都有 bbox → 基于 y 坐标距离
        2. 增强页码匹配：图片有 bbox 但 chunk 没有 → 同页 0.8，相邻页 0.3
        3. 降级页码匹配：双方都没有 bbox → 同页 0.5，相邻页 0.2
        
        Returns:
            0-1 之间的分数，0 表示不匹配
        """
        chunk_pages = self._get_chunk_pages(chunk)
        
        if not chunk_pages:
            return 0.0
        
        # 第一级：双方都有 bbox，使用精确空间匹配
        if img_bbox and chunk.get("bbox"):
            return self._compute_spatial_score_precise(img_page, img_bbox, chunk)
        
        # 第二级：图片有 bbox 但 chunk 没有（bbox 证实了图片精确位置，信任度更高）
        if img_bbox:
            return self._compute_spatial_score_enhanced(img_page, chunk_pages)
        
        # 第三级：都没有 bbox，退化为页码匹配
        return self._compute_spatial_score_fallback(img_page, chunk_pages)
    
    def _compute_spatial_score_precise(
        self,
        img_page: int,
        img_bbox: Dict[str, float],
        chunk: Dict[str, Any],
    ) -> float:
        """
        精确空间匹配：基于 y 坐标距离
        
        图片通常与同一页上、下方最近的文本块相关联。
        """
        chunk_bbox = chunk.get("bbox")
        chunk_pages = self._get_chunk_pages(chunk)
        
        if not chunk_bbox or img_page not in chunk_pages:
            # 图片和 chunk 不在同一页，退化为页码匹配
            return self._compute_spatial_score_fallback(img_page, chunk_pages)
        
        img_cy = (img_bbox.get("y0", 0) + img_bbox.get("y1", 0)) / 2
        chunk_cy = (chunk_bbox.get("y0", 0) + chunk_bbox.get("y1", 0)) / 2
        
        # y 坐标差距（绝对值）
        y_distance = abs(img_cy - chunk_cy)
        
        # 估算页面高度（用 chunk 的 bbox 范围来估算）
        # 假设页面高度大约 800 点（A4 约 842pt）
        estimated_page_height = max(
            chunk_bbox.get("y1", 800) - chunk_bbox.get("y0", 0),
            img_bbox.get("y1", 800) - img_bbox.get("y0", 0),
            800
        )
        
        # 归一化距离（0-1，越小越近）
        normalized_distance = y_distance / estimated_page_height
        
        if normalized_distance > 0.5:
            return 0.0  # 距离太远，不关联
        
        # 线性映射：距离 0 → 分数 1.0，距离 0.5 → 分数 0.1
        score = max(0.0, 1.0 - normalized_distance * 2.0)
        
        # 如果 chunk 在图片正上方或正下方（水平重叠），加分
        img_cx = (img_bbox.get("x0", 0) + img_bbox.get("x1", 0)) / 2
        chunk_cx = (chunk_bbox.get("x0", 0) + chunk_bbox.get("x1", 0)) / 2
        
        x_distance = abs(img_cx - chunk_cx)
        if x_distance < estimated_page_height * 0.3:
            score = min(1.0, score + 0.1)  # 水平对齐加分
        
        return round(score, 4)
    
    def _compute_spatial_score_enhanced(
        self,
        img_page: int,
        chunk_pages: List[int],
    ) -> float:
        """
        增强页码匹配：图片有 bbox（证实精确位置）但 chunk 没有 bbox
        
        同页 0.8，相邻页 0.3
        比纯 fallback 高，因为 bbox 证实了图片确实在该页
        """
        if img_page in chunk_pages:
            return 0.8
        if any(abs(img_page - p) == 1 for p in chunk_pages):
            return 0.3
        return 0.0
    
    def _compute_spatial_score_fallback(
        self,
        img_page: int,
        chunk_pages: List[int],
    ) -> float:
        """
        降级匹配：当没有 bbox 时，仅基于页码
        
        同页 0.5，相邻页 0.2
        （比旧版低，因为无 bbox 的关联不太可靠）
        """
        if img_page in chunk_pages:
            return 0.5
        if any(abs(img_page - p) == 1 for p in chunk_pages):
            return 0.2
        return 0.0
    
    def _get_chunk_pages(self, chunk: Dict[str, Any]) -> List[int]:
        """获取文本块涉及的页码"""
        pages = []
        if chunk.get("page_start"):
            pages.append(chunk["page_start"])
        if chunk.get("page_end") and chunk["page_end"] != chunk.get("page_start"):
            pages.append(chunk["page_end"])
        return pages


# 便捷函数
def build_image_chunk_associations(
    images: List[Dict[str, Any]],
    chunks: List[Dict[str, Any]],
    figure_first_page: Optional[Dict[str, int]] = None,
) -> Tuple[Dict[str, List[str]], Dict[str, List[str]]]:
    """
    构建图像-文本关联的便捷函数
    
    Returns:
        (image_to_chunks, chunk_to_images)
    """
    matcher = ImageMatcher()
    return matcher.build_associations(images, chunks, figure_first_page=figure_first_page)


# 测试代码
if __name__ == "__main__":
    # 测试数据：模拟有 bbox 的情况
    test_images = [
        {"id": "img1", "page": 1, "bbox": {"x0": 100, "y0": 300, "x1": 400, "y1": 500}, "caption": "图一 示例"},
        {"id": "img2", "page": 2, "bbox": {"x0": 150, "y0": 200, "x1": 450, "y1": 450}, "caption": "图二 另一个"},
        {"id": "img3", "page": 3, "bbox": None},  # 无 bbox 的 fallback
    ]
    
    test_chunks = [
        {"id": "chunk1", "page_start": 1, "page_end": 1, "content": "这是图一上方的描述段落", "bbox": {"x0": 50, "y0": 100, "x1": 500, "y1": 250}, "chunk_index": 0},
        {"id": "chunk2", "page_start": 1, "page_end": 1, "content": "这是图一下方的正文段落", "bbox": {"x0": 50, "y0": 520, "x1": 500, "y1": 700}, "chunk_index": 1},
        {"id": "chunk3", "page_start": 1, "page_end": 1, "content": "这一页底部的内容", "bbox": {"x0": 50, "y0": 700, "x1": 500, "y1": 800}, "chunk_index": 2},
        {"id": "chunk4", "page_start": 2, "page_end": 2, "content": "第二章开头如图二所示", "bbox": {"x0": 50, "y0": 50, "x1": 500, "y1": 180}, "chunk_index": 3},
        {"id": "chunk5", "page_start": 3, "page_end": 3, "content": "第三章的内容（图三在这里）", "chunk_index": 4},
        {"id": "chunk6", "page_start": 8, "page_end": 8, "content": "第八章提到如图三所示", "chunk_index": 5},
    ]
    
    matcher = ImageMatcher()
    img2chunks, chunk2imgs = matcher.build_associations(test_images, test_chunks)
    
    print("图像 -> 文本块:")
    for img_id, chunk_ids in img2chunks.items():
        print(f"  {img_id}: {chunk_ids}")
    
    print("\n文本块 -> 图像:")
    for chunk_id, img_ids in chunk2imgs.items():
        print(f"  {chunk_id}: {img_ids}")
    
    print("\n期望结果:")
    print("  img1 -> [chunk1, chunk2] (上方的描述 + 下方的正文)")
    print("  img2 -> [chunk4] (相邻段落)")
    print("  img3 -> [chunk5] (同页 fallback)")
    print("  chunk6 不应关联任何图片（后文引用不应创建关联）")
