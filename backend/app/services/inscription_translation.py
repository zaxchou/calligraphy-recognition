"""
题跋古文翻译服务
支持古文→现代汉语（白话文）+ 古文→英文
"""

import os
import httpx
from typing import Optional, Literal
from pydantic import BaseModel

from app.core.config import get_settings


class TranslationResult(BaseModel):
    """翻译结果"""
    original: str
    translated: str
    target: Literal["modern_chinese", "english"]
    success: bool
    error: Optional[str] = None


# ── 白话文翻译 Prompt ──────────────────────────────────────────────────
MODERN_CHINESE_PROMPT = """你是一位中国古代书画题跋翻译专家。请将以下古文题跋翻译成当代人读得懂的现代汉语。

要求：
1. 把古文转换成今天普通人说的话，让完全没学过古文的人也能看懂
2. 纪年、地名、人名直接保留原文，不要翻译
3. 印章落款格式（"某某印""某某题"）保留原文
4. 遇到典故或隐喻需要解释清楚，不能只做字面翻译
5. 直接返回翻译结果，不要任何解释或注释

古文题跋：
{inscription}

现代文翻译："""

# ── 英文翻译 Prompt ──────────────────────────────────────────────────
ENGLISH_PROMPT = """You are an expert translator of classical Chinese calligraphy inscriptions (tiba). Translate the following inscription into natural, fluent English.

Requirements:
1. Convert classical/literary Chinese into readable English suitable for non-specialists.
2. Reign years: keep the original Chinese (e.g. "乾隆十六年") and add the Western year in brackets: (1751).
3. Place names and personal names: romanize in pinyin without tones (e.g. "Yangzhou", "Li Shan").
4. Seal and signature formats: render as [Seal: XXX] or [Signed: XXX].
5. Allusions and metaphors: explain in plain English — do NOT just transliterate the characters.
6. Return ONLY the translation. No explanations, no notes, no preamble.

Source text:
{inscription}

English translation:"""


async def translate_inscription(inscription: str, target: str = "modern_chinese") -> TranslationResult:
    """
    翻译古文题跋

    Args:
        inscription: 古文题跋原文
        target: "modern_chinese"（白话文）或 "english"（英文）

    Returns:
        TranslationResult
    """
    settings = get_settings()
    from app.services.qwen_llm_client import get_text_llm_config
    api_key, base_url, default_model = get_text_llm_config()
    model = settings.QWEN_TRANSLATION_MODEL

    if not api_key:
        return TranslationResult(
            original=inscription, translated="", target=target,
            success=False, error="未配置 QWEN_API_KEY")

    if not inscription or not inscription.strip():
        return TranslationResult(
            original=inscription, translated="", target=target,
            success=False, error="题跋内容为空")

    prompt = (MODERN_CHINESE_PROMPT if target == "modern_chinese" else ENGLISH_PROMPT).format(
        inscription=inscription.strip())

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "你是一位中国古代书画题跋翻译专家。" if target == "modern_chinese" else "You are an expert translator of classical Chinese art inscriptions."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.3,
        "max_tokens": 4096,
        "enable_thinking": settings.QWEN_THINKING_ENABLED
    }

    url = f"{base_url}/chat/completions"

    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=15.0)) as client:
                resp = await client.post(url, headers=headers, json=payload)
                resp.raise_for_status()
                result = resp.json()

                if "choices" in result and len(result["choices"]) > 0:
                    content = result["choices"][0].get("message", {}).get("content", "").strip()
                    return TranslationResult(
                        original=inscription, translated=content, target=target, success=True)
                else:
                    return TranslationResult(
                        original=inscription, translated="", target=target,
                        success=False, error=f"API响应格式异常: {result}")

        except httpx.TimeoutException:
            if attempt < 2:
                continue
            return TranslationResult(
                original=inscription, translated="", target=target,
                success=False, error="API调用超时（已重试2次）")
        except httpx.HTTPStatusError as e:
            return TranslationResult(
                original=inscription, translated="", target=target,
                success=False, error=f"HTTP错误: {e.response.status_code}")
        except Exception as e:
            return TranslationResult(
                original=inscription, translated="", target=target,
                success=False, error=f"翻译失败: {str(e)}")


def translate_inscription_sync(inscription: str, target: str = "modern_chinese") -> TranslationResult:
    """同步版本的翻译函数（用于worker等非异步环境）"""
    settings = get_settings()
    from app.services.qwen_llm_client import get_text_llm_config
    api_key, base_url, default_model = get_text_llm_config()
    model = settings.QWEN_TRANSLATION_MODEL

    if not api_key:
        return TranslationResult(
            original=inscription, translated="", target=target,
            success=False, error="未配置 QWEN_API_KEY")

    if not inscription or not inscription.strip():
        return TranslationResult(
            original=inscription, translated="", target=target,
            success=False, error="题跋内容为空")

    prompt = (MODERN_CHINESE_PROMPT if target == "modern_chinese" else ENGLISH_PROMPT).format(
        inscription=inscription.strip())

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "你是一位中国古代书画题跋翻译专家。" if target == "modern_chinese" else "You are an expert translator of classical Chinese art inscriptions."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.3,
        "max_tokens": 4096,
        "enable_thinking": settings.QWEN_THINKING_ENABLED
    }

    url = f"{base_url}/chat/completions"

    for attempt in range(3):
        try:
            with httpx.Client(timeout=httpx.Timeout(120.0, connect=15.0)) as client:
                resp = client.post(url, headers=headers, json=payload)
                resp.raise_for_status()
                result = resp.json()

                if "choices" in result and len(result["choices"]) > 0:
                    content = result["choices"][0].get("message", {}).get("content", "").strip()
                    return TranslationResult(
                        original=inscription, translated=content, target=target, success=True)
                else:
                    return TranslationResult(
                        original=inscription, translated="", target=target,
                        success=False, error=f"API响应格式异常: {result}")

        except httpx.TimeoutException:
            if attempt < 2:
                continue
            return TranslationResult(
                original=inscription, translated="", target=target,
                success=False, error="API调用超时（已重试2次）")
        except Exception as e:
            return TranslationResult(
                original=inscription, translated="", target=target,
                success=False, error=f"翻译失败: {str(e)}")
