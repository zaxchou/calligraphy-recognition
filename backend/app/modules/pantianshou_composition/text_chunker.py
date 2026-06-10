"""
文本分块策略模块
支持语义分块、固定长度、滑动窗口等多种策略
"""

import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field


@dataclass
class TextChunk:
    """文本块"""
    content: str
    chunk_index: int
    chapter_title: Optional[str] = None
    page_start: Optional[int] = None
    page_end: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    bbox: Optional[Dict[str, float]] = None  # 合并后的边界框 {x0, y0, x1, y1}
    
    def compute_hash(self) -> str:
        """计算内容哈希"""
        import hashlib
        return hashlib.md5(self.content.encode("utf-8")).hexdigest()
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "content": self.content,
            "chunk_index": self.chunk_index,
            "chapter_title": self.chapter_title,
            "page_start": self.page_start,
            "page_end": self.page_end,
            "metadata": self.metadata,
            "bbox": self.bbox,
            "hash": self.compute_hash(),
        }


class TextChunker:
    """文本分块器"""
    
    def __init__(self,
                 strategy: str = "semantic",
                 chunk_size: int = 500,
                 chunk_overlap: float = 0.05,  # 降低重叠防止内容重复
                 min_chunk_size: int = 100,
                 max_chunk_size: int = 1000):
        """
        初始化分块器
        
        Args:
            strategy: 分块策略 - semantic(语义)/fixed(固定长度)/sliding(滑动窗口)
            chunk_size: 目标块大小（字符数）
            chunk_overlap: 重叠比例（0-1）
            min_chunk_size: 最小块大小
            max_chunk_size: 最大块大小
        """
        self.strategy = strategy
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_size = min_chunk_size
        self.max_chunk_size = max_chunk_size
    
    def chunk(self, texts: List[Dict[str, Any]]) -> List[TextChunk]:
        """
        对文本列表进行分块
        
        Args:
            texts: 文本块列表，每个包含 content, page, chapter_title, bbox 等
        
        Returns:
            分块后的 TextChunk 列表
        """
        if self.strategy == "semantic":
            return self._semantic_chunk(texts)
        elif self.strategy == "fixed":
            return self._fixed_chunk(texts)
        elif self.strategy == "sliding":
            return self._sliding_chunk(texts)
        else:
            raise ValueError(f"未知的分块策略: {self.strategy}")
    
    @staticmethod
    def _merge_bboxes(bboxes: List[Optional[Dict[str, float]]]) -> Optional[Dict[str, float]]:
        """合并多个 bbox 为一个包含所有区域的最小外接矩形"""
        valid = [b for b in bboxes if b is not None]
        if not valid:
            return None
        if len(valid) == 1:
            return valid[0]
        return {
            "x0": min(b["x0"] for b in valid),
            "y0": min(b["y0"] for b in valid),
            "x1": max(b["x1"] for b in valid),
            "y1": max(b["y1"] for b in valid),
        }
    
    def _semantic_chunk(self, texts: List[Dict[str, Any]]) -> List[TextChunk]:
        """
        语义分块策略
        基于段落和章节边界进行分割，同时传播 bbox 信息
        """
        chunks = []
        chunk_index = 0
        
        # 按章节分组
        chapter_groups = {}
        for text in texts:
            chapter = text.get("chapter_title") or "正文"
            if chapter not in chapter_groups:
                chapter_groups[chapter] = []
            chapter_groups[chapter].append(text)
        
        # 对每个章节进行分块
        for chapter, chapter_texts in chapter_groups.items():
            current_chunk = []
            current_size = 0
            page_start = None
            page_end = None
            current_bboxes: List[Optional[Dict[str, float]]] = []  # 跟踪当前块的 bbox
            
            for text in chapter_texts:
                content = text.get("content", "").strip()
                page = text.get("page")
                text_bbox = text.get("bbox")  # 获取文本块的 bbox
                
                if not content:
                    continue
                
                # 记录页码
                if page_start is None:
                    page_start = page
                page_end = page
                
                # 检查是否需要分割
                if current_size + len(content) > self.chunk_size and current_chunk:
                    # 保存当前块
                    chunk_content = "\n\n".join(current_chunk)
                    if len(chunk_content) >= self.min_chunk_size:
                        merged_bbox = self._merge_bboxes(current_bboxes)
                        chunks.append(TextChunk(
                            content=chunk_content,
                            chunk_index=chunk_index,
                            chapter_title=chapter,
                            page_start=page_start,
                            page_end=page_end,
                            bbox=merged_bbox,
                        ))
                        chunk_index += 1
                    
                    # 开始新块（保留部分重叠内容）
                    overlap_count = max(1, int(len(current_chunk) * self.chunk_overlap))
                    current_chunk = current_chunk[-overlap_count:] if overlap_count > 0 else []
                    current_size = sum(len(c) for c in current_chunk)
                    current_bboxes = current_bboxes[-overlap_count:] if overlap_count > 0 else []
                    page_start = page
                
                current_chunk.append(content)
                current_size += len(content)
                if text_bbox:
                    current_bboxes.append(text_bbox)
            
            # 处理剩余的文本
            if current_chunk:
                chunk_content = "\n\n".join(current_chunk)
                if len(chunk_content) >= self.min_chunk_size:
                    merged_bbox = self._merge_bboxes(current_bboxes)
                    chunks.append(TextChunk(
                        content=chunk_content,
                        chunk_index=chunk_index,
                        chapter_title=chapter,
                        page_start=page_start,
                        page_end=page_end,
                        bbox=merged_bbox,
                    ))
                    chunk_index += 1
        
        return chunks
    
    def _fixed_chunk(self, texts: List[Dict[str, Any]]) -> List[TextChunk]:
        """
        固定长度分块策略
        按固定字符数分割，不考虑语义边界
        """
        # 合并所有文本
        full_text = "\n\n".join(t.get("content", "") for t in texts)
        
        chunks = []
        chunk_index = 0
        start = 0
        
        while start < len(full_text):
            end = min(start + self.chunk_size, len(full_text))
            
            # 尝试在句子边界分割
            if end < len(full_text):
                # 查找最近的句号、问号、感叹号
                for char in [".", "?", "!", "。", "？", "！", "\n"]:
                    pos = full_text.rfind(char, start, end)
                    if pos > start + self.min_chunk_size:
                        end = pos + 1
                        break
            
            content = full_text[start:end].strip()
            if len(content) >= self.min_chunk_size:
                chunks.append(TextChunk(
                    content=content,
                    chunk_index=chunk_index,
                    page_start=None,  # 固定长度分块不保留页码信息
                    page_end=None,
                ))
                chunk_index += 1
            
            # 计算下一个起始位置（考虑重叠）
            overlap_size = int(self.chunk_size * self.chunk_overlap)
            start = end - overlap_size if end < len(full_text) else end
        
        return chunks
    
    def _sliding_chunk(self, texts: List[Dict[str, Any]]) -> List[TextChunk]:
        """
        滑动窗口分块策略
        固定窗口大小，固定步长滑动
        """
        # 合并所有文本
        full_text = "\n\n".join(t.get("content", "") for t in texts)
        
        chunks = []
        chunk_index = 0
        step_size = int(self.chunk_size * (1 - self.chunk_overlap))
        
        start = 0
        while start < len(full_text):
            end = min(start + self.chunk_size, len(full_text))
            
            content = full_text[start:end].strip()
            if len(content) >= self.min_chunk_size:
                chunks.append(TextChunk(
                    content=content,
                    chunk_index=chunk_index,
                    page_start=None,
                    page_end=None,
                ))
                chunk_index += 1
            
            start += step_size
        
        return chunks
    
    def smart_merge(self, chunks: List[TextChunk]) -> List[TextChunk]:
        """
        智能合并短块
        将过短的块与相邻块合并，同时合并 bbox
        """
        if not chunks:
            return chunks
        
        merged = []
        i = 0
        
        while i < len(chunks):
            current = chunks[i]
            
            # 如果当前块太短，尝试与下一个合并
            if len(current.content) < self.min_chunk_size and i + 1 < len(chunks):
                next_chunk = chunks[i + 1]
                
                # 检查是否可以合并（同一章节）
                if current.chapter_title == next_chunk.chapter_title:
                    merged_content = current.content + "\n\n" + next_chunk.content
                    
                    # 检查合并后是否超过最大长度
                    if len(merged_content) <= self.max_chunk_size:
                        merged_bbox = self._merge_bboxes([current.bbox, next_chunk.bbox])
                        current = TextChunk(
                            content=merged_content,
                            chunk_index=len(merged),
                            chapter_title=current.chapter_title,
                            page_start=current.page_start,
                            page_end=next_chunk.page_end,
                            bbox=merged_bbox,
                        )
                        i += 1  # 跳过下一个块
            
            merged.append(current)
            i += 1
        
        # 重新编号
        for idx, chunk in enumerate(merged):
            chunk.chunk_index = idx
        
        return merged


# 便捷函数
def chunk_texts(texts: List[Dict[str, Any]], 
                strategy: str = "semantic",
                chunk_size: int = 500) -> List[TextChunk]:
    """
    对文本进行分块的便捷函数
    
    Args:
        texts: 文本列表
        strategy: 分块策略
        chunk_size: 块大小
    
    Returns:
        分块结果
    """
    chunker = TextChunker(strategy=strategy, chunk_size=chunk_size)
    chunks = chunker.chunk(texts)
    return chunker.smart_merge(chunks)


# 测试代码
if __name__ == "__main__":
    # 测试数据
    test_texts = [
        {"content": "第一章 概述\n这是第一章的内容，介绍了基本概念。", "page": 1, "chapter_title": "第一章 概述"},
        {"content": "第一节 背景\n详细描述了项目背景。", "page": 1, "chapter_title": "第一章 概述"},
        {"content": "第二节 目标\n明确了项目目标。", "page": 2, "chapter_title": "第一章 概述"},
        {"content": "第二章 方法\n介绍了研究方法。", "page": 3, "chapter_title": "第二章 方法"},
        {"content": "第一节 实验设计\n详细说明了实验设计。", "page": 3, "chapter_title": "第二章 方法"},
    ]
    
    print("=== 语义分块 ===")
    chunker = TextChunker(strategy="semantic", chunk_size=100)
    chunks = chunker.chunk(test_texts)
    for chunk in chunks:
        print(f"[{chunk.chapter_title}] p{chunk.page_start}-{chunk.page_end}: {chunk.content[:50]}...")
    
    print("\n=== 固定长度分块 ===")
    chunker = TextChunker(strategy="fixed", chunk_size=100)
    chunks = chunker.chunk(test_texts)
    for chunk in chunks:
        print(f"[{chunk.chunk_index}]: {chunk.content[:50]}...")
