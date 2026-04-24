"""
题跋古文翻译服务
使用 qwen-plus-3.6 将古文题跋翻译为现代文
"""

import os
import httpx
from typing import Optional
from pydantic import BaseModel

from app.core.config import get_settings


class TranslationResult(BaseModel):
    """翻译结果"""
    original: str
    modern: str
    success: bool
    error: Optional[str] = None


# 翻译提示词
TRANSLATION_PROMPT = """你是一位精通中国古代书画题跋的专家学者。请将以下古文题跋翻译成通顺的现代汉语。

要求：
1. 准确理解古文含义，保持原文的语气和情感
2. 对于书画专业术语（如纪年、落款格式、斋号等）要准确翻译
3. 保留原文的文化内涵，不要过度口语化
4. 直接返回翻译结果，不要添加解释或注释

古文题跋：
{inscription}

现代文翻译："""


async def translate_inscription(inscription: str) -> TranslationResult:
    """
    翻译古文题跋为现代文
    
    Args:
        inscription: 古文题跋原文
        
    Returns:
        TranslationResult: 翻译结果
    """
    settings = get_settings()
    api_key = settings.QWEN_API_KEY
    model = settings.QWEN_TRANSLATION_MODEL
    base_url = settings.QWEN_BASE_URL
    
    if not api_key:
        return TranslationResult(
            original=inscription,
            modern="",
            success=False,
            error="未配置 QWEN_API_KEY"
        )
    
    if not inscription or not inscription.strip():
        return TranslationResult(
            original=inscription,
            modern="",
            success=False,
            error="题跋内容为空"
        )
    
    prompt = TRANSLATION_PROMPT.format(inscription=inscription.strip())
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "你是一位中国古代书画题跋翻译专家。"},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.3,
        "max_tokens": 4096,
        "enable_thinking": settings.QWEN_THINKING_ENABLED
    }

    # 使用 OpenAI 兼容模式调用
    url = f"{base_url}/chat/completions"

    # 重试机制：超时最多重试2次
    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=15.0)) as client:
                resp = await client.post(url, headers=headers, json=payload)
                resp.raise_for_status()
                result = resp.json()

                # 解析响应
                if "choices" in result and len(result["choices"]) > 0:
                    content = result["choices"][0].get("message", {}).get("content", "").strip()
                    return TranslationResult(
                        original=inscription,
                        modern=content,
                        success=True
                    )
                else:
                    return TranslationResult(
                        original=inscription,
                        modern="",
                        success=False,
                        error=f"API响应格式异常: {result}"
                    )

        except httpx.TimeoutException:
            if attempt < 2:
                # 重试
                continue
            return TranslationResult(
                original=inscription,
                modern="",
                success=False,
                error="API调用超时（已重试2次）"
            )
        except httpx.HTTPStatusError as e:
            return TranslationResult(
                original=inscription,
                modern="",
                success=False,
                error=f"HTTP错误: {e.response.status_code}"
            )
        except Exception as e:
            return TranslationResult(
                original=inscription,
                modern="",
                success=False,
                error=f"翻译失败: {str(e)}"
            )


def translate_inscription_sync(inscription: str) -> TranslationResult:
    """
    同步版本的翻译函数（用于worker等非异步环境）
    """
    settings = get_settings()
    api_key = settings.QWEN_API_KEY
    model = settings.QWEN_TRANSLATION_MODEL
    base_url = settings.QWEN_BASE_URL
    
    if not api_key:
        return TranslationResult(
            original=inscription,
            modern="",
            success=False,
            error="未配置 QWEN_API_KEY"
        )
    
    if not inscription or not inscription.strip():
        return TranslationResult(
            original=inscription,
            modern="",
            success=False,
            error="题跋内容为空"
        )
    
    prompt = TRANSLATION_PROMPT.format(inscription=inscription.strip())
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "你是一位中国古代书画题跋翻译专家。"},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.3,
        "max_tokens": 4096,
        "enable_thinking": settings.QWEN_THINKING_ENABLED
    }

    url = f"{base_url}/chat/completions"

    # 重试机制：超时最多重试2次
    for attempt in range(3):
        try:
            with httpx.Client(timeout=httpx.Timeout(120.0, connect=15.0)) as client:
                resp = client.post(url, headers=headers, json=payload)
                resp.raise_for_status()
                result = resp.json()

                if "choices" in result and len(result["choices"]) > 0:
                    content = result["choices"][0].get("message", {}).get("content", "").strip()
                    return TranslationResult(
                        original=inscription,
                        modern=content,
                        success=True
                    )
                else:
                    return TranslationResult(
                        original=inscription,
                        modern="",
                        success=False,
                        error=f"API响应格式异常: {result}"
                    )

        except httpx.TimeoutException:
            if attempt < 2:
                continue
            return TranslationResult(
                original=inscription,
                modern="",
                success=False,
                error="API调用超时（已重试2次）"
            )
        except Exception as e:
            return TranslationResult(
                original=inscription,
                modern="",
                success=False,
                error=f"翻译失败: {str(e)}"
            )
