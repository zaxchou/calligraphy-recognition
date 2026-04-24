#!/usr/bin/env python3
"""
图注匹配器 - 基于页面邻近度和 OCR 的图注提取

功能：
1. 页面邻近度匹配：根据图和图注的页面位置进行匹配
2. OCR 图注提取：从图片下方区域提取图注文字
"""

import re
import json
import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from collections import defaultdict
import numpy as np

# 可选的 OCR 库，如果没有安装则使用备用方案
try:
    import easyocr
    EASYOCR_AVAILABLE = True
except ImportError:
    EASYOCR_AVAILABLE = False

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class FigureInfo:
    """图片信息"""
    figure_id: str
    page: int
    filename: str
    image_path: str
    artist: Optional[str] = None
    artwork_title: Optional[str] = None
    figure_type: str = "unknown"
    caption: Optional[str] = None


@dataclass
class TextCaption:
    """文本中的图注"""
    figure_num: str  # 阿拉伯数字，如 "11"
    era: str
    artist: str
    title: str
    page: int
    full_text: str


@dataclass
class MatchResult:
    """匹配结果"""
    figure_id: str
    caption: Optional[TextCaption]
    confidence: float  # 0-1
    distance: int  # 页面距离
    method: str  # "proximity" | "ocr" | "none"


class FigureCaptionMatcher:
    """图注匹配器"""

    def __init__(self):
        self._ocr_reader = None
        self._captions_cache: List[TextCaption] = []

    def _get_ocr_reader(self):
        """懒加载 OCR 阅读器"""
        if self._ocr_reader is None and EASYOCR_AVAILABLE:
            logger.info("初始化 EasyOCR (中文+英文)...")
            self._ocr_reader = easyocr.Reader(['ch_sim', 'en'], gpu=False)
        return self._ocr_reader

    def extract_captions_from_text(self, text: str) -> List[TextCaption]:
        """从教程文本中提取图注及其页码"""
        captions = []
        current_page = 0

        lines = text.split('\n')
        for line in lines:
            line = line.strip()

            # 检测页码标记
            page_match = re.match(r'===== PAGE (\d+) =====', line)
            if page_match:
                current_page = int(page_match.group(1))
                continue

            # 匹配图注格式：图 11  清代  朱耷  《石榴》
            m = re.match(
                r'图\s*(\d+)\s+'  # 图号
                r'([^\s《]+)\s+'  # 朝代
                r'([^\s《]+)\s*'  # 作者
                r'《(.+?)》',      # 作品名
                line
            )

            if m:
                captions.append(TextCaption(
                    figure_num=m.group(1),
                    era=m.group(2).strip(),
                    artist=m.group(3).strip(),
                    title=m.group(4).strip(),
                    page=current_page,
                    full_text=line[:150]
                ))

        self._captions_cache = captions
        return captions

    def chinese_to_arabic(self, zh_num: str) -> Optional[int]:
        """中文数字转阿拉伯数字"""
        zh_to_val = {
            '一': 1, '二': 2, '三': 3, '四': 4, '五': 5,
            '六': 6, '七': 7, '八': 8, '九': 9, '十': 10,
            '〇': 0, '零': 0
        }

        if not zh_num:
            return None

        if zh_num.startswith('图'):
            zh_num = zh_num[1:]

        if zh_num in zh_to_val:
            return zh_to_val[zh_num]

        # 处理组合数字
        total = 0
        temp = 0

        for char in zh_num:
            if char in zh_to_val:
                val = zh_to_val[char]
                if val == 10:
                    if temp == 0:
                        temp = 1
                    total += temp * 10
                    temp = 0
                else:
                    temp = val

        total += temp
        return total if total > 0 else None

    def match_by_proximity(
        self,
        figure: FigureInfo,
        captions: List[TextCaption],
        max_distance: int = 5
    ) -> MatchResult:
        """
        基于页面邻近度匹配图注

        Args:
            figure: 图片信息
            captions: 所有文本图注
            max_distance: 最大允许页面距离

        Returns:
            MatchResult: 匹配结果
        """
        arabic_num = self.chinese_to_arabic(figure.figure_id)
        if arabic_num is None:
            return MatchResult(
                figure_id=figure.figure_id,
                caption=None,
                confidence=0.0,
                distance=-1,
                method="none"
            )

        arabic_str = str(arabic_num)
        best_caption = None
        best_distance = float('inf')

        # 查找相同图号的图注
        for caption in captions:
            if caption.figure_num == arabic_str:
                distance = abs(figure.page - caption.page)
                if distance < best_distance and distance <= max_distance:
                    best_distance = distance
                    best_caption = caption

        if best_caption is None:
            return MatchResult(
                figure_id=figure.figure_id,
                caption=None,
                confidence=0.0,
                distance=-1,
                method="none"
            )

        # 计算置信度
        if best_distance <= 2:
            confidence = 0.9 + (2 - best_distance) * 0.05  # 0.9-1.0
        elif best_distance <= 5:
            confidence = 0.6 + (5 - best_distance) * 0.1  # 0.6-0.8
        elif best_distance <= 10:
            confidence = 0.3 + (10 - best_distance) * 0.06  # 0.3-0.5
        else:
            confidence = 0.1

        return MatchResult(
            figure_id=figure.figure_id,
            caption=best_caption,
            confidence=confidence,
            distance=best_distance,
            method="proximity"
        )

    def extract_caption_by_ocr(self, image_path: str) -> Optional[str]:
        """
        使用 OCR 从图片下方提取图注

        Args:
            image_path: 图片路径

        Returns:
            提取的图注文字，如果失败则返回 None
        """
        if not EASYOCR_AVAILABLE or not CV2_AVAILABLE:
            logger.warning("OCR 不可用 (EasyOCR=%s, CV2=%s)", EASYOCR_AVAILABLE, CV2_AVAILABLE)
            return None

        try:
            # 读取图片
            img = cv2.imread(image_path)
            if img is None:
                logger.warning("无法读取图片: %s", image_path)
                return None

            h, w = img.shape[:2]

            # 提取下方 20% 区域（通常是图注位置）
            bottom_region = img[int(h * 0.8):, :]

            # OCR 识别
            reader = self._get_ocr_reader()
            results = reader.readtext(bottom_region)

            # 合并识别结果
            texts = [r[1] for r in results]
            full_text = ' '.join(texts)

            # 提取图注模式
            caption_match = re.search(
                r'图\s*\d+\s+[^\s《]+\s+[^\s《]+\s+《.+?》',
                full_text
            )

            if caption_match:
                return caption_match.group(0)

            # 如果没有完整图注，返回识别到的所有文字
            return full_text if full_text else None

        except Exception as e:
            logger.error("OCR 提取失败: %s", e)
            return None

    def match_with_ocr_fallback(
        self,
        figure: FigureInfo,
        captions: List[TextCaption],
        use_ocr: bool = True
    ) -> MatchResult:
        """
        先尝试页面邻近度匹配，失败时使用 OCR

        Args:
            figure: 图片信息
            captions: 所有文本图注
            use_ocr: 是否使用 OCR 作为备用

        Returns:
            MatchResult: 匹配结果
        """
        # 先尝试页面邻近度匹配
        result = self.match_by_proximity(figure, captions)

        if result.confidence >= 0.6:
            return result

        # 如果邻近度匹配失败且允许 OCR
        if use_ocr and result.confidence < 0.3:
            ocr_text = self.extract_caption_by_ocr(figure.image_path)

            if ocr_text:
                # 尝试从 OCR 文本解析图注
                m = re.match(
                    r'图\s*(\d+)\s+([^\s《]+)\s+([^\s《]+)\s+《(.+?)》',
                    ocr_text
                )

                if m:
                    ocr_caption = TextCaption(
                        figure_num=m.group(1),
                        era=m.group(2).strip(),
                        artist=m.group(3).strip(),
                        title=m.group(4).strip(),
                        page=figure.page,  # 使用图片所在页
                        full_text=ocr_text
                    )

                    return MatchResult(
                        figure_id=figure.figure_id,
                        caption=ocr_caption,
                        confidence=0.7,  # OCR 结果置信度中等
                        distance=0,
                        method="ocr"
                    )

        return result

    def batch_match(
        self,
        figures: List[FigureInfo],
        text_content: Optional[str] = None,
        use_ocr: bool = True,
        min_confidence: float = 0.6
    ) -> Dict[str, MatchResult]:
        """
        批量匹配图注

        Args:
            figures: 图片列表
            text_content: 教程文本内容，如果为 None 则使用缓存的 captions
            use_ocr: 是否使用 OCR
            min_confidence: 最小置信度阈值

        Returns:
            匹配结果字典 {figure_id: MatchResult}
        """
        # 获取图注
        if text_content:
            captions = self.extract_captions_from_text(text_content)
        else:
            captions = self._captions_cache

        results = {}
        for figure in figures:
            result = self.match_with_ocr_fallback(figure, captions, use_ocr)

            # 只保留高置信度的匹配
            if result.confidence >= min_confidence:
                results[figure.figure_id] = result

        return results

    def update_metadata(
        self,
        metadata_path: str,
        matches: Dict[str, MatchResult],
        output_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        更新 figure_metadata.json

        Args:
            metadata_path: 原 metadata 文件路径
            matches: 匹配结果字典
            output_path: 输出路径，如果为 None 则覆盖原文件

        Returns:
            更新后的 metadata 字典
        """
        with open(metadata_path, 'r', encoding='utf-8') as f:
            metadata = json.load(f)

        updated_count = 0

        for figure_id, match in matches.items():
            if figure_id not in metadata:
                continue

            meta = metadata[figure_id]
            caption = match.caption

            if caption is None:
                continue

            # 更新字段
            if not meta.get('artist') and caption.artist:
                meta['artist'] = caption.artist
                updated_count += 1

            if not meta.get('artwork_title') and caption.title:
                meta['artwork_title'] = caption.title

            if not meta.get('era') and caption.era:
                meta['era'] = caption.era

            if match.method == "ocr":
                meta['caption_source'] = 'ocr'
            else:
                meta['caption_source'] = f'text_page_{caption.page}'

            meta['caption_confidence'] = match.confidence

            # 如果原来是 unknown，改为 artwork
            if meta.get('figure_type') == 'unknown' and caption.artist:
                meta['figure_type'] = 'artwork'

        # 保存
        out_path = output_path or metadata_path
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

        logger.info("更新了 %d 个图的元数据", updated_count)
        return metadata


# 便捷函数
def fix_figure_metadata(
    metadata_path: str = "backend/data/knowledge/figure_metadata.json",
    tutorial_path: str = "bird_flower_tutorial.txt",
    use_ocr: bool = False,
    min_confidence: float = 0.6
) -> Dict[str, MatchResult]:
    """
    修复 figure_metadata.json 的便捷函数

    Args:
        metadata_path: metadata 文件路径
        tutorial_path: 教程文本路径
        use_ocr: 是否使用 OCR
        min_confidence: 最小置信度

    Returns:
        匹配结果字典
    """
    matcher = FigureCaptionMatcher()

    # 加载 metadata
    with open(metadata_path, 'r', encoding='utf-8') as f:
        metadata = json.load(f)

    figures = []
    for fig_id, meta in metadata.items():
        figures.append(FigureInfo(
            figure_id=fig_id,
            page=meta.get('page', 0),
            filename=meta.get('filename', ''),
            image_path=meta.get('image_path', ''),
            artist=meta.get('artist'),
            artwork_title=meta.get('artwork_title'),
            figure_type=meta.get('figure_type', 'unknown')
        ))

    # 加载教程文本
    with open(tutorial_path, 'r', encoding='utf-8') as f:
        text = f.read()

    # 批量匹配
    results = matcher.batch_match(figures, text, use_ocr, min_confidence)

    # 更新 metadata
    matcher.update_metadata(metadata_path, results)

    return results


if __name__ == "__main__":
    # 测试
    logging.basicConfig(level=logging.INFO)

    results = fix_figure_metadata(use_ocr=False, min_confidence=0.6)

    print(f"\n匹配完成，共修复 {len(results)} 个图")
    for fig_id, result in list(results.items())[:5]:
        print(f"\n{fig_id}:")
        print(f"  方法: {result.method}")
        print(f"  置信度: {result.confidence:.2f}")
        if result.caption:
            print(f"  匹配: {result.caption.era} {result.caption.artist}《{result.caption.title}》")
