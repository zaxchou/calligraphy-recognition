#!/usr/bin/env python3
"""
构建 v3 情感词典候选词表

来源：
1. FCCPSL（14,368 古典诗歌情感词）— 与实标题跋交叉匹配
2. 现有 emotion_lexicon.json（385 词）
3. 题跋语料中实际出现的高频多字词组

输出：candidate_words_v3.json → 供 build_emotion_lexicon.py 调用 DeepSeek 重新打分
"""
import sqlite3, json, os, re, sys
from collections import Counter, defaultdict

# ── 配置 ──────────────────────────────────────────────
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BACKEND_DIR, 'data', 'calligraphy_new.db')
EXISTING_LEXICON_PATH = os.path.join(BACKEND_DIR, 'app', 'services', 'emotion_lexicon.json')
FCCPSL_PATH = os.path.join(BACKEND_DIR, 'scripts', 'fccpsl_candidates.json')
OUTPUT_PATH = os.path.join(BACKEND_DIR, 'scripts', 'candidate_words_v3.json')
MIN_INSCRIPTION_FREQ = 2  # 至少出现 2 次才收录


def load_inscriptions(db_path: str) -> list:
    """从数据库加载所有题跋文本"""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT inscription_content FROM tubi_analyses WHERE inscription_content IS NOT NULL AND inscription_content != ''")
    texts = [r[0] for r in cur.fetchall()]
    conn.close()
    print(f"  题跋总数: {len(texts)}")
    return texts


def extract_ngrams(texts: list, min_freq: int = 2) -> dict:
    """从题跋中提取 2-4 字高频词组"""
    ngram_counts = Counter()

    for text in texts:
        # 按标点/空格分词
        tokens = re.split(r'[，。！？、；：""''（）\s\n\r]+', text)
        for token in tokens:
            token = token.strip()
            if len(token) < 2:
                continue
            # 2-gram
            for i in range(len(token) - 1):
                ngram_counts[token[i:i+2]] += 1
            # 3-gram
            for i in range(len(token) - 2):
                ngram_counts[token[i:i+3]] += 1
            # 4-gram
            for i in range(len(token) - 3):
                ngram_counts[token[i:i+4]] += 1

    # 过滤低频
    return {word: count for word, count in ngram_counts.items() if count >= min_freq}


def load_existing_lexicon(path: str) -> dict:
    """加载现有情感词典"""
    with open(path, encoding='utf-8') as f:
        data = json.load(f)
    print(f"  现有词库: {data.get('total_words', len(data['entries']))} 词")
    return data['entries']


def load_fccpsl(path: str) -> list:
    """加载 FCCPSL"""
    with open(path, encoding='utf-8') as f:
        data = json.load(f)
    print(f"  FCCPSL: {data['total_words']} 词")
    return data['words']


def build_candidate_list(
    existing_entries: dict,
    fccpsl_words: list,
    ngrams: dict,
    all_texts: list,
) -> dict:
    """构建最终候选词表"""

    existing_words = set(existing_entries.keys())
    existing_scores = {w: v['score'] for w, v in existing_entries.items()}

    # 合并文本用于匹配
    all_text = ' '.join(all_texts)

    # ── 来源 1: 现有词库全部保留 ──
    candidates = {}
    for word in existing_words:
        candidates[word] = {
            'word': word,
            'source': 'existing',
            'original_score': existing_scores.get(word),
            'fccpsl_polarity': None,
            'fccpsl_category': None,
        }

    # ── 来源 2: FCCPSL 中与题跋匹配的词 ──
    fccpsl_word_map = {w['word']: w for w in fccpsl_words}
    fccpsl_matched = set()
    for word, info in fccpsl_word_map.items():
        if len(word) < 2:
            continue  # 单字跳过（现有词库已覆盖）
        if word in candidates:
            continue  # 已收录
        if word in all_text:
            fccpsl_matched.add(word)
            candidates[word] = {
                'word': word,
                'source': 'fccpsl',
                'original_score': None,
                'fccpsl_polarity': info['c1_polarity'],
                'fccpsl_category': info['c3'],
            }

    print(f"  FCCPSL 匹配题跋: {len(fccpsl_matched)} 词")

    # ── 来源 3: 高频 n-gram 中未覆盖的词 ──
    new_from_ngrams = 0
    for word, freq in sorted(ngrams.items(), key=lambda x: -x[1]):
        if word in candidates:
            continue
        # 至少 3 字以上，出现频率高
        if len(word) >= 3 and freq >= 3:
            candidates[word] = {
                'word': word,
                'source': 'ngram',
                'original_score': None,
                'fccpsl_polarity': None,
                'fccpsl_category': None,
            }
            new_from_ngrams += 1

    print(f"  语料高频词组新增: {new_from_ngrams} 词")

    return candidates


def main():
    print("=" * 60)
    print("构建 v3 情感词典候选词表")
    print("=" * 60)

    # 1. 加载数据
    print("\n[1/4] 加载题跋语料...")
    texts = load_inscriptions(DB_PATH)

    print("\n[2/4] 加载现有词典 + FCCPSL...")
    existing = load_existing_lexicon(EXISTING_LEXICON_PATH)
    fccpsl = load_fccpsl(FCCPSL_PATH)

    print("\n[3/4] 提取高频词组...")
    ngrams = extract_ngrams(texts, MIN_INSCRIPTION_FREQ)
    print(f"  高频 2-4 词组合计: {len(ngrams)}")

    print("\n[4/4] 构建候选词表...")
    candidates = build_candidate_list(existing, fccpsl, ngrams, texts)

    # 统计
    by_source = Counter(v['source'] for v in candidates.values())
    print(f"\n  候选词总数: {len(candidates)}")
    print(f"  来源分布:")
    for src, count in by_source.most_common():
        print(f"    {src}: {count}")

    # 按来源分组保存
    output = {
        'version': 'v3',
        'total_words': len(candidates),
        'generated_at': __import__('datetime').datetime.now().isoformat(),
        'source_stats': dict(by_source),
        'words': list(candidates.values()),
    }

    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n保存到: {OUTPUT_PATH}")
    print("完成!")


if __name__ == '__main__':
    main()
