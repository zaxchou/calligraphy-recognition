"""
题跋内容主题 LLM 分类脚本
使用 qwen-turbo 对题跋内容进行 6 类主题分类，替代关键词规则
"""
import sqlite3
import json
import httpx
import os
import sys
from datetime import datetime

DB_PATH = "data/calligraphy.db"

from app.core.config import get_settings
_settings = get_settings()
API_KEY = _settings.QWEN_API_KEY
BASE_URL = _settings.QWEN_BASE_URL
MODEL = _settings.QWEN_TRANSLATION_MODEL

THEMES = {
    1: "记录创作信息",
    2: "即景寄兴与抒怀",
    3: "讽喻社会与民生",
    4: "阐述画理画法",
    5: "世俗祈愿与谐趣",
    6: "应酬送人与雅交",
}

THEME_CLASSIFY_PROMPT = """你是一位中国古代书画题跋研究专家。请根据以下题跋内容，判断它属于哪个主题类别。

【主题类别】
1. 记录创作信息：题跋记录作画时间、地点、画家自述创作经过，或临摹前人画作、题写画名等
2. 即景寄兴与抒怀：题跋描写眼前景物、表达当下感怀、抒发诗情画意
3. 讽喻社会与民生：题跋讽刺社会现象、关注民间疾苦、表达对官场或世道的批判
4. 阐述画理画法：题跋论说绘画技法、笔墨道理、师承渊源、雅俗之辨
5. 世俗祈愿与谐趣：题跋含有吉祥祝福（福寿富贵）、玩笑戏语、或世俗应景之词
6. 应酬送人与雅交：题跋提及为谁而作、请人指教、敬请雅正、赠送友人等应酬交往内容

【判断规则】
- 一条题跋可能属于多个主题，按相关程度排序
- 置信度：高度相关=0.9，中度=0.7，低度=0.5

【输出格式】
只返回 JSON，不要其他文字：
{{"themes": [{{"code": 1, "name": "记录创作信息", "confidence": 0.9}}, ...], "reasoning": "简要说明"}}

【题跋内容】
{inscription}

【输出】"""

def classify_with_llm(inscription: str) -> dict:
    if not inscription or not inscription.strip():
        return {"themes": [{"code": 0, "name": "未分类", "confidence": 0.0}], "reasoning": "题跋为空"}

    safe_content = inscription.strip().replace("{", "{{").replace("}", "}}")
    prompt = THEME_CLASSIFY_PROMPT.format(inscription=safe_content)

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": "你是一位严谨的中国古代书画题跋研究专家。"},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.3,
        "max_tokens": 512
    }

    try:
        with httpx.Client(timeout=httpx.Timeout(60.0, connect=10.0)) as client:
            resp = client.post(f"{BASE_URL}/chat/completions", headers=headers, json=payload)
            resp.raise_for_status()
            result = resp.json()

            if "choices" in result and len(result["choices"]) > 0:
                content = result["choices"][0].get("message", {}).get("content", "").strip()
                if content.startswith("```"):
                    lines = content.split("\n")
                    content = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])
                data = json.loads(content)
                if "themes" in data and isinstance(data["themes"], list):
                    valid_themes = []
                    for t in data["themes"]:
                        if "code" in t and 1 <= t["code"] <= 6:
                            valid_themes.append({
                                "code": t["code"],
                                "name": THEMES.get(t["code"], "未知"),
                                "confidence": min(float(t.get("confidence", 0.5)), 0.9)
                            })
                    if valid_themes:
                        valid_themes.sort(key=lambda x: x["confidence"], reverse=True)
                        return {"themes": valid_themes, "reasoning": data.get("reasoning", "")}
                return {"themes": [{"code": 0, "name": "未分类", "confidence": 0.0}], "reasoning": "格式解析失败"}
    except httpx.TimeoutException:
        return {"themes": [{"code": 0, "name": "未分类", "confidence": 0.0}], "reasoning": "LLM超时"}
    except json.JSONDecodeError as e:
        return {"themes": [{"code": 0, "name": "未分类", "confidence": 0.0}], "reasoning": f"JSON解析失败"}
    except Exception as e:
        return {"themes": [{"code": 0, "name": "未分类", "confidence": 0.0}], "reasoning": f"错误"}


def main():
    if not API_KEY:
        print("ERROR: QWEN_API_KEY not set")
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("""
        SELECT id, inscription_content FROM tubi_analyses
        WHERE inscription_content IS NOT NULL
        AND LENGTH(inscription_content) > 0
    """)
    rows = cur.fetchall()
    total = len(rows)

    print(f"[INFO] Starting LLM theme classification, {total} records...")
    print(f"[INFO] Model: {MODEL}")
    print("-" * 50)

    updated = 0
    errors = 0

    for idx, (record_id, content) in enumerate(rows):
        sys.stdout.write(f"[{idx+1}/{total}] id={record_id} ... ")
        sys.stdout.flush()

        result = classify_with_llm(content)

        if result["themes"][0]["code"] != 0:
            themes = result["themes"]
            theme_tags = ",".join([f"{t['name']}:{t['confidence']}" for t in themes])

            cur.execute("SELECT content_analysis FROM tubi_analyses WHERE id = ?", (record_id,))
            row = cur.fetchone()
            ca = json.loads(row[0]) if row and row[0] else {}
            ca["themes"] = [{"code": t["code"], "name": t["name"], "confidence": t["confidence"]} for t in themes]

            cur.execute("""
                UPDATE tubi_analyses
                SET content_analysis = ?,
                    theme_tags = ?,
                    updated_at = ?
                WHERE id = ?
            """, (json.dumps(ca, ensure_ascii=False), theme_tags, datetime.now(), record_id))
            conn.commit()
            updated += 1
            codes_str = "/".join([str(t["code"]) for t in themes])
            print(f"OK codes={codes_str}")
        else:
            errors += 1
            print(f"FAIL reason={result['reasoning'][:30]}")

    conn.close()

    print("-" * 50)
    print(f"[DONE] Updated={updated} Errors={errors}")


if __name__ == "__main__":
    main()
