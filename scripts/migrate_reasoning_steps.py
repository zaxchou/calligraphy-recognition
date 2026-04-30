"""
迁移脚本 v3：给 content_analysis 中的 sentiment 补充 reasoning_steps 字段
遍历 tubi_analyses 表，解析 content_analysis JSON，
对已有 sentiment 但无 reasoning_steps 的记录，补充结构化推导步骤
"""
import sqlite3
import json
import os
import re

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       'backend', 'data', 'calligraphy.db')

def parse_reasoning_text(reasoning_text):
    """
    从旧版 reasoning 文本中解析出各步骤的信息
    格式示例：早期(积极)；画材:清雅/明快；情感分=1.2；身世自况例外：反讽→消极
    """
    steps = []

    # 1. 时期基线
    stage_match = re.search(r'(早期|中期|晚期|年代不详)\((.+?)\)', reasoning_text)
    if stage_match:
        stage = stage_match.group(1)
        baseline = stage_match.group(2)
        if stage == '早期':
            offset = 0.63
        elif stage == '中期':
            offset = -0.19
        elif stage == '晚期':
            offset = -1.26
        else:
            offset = 0
        steps.append({
            'label': '时期基线',
            'detail': f'{stage}作品，情感偏{baseline}',
            'offset': offset,
            'icon': '📅'
        })

    # 2. 画材情感
    paint_match = re.search(r'画材:([^；]+)', reasoning_text)
    if paint_match:
        emotions = paint_match.group(1)
        if any(w in emotions for w in ['清雅', '明快', '淡逸']):
            offset = 0.3
        elif any(w in emotions for w in ['荒寒', '沉郁', '悲凉']):
            offset = -0.3
        else:
            offset = 0
        steps.append({
            'label': '画材情感',
            'detail': f'画面元素→{emotions}',
            'offset': offset,
            'icon': '🎨'
        })

    # 3. 文本情感（从 emotion_score 反推）
    score_match = re.search(r'情感分=([+-]?[\d.]+)', reasoning_text)
    if score_match:
        text_score = float(score_match.group(1))
        steps.append({
            'label': '文本情感',
            'detail': '题跋用词的情感倾向',
            'offset': round(text_score, 2),
            'icon': '📝'
        })

    return steps

def build_reasoning_steps(sentiment, v4_signals=None, v4_special_rules=None):
    """构建结构化的推导步骤"""
    reasoning_text = sentiment.get('reasoning', '')
    polarity = sentiment.get('polarity', 'neutral')
    emotion_score = sentiment.get('emotion_score', 0)

    steps = parse_reasoning_text(reasoning_text)

    # 如果解析失败，至少显示一个默认步骤
    if not steps:
        steps.append({
            'label': '情感分析',
            'detail': reasoning_text or '基于题跋内容分析',
            'offset': round(emotion_score, 2),
            'icon': '📝'
        })

    # 添加最终判定步骤
    polarity_cn = {'positive': '积极', 'negative': '消极', 'neutral': '中性'}.get(polarity, '中性')
    steps.append({
        'label': '最终判定',
        'detail': f'综合得分 {emotion_score:+.2f} → {polarity_cn}',
        'offset': None,
        'icon': '[完成]' if polarity == 'positive' else '[完成]' if polarity == 'negative' else '➖'
    })

    return steps

def migrate():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # 找出所有有 content_analysis 的记录
    cur.execute("SELECT id, image_id, content_analysis FROM tubi_analyses WHERE content_analysis IS NOT NULL")
    rows = cur.fetchall()

    print(f'找到 {len(rows)} 条记录，开始检查...')

    migrated = 0
    skipped = 0

    for row in rows:
        rec_id = row['id']
        image_id = row['image_id']

        try:
            ca = json.loads(row['content_analysis']) if isinstance(row['content_analysis'], str) else row['content_analysis']
        except Exception as e:
            print(f'  [跳过] id={rec_id}, image_id={image_id}，JSON解析失败: {e}')
            skipped += 1
            continue

        if not isinstance(ca, dict) or 'sentiment' not in ca:
            skipped += 1
            continue

        sentiment = ca['sentiment']

        # 已经有 reasoning_steps，跳过
        if isinstance(sentiment, dict) and sentiment.get('reasoning_steps'):
            skipped += 1
            continue

        # 构建 reasoning_steps
        v4_signals = ca.get('v4_signals')
        v4_special_rules = ca.get('v4_special_rules')
        steps = build_reasoning_steps(sentiment, v4_signals, v4_special_rules)

        # 添加到 sentiment
        if isinstance(sentiment, dict):
            sentiment['reasoning_steps'] = steps
            ca['sentiment'] = sentiment

            # 写回数据库
            cur.execute("UPDATE tubi_analyses SET content_analysis = ? WHERE id = ?",
                       (json.dumps(ca, ensure_ascii=False), rec_id))
            migrated += 1

            if migrated % 10 == 0:
                print(f'  已处理 {migrated} 条...')

    conn.commit()
    conn.close()
    print(f'[完成] 迁移完成，共更新 {migrated} 条记录，跳过 {skipped} 条')

if __name__ == '__main__':
    migrate()
