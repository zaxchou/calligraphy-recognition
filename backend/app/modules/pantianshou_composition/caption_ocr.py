#!/usr/bin/env python3
"""
OCR 图注提取模块

从图片下方区域提取图注文字，支持：
1. EasyOCR - 主要 OCR 引擎
2. PaddleOCR - 备选（中文效果更好）
3. Tesseract - 备选
"""

import re
import logging
from typing import Optional, List, Tuple
from dataclasses import dataclass
import numpy as np

logger = logging.getLogger(__name__)

# 尝试导入 OCR 库
OCR_ENGINES = {}

try:
    import easyocr
    OCR_ENGINES['easyocr'] = True
except ImportError:
    OCR_ENGINES['easyocr'] = False

try:
    from paddleocr import PaddleOCR
    OCR_ENGINES['paddleocr'] = True
except ImportError:
    OCR_ENGINES['paddleocr'] = False

try:
    import pytesseract
    OCR_ENGINES['tesseract'] = False  # 默认禁用，需要额外配置
except ImportError:
    OCR_ENGINES['tesseract'] = False

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False


@dataclass
class OCRCaption:
    """OCR 提取的图注"""
    text: str
    confidence: float
    engine: str
    region: str  # "bottom" | "full"


class CaptionOCR:
    """图注 OCR 提取器"""

    # 图注匹配正则表达式
    CAPTION_PATTERNS = [
        # 标准格式：图 11  清代  朱耷  《石榴》
        r'图\s*(\d+)\s+([^\s《]+)\s+([^\s《]+)\s+《(.+?)》',
        # 紧凑格式：图11清代朱耷《石榴》
        r'图(\d+)([^\d《]+)《(.+?)》',
        # 中文数字：图十一 清代 朱耷 《石榴》
        r'(图[一二三四五六七八九十〇零]+)\s+([^\s《]+)\s+([^\s《]+)\s+《(.+?)》',
    ]

    def __init__(self, engine: str = "auto", gpu: bool = False):
        """
        初始化 OCR 引擎

        Args:
            engine: OCR 引擎选择 ("auto", "easyocr", "paddleocr", "tesseract")
            gpu: 是否使用 GPU
        """
        self.engine_name = engine
        self.gpu = gpu
        self._ocr_engine = None

        if engine == "auto":
            # 自动选择最佳引擎
            if OCR_ENGINES.get('paddleocr'):
                self.engine_name = "paddleocr"
            elif OCR_ENGINES.get('easyocr'):
                self.engine_name = "easyocr"
            else:
                raise RuntimeError("没有可用的 OCR 引擎，请安装 easyocr 或 paddleocr")

        if not OCR_ENGINES.get(self.engine_name):
            raise RuntimeError(f"OCR 引擎 {self.engine_name} 不可用")

        logger.info(f"使用 OCR 引擎: {self.engine_name}")

    def _init_engine(self):
        """懒加载 OCR 引擎"""
        if self._ocr_engine is not None:
            return self._ocr_engine

        if self.engine_name == "easyocr":
            self._ocr_engine = easyocr.Reader(
                ['ch_sim', 'en'],
                gpu=self.gpu,
                verbose=False
            )
        elif self.engine_name == "paddleocr":
            self._ocr_engine = PaddleOCR(
                use_angle_cls=True,
                lang='ch',
                show_log=False,
                use_gpu=self.gpu
            )

        return self._ocr_engine

    def _extract_bottom_region(
        self,
        image: np.ndarray,
        ratio: float = 0.25
    ) -> np.ndarray:
        """
        提取图片下方区域

        Args:
            image: 输入图片 (BGR 格式)
            ratio: 提取下方区域的比例 (0-1)

        Returns:
            下方区域图片
        """
        h, w = image.shape[:2]
        bottom_h = int(h * ratio)
        return image[h - bottom_h:h, :]

    def _recognize_easyocr(self, image: np.ndarray) -> List[Tuple[str, float]]:
        """使用 EasyOCR 识别"""
        engine = self._init_engine()
        results = engine.readtext(image)
        return [(r[1], r[2]) for r in results]  # (text, confidence)

    def _recognize_paddleocr(self, image: np.ndarray) -> List[Tuple[str, float]]:
        """使用 PaddleOCR 识别"""
        engine = self._init_engine()
        result = engine.ocr(image, cls=True)

        texts = []
        if result and result[0]:
            for line in result[0]:
                if line:
                    text = line[1][0]
                    conf = line[1][1]
                    texts.append((text, conf))
        return texts

    def recognize(self, image: np.ndarray) -> List[Tuple[str, float]]:
        """
        识别图片中的文字

        Args:
            image: 输入图片 (BGR 格式)

        Returns:
            [(text, confidence), ...]
        """
        if not CV2_AVAILABLE:
            logger.error("OpenCV 不可用")
            return []

        if self.engine_name == "easyocr":
            return self._recognize_easyocr(image)
        elif self.engine_name == "paddleocr":
            return self._recognize_paddleocr(image)
        else:
            return []

    def extract_caption(
        self,
        image_path: str,
        use_bottom_region: bool = True,
        bottom_ratio: float = 0.25
    ) -> Optional[OCRCaption]:
        """
        从图片中提取图注

        Args:
            image_path: 图片路径
            use_bottom_region: 是否只识别下方区域
            bottom_ratio: 下方区域比例

        Returns:
            OCRCaption 或 None
        """
        if not CV2_AVAILABLE:
            logger.error("OpenCV 不可用，无法进行 OCR")
            return None

        # 读取图片
        image = cv2.imread(image_path)
        if image is None:
            logger.warning(f"无法读取图片: {image_path}")
            return None

        # 提取区域
        if use_bottom_region:
            region = self._extract_bottom_region(image, bottom_ratio)
            region_name = "bottom"
        else:
            region = image
            region_name = "full"

        # OCR 识别
        try:
            results = self.recognize(region)
        except Exception as e:
            logger.error(f"OCR 识别失败: {e}")
            return None

        if not results:
            return None

        # 合并所有识别结果
        all_text = ' '.join([r[0] for r in results])
        avg_confidence = sum([r[1] for r in results]) / len(results)

        # 尝试匹配图注模式
        for pattern in self.CAPTION_PATTERNS:
            match = re.search(pattern, all_text)
            if match:
                return OCRCaption(
                    text=match.group(0),
                    confidence=avg_confidence,
                    engine=self.engine_name,
                    region=region_name
                )

        # 如果没有匹配到完整图注，返回所有识别到的文字
        if all_text:
            return OCRCaption(
                text=all_text[:200],  # 限制长度
                confidence=avg_confidence,
                engine=self.engine_name,
                region=region_name
            )

        return None

    def extract_caption_with_fallback(
        self,
        image_path: str,
        min_confidence: float = 0.5
    ) -> Optional[OCRCaption]:
        """
        提取图注（带备用策略）

        先尝试下方区域，如果失败则尝试全图
        """
        # 尝试下方区域
        result = self.extract_caption(image_path, use_bottom_region=True)
        if result and result.confidence >= min_confidence:
            return result

        # 尝试全图
        result = self.extract_caption(image_path, use_bottom_region=False)
        if result:
            return result

        return None


def extract_caption_from_image(
    image_path: str,
    engine: str = "auto",
    use_bottom_region: bool = True
) -> Optional[str]:
    """
    便捷函数：从图片提取图注

    Args:
        image_path: 图片路径
        engine: OCR 引擎
        use_bottom_region: 是否只识别下方区域

    Returns:
        图注文字或 None
    """
    try:
        ocr = CaptionOCR(engine=engine)
        result = ocr.extract_caption(image_path, use_bottom_region)
        return result.text if result else None
    except Exception as e:
        logger.error(f"提取图注失败: {e}")
        return None


if __name__ == "__main__":
    # 测试
    logging.basicConfig(level=logging.INFO)

    import sys
    if len(sys.argv) > 1:
        image_path = sys.argv[1]
        caption = extract_caption_from_image(image_path)
        print(f"提取结果: {caption}")
    else:
        print("用法: python caption_ocr.py <图片路径>")
