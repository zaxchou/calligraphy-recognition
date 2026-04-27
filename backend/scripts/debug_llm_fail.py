"""排查 LLM 调用失败原因"""
import sys, os, asyncio
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.chdir(os.path.join(os.path.dirname(__file__), ".."))

from app.services.inscription_content_analyzer import llm_analyze_combined

# 取一个之前失败的文本
test_texts = [
    "闲爱孤云静爱僧，得闲一味是无能。何时大茅棚下去，煮雪烹茶对山",
    "十二月春都占来。李鱓制",
    "天地一沙鸥。李鱓",
    "一窗灯影一床书，窗外萧疏竹有无。记自寻天池旧诗，句狂风骤雨老",
]

for text in test_texts:
    r = asyncio.run(llm_analyze_combined(text, artist="李鱓"))
    status = "OK" if r.get("success") else "FAIL"
    themes = [(t["name"]) for t in r.get("themes", [])] if r.get("themes") else []
    err = r.get("error", "")[:80]
    print(f"  [{status}] {text[:30]}... themes={themes}")
    if err:
        print(f"           error: {err}")
