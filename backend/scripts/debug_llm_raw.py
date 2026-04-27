"""查看 DeepSeek 返回的原始内容"""
import sys, os, httpx, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.chdir(os.path.join(os.path.dirname(__file__), ".."))

from app.core.config import get_settings
from app.services.qwen_llm_client import get_text_llm_config

api_key, base_url, model = get_text_llm_config()
settings = get_settings()

text = "闲爱孤云静爱僧，得闲一味是无能。何时大茅棚下去，煮雪烹茶对山"

from app.services.inscription_content_analyzer import _get_artist_theme_note
note, _ = _get_artist_theme_note("李鱓")
prompt = "你是中国古代书画题跋研究专家。分析以下题跋的主题（六大类）和情感倾向。\n【主题】\n1. 身世自况: 自嘲、自伤、命运感怀\n2. 咏物寄兴: 咏物咏景兼抒情\n3. 画理自叙: 创作谈\n4. 时事讽喻: 社会批判\n5. 吉语祥瑞: 吉祥祝福\n6. 交游赠答: 赠送友人\n\n【画家提示】" + note + "\n\n题跋文本：\n" + text[:500] + "\n\n返回严格JSON格式（不要markdown包裹），不要多余文字：\n{\"themes\":[{\"code\":1,\"name\":\"身世自况\",\"confidence\":0.9}],\"sentiment\":{\"polarity\":\"negative\",\"intensity\":0.7},\"overall_reasoning\":\"...\"}"

print("=== 原始请求 ===")
print(f"model: {model}")
print(f"text length: {len(text)}")

# 直接发请求看原始返回
req = {
    "model": model,
    "messages": [{"role": "user", "content": prompt}],
    "max_tokens": 500,
    "temperature": 0.1,
    "thinking": {"type": "disabled"}
}

r = httpx.post(
    f"{base_url}/chat/completions",
    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
    json=req,
    timeout=30
)

raw = r.json()
content = raw["choices"][0]["message"]["content"]
print(f"\n=== 原始返回（共 {len(content)} 字符）===")
print(content[:800])
print("\n...")

# 看第 500-600 字符附近
print(f"\n=== 问题区域 (char 500-600) ===")
print(repr(content[500:600]))
