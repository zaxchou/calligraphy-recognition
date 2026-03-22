"""
OCR服务 - 使用EasyOCR进行文字识别
"""
import cv2
import numpy as np
from PIL import Image
import io
from typing import List, Dict, Optional

# 延迟导入EasyOCR，避免启动时加载
try:
    import easyocr
    HAS_EASYOCR = True
except ImportError:
    HAS_EASYOCR = False
    print("警告: EasyOCR未安装，OCR功能不可用")


class OCRService:
    """OCR识别服务"""
    
    def __init__(self):
        self.reader = None
        self.is_initialized = False
    
    def initialize(self):
        """初始化OCR阅读器"""
        if not HAS_EASYOCR:
            return False
        
        if self.reader is None:
            try:
                # 使用中文和英文模型
                self.reader = easyocr.Reader(['ch_sim', 'en'], gpu=False)
                self.is_initialized = True
                print("✓ OCR服务初始化完成")
                return True
            except Exception as e:
                print(f"✗ OCR初始化失败: {e}")
                return False
        return True
    
    def recognize(self, image_bytes: bytes) -> Dict:
        """
        识别图像中的文字
        
        Args:
            image_bytes: 图像字节数据
            
        Returns:
            识别结果
        """
        if not self.initialize():
            return {
                'success': False,
                'message': 'OCR服务未初始化',
                'texts': []
            }
        
        try:
            # 将字节转换为numpy数组
            nparr = np.frombuffer(image_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if img is None:
                return {
                    'success': False,
                    'message': '无法读取图像',
                    'texts': []
                }
            
            # 进行OCR识别
            results = self.reader.readtext(img)
            
            # 解析结果
            texts = []
            for (bbox, text, conf) in results:
                texts.append({
                    'text': text,
                    'confidence': float(conf),
                    'bbox': bbox
                })
            
            # 按置信度排序
            texts.sort(key=lambda x: x['confidence'], reverse=True)
            
            return {
                'success': True,
                'message': f'识别到 {len(texts)} 个文本',
                'texts': texts
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'OCR识别失败: {str(e)}',
                'texts': []
            }
    
    def recognize_single_char(self, image_bytes: bytes) -> Dict:
        """
        识别单字符（取置信度最高的结果）
        
        Args:
            image_bytes: 图像字节数据
            
        Returns:
            单字符识别结果
        """
        result = self.recognize(image_bytes)
        
        if not result['success'] or not result['texts']:
            return {
                'success': False,
                'message': '未识别到文字',
                'character': None,
                'confidence': 0
            }
        
        # 取置信度最高的结果
        best = result['texts'][0]
        char = best['text'].strip()
        
        # 如果是多字符，取第一个
        if len(char) > 1:
            char = char[0]
        
        return {
            'success': True,
            'message': '识别成功',
            'character': char,
            'confidence': best['confidence'],
            'all_results': result['texts']
        }


# 全局OCR服务实例
_ocr_service = None

def get_ocr_service() -> OCRService:
    """获取OCR服务实例（单例模式）"""
    global _ocr_service
    if _ocr_service is None:
        _ocr_service = OCRService()
    return _ocr_service
