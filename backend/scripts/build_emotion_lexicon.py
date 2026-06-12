"""
情感词典构建脚本 v3
────────────────────────────────────────
用 DeepSeek 对候选情感词在书画语境下打分（-4 到 +4）

流程：
1. 加载候选词列表（v3 格式，含来源标记和 FCCPSL 极性）
2. 保留已有词库的评分，只对新增词调用 DeepSeek
3. 分批发送给 DeepSeek（每批 20 词）
4. 收集评分结果，合并输出 emotion_lexicon_v3.json

用法：
python -m scripts.build_emotion_lexicon --output backend/app/services/emotion_lexicon_v3.json
"""

import asyncio
import json
import os
import sys
import argparse
from typing import Dict, List, Optional
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import get_settings
from app.services.qwen_llm_client import get_text_llm_config


# 打分 prompt
LEXICON_RATING_PROMPT = """你是中国古代书画题跋情感分析专家。请对以下词语在书画题跋语境下的情感强度打分。

【评分标准】
- -4：极度消极（如：怒、愤、恨）
- -3：强烈消极（如：愁、苦、凄）
- -2：中等消极（如：凉、寒、叹）
- -1：轻微消极（如：残、衰、倦）
- 0：中性（如：山、水、花）
- +1：轻微积极（如：清、雅、闲）
- +2：中等积极（如：喜、笑、乐）
- +3：强烈积极（如：傲、健、凌）
- +4：极度积极（如：大吉、多寿、平安）

【特别注意】
- 某些词在书画语境下情感可能不同于日常用法（如"狂"在书画中可能是积极的创作激情）
- 某些词是自嘲/反讽（如"莫笑""自笑"在李鱓题跋中是消极的）
- 保持一致性：相似情感强度的词应有相近分数

【待评分词语】
{words}

【输出格式】
只返回 JSON，格式为：
{{"评分": {{"词1": 分数, "词2": 分数, ...}}}}

注意：分数必须是整数，范围 -4 到 +4。"""


def _classification_label(score: int) -> str:
    """根据分数返回情感分类标签"""
    if score <= -3: return "negative_strong"
    elif score <= -2: return "negative_moderate"
    elif score < 0: return "negative_mild"
    elif score == 0: return "neutral"
    elif score <= 1: return "positive_mild"
    elif score <= 2: return "positive_moderate"
    else: return "positive_strong"


async def rate_words_batch(words: List[str], api_key: str, base_url: str, model: str) -> Dict[str, int]:
    """让 LLM 对一批词语打分"""
    import httpx

    prompt = LEXICON_RATING_PROMPT.format(words="、".join(words))

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "你是中国古代书画题跋情感分析专家。"},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.1,
        "max_tokens": 2000,
    }

    url = f"{base_url}/chat/completions"

    async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=15.0)) as client:
        resp = await client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        result = resp.json()

        content = result["choices"][0]["message"]["content"].strip()
        # 提取 JSON
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]

        parsed = json.loads(content)
        return parsed.get("评分", parsed)


def load_existing_scores(existing_lexicon_path: Optional[str]) -> Dict[str, int]:
    """加载已有词库的评分，避免重复调用 API"""
    if not existing_lexicon_path or not os.path.exists(existing_lexicon_path):
        return {}
    with open(existing_lexicon_path, encoding='utf-8') as f:
        data = json.load(f)
    entries = data.get('entries', {})
    scores = {word: info['score'] for word, info in entries.items()}
    print(f"  已加载 {len(scores)} 个现有词评分")
    return scores


async def build_lexicon(candidate_words: List[str], output_path: str,
                        batch_size: int = 20,
                        existing_scores: Dict[str, int] = None):
    """主流程：批量构建情感词典"""
    settings = get_settings()
    api_key, base_url, default_model = get_text_llm_config()
    model = settings.QWEN_TRANSLATION_MODEL

    all_ratings = dict(existing_scores or {})

    # 找出需要打分的词
    words_to_rate = [w for w in candidate_words if w not in all_ratings]
    already_have = len(candidate_words) - len(words_to_rate)

    print(f"\n{'='*60}")
    print(f"情感词典构建 v3")
    print(f"候选词数: {len(candidate_words)}")
    print(f"已有评分: {already_have}")
    print(f"需调用 API: {len(words_to_rate)}")
    print(f"模型: {model}")
    print(f"批次大小: {batch_size}")
    print(f"{'='*60}\n")

    if not words_to_rate:
        print("所有词已有评分，无需调用 API。")
    else:
        # 分批处理
        batches = [words_to_rate[i:i+batch_size] for i in range(0, len(words_to_rate), batch_size)]
        print(f"分 {len(batches)} 批处理\n")

        failed_words = []

        for i, batch in enumerate(batches):
            print(f"[{i+1}/{len(batches)}] 评分中...", end="", flush=True)
            try:
                ratings = await rate_words_batch(batch, api_key, base_url, model)
                all_ratings.update(ratings)
                print(f" [OK] 收到 {len(ratings)} 个评分")
            except Exception as e:
                print(f" [FAIL] 失败: {e}")
                failed_words.extend(batch)

            # 避免 API 限流
            if i < len(batches) - 1:
                await asyncio.sleep(1)

        # 处理失败的词（重试）
        if failed_words:
            print(f"\n重试 {len(failed_words)} 个失败的词...")
            for word in failed_words:
                try:
                    ratings = await rate_words_batch([word], api_key, base_url, model)
                    all_ratings.update(ratings)
                    print(f"  [OK] {word}: {ratings.get(word, '?')}")
                except Exception as e:
                    print(f"  [FAIL] {word}: {e}")
                    all_ratings[word] = 0  # 默认中性

    # 构建完整词典（含来源标记）
    lexicon = {
        "version": "3.0",
        "generated_at": datetime.now().isoformat(),
        "method": "llm_rating + fccpsl",
        "model": model,
        "total_words": len(all_ratings),
        "entries": {}
    }

    for word in sorted(all_ratings.keys()):
        score = all_ratings[word]
        # 判断来源
        if word in (existing_scores or {}):
            source = "llm_rated"
        else:
            source = "llm_rated_v3"

        lexicon["entries"][word] = {
            "score": score,
            "category": _classification_label(score),
            "source": source
        }

    # 保存
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(lexicon, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*60}")
    print(f"词典构建完成")
    print(f"总词数: {len(lexicon['entries'])}")
    print(f"输出: {output_path}")
    print(f"{'='*60}\n")

    # 打印统计
    categories = {}
    sources = {}
    for entry in lexicon["entries"].values():
        cat = entry["category"]
        categories[cat] = categories.get(cat, 0) + 1
        src = entry["source"]
        sources[src] = sources.get(src, 0) + 1
    print("分类统计:")
    for cat, count in sorted(categories.items()):
        print(f"  {cat}: {count}")
    print("\n来源统计:")
    for src, count in sorted(sources.items()):
        print(f"  {src}: {count}")

    return lexicon


def main():
    parser = argparse.ArgumentParser(description="情感词典构建脚本 v3")
    parser.add_argument("--output", type=str,
                       default="backend/app/services/emotion_lexicon_v3.json",
                       help="输出路径")
    parser.add_argument("--batch-size", type=int, default=20, help="每批词数")
    parser.add_argument("--words-file", type=str,
                       default="backend/scripts/candidate_words_v3.json",
                       help="候选词文件（v3 格式）")
    parser.add_argument("--existing-lexicon", type=str,
                       default="backend/app/services/emotion_lexicon.json",
                       help="现有词库路径（已有评分不再重复调用 API）")

    args = parser.parse_args()

    # 加载候选词
    with open(args.words_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    # v3 格式: words 是对象列表，提取 word 字段
    if isinstance(data.get('words'), list) and len(data['words']) > 0 and isinstance(data['words'][0], dict):
        words = [w['word'] for w in data['words']]
    else:
        words = data['words']

    print(f"候选词文件: {args.words_file}")
    print(f"候选词数: {len(words)}")

    # 加载已有评分
    existing_scores = load_existing_scores(args.existing_lexicon)

    asyncio.run(build_lexicon(words, args.output, args.batch_size, existing_scores))


if __name__ == "__main__":
    main()
