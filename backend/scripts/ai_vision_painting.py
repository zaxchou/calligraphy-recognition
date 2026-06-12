"""
AI 识图补充画材（仅处理无 analysis_note 的作品）
────────────────────────────────────────
用视觉模型分析画作图片，提取画材关键词并更新数据库
"""

import base64
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import get_settings
from app.services.inscription_content_analyzer import match_painting_materials

import httpx

PROMPT = """你是中国古代书画鉴定专家。看这幅画，提取画面中描绘的主要物象。

要求：
1. 只提取画面中实际描绘的物象
2. 用具体中文词（竹、石、牡丹、山水、鱼、虾等）
3. 只返回 JSON 数组，不要其他文字

["物象1", "物象2"]"""


def analyze_image(image_path: str, api_key: str, base_url: str):
    with open(image_path, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode()

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": "qwen-vl-plus",
        "messages": [{"role": "user", "content": [
            {"type": "text", "text": PROMPT},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}},
        ]}],
        "temperature": 0.1,
        "max_tokens": 200,
    }

    with httpx.Client(timeout=httpx.Timeout(60.0, connect=10.0)) as client:
        resp = client.post(f"{base_url}/chat/completions", headers=headers, json=payload)
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"].strip()
        if "```" in content:
            content = content.split("```")[1].replace("json", "").strip()
        return json.loads(content)


def main():
    settings = get_settings()
    api_key = settings.QWEN_API_KEY
    base_url = settings.QWEN_BASE_URL
    upload_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "uploads")

    import sqlite3
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "calligraphy.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT id, image_id, title, content_analysis FROM tubi_analyses WHERE content_analysis IS NOT NULL")

    updated = 0
    failed = 0

    for row in cur.fetchall():
        ca = json.loads(row["content_analysis"])
        v4 = ca.get("v4_signals", {})
        if v4.get("painting"):
            continue

        print(f'[{row["id"]}] {row["title"]}...', end="", flush=True)

        # 找图片
        image_path = None
        for ext in [".jpg", ".jpeg", ".png", ".webp"]:
            p = os.path.join(upload_dir, f'{row["image_id"]}{ext}')
            if os.path.exists(p):
                image_path = p
                break
        if not image_path:
            print(" ✗ 无图片")
            failed += 1
            continue

        # AI 识图
        try:
            keywords = analyze_image(image_path, api_key, base_url)
        except Exception as e:
            print(f" ✗ {e}")
            failed += 1
            continue

        if not keywords or not isinstance(keywords, list):
            print(" ✗ 无结果")
            failed += 1
            continue

        # 匹配画材规则
        virtual_title = " ".join(keywords)
        matches = match_painting_materials(virtual_title, None, virtual_title)
        if not matches:
            print(f" ✗ {keywords} 无法匹配")
            failed += 1
            continue

        # 更新数据库
        if "v4_signals" not in ca:
            ca["v4_signals"] = {}
        ca["v4_signals"]["painting"] = matches
        cur.execute("UPDATE tubi_analyses SET content_analysis = ? WHERE id = ?",
                   (json.dumps(ca, ensure_ascii=False), row["id"]))
        conn.commit()
        print(f" ✓ {keywords}")
        updated += 1

    conn.close()
    print(f"\n完成: 成功 {updated}, 失败 {failed}")


if __name__ == "__main__":
    main()
