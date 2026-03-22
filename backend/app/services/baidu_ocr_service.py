"""
百度OCR服务 - 使用百度AI开放平台进行高精度文字识别
"""
import cv2
import numpy as np
import requests
import base64
from typing import Dict, List
from PIL import Image


class BaiduOCRService:
    """百度OCR识别服务"""
    
    def __init__(self):
        # 百度OCR API配置 - 使用免费版
        self.api_key = "YOUR_API_KEY"  # 需要用户自己申请
        self.secret_key = "YOUR_SECRET_KEY"  # 需要用户自己申请
        self.access_token = None
        self.api_url = "https://aip.baidubce.com/rest/2.0/ocr/v1/accurate_basic"
        
    def get_access_token(self) -> str:
        """获取百度API访问令牌"""
        if self.access_token:
            return self.access_token
            
        url = f"https://aip.baidubce.com/oauth/2.0/token"
        params = {
            "grant_type": "client_credentials",
            "client_id": self.api_key,
            "client_secret": self.secret_key
        }
        
        try:
            response = requests.post(url, params=params, timeout=10)
            result = response.json()
            self.access_token = result.get("access_token")
            return self.access_token
        except Exception as e:
            print(f"获取access_token失败: {e}")
            return None
    
    def recognize(self, image_bytes: bytes) -> Dict:
        """
        使用百度OCR识别图像中的文字
        
        Args:
            image_bytes: 图像字节数据
            
        Returns:
            识别结果
        """
        access_token = self.get_access_token()
        if not access_token:
            return {
                'success': False,
                'message': '无法获取API访问令牌',
                'texts': []
            }
        
        try:
            # 对图像进行预处理以提高识别率
            img = self._preprocess_image(image_bytes)
            
            # 转换为base64
            _, buffer = cv2.imencode('.png', img)
            img_base64 = base64.b64encode(buffer).decode('utf-8')
            
            # 调用百度OCR API
            url = f"{self.api_url}?access_token={access_token}"
            headers = {'Content-Type': 'application/x-www-form-urlencoded'}
            params = {
                'image': img_base64,
                'language_type': 'CHN_ENG',
                'detect_direction': 'true',
                'paragraph': 'false',
                'probability': 'true'
            }
            
            response = requests.post(url, headers=headers, data=params, timeout=30)
            result = response.json()
            
            if 'error_code' in result:
                return {
                    'success': False,
                    'message': f"API错误: {result.get('error_msg', '未知错误')}",
                    'texts': []
                }
            
            # 解析结果
            texts = []
            words_result = result.get('words_result', [])
            for item in words_result:
                text = item.get('words', '').strip()
                probability = item.get('probability', {})
                avg_confidence = probability.get('average', 0) if isinstance(probability, dict) else 0
                
                if text:
                    texts.append({
                        'text': text,
                        'confidence': avg_confidence * 100 if avg_confidence <= 1 else avg_confidence
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
    
    def _preprocess_image(self, image_bytes: bytes) -> np.ndarray:
        """预处理图像以提高OCR识别率"""
        # 读取图像
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if img is None:
            raise ValueError("无法读取图像")
        
        # 转换为灰度
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # 判断背景颜色
        mean_val = np.mean(gray)
        
        if mean_val < 127:
            # 深色背景，需要反转
            gray = 255 - gray
        
        # 自适应二值化
        binary = cv2.adaptiveThreshold(
            gray, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            11, 2
        )
        
        # 去噪
        denoised = cv2.fastNlMeansDenoising(binary, None, 10, 7, 21)
        
        # 转回3通道
        result = cv2.cvtColor(denoised, cv2.COLOR_GRAY2BGR)
        
        return result
    
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


# 全局服务实例
_baidu_ocr_service = None

def get_baidu_ocr_service() -> BaiduOCRService:
    """获取百度OCR服务实例（单例模式）"""
    global _baidu_ocr_service
    if _baidu_ocr_service is None:
        _baidu_ocr_service = BaiduOCRService()
    return _baidu_ocr_service
