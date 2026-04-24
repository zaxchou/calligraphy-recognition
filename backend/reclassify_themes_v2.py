"""
题跋内容主题+情感 LLM 分类脚本 v3
基于专家详细规则：6大主题 + 3档情感
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

CLASSIFY_PROMPT = """你是一位中国古代书画题跋研究专家。请根据以下题跋内容，严格按照六类定义判断其主题归属。

【六大主题定义 + 判定优先级】

**优先级顺序：先看1→2→3→4→5→6，符合即归入**

**主题3（讽喻社会与民生）优先级最高**
- 定义：关注现实、批判时弊、揭露民生疾苦、讽刺权贵
- 关键词：官吏、催租、官粮、村愚、纨绔、舆隶、夺朱、世味辣、利市、卖画、俗尘
- 符合则直接归入，同时可并存其他主题

**主题2（即景寄兴与抒怀）次高**
- 定义：借景抒情、托物言志，表达个人心境、人生感悟
- 关键词：孤、愁、遥、故山、苍松、劲竹、傲霜、凌云、闲、静
- 无社会批判时归此

**主题6（应酬送人与雅交）中等**
- 定义：为亲友、官员所作，含祝贺、送别、应酬性质
- 关键词：请指教、敬请、雅正、祝、贺、送、赠、年兄、先生、亲翁
- 明确受赠对象时归此

**主题5（世俗祈愿与谐趣）中等**
- 定义：世俗吉祥寓意，或带生活化、趣味化描写
- 关键词：多寿、子孙贤、百事大吉、平安、顺遂、同到白头、雅蒜、谐音（鸡=吉、鱼=余、蝠=福）
- 吉祥寓意明确时归此

**主题4（阐述画理画法）低**
- 定义：探讨笔墨技法、宗派师承、创作理念
- 关键词：仿、拟、摹、临、笔意、墨法、自娱、画理
- 以理论探讨为主时归此

**主题1（记录创作信息）最低**
- 定义：仅记录创作时间、地点、别号，无其他明确主题
- 关键词：制、写、画、题、于某斋、懊道人、复堂
- 仅当题跋无其他明确主题时归此

【判断规则】
- **必须返回至少2个主题**（题跋字数少于5字除外）
- 按优先级排序：讽喻社会与民生是主导时要排在最前
- 典型组合示例：
  - "日日临池画水仙..." → 记录创作信息(0.9), 阐述画理画法(0.7)
  - "闲爱孤云静爱僧..." → 即景寄兴与抒怀(0.9), 记录创作信息(0.7)
  - 含"世味"/"防辣"/"利市"/"催租"/"夺朱" → 讽喻社会与民生(0.8), 即景寄兴与抒怀(0.6)
  - "富贵花无脂粉恶态" → 讽喻社会与民生(0.9), 阐述画理画法(0.7)
  - 祝寿题跋 → 应酬送人与雅交(0.9), 世俗祈愿与谐趣(0.7)
  - "一路荣华" → 世俗祈愿与谐趣(0.8), 即景寄兴与抒怀(0.5)

【输出格式】只返回JSON，不要其他文字：
{{"themes": [{{"code": 3, "name": "讽喻社会与民生", "confidence": 0.9}}, ...], "reasoning": "简要说明"}}

【题跋内容】
{inscription}

【输出】"""

SENTIMENT_PROMPT = """你是一位中国古代书画题跋情感分析专家。请严格判断以下题跋的情感倾向。

【情感分类——必须严格遵守】

**positive（积极）必须满足以下之一**：
- 歌颂品格/理想：赞松竹梅菊高洁，寄托凌云志向
- 世俗祈愿：多子多福、长命富贵、平安吉祥
- 创作愉悦/自信：享受笔墨，表达艺术自信
- 友情雅交：真诚祝贺友人升迁、寿辰
- 关键词：凌云、傲霜、多寿子孙贤、平安、大吉、自怡悦、笑口、好音、春色

**negative（消极）满足以下之一**：
- 仕途失意：感慨年老无成、白发、被贬、无心情
- 社会批判：揭露官吏凶横、赋税沉重、民生疾苦
- 生活困顿：卖画艰难、催租恼人、衣食无着
- 世态炎凉：讽刺豪门奢靡、人心势利（世味辣、防辣）
- 压抑愁苦：风雨凄凄、荒园冷淡、故山遥不可及
- 关键词：老夫、白发、艰难、困、寒、凄、恼、恨、俗尘、催租、画贱、世味、辣、悔、孤、愁、遥

**neutral（中性）**：仅客观记录创作信息、纯技法讨论、无明显情感表达

【特别注意】
- 李鱓题跋多含蓄，"借景抒怀"常暗藏压抑愤懑，**表面写景但有愁苦词即判negative**
- 祝寿/吉祥语明确出现 → positive
- 纯年款/仅署名/纯技法说明 → neutral

【输出格式】只返回JSON，不要其他文字：
{{"polarity": "negative", "reasoning": "简要说明"}}

【题跋内容】
{inscription}

【输出】"""


def classify_with_llm(inscription: str, prompt_type="theme") -> dict:
    if not inscription or not inscription.strip():
        if prompt_type == "theme":
            return {"themes": [{"code": 0, "name": "未分类", "confidence": 0.0}], "reasoning": "题跋为空"}
        return {"polarity": "neutral", "reasoning": "题跋为空"}

    template = CLASSIFY_PROMPT if prompt_type == "theme" else SENTIMENT_PROMPT
    prompt = template.format(inscription=inscription.strip())

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

                if prompt_type == "theme":
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
                else:
                    polarity = data.get("polarity", "neutral")
                    if polarity not in ("positive", "negative", "neutral"):
                        polarity = "neutral"
                    return {"polarity": polarity, "reasoning": data.get("reasoning", "")}
    except httpx.TimeoutException:
        if prompt_type == "theme":
            return {"themes": [{"code": 0, "name": "未分类", "confidence": 0.0}], "reasoning": "LLM超时"}
        return {"polarity": "neutral", "reasoning": "LLM超时"}
    except json.JSONDecodeError:
        if prompt_type == "theme":
            return {"themes": [{"code": 0, "name": "未分类", "confidence": 0.0}], "reasoning": "JSON解析失败"}
        return {"polarity": "neutral", "reasoning": "JSON解析失败"}
    except Exception:
        if prompt_type == "theme":
            return {"themes": [{"code": 0, "name": "未分类", "confidence": 0.0}], "reasoning": "错误"}
        return {"polarity": "neutral", "reasoning": "错误"}


def main():
    if not API_KEY:
        print("ERROR: QWEN_API_KEY not set")
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT id, inscription_content, content_analysis FROM tubi_analyses WHERE inscription_content IS NOT NULL AND LENGTH(inscription_content) > 0")
    rows = cur.fetchall()
    total = len(rows)

    print(f"[INFO] v3 re-classification: {total} records | Model: {MODEL}")
    print(f"[INFO] Theme: multi-label required (min 2) | Sentiment: strict rules")
    print("-" * 50)

    updated = 0
    errors = 0
    fuyu_count = 0
    sentiment_stats = {"positive": 0, "negative": 0, "neutral": 0}

    for idx, (record_id, content, old_ca) in enumerate(rows):
        sys.stdout.write(f"[{idx+1}/{total}] id={record_id} ... ")
        sys.stdout.flush()

        theme_result = classify_with_llm(content, "theme")
        sentiment_result = classify_with_llm(content, "sentiment")

        if theme_result["themes"][0]["code"] != 0:
            themes = theme_result["themes"]
            theme_tags = ",".join([f"{t['name']}:{t['confidence']}" for t in themes])

            if len(themes) == 1:
                print(f"SINGLE theme WARN: id={record_id} code={themes[0]['code']}")

            old_data = json.loads(old_ca) if old_ca else {}
            old_data["themes"] = [{"code": t["code"], "name": t["name"], "confidence": t["confidence"]} for t in themes]
            old_data["sentiment"] = {
                "polarity": sentiment_result["polarity"],
                "reasoning": sentiment_result.get("reasoning", "")
            }

            cur.execute("UPDATE tubi_analyses SET content_analysis=?, theme_tags=?, updated_at=? WHERE id=?",
                (json.dumps(old_data, ensure_ascii=False), theme_tags, datetime.now(), record_id))
            conn.commit()
            updated += 1

            if any(t["code"] == 3 for t in themes):
                fuyu_count += 1

            pol = sentiment_result["polarity"]
            sentiment_stats[pol] = sentiment_stats.get(pol, 0) + 1

            codes_str = "/".join([str(t["code"]) for t in themes])
            print(f"OK codes={codes_str} sentiment={pol}")
        else:
            errors += 1
            print(f"FAIL reason={theme_result['reasoning'][:30]}")

    conn.close()

    print("-" * 50)
    print(f"[DONE] Updated={updated} Errors={errors}")
    print(f"[THEME] 讽喻社会与民生: {fuyu_count} ({fuyu_count/max(updated,1)*100:.1f}%)")
    print(f"[SENTIMENT] positive={sentiment_stats['positive']} negative={sentiment_stats['negative']} neutral={sentiment_stats['neutral']}")


if __name__ == "__main__":
    main()
