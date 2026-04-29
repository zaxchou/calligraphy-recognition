"""
MinerU 输出解析器
将 MinerU 云 API 的输出转换为 PdfContent 格式
"""

import os
import re
import logging
from typing import List, Optional, Dict, Any
from pathlib import Path

from .pdf_processor import (
    PdfContent,
    PdfMetadata,
    ExtractedText,
    ExtractedImage,
    ExtractedTable,
)

logger = logging.getLogger(__name__)


class MineruParser:
    """将 MinerU 输出转换为 PdfContent 格式"""
    
    # 图号正则
    _FIGURE_PATTERNS = [
        re.compile(r"图\s*([一二三四五六七八九十百千\d]+(?:[一二三四五六七八九十百千]+\d*)*)"),
        re.compile(r"Figure\s*(\d+)", re.IGNORECASE),
    ]
    
    # 章节标题模式
    _CHAPTER_PATTERNS = [
        re.compile(r"^第[一二三四五六七八九十\d]+章"),
        re.compile(r"^第[一二三四五六七八九十\d]+节"),
        re.compile(r"^\d+\.\d+"),
        re.compile(r"^[一二三四五六七八九十]+、"),
    ]
    
    def __init__(self):
        self._image_counter = 0
    
    def parse(
        self,
        content_list: List[Dict[str, Any]],
        images_dir: str,
        full_md: Optional[str] = None,
        pdf_path: Optional[str] = None,
    ) -> PdfContent:
        """将 MinerU 输出转换为 PdfContent
        
        Args:
            content_list: MinerU 的 content_list.json 内容
            images_dir: 图片目录路径
            full_md: 完整 Markdown 文本（可选）
            pdf_path: 原始 PDF 路径（用于提取文件名）
        
        Returns:
            PdfContent
        """
        self._image_counter = 0
        
        content = PdfContent()
        
        # 设置元数据
        content.metadata = self._extract_metadata(content_list, pdf_path)
        
        # 提取文本和图片
        current_chapter = None
        
        for item in content_list:
            item_type = item.get("type", "")
            page_idx = item.get("page_idx", 0)  # 0-based
            page_1based = page_idx + 1
            
            if item_type == "text":
                # 文本块
                text = item.get("text", "").strip()
                if not text or len(text) < 3:
                    continue
                
                # 检测章节标题
                is_chapter = self._is_chapter_title(text)
                if is_chapter:
                    current_chapter = text
                    continue
                
                # 检测图注 — 跳过
                if self._is_caption(text):
                    continue
                
                # 提取 bbox
                bbox = self._extract_bbox(item)
                
                extracted = ExtractedText(
                    content=text,
                    page=page_1based,
                    chapter_title=current_chapter,
                    bbox=bbox,
                    block_type="text",
                )
                content.texts.append(extracted)
            
            elif item_type == "image":
                # 图片
                img_path = item.get("img_path", "")
                if not img_path:
                    continue
                
                # 构建完整图片路径
                full_img_path = os.path.join(images_dir, os.path.basename(img_path))
                if not os.path.exists(full_img_path):
                    logger.warning(f"图片不存在: {full_img_path}")
                    continue
                
                # 读取图片数据
                try:
                    with open(full_img_path, "rb") as f:
                        image_data = f.read()
                except Exception as e:
                    logger.warning(f"读取图片失败: {e}")
                    continue
                
                # 生成文件名
                self._image_counter += 1
                file_name = f"page_{page_1based}_img_{self._image_counter}.png"
                
                # 提取 bbox
                bbox = self._extract_bbox(item)
                
                # 尝试从附近文本提取图号和图注
                figure_id, caption = self._find_nearby_caption(
                    content_list, item, page_idx
                )
                
                extracted = ExtractedImage(
                    image_data=image_data,
                    page=page_1based,
                    file_name=file_name,
                    bbox=bbox,
                    figure_id=figure_id,
                    caption=caption,
                    ext="png",
                )
                content.images.append(extracted)
            
            elif item_type == "title":
                # 标题 — 更新当前章节
                title = item.get("text", "").strip()
                if title:
                    current_chapter = title
            
            elif item_type == "table":
                # 表格
                table_text = item.get("text", "").strip()
                if not table_text or len(table_text) < 10:
                    continue
                
                # 提取 bbox
                bbox = self._extract_bbox(item)
                
                # 表格序号
                table_index = len(content.tables) + 1
                
                extracted = ExtractedTable(
                    content=table_text,
                    page=page_1based,
                    chapter_title=current_chapter,
                    bbox=bbox,
                    table_index=table_index,
                )
                content.tables.append(extracted)
        
        # 构建图号首次出现位置映射
        self._build_figure_first_page(content)
        
        # 提取文档大纲
        content.outline = self._extract_outline(content_list)
        
        # 存储 full_md
        if full_md:
            content.full_md = full_md
            
            # 如果 content_list 没有标题，尝试从 Markdown 中提取大纲
            if not content.outline:
                content.outline = self._extract_outline_from_markdown(full_md)
        
        logger.info(
            f"MinerU 解析完成: {content.metadata.total_pages}页, "
            f"{len(content.texts)}文本块, {len(content.images)}图片, "
            f"{len(content.tables)}表格, {len(content.figure_first_page)}个图号, "
            f"{len(content.outline)}个大纲项"
        )
        
        return content
    
    def _extract_metadata(
        self,
        content_list: List[Dict[str, Any]],
        pdf_path: Optional[str] = None,
    ) -> PdfMetadata:
        """提取元数据"""
        # 计算总页数
        pages = set()
        for item in content_list:
            if "page_idx" in item:
                pages.add(item["page_idx"])
        total_pages = max(pages) + 1 if pages else 0
        
        # 从文件名猜测标题（去掉 UUID 前缀）
        title = None
        if pdf_path:
            file_name = os.path.basename(pdf_path)
            # 去掉 UUID 前缀：{uuid}_{原始文件名} → {原始文件名}
            if '_' in file_name and len(file_name.split('_')[0]) == 36:
                # UUID 格式：8-4-4-4-12，长度 36
                parts = file_name.split('_', 1)
                if len(parts) == 2:
                    file_name = parts[1]
            title = os.path.splitext(file_name)[0]
        
        return PdfMetadata(
            title=title,
            total_pages=total_pages,
        )
    
    def _extract_bbox(self, item: Dict[str, Any]) -> Optional[Dict[str, float]]:
        """从 MinerU item 中提取 bbox"""
        bbox = item.get("bbox")
        if not bbox:
            return None
        
        # MinerU bbox 格式: [x0, y0, x1, y1]
        if isinstance(bbox, list) and len(bbox) == 4:
            return {
                "x0": bbox[0],
                "y0": bbox[1],
                "x1": bbox[2],
                "y1": bbox[3],
            }
        
        return None
    
    def _is_chapter_title(self, text: str) -> bool:
        """判断是否为章节标题"""
        for pattern in self._CHAPTER_PATTERNS:
            if pattern.match(text):
                return True
        return False
    
    def _is_caption(self, text: str) -> bool:
        """判断是否为图注/表注"""
        caption_patterns = [
            r"^图[一二三四五六七八九十百千\d]",
            r"^表[一二三四五六七八九十\d]+",
            r"^Figure\s*\d+",
            r"^Table\s*\d+",
        ]
        
        for pattern in caption_patterns:
            if re.match(pattern, text, re.IGNORECASE):
                return True
        
        return False
    
    def _is_figure_reference(self, text: str) -> bool:
        """判断文本是否为对图的引用（而非图注本身）"""
        if self._is_caption(text):
            return False
        
        ref_patterns = [
            r"如\s*图[一二三四五六七八九十百千\d]",
            r"参\s*见\s*图[一二三四五六七八九十百千\d]",
            r"见\s*图[一二三四五六七八九十百千\d]",
        ]
        for pattern in ref_patterns:
            if re.search(pattern, text):
                return True
        return False
    
    def _normalize_figure_id(self, raw: str) -> str:
        """标准化图号"""
        raw = raw.strip()
        raw = re.sub(r'\s+', '', raw)
        raw = raw.replace("圖", "图")
        return raw
    
    def _extract_figure_ids_from_text(self, text: str) -> List[str]:
        """从文本中提取所有图号"""
        found = []
        for pattern in self._FIGURE_PATTERNS:
            for m in pattern.finditer(text):
                fig_id = f"图{m.group(1)}"
                fig_id = self._normalize_figure_id(fig_id)
                if fig_id not in found:
                    found.append(fig_id)
        return found
    
    def _find_nearby_caption(
        self,
        content_list: List[Dict[str, Any]],
        image_item: Dict[str, Any],
        page_idx: int,
    ) -> tuple[Optional[str], Optional[str]]:
        """查找图片附近的图注
        
        Returns:
            (figure_id, caption) 元组
        """
        img_bbox = self._extract_bbox(image_item)
        if not img_bbox:
            return None, None
        
        # 在同页查找图注
        img_cy = (img_bbox["y0"] + img_bbox["y1"]) / 2
        best_caption = None
        best_dist = float("inf")
        
        for item in content_list:
            if item.get("page_idx") != page_idx:
                continue
            
            text = item.get("text", "").strip()
            if not text or not self._is_caption(text):
                continue
            
            cap_bbox = self._extract_bbox(item)
            if not cap_bbox:
                continue
            
            cap_cy = (cap_bbox["y0"] + cap_bbox["y1"]) / 2
            dist = abs(cap_cy - img_cy)
            
            if dist < best_dist:
                best_dist = dist
                best_caption = text
        
        # 假设页面高度约 800（MinerU 输出通常是归一化坐标）
        page_height = 800
        if best_caption and best_dist < page_height * 0.3:
            fig_ids = self._extract_figure_ids_from_text(best_caption)
            figure_id = fig_ids[0] if fig_ids else None
            return figure_id, best_caption
        
        return None, None
    
    def _extract_outline(self, content_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """提取文档大纲（从 title 类型的 item）"""
        outline = []
        for item in content_list:
            if item.get("type") == "title":
                title = item.get("text", "").strip()
                if title:
                    page_idx = item.get("page_idx", 0)
                    outline.append({
                        "title": title,
                        "page": page_idx + 1,  # 转换为 1-based
                        "level": self._detect_heading_level(title),
                    })
        return outline
    
    def _detect_heading_level(self, title: str) -> int:
        """检测标题级别（1=章, 2=节, 3=小节）"""
        if re.match(r'^第[一二三四五六七八九十\d]+章', title):
            return 1
        elif re.match(r'^第[一二三四五六七八九十\d]+节', title):
            return 2
        elif re.match(r'^\d+\.\d+', title):
            return 2
        elif re.match(r'^[一二三四五六七八九十]+、', title):
            return 2
        else:
            return 3
    
    def _extract_outline_from_markdown(self, markdown: str) -> List[Dict[str, Any]]:
        """从 Markdown 内容中提取大纲（当 MinerU content_list 没有标题时使用）
        
        改进：尝试从标题文本中解析页码（如 "第一章...009" → page=9），
        并根据章节页码估算无页码标题的位置。
        """
        outline = []
        lines = markdown.split('\n')
        
        # 页码提取正则：匹配省略号/空格后的数字（1-3位）
        page_pattern = re.compile(r'[…\s]+(\d{1,3})$')
        
        for line in lines:
            line = line.strip()
            # 匹配 Markdown 标题：# 标题, ## 标题, ### 标题
            match = re.match(r'^(#{1,3})\s+(.+)$', line)
            if match:
                level = len(match.group(1))  # # = 1, ## = 2, ### = 3
                title = match.group(2).strip()
                if title and len(title) > 1:  # 过滤掉太短的标题
                    # 尝试从标题中提取页码
                    page = 0
                    page_match = page_pattern.search(title)
                    if page_match:
                        page = int(page_match.group(1))
                    
                    outline.append({
                        "title": title,
                        "page": page,
                        "level": level,
                    })
        
        # 估算无页码标题的位置：根据前后有页码的标题进行线性插值
        self._estimate_missing_pages(outline)
        
        return outline
    
    def _estimate_missing_pages(self, outline: List[Dict[str, Any]]):
        """估算没有页码的标题位置
        
        根据前后有页码的标题进行线性插值。
        """
        if not outline:
            return
        
        # 找到所有有页码的项
        indexed_items = [(i, item) for i, item in enumerate(outline) if item.get("page", 0) > 0]
        
        if len(indexed_items) < 2:
            # 不足两个有页码的项，无法插值
            return
        
        # 对每两个有页码的项之间的无页码项进行插值
        for idx in range(len(indexed_items) - 1):
            i1, item1 = indexed_items[idx]
            i2, item2 = indexed_items[idx + 1]
            
            page1 = item1["page"]
            page2 = item2["page"]
            
            if page1 >= page2:
                continue  # 无效的页码范围
            
            # 计算中间项的数量
            middle_count = i2 - i1 - 1
            if middle_count <= 0:
                continue
            
            # 线性插值
            for j in range(i1 + 1, i2):
                if outline[j].get("page", 0) == 0:
                    # 根据位置比例估算页码
                    ratio = (j - i1) / (i2 - i1)
                    estimated_page = int(page1 + ratio * (page2 - page1))
                    outline[j]["page"] = max(1, estimated_page)
    
    def _build_figure_first_page(self, content: PdfContent):
        """构建图号首次出现位置映射"""
        for text in content.texts:
            fig_ids = self._extract_figure_ids_from_text(text.content)
            for fig_id in fig_ids:
                if fig_id not in content.figure_first_page:
                    content.figure_first_page[fig_id] = text.page
        
        for img in content.images:
            if img.figure_id and img.figure_id not in content.figure_first_page:
                content.figure_first_page[img.figure_id] = img.page


def parse_mineru_result(
    content_list: List[Dict[str, Any]],
    images_dir: str,
    full_md: Optional[str] = None,
    pdf_path: Optional[str] = None,
) -> PdfContent:
    """便捷函数：将 MinerU 输出转换为 PdfContent
    
    Args:
        content_list: MinerU 的 content_list.json 内容
        images_dir: 图片目录路径
        full_md: 完整 Markdown 文本（可选）
        pdf_path: 原始 PDF 路径（可选）
    
    Returns:
        PdfContent
    """
    parser = MineruParser()
    return parser.parse(content_list, images_dir, full_md, pdf_path)
