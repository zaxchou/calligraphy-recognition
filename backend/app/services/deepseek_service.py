"""
DeepSeek AI 服务 - 用于增强书法字体识别
由于 DeepSeek API 不支持图像输入，改用特征描述的方式
"""
import json
import requests
from typing import Optional, Dict, Any, List
from app.core.config import get_settings

settings = get_settings()


class DeepSeekService:
    """DeepSeek AI 服务封装 - 使用特征描述进行识别"""
    
    API_URL = "https://api.deepseek.com/v1/chat/completions"
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.DEEPSEEK_API_KEY
        if not self.api_key:
            raise ValueError("DeepSeek API Key 未配置")
    
    def recognize_by_features(
        self, 
        features_description: str,
        candidates: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        使用 DeepSeek AI 根据特征描述识别书法字体
        
        Args:
            features_description: 特征描述文本
            candidates: 候选字形列表
            
        Returns:
            识别结果
        """
        # 构建提示词
        if candidates:
            candidate_str = ", ".join(candidates)
            prompt = f"""你是一位书法字体识别专家。请根据以下特征描述判断这是哪个汉字。

候选汉字：{candidate_str}

特征描述：
{features_description}

请仔细分析这些特征，然后：
1. 判断这是哪个汉字（必须从候选字中选择）
2. 给出置信度（0-100%）
3. 简要说明判断理由

请以 JSON 格式返回结果：
{{"character": "识别的汉字", "confidence": 95.5, "reason": "判断理由"}}"""
        else:
            prompt = f"""你是一位书法字体识别专家。请根据以下特征描述判断这是哪个汉字。

特征描述：
{features_description}

请仔细分析这些特征，然后：
1. 判断这是哪个汉字
2. 给出置信度（0-100%）
3. 简要说明判断理由

请以 JSON 格式返回结果：
{{"character": "识别的汉字", "confidence": 95.5, "reason": "判断理由"}}"""
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "deepseek-chat",
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.1,
            "max_tokens": 500
        }
        
        try:
            response = requests.post(
                self.API_URL,
                headers=headers,
                json=payload,
                timeout=30
            )
            
            response.raise_for_status()
            
            result = response.json()
            ai_response = result['choices'][0]['message']['content']
            
            # 解析 AI 返回的 JSON
            ai_response = ai_response.strip()
            if ai_response.startswith('```json'):
                ai_response = ai_response[7:]
            if ai_response.startswith('```'):
                ai_response = ai_response[3:]
            if ai_response.endswith('```'):
                ai_response = ai_response[:-3]
            ai_response = ai_response.strip()
            
            recognition_result = json.loads(ai_response)
            
            character = recognition_result.get("character", "").strip()
            confidence = float(recognition_result.get("confidence", 0))
            
            return {
                "success": True,
                "character": character,
                "confidence": confidence,
                "reason": recognition_result.get("reason", ""),
                "raw_response": ai_response
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "character": "",
                "confidence": 0
            }


# 全局服务实例
deepseek_service: Optional[DeepSeekService] = None


def get_deepseek_service() -> DeepSeekService:
    """获取 DeepSeek 服务实例（单例模式）"""
    global deepseek_service
    if deepseek_service is None:
        deepseek_service = DeepSeekService()
    return deepseek_service
