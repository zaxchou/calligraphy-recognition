"""
PDF 解析模块
支持文本提取、图像提取、元数据解析
"""

import os
import re
import hashlib
import fitz  # PyMuPDF
from PIL import Image
from io import BytesIO
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ExtractedText:
    """提取的文本块"""
    content: str
    page: int
    chapter_title: Optional[str] = None
    bbox: Optional[Dict[str, float]] = None
    block_type: str = "text"  # text, title, caption
    
    def compute_hash(self) -> str:
        """计算内容哈希"""
        return hashlib.md5(self.content.encode("utf-8")).hexdigest()


@dataclass
class ExtractedImage:
    """提取的图像"""
    image_data: bytes
    page: int
    file_name: str
    bbox: Optional[Dict[str, float]] = None
    figure_id: Optional[str] = None
    caption: Optional[str] = None  # 图注文本（如"图三七 清代 朱耷《菊花》"）
    ext: str = "png"
    
    def compute_hash(self) -> str:
        """计算图像感知哈希（简化版）"""
        return hashlib.md5(self.image_data).hexdigest()[:16]
    
    def save(self, output_dir: str) -> str:
        """保存图像到指定目录"""
        os.makedirs(output_dir, exist_ok=True)
        file_path = os.path.join(output_dir, self.file_name)
        
        # 转换并保存
        img = Image.open(BytesIO(self.image_data))
        if img.mode in ('RGBA', 'P'):
            img = img.convert('RGB')
        img.save(file_path, 'PNG')
        
        return file_path


@dataclass
class PdfMetadata:
    """PDF 元数据"""
    title: Optional[str] = None
    author: Optional[str] = None
    total_pages: int = 0
    subject: Optional[str] = None
    keywords: Optional[str] = None


@dataclass
class ExtractedTable:
    """提取的表格"""
    content: str  # 表格内容（Markdown 或纯文本格式）
    page: int
    chapter_title: Optional[str] = None
    bbox: Optional[Dict[str, float]] = None
    table_index: int = 0  # 表格序号
    
    def compute_hash(self) -> str:
        """计算内容哈希"""
        return hashlib.md5(self.content.encode("utf-8")).hexdigest()


@dataclass
class PdfContent:
    """PDF 内容容器"""
    metadata: PdfMetadata = field(default_factory=PdfMetadata)
    texts: List[ExtractedText] = field(default_factory=list)
    images: List[ExtractedImage] = field(default_factory=list)
    tables: List[ExtractedTable] = field(default_factory=list)  # 新增表格列表
    # 记录每个图号首次出现的页码，用于后续关联时排除重复引用
    figure_first_page: Dict[str, int] = field(default_factory=dict)
    full_md: Optional[str] = None  # 完整 Markdown 内容
    outline: List[Dict[str, Any]] = field(default_factory=list)  # 文档大纲
    
    def get_chapters(self) -> List[str]:
        """获取所有章节标题"""
        chapters = set()
        for text in self.texts:
            if text.chapter_title:
                chapters.add(text.chapter_title)
        return sorted(list(chapters))


# 图号正则：匹配"图X"各种格式
_FIGURE_PATTERNS = [
    re.compile(r"图\s*([一二三四五六七八九十百千\d]+(?:[一二三四五六七八九十百千]+\d*)*)"),
    re.compile(r"Figure\s*(\d+)", re.IGNORECASE),
]


class PdfProcessor:
    """PDF 处理器"""
    
    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path
        self.doc = None
        
    def __enter__(self):
        self.doc = fitz.open(self.pdf_path)
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.doc:
            self.doc.close()
            self.doc = None
    
    def extract_metadata(self) -> PdfMetadata:
        """提取 PDF 元数据"""
        meta = self.doc.metadata
        return PdfMetadata(
            title=meta.get("title") or self._guess_title(),
            author=meta.get("author"),
            total_pages=len(self.doc),
            subject=meta.get("subject"),
            keywords=meta.get("keywords"),
        )
    
    def _guess_title(self) -> Optional[str]:
        """从文件名或第一页内容猜测标题"""
        # 从文件名提取
        file_name = os.path.basename(self.pdf_path)
        name_without_ext = os.path.splitext(file_name)[0]
        
        # 尝试从第一页提取大标题
        if len(self.doc) > 0:
            first_page = self.doc[0]
            blocks = first_page.get_text("blocks")
            for block in blocks[:3]:  # 只看前3个块
                text = block[4].strip()
                if len(text) > 5 and len(text) < 100:
                    # 可能是标题
                    return text
        
        return name_without_ext
    
    def _normalize_figure_id(self, raw: str) -> str:
        """标准化图号，统一为 '图X' 格式"""
        raw = raw.strip()
        # 去掉空格
        raw = re.sub(r'\s+', '', raw)
        # "圖" -> "图"
        raw = raw.replace("圖", "图")
        return raw
    
    def _extract_figure_ids_from_text(self, text: str) -> List[str]:
        """从文本中提取所有图号"""
        found = []
        for pattern in _FIGURE_PATTERNS:
            for m in pattern.finditer(text):
                fig_id = f"图{m.group(1)}" if pattern.pattern.startswith("Fig") else f"图{m.group(1)}"
                fig_id = self._normalize_figure_id(fig_id)
                if fig_id not in found:
                    found.append(fig_id)
        return found
    
    def _is_chapter_title(self, text: str, y_pos: float, page_height: float) -> bool:
        """判断是否为章节标题（启发式）"""
        # 常见章节模式
        chapter_patterns = [
            r"^第[一二三四五六七八九十\d]+章",
            r"^第[一二三四五六七八九十\d]+节",
            r"^\d+\.\d+",
            r"^[一二三四五六七八九十]+、",
        ]
        
        for pattern in chapter_patterns:
            if re.match(pattern, text):
                return True
        
        # 位置在页面顶部且较短
        if y_pos < page_height * 0.2 and 5 < len(text) < 50:
            # 检查是否包含"章"、"节"等关键词
            if any(kw in text for kw in ["章", "节", "部分", "单元"]):
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
        """判断文本是否为对图的引用（而非图注本身）
        
        图注: "图三七 清代 朱耷《菊花》" — 以"图X"开头
        引用: "如图三所示" — "图X"出现在句子中间
        """
        # 如果以"图X"开头，是图注
        if self._is_caption(text):
            return False
        
        # 检查是否包含"如图X""参见图X""见图X"等引用模式
        ref_patterns = [
            r"如\s*图[一二三四五六七八九十百千\d]",
            r"参\s*见\s*图[一二三四五六七八九十百千\d]",
            r"见\s*图[一二三四五六七八九十百千\d]",
            r"以\s*图[一二三四五六七八九十百千\d]",
            r"从\s*图[一二三四五六七八九十百千\d]",
            r"对\s*比\s*图[一二三四五六七八九十百千\d]",
            r"按\s*照\s*图[一二三四五六七八九十百千\d]",
        ]
        for pattern in ref_patterns:
            if re.search(pattern, text):
                return True
        return False
    
    def _get_image_bbox(self, page, xref: int) -> Optional[Dict[str, float]]:
        """获取图片在页面上的真实边界框"""
        try:
            rects = page.get_image_rects(xref)
            if rects:
                r = rects[0]  # 取第一个（最大的）矩形
                return {"x0": r.x0, "y0": r.y0, "x1": r.x1, "y1": r.y1}
        except Exception:
            pass
        return None
    
    def extract_texts(self, start_page: int = 0, end_page: Optional[int] = None) -> List[ExtractedText]:
        """
        提取文本内容
        
        Args:
            start_page: 起始页码（0-based）
            end_page: 结束页码（不包含）
        
        Returns:
            提取的文本块列表
        """
        texts = []
        end_page = end_page or len(self.doc)
        current_chapter = None
        
        for page_num in range(start_page, min(end_page, len(self.doc))):
            page = self.doc[page_num]
            
            # 获取文本块
            blocks = page.get_text("blocks")
            
            for block in blocks:
                x0, y0, x1, y1, text, block_no, block_type = block
                text = text.strip()
                
                if not text or len(text) < 3:
                    continue
                
                # 检测章节标题（启发式规则）
                is_chapter = self._is_chapter_title(text, y0, page.rect.height)
                if is_chapter:
                    current_chapter = text
                    # 不将章节标题作为正文内容存储
                    continue

                # 检测图注 — 跳过，不作为正文内容
                if self._is_caption(text):
                    continue

                extracted = ExtractedText(
                    content=text,
                    page=page_num + 1,  # 1-based page number
                    chapter_title=current_chapter,
                    bbox={"x0": x0, "y0": y0, "x1": x1, "y1": y1},
                    block_type="text",
                )
                texts.append(extracted)
        
        return texts
    
    def extract_images(self, start_page: int = 0, end_page: Optional[int] = None,
                       min_size: int = 100) -> List[ExtractedImage]:
        """
        提取图像
        
        Args:
            start_page: 起始页码
            end_page: 结束页码
            min_size: 最小图像尺寸（像素）
        
        Returns:
            提取的图像列表
        """
        import logging
        logger = logging.getLogger(__name__)
        
        images = []
        end_page = end_page or len(self.doc)
        image_counter = 0
        
        for page_num in range(start_page, min(end_page, len(self.doc))):
            page = self.doc[page_num]
            page_1based = page_num + 1
            
            # --- 步骤1: 收集本页所有文本块的 bbox 信息 ---
            text_blocks = page.get_text("blocks")
            page_text_blocks = []
            for block in text_blocks:
                bx0, by0, bx1, by1, btext, _, _ = block
                btext = btext.strip()
                if not btext or len(btext) < 3:
                    continue
                page_text_blocks.append({
                    "x0": bx0, "y0": by0, "x1": bx1, "y1": by1,
                    "text": btext,
                    "is_caption": self._is_caption(btext),
                })
            
            # --- 步骤2: 收集本页所有图注 ---
            page_captions = []
            for tb in page_text_blocks:
                if tb["is_caption"]:
                    page_captions.append(tb)
            
            # --- 步骤3: 提取图片，带真实 bbox ---
            image_list = page.get_images(full=True)
            
            # 记录已使用的 xref，避免同一图片重复处理
            seen_xrefs = set()
            
            for img_index, img in enumerate(image_list):
                xref = img[0]
                if xref in seen_xrefs:
                    continue
                seen_xrefs.add(xref)
                
                base_image = self.doc.extract_image(xref)
                image_bytes = base_image["image"]
                
                # 检查图像尺寸
                try:
                    pil_img = Image.open(BytesIO(image_bytes))
                    width, height = pil_img.size
                    
                    if width < min_size or height < min_size:
                        continue
                    
                    # 生成文件名
                    image_counter += 1
                    file_name = f"page_{page_1based}_img_{image_counter}.png"
                    
                    # 获取真实 bbox
                    bbox = self._get_image_bbox(page, xref)
                    
                    # --- 步骤4: 空间匹配图注 ---
                    caption = None
                    figure_id = None
                    
                    if page_captions and bbox:
                        img_cy = (bbox["y0"] + bbox["y1"]) / 2  # 图片中心 y 坐标
                        best_caption = None
                        best_dist = float("inf")
                        
                        for cap in page_captions:
                            cap_cy = (cap["y0"] + cap["y1"]) / 2
                            dist = abs(cap_cy - img_cy)
                            # 图注应在图片附近（同页 y 坐标差距不超过页面高度的 30%）
                            if dist < best_dist:
                                best_dist = dist
                                best_caption = cap
                        
                        # 页面高度
                        page_height = page.rect.height
                        if best_caption and best_dist < page_height * 0.3:
                            caption = best_caption["text"]
                            # 从图注文本提取图号
                            fig_ids = self._extract_figure_ids_from_text(caption)
                            if fig_ids:
                                figure_id = fig_ids[0]  # 取第一个图号
                    
                    # 如果没有通过图注匹配到 figure_id，保留旧逻辑作为 fallback
                    if not figure_id:
                        figure_id = self._extract_figure_id(page, img_index)
                    
                    extracted = ExtractedImage(
                        image_data=image_bytes,
                        page=page_1based,
                        file_name=file_name,
                        bbox=bbox,
                        figure_id=figure_id,
                        caption=caption,
                        ext="png",
                    )
                    images.append(extracted)
                    
                except Exception as e:
                    logger.warning(f"处理图像失败 page {page_1based}: {e}")
                    continue
        
        return images
    
    def _extract_figure_id(self, page, img_index: int) -> Optional[str]:
        """从页面文本中提取图号（fallback，当无法通过 bbox 空间匹配时使用）"""
        text = page.get_text()
        
        # 查找图号模式
        patterns = [
            r"图\s*([一二三四五六七八九十\d]+)",
            r"Figure\s*(\d+)",
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text)
            if matches and img_index < len(matches):
                return f"图{matches[img_index]}"
        
        return None
    
    def process_full(self, output_dir: Optional[str] = None) -> PdfContent:
        """
        完整处理 PDF
        
        Args:
            output_dir: 图像输出目录
        
        Returns:
            PdfContent 包含所有提取的内容
        """
        import logging
        logger = logging.getLogger(__name__)
        
        content = PdfContent()
        
        # 提取元数据
        content.metadata = self.extract_metadata()
        
        # 提取文本
        content.texts = self.extract_texts()
        
        # 提取图像（含 bbox 和 caption）
        content.images = self.extract_images()
        
        # --- 构建图号首次出现位置映射 ---
        # 扫描所有页面的文本，记录每个图号首次出现的页码
        # 这样后续关联时可以区分"图注（首次定义）"和"引用（后续提到）"
        for page_num in range(len(self.doc)):
            page = self.doc[page_num]
            page_text = page.get_text()
            fig_ids = self._extract_figure_ids_from_text(page_text)
            for fig_id in fig_ids:
                if fig_id not in content.figure_first_page:
                    content.figure_first_page[fig_id] = page_num + 1  # 1-based
        
        logger.info(
            f"PDF处理完成: {content.metadata.total_pages}页, "
            f"{len(content.texts)}文本块, {len(content.images)}图片, "
            f"{len(content.figure_first_page)}个图号"
        )
        
        # 保存图像（如果指定了输出目录）
        if output_dir:
            for img in content.images:
                img.save(output_dir)
        
        return content


def process_pdf_file(pdf_path: str, output_dir: Optional[str] = None) -> PdfContent:
    """
    处理 PDF 文件的便捷函数
    
    Args:
        pdf_path: PDF 文件路径
        output_dir: 图像输出目录
    
    Returns:
        PdfContent
    """
    with PdfProcessor(pdf_path) as processor:
        return processor.process_full(output_dir)


# 测试代码
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        pdf_file = sys.argv[1]
        output = os.path.join(os.path.dirname(pdf_file), "extracted")
        
        print(f"处理 PDF: {pdf_file}")
        content = process_pdf_file(pdf_file, output)
        
        print(f"\n元数据:")
        print(f"  标题: {content.metadata.title}")
        print(f"  作者: {content.metadata.author}")
        print(f"  页数: {content.metadata.total_pages}")
        
        print(f"\n提取结果:")
        print(f"  文本块: {len(content.texts)}")
        print(f"  图像: {len(content.images)}")
        print(f"  章节: {content.get_chapters()[:5]}")  # 前5个章节
        
        # 打印图号首次出现位置
        if content.figure_first_page:
            print(f"\n图号首次出现位置 (共{len(content.figure_first_page)}个):")
            for fig_id, page in sorted(content.figure_first_page.items(), key=lambda x: x[1])[:10]:
                print(f"  {fig_id} -> 第{page}页")
        
        # 打印图片的 bbox 和 caption
        for img in content.images[:5]:
            print(f"\n图片: {img.file_name}")
            print(f"  页码: {img.page}")
            print(f"  bbox: {img.bbox}")
            print(f"  figure_id: {img.figure_id}")
            print(f"  caption: {img.caption}")
