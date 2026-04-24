"""
题跋内容主题+情感 LLM 分类脚本 v3
严格遵循专家规则：就文论文，不含不延
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

CLASSIFY_PROMPT = """你是一位中国古代书画题跋研究专家。请根据以下题跋内容，严格按照六类定义和优先级进行主题分类。

【核心原则：就文论文，不含不延。如果文字本身没有提供超出"何人何时何地所作"的信息，就归入"记录创作信息"。】

【六大主题判定流程】
第一步：看是否有"讽喻社会与民生"内容
关键词：官吏、催租、官粮、村愚、纨绔、舆隶凶、夺朱、世味辣、利市、卖画难、俗尘、辛辣
符合则归入讽喻社会与民生

第二步：看是否有"应酬送人与雅交"内容
关键词：请指教、敬请、雅正、祝、贺、送、赠、年兄、先生、亲翁、索画
符合则归入应酬送人与雅交

第三步：看是否有"世俗祈愿与谐趣"内容
关键词：多寿、子孙贤、百事大吉、平安、顺遂、同到白头、雅蒜、谐音（鸡=吉、鱼=余、蝠=福）
符合则归入世俗祈愿与谐趣

第四步：看是否有"阐述画理画法"内容
关键词：仿、拟、摹（摹XX笔/意）、笔意、墨法、自娱、画理、悬腕、中锋
符合则归入阐述画理画法

第五步：看是否有"即景寄兴与抒怀"内容
关键词：孤、愁、遥、故山、苍松、劲竹、傲霜、凌云、闲、静、感怀、借景
符合则归入即景寄兴与抒怀

第六步：只有时间地点署名，别无其他 → 记录创作信息

【重要规则】
- 典型题跋有2-3个主题共存（讽喻/世俗/应酬 常与即景共存）
- 纯记录类题跋（如"雍正六年春李鱓"）只有1个主题：记录创作信息
- 临摹信息（"摹XX笔"）属于阐述画理画法，不是记录创作信息
- 置信度：高度相关=0.9，中度=0.7，低度=0.5

【输出格式】只返回JSON：
{{"themes": [{{"code": 1, "name": "记录创作信息", "confidence": 0.9}}], "reasoning": "说明"}}

【题跋内容】
{inscription}

【输出】"""


SENTIMENT_PROMPT = """你是一位中国古代书画题跋情感分析专家。请分析以下题跋的情感倾向。

【情感分类标准】

positive（积极）：以下情况才判定
- 明显祝福吉祥：多寿、子孙贤、大吉、百事大吉、平安、同到白头
- 歌颂品格理想：赞松竹梅菊高洁、凌云志向
- 创作愉悦自信：自怡悦、酣畅淋漓
- 友情真诚祝贺

negative（消极）：出现以下任一关键词即判
- 感叹年华/状态衰落：老夫、白发、老、残、衰、败、无力
- 世态炎凉：世味、世情、防辣、人情冷暖、辣
- 生计艰难：卖画难、利市、佣儿、催租、租税、艰难
- 压抑愁苦：叹、悲、愁、苦、恼、凄、寒、荒园
- 讽刺讥诮：讽刺、讥诮、无奈、困
- 怀才不遇：悔、恨、不得

neutral（中立）：仅记录时间地点、无情感词汇
- 纯记录：时间+地点+署名（如"雍正六年春李鱓"）
- 纯技法：临摹前人笔法

【特别注意】李鱓题跋情感含蓄，即使表面写景，若语境萧瑟或意象凄凉，仍应判negative。
但"仅署姓名时间"必须判neutral，不得过度解读。

【输出格式】只返回JSON：
{{"polarity": "negative", "reasoning": "说明"}}

【题跋内容】
{inscription}

【输出】"""


def call_llm(inscription: str, prompt_type: str) -> dict:
    if not inscription or not inscription.strip():
        if prompt_type == "theme":
            return {"themes": [{"code": 1, "name": "记录创作信息", "confidence": 0.9}], "reasoning": "题跋为空"}
        return {"polarity": "neutral", "reasoning": "题跋为空"}

    prompt = CLASSIFY_PROMPT if prompt_type == "theme" else SENTIMENT_PROMPT
    prompt = prompt.format(inscription=inscription.strip())

    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
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
            content = result["choices"][0]["message"]["content"].strip()
            if content.startswith("```"):
                lines = content.split("\n")
                content = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])
            data = json.loads(content)

            if prompt_type == "theme":
                themes = []
                for t in data.get("themes", []):
                    if 1 <= t.get("code", 0) <= 6:
                        themes.append({
                            "code": t["code"],
                            "name": THEMES.get(t["code"], "未知"),
                            "confidence": min(float(t.get("confidence", 0.5)), 0.9)
                        })
                themes.sort(key=lambda x: x["confidence"], reverse=True)
                if not themes:
                    themes = [{"code": 1, "name": "记录创作信息", "confidence": 0.9}]
                return {"themes": themes, "reasoning": data.get("reasoning", "")}
            else:
                p = data.get("polarity", "neutral")
                if p not in ("positive", "negative", "neutral"):
                    p = "neutral"
                return {"polarity": p, "reasoning": data.get("reasoning", "")}
    except Exception as e:
        if prompt_type == "theme":
            return {"themes": [{"code": 1, "name": "记录创作信息", "confidence": 0.9}], "reasoning": str(e)}
        return {"polarity": "neutral", "reasoning": str(e)}


def main():
    if not API_KEY:
        print("ERROR: QWEN_API_KEY not set")
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT id, inscription_content, content_analysis FROM tubi_analyses WHERE inscription_content IS NOT NULL AND LENGTH(inscription_content) > 0")
    rows = cur.fetchall()
    total = len(rows)

    print(f"[INFO] v3 classification: {total} records | Model: {MODEL}")
    print("-" * 50)

    updated = errors = fuyu_count = 0

    for idx, (record_id, content, old_ca) in enumerate(rows):
        sys.stdout.write(f"[{idx+1}/{total}] id={record_id} ... ")
        sys.stdout.flush()

        theme_result = call_llm(content, "theme")
        sentiment_result = call_llm(content, "sentiment")

        themes = theme_result["themes"]
        theme_tags = ",".join([f"{t['name']}:{t['confidence']}" for t in themes])

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

        codes = "/".join([str(t["code"]) for t in themes])
        print(f"OK codes={codes} sentiment={sentiment_result['polarity']}")

    conn.close()
    print("-" * 50)
    print(f"[DONE] Updated={updated} Errors={errors}")
    print(f"[INFO] 讽喻社会与民生: {fuyu_count} ({fuyu_count/max(updated,1)*100:.1f}%)")


if __name__ == "__main__":
    main()
