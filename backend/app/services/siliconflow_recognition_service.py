"""
SiliconFlow AI 字体识别服务 - 使用 Kimi-K2.5 模型
支持直接图像输入进行书法字体识别
"""
import json
import base64
import httpx
from typing import Optional, Dict, Any, List
from app.core.config import get_settings

settings = get_settings()

# SiliconFlow API 配置
import os
SILICONFLOW_API_KEY = os.getenv("SILICONFLOW_API_KEY", "")
SILICONFLOW_API_URL = "https://api.siliconflow.cn/v1/chat/completions"
MODEL_NAME = "Pro/moonshotai/Kimi-K2.5"


class SiliconFlowRecognitionService:
    """SiliconFlow AI 字体识别服务 - 支持图像输入"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or SILICONFLOW_API_KEY
        # 允许空 Key，只是不启用 AI 功能
        if not self.api_key:
            print("警告: SiliconFlow API Key 未配置，AI 识别功能将不可用")
    
    def recognize_character(
        self, 
        image_bytes: bytes,
        candidates: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        使用 Kimi-K2.5 识别书法字体
        
        Args:
            image_bytes: 图片二进制数据
            candidates: 候选字形列表（可选）
            
        Returns:
            识别结果
        """
        try:
            # 将图片转为 base64
            base64_image = base64.b64encode(image_bytes).decode("utf-8")
            
            # 构建提示词
            if candidates:
                candidate_str = ", ".join(candidates)
                prompt = f"""你是一位专业的书法字体识别专家。请识别这张图片中的汉字。

候选汉字：{candidate_str}

请仔细观察图片中的书法字体，注意：
1. 笔画结构和形态
2. 整体字形特征
3. 书法风格特点

请从候选字中选择最匹配的一个，并以 JSON 格式返回结果：
{{"character": "识别的汉字", "confidence": 95.5, "reason": "判断理由"}}

注意：必须从候选字列表中选择，只返回 JSON，不要有其他内容。"""
            else:
                prompt = """你是一位专业的书法字体识别专家。请识别这张图片中的汉字。

请仔细观察图片中的书法字体，注意：
1. 笔画结构和形态
2. 整体字形特征
3. 书法风格特点

请以 JSON 格式返回结果：
{"character": "识别的汉字", "confidence": 95.5, "reason": "判断理由"}

只返回 JSON，不要有其他内容。"""
            
            payload = {
                "model": MODEL_NAME,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": prompt
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ],
                "stream": False,
                "max_tokens": 512,
                "temperature": 0.1
            }
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            # 使用较短的超时时间
            timeout = httpx.Timeout(60.0, connect=10.0)
            
            with httpx.Client(timeout=timeout) as client:
                response = client.post(SILICONFLOW_API_URL, headers=headers, json=payload)
                response.raise_for_status()
                result = response.json()
                
                content = result["choices"][0]["message"]["content"]
                
                # 清理 JSON 格式
                content = content.strip()
                if content.startswith("```json"):
                    content = content[7:]
                if content.startswith("```"):
                    content = content[3:]
                if content.endswith("```"):
                    content = content[:-3]
                content = content.strip()
                
                recognition_result = json.loads(content)
                
                character = recognition_result.get("character", "").strip()
                confidence = float(recognition_result.get("confidence", 0))
                
                return {
                    "success": True,
                    "character": character,
                    "confidence": confidence,
                    "reason": recognition_result.get("reason", ""),
                    "raw_response": content
                }
                
        except httpx.TimeoutException:
            print("SiliconFlow API 请求超时")
            return {
                "success": False,
                "error": "API请求超时，请重试",
                "character": "",
                "confidence": 0
            }
        except httpx.HTTPStatusError as e:
            print(f"SiliconFlow API HTTP错误: {e.response.status_code}")
            return {
                "success": False,
                "error": f"API请求错误: {e.response.status_code}",
                "character": "",
                "confidence": 0
            }
        except json.JSONDecodeError as e:
            print(f"SiliconFlow JSON解析错误: {str(e)}")
            return {
                "success": False,
                "error": f"JSON解析错误: {str(e)}",
                "character": "",
                "confidence": 0
            }
        except Exception as e:
            print(f"SiliconFlow 识别失败: {str(e)}")
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "error": f"识别失败: {str(e)}",
                "character": "",
                "confidence": 0
            }


# 全局服务实例
_recognition_service: Optional[SiliconFlowRecognitionService] = None


def get_siliconflow_recognition_service() -> SiliconFlowRecognitionService:
    """获取 SiliconFlow 字体识别服务实例（单例模式）"""
    global _recognition_service
    if _recognition_service is None:
        _recognition_service = SiliconFlowRecognitionService()
    return _recognition_service
