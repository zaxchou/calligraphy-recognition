"""确认 llm_analyze_combined 中原始返回"""
import sys, os, httpx, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.chdir(os.path.join(os.path.dirname(__file__), ".."))

from app.core.config import get_settings
from app.services.qwen_llm_client import get_text_llm_config
from app.services.inscription_content_analyzer import _get_artist_theme_note, LLM_COMBINED_PROMPT_V1

api_key, base_url, model = get_text_llm_config()

text = "十二月春都占来。李鱓制"
note, _ = _get_artist_theme_note("李鱓")
prompt = LLM_COMBINED_PROMPT_V1.format(text=text[:500], artist_note=note)

# 用和 llm_analyze_combined 一样的请求体
request_body = {
    "model": model,
    "messages": [{"role": "user", "content": prompt}],
    "max_tokens": 500,
    "temperature": 0.1,
}
if "deepseek" in base_url.lower() or "deepseek" in model.lower():
    request_body["thinking"] = {"type": "disabled"}
else:
    request_body["enable_thinking"] = False

r = httpx.post(
    f"{base_url}/chat/completions",
    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
    json=request_body,
    timeout=30
)

raw = r.json()["choices"][0]["message"]["content"].strip()

# 打印原始返回的前后部分
print(f"长度: {len(raw)}")
print(f"起始: {repr(raw[:50])}")
print(f"结束: {repr(raw[-50:])}")

# 模拟 llm_analyze_combined 的提取
raw_clean = raw.strip()
if raw_clean.startswith("```"):
    raw_clean = raw_clean.split("\n", 1)[-1] if "\n" in raw_clean else raw_clean
    raw_clean = raw_clean.rsplit("```", 1)[0] if "```" in raw_clean else raw_clean
brace_start = raw_clean.find("{")
brace_end = raw_clean.rfind("}")
if brace_start >= 0 and brace_end > brace_start:
    raw_clean = raw_clean[brace_start:brace_end+1]

print(f"提取后长度: {len(raw_clean)}")
print(f"提取起始: {repr(raw_clean[:50])}")
print(f"提取结束: {repr(raw_clean[-50:])}")

try:
    parsed = json.loads(raw_clean)
    print(f"解析成功! themes: {[(t['name']) for t in parsed.get('themes',[])]}")
except Exception as e:
    print(f"解析失败: {str(e)[:100]}")
    print(f"失败位置附近: {repr(raw_clean[600:650])}")
