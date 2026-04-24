# -*- coding: utf-8 -*-
"""
题跋艺术多模态数据库深度洞察分析服务
使用 Qwen3.6 基于统计数据生成学术突破性综合洞察报告
支持多画家，根据画家名字自动选择对应的背景上下文
"""

import os
import httpx
from typing import Optional, Dict, Any, List
from pydantic import BaseModel
from collections import defaultdict

from app.core.config import get_settings
from app.services.artist_context_registry import get_artist_context, get_artist_display_name


class InsightResult(BaseModel):
    success: bool
    report: str = ""
    sections: Optional[Dict[str, str]] = None
    error: Optional[str] = None


# =============================================================================
# 提示词构建
# =============================================================================

INSIGHT_SYSTEM_PROMPT = """你是一位精通中国艺术史、书画鉴定与计算人文的交叉领域专家。你对{artist_name}的艺术生涯与题跋风格演变有深入研究。你的分析风格是：用具体作品讲故事，从数据中发现有温度的艺术史洞察。"""

INSIGHT_USER_PROMPT_TEMPLATE = """## 角色
你是一位精通中国艺术史、书画鉴定与计算人文的交叉领域专家。你对{artist_name}的艺术生涯与题跋风格演变有深入研究。你的分析风格是：用具体作品讲故事，从数据中发现有温度的艺术史洞察。

## {artist_name}生平背景（重要参考）
{artist_context}

## 数据说明
你将基于以下结构化数据表进行分析。所有论断必须引用具体数据。

### A. 基础统计
总作品数：{total_count}幅

分期统计：
{period_stats}

各作品面积数据（题跋面积占比、绘画面积占比、留白面积占比）：
{area_stats}

### B. 题跋文本与语义数据
主题分布（按时期）：
{theme_distribution}

情感分布（按时期）：
{sentiment_distribution}

情感极性总体：积极 {pos_count}次 / 消极 {neg_count}次 / 中性 {neu_count}次

高频特征词（按维度）：
{feature_words}

典型题跋原文示例（附白话翻译）：
{典型题跋}

### C. 空间量化数据
题跋空间分布类型频率：
{layout_form_distribution}

位置分布（出现频次）：
{position_distribution}

### D. 印章数据
印章内容汇总：
{seal_data}

### E. 尺寸统计
作品尺寸分布（高度）：
{size_distribution}

分期平均尺寸：
{period_size_distribution}

### F. 内容-形式关联
卡方检验结果：χ²={chi2:.3f}，p={p_value:.4f}，{'显著' if significant else '不显著'}

侵入式题跋相关数据：
{invasive_data}

### G. 画材/题材标签统计
高频画材标签（从作品标题和AI分析中提取）：
{material_tags}

画材×主题交叉分析：
{material_theme_cross}

画材×时期演变：
{material_period_cross}

## 分析策略

**不要写成教科书式的四章节分析。要像一个人给你讲他读这批数据时发现的故事。**

请按以下三幕结构来组织你的报告：

---

### 【第一幕：数据中发现】（约400字）

从数据中找出3-5个"反直觉"或"有意思"的发现，每个发现用一句话总结，然后立即给出数字证据。

格式：「发现 + 数字 + 简评」

例如：
- "{artist_name}的讽喻并不少见"——在全部{n}幅作品中，有{x}幅被划为社会讽喻主题，占比超过xx%，这个数字打破了他"以俗为雅"只写生活小事的印象
- "题跋面积在晚期反而缩小"——晚期{n}幅作品的题跋面积均值仅为{xx}%，而中期为{xx}%，说明他越到晚年越"惜墨如金"……

---

### 【第二幕：用作品讲故事】（约600字）

从中选2个最有洞见的发现，每个配一个具体作品的故事。

每个故事结构：
「作品名 + 创作时间 + 背景 + 题跋内容摘要 + 数据印证」

结合{artist_name}的生平，解释为什么这个作品会出现这样的题跋风格。引用具体数字说明这个作品的数据特征在同期中处于什么位置。

---

### 【第三幕：规律与追问】（约300字）

综合以上分析，提出：
1. {artist_name}题跋艺术的"数据指纹"——3个最核心的数字特征
2. 一个还没有答案的开放性问题——基于现有数据值得进一步研究的方向
3. 针对一个常见认知偏差的数据纠正（比如"{artist_name}题跋缺乏讽喻"的误解）

---

## 输出格式要求

直接写正文，不需要 markdown 标题。
每段必须包含具体数字引用（几幅、百分之几、哪个时期、哪个数值）。
行文禁止使用"研究表明""通过上述分析""综上所述"，允许"更有意思的是""这背后其实""你可能没想到的是"等自然连接。
总字数约1200-1500字。

{typical_examples}

好，开始写你的数据洞察报告："""


# =============================================================================
# 数据构建函数
# =============================================================================

def build_period_stats(stats_data: Dict[str, Any]) -> str:
    lines = []
    for p in stats_data.get('period_stats', []):
        lines.append(
            f"  {p.get('period', '未知')}：{p.get('count', 0)}幅，"
            f"平均字数 {p.get('avg_char_count', 0)}，最大 {p.get('max_char_count', 0)}，"
            f"平均词数 {p.get('avg_word_count', 0)}"
        )
    return '\n'.join(lines) if lines else "（暂无数据）"


def build_area_stats(records: List[Dict]) -> str:
    if not records:
        return "（暂无面积数据）"
    period_areas = defaultdict(list)
    for r in records:
        if r.get('period_phase') and r.get('inscription_percent') is not None:
            period_areas[r['period_phase']].append(r['inscription_percent'])

    lines = []
    for phase in ['早期', '中期', '晚期', '年代不详', '未分期']:
        vals = period_areas.get(phase, [])
        if vals:
            avg = sum(vals) / len(vals)
            lines.append(f"  {phase}：{len(vals)}条记录，平均题跋占比 {avg:.1f}%，范围 {min(vals):.1f}%-{max(vals):.1f}%")
    return '\n'.join(lines) if lines else "（暂无面积数据）"


def build_theme_distribution(stats_data: Dict[str, Any]) -> str:
    dist = stats_data.get('theme_distribution', [])
    if not dist:
        return "（暂无主题数据）"

    # 按(时期,主题)聚合
    by_period = defaultdict(lambda: defaultdict(int))
    period_totals = defaultdict(int)
    for item in dist:
        by_period[item['period']][item['theme_name']] += item['count']
        period_totals[item['period']] += item['count']

    lines = []
    for period in ['早期', '中期', '晚期', '年代不详', '未分期']:
        themes = by_period.get(period, {})
        total = period_totals.get(period, 0)
        if not themes:
            continue
        parts = [f"{t}({c}次，{c/max(total,1)*100:.0f}%)" for t, c in sorted(themes.items(), key=lambda x: -x[1])]
        lines.append(f"  {period}（{total}条）：{' / '.join(parts)}")
    return '\n'.join(lines) if lines else "（暂无主题数据）"


def build_sentiment_distribution(stats_data: Dict[str, Any]) -> str:
    dist = stats_data.get('sentiment_distribution', [])
    if not dist:
        return "（暂无情感数据）"

    by_period = defaultdict(lambda: defaultdict(int))
    period_totals = defaultdict(int)
    for item in dist:
        by_period[item['period']][item['polarity']] += item['count']
        period_totals[item['period']] += item['count']

    pol_labels = {'positive': '积极', 'negative': '消极', 'neutral': '中性'}
    lines = []
    for period in ['早期', '中期', '晚期', '年代不详', '未分期']:
        sents = by_period.get(period, {})
        total = period_totals.get(period, 0)
        if not sents:
            continue
        parts = [f"{pol_labels.get(p,p)}({c}次)" for p, c in sents.items()]
        lines.append(f"  {period}（{total}条）：{' / '.join(parts)}")
    return '\n'.join(lines) if lines else "（暂无情感数据）"


def build_feature_words(stats_data: Dict[str, Any]) -> str:
    feat = stats_data.get('feature_word_stats', [])
    if not feat:
        return "（暂无特征词数据）"

    dim_labels = {
        'core_arts': '核心艺术理念',
        'emotion': '情感心境',
        'social': '社会民生',
        'spacetime': '时空人物',
        'philosophy': '哲学审美',
    }

    by_dim = defaultdict(list)
    for item in feat:
        dim = dim_labels.get(item['dimension'], item['dimension'])
        by_dim[dim].append((item['word'], item['count']))

    lines = []
    for dim, words_cnts in by_dim.items():
        top5 = sorted(words_cnts, key=lambda x: -x[1])[:6]
        lines.append(f"  {dim}：{', '.join([f'{w}({c}次)' for w, c in top5])}")
    return '\n'.join(lines) if lines else "（暂无特征词数据）"


def build_layout_form_distribution(stats_data: Dict[str, Any]) -> str:
    dist = stats_data.get('layout_form_distribution', [])
    if not dist:
        return "（暂无布局形式数据）"
    lines = [f"  {d['form_name']}：{d['count']}次（{d['percentage']:.1f}%）" for d in dist]
    return '\n'.join(lines)


def build_seal_data(records: List[Dict]) -> str:
    seals = [r.get('seal_content', '') for r in records if r.get('seal_content')]
    if not seals:
        return "（暂无印章数据）"
    # 简单词频统计
    seal_words = defaultdict(int)
    for s in seals:
        parts = s.replace('作者印：', '').replace('鉴藏印：', '').split('、')
        for p in parts:
            p = p.strip()
            if p:
                seal_words[p] += 1
    top = sorted(seal_words.items(), key=lambda x: -x[1])[:20]
    lines = [f"  {w}：{c}次" for w, c in top]
    return '\n'.join(lines) if lines else "（暂无印章数据）"


def build_typical_examples(records: List[Dict], n: int = 6) -> str:
    """选取各时期、各主题的典型题跋示例"""
    examples = []
    # 按时期和主题各选一个
    seen = set()
    for r in records:
        period = r.get('period_phase', '未分期')
        ca = r.get('content_analysis')
        themes = []
        if ca:
            themes = [t.get('name') for t in ca.get('themes', [])]
        key = f"{period}:{','.join(themes)}"
        if key not in seen and r.get('inscription_content'):
            seen.add(key)
            year = r.get('year', '?')
            content = r.get('inscription_content', '')[:60]
            modern = (r.get('inscription_modern') or '')[:60]
            themes_str = '、'.join(themes) if themes else '未知'
            polarity = ca.get('sentiment', {}).get('polarity', '?') if ca else '?'
            ins_pct = r.get('inscription_percent')
            ins_pct_str = f"，题跋面积{ins_pct:.1f}%" if ins_pct is not None else ""
            examples.append(
                f"  《{r.get('title', '无名')}》（{year}年，{period}，主题：{themes_str}，情感：{polarity}{ins_pct_str}）\n"
                f"    原文：{content}\n    翻译：{modern}"
            )
        if len(examples) >= n:
            break
    return '\n'.join(examples) if examples else "（暂无典型示例）"


def build_position_distribution(records: List[Dict]) -> str:
    positions = defaultdict(int)
    for r in records:
        pa = r.get('position_analysis')
        if pa and isinstance(pa, dict):
            pos = pa.get('position', '未知')
            positions[pos] += 1
    if not positions:
        return "（暂无位置数据）"
    lines = [f"  {p}：{c}次" for p, c in sorted(positions.items(), key=lambda x: -x[1])]
    return '\n'.join(lines)


def build_invasive_data(corr_data: Optional[Dict[str, Any]]) -> str:
    if not corr_data:
        return "（暂无关联数据）"
    inv = corr_data.get('invasive_analysis', {})
    items = inv.get('invasive_items', [])
    if not items:
        return "（暂无侵入式分析数据）"
    lines = [f"  {it.get('title','无名')}：主题={it.get('theme','?')}，情感={it.get('sentiment','?')}，题跋占比={it.get('inscription_percent','?')}%" for it in items[:5]]
    return '\n'.join(lines)


def build_material_tags(records: List[Dict]) -> str:
    """构建画材标签统计"""
    if not records:
        return "（暂无画材标签数据）"
    
    tag_counts = defaultdict(int)
    for r in records:
        tags_str = r.get('material_tags', '')
        if tags_str:
            for tag in tags_str.split(','):
                tag = tag.strip()
                if tag:
                    tag_counts[tag] += 1
    
    if not tag_counts:
        return "（暂无画材标签数据）"
    
    # 取前15个高频标签
    top_tags = sorted(tag_counts.items(), key=lambda x: -x[1])[:15]
    total = sum(tag_counts.values())
    lines = [f"  {tag}：{count}次（{count/total*100:.1f}%）" for tag, count in top_tags]
    return '\n'.join(lines)


def build_material_theme_cross(records: List[Dict]) -> str:
    """构建画材×主题交叉分析"""
    if not records:
        return "（暂无交叉数据）"
    
    # 统计每个画材对应的主题分布
    material_themes = defaultdict(lambda: defaultdict(int))
    for r in records:
        tags_str = r.get('material_tags', '')
        if not tags_str:
            continue
        
        # 获取主题
        ca = r.get('content_analysis')
        themes = []
        if ca:
            themes = [t.get('name') for t in ca.get('themes', [])]
        
        for tag in tags_str.split(','):
            tag = tag.strip()
            if tag:
                for theme in themes:
                    material_themes[tag][theme] += 1
    
    if not material_themes:
        return "（暂无交叉数据）"
    
    # 取前8个高频画材，展示其主题分布
    top_materials = sorted(material_themes.keys(), 
                         key=lambda x: sum(material_themes[x].values()), 
                         reverse=True)[:8]
    
    lines = []
    for material in top_materials:
        theme_dist = material_themes[material]
        total = sum(theme_dist.values())
        top_themes = sorted(theme_dist.items(), key=lambda x: -x[1])[:3]
        theme_str = '、'.join([f"{t}({c}次)" for t, c in top_themes])
        lines.append(f"  {material}（共{total}次）：主要主题→{theme_str}")
    
    return '\n'.join(lines)


def build_material_period_cross(records: List[Dict]) -> str:
    """构建画材×时期演变分析"""
    if not records:
        return "（暂无交叉数据）"
    
    # 统计每个画材在各时期的分布
    material_periods = defaultdict(lambda: defaultdict(int))
    for r in records:
        tags_str = r.get('material_tags', '')
        if not tags_str:
            continue
        
        period = r.get('period_phase', '未分期')
        for tag in tags_str.split(','):
            tag = tag.strip()
            if tag:
                material_periods[tag][period] += 1
    
    if not material_periods:
        return "（暂无交叉数据）"
    
    # 取前6个高频画材，展示其时期分布
    top_materials = sorted(material_periods.keys(),
                         key=lambda x: sum(material_periods[x].values()),
                         reverse=True)[:6]
    
    lines = []
    periods = ['早期', '中期', '晚期', '年代不详']
    for material in top_materials:
        period_dist = material_periods[material]
        total = sum(period_dist.values())
        period_str = ' → '.join([f"{p}:{period_dist.get(p, 0)}次" for p in periods])
        lines.append(f"  {material}（共{total}次）：{period_str}")
    
    return '\n'.join(lines)


def build_size_distribution(records: List[Dict]) -> str:
    """构建尺寸分布统计"""
    if not records:
        return "（暂无尺寸数据）"
    
    size_counts = defaultdict(int)
    total = 0
    for r in records:
        h = r.get('artwork_height_cm')
        if h:
            total += 1
            if h < 70:
                size_counts["小幅"] += 1
            elif h <= 150:
                size_counts["中幅"] += 1
            else:
                size_counts["大幅"] += 1
    
    if total == 0:
        return "（暂无尺寸数据）"
    
    lines = []
    for cat in ["小幅", "中幅", "大幅"]:
        cnt = size_counts.get(cat, 0)
        pct = cnt / total * 100 if total > 0 else 0
        lines.append(f"  {cat}：{cnt}次（{pct:.1f}%）")
    
    return '\n'.join(lines)


def build_period_size_distribution(records: List[Dict]) -> str:
    """构建分期尺寸统计"""
    if not records:
        return "（暂无尺寸数据）"
    
    period_sizes = defaultdict(lambda: {"heights": [], "widths": [], "count": 0})
    for r in records:
        period = r.get('period_phase', '未分期')
        h = r.get('artwork_height_cm')
        w = r.get('artwork_width_cm')
        if h:
            period_sizes[period]["heights"].append(h)
            period_sizes[period]["count"] += 1
        if w:
            period_sizes[period]["widths"].append(w)
    
    if not period_sizes:
        return "（暂无尺寸数据）"
    
    lines = []
    for period in ['早期', '中期', '晚期', '年代不详']:
        if period not in period_sizes:
            continue
        data = period_sizes[period]
        avg_h = sum(data["heights"]) / len(data["heights"]) if data["heights"] else 0
        avg_w = sum(data["widths"]) / len(data["widths"]) if data["widths"] else 0
        lines.append(f"  {period}：{data['count']}条，平均高度{avg_h:.1f}cm，平均宽度{avg_w:.1f}cm")
    
    return '\n'.join(lines) if lines else "（暂无尺寸数据）"


# =============================================================================
# 主函数
# =============================================================================

async def generate_insight(
    stats_data: Dict[str, Any],
    corr_data: Optional[Dict[str, Any]] = None,
    records: Optional[List[Dict]] = None,
    artist: str = "李鱓",
) -> InsightResult:
    """
    基于统计数据和原始记录生成深度洞察报告
    
    Args:
        stats_data: 统计数据
        corr_data: 关联数据
        records: 原始记录
        artist: 画家名字，用于选择对应的背景上下文
    """
    settings = get_settings()
    api_key = settings.QWEN_API_KEY
    model = settings.QWEN_INSIGHT_MODEL
    base_url = settings.QWEN_BASE_URL

    if not api_key:
        return InsightResult(success=False, error="未配置 QWEN_API_KEY")
    
    # 获取画家背景上下文
    artist_context = get_artist_context(artist)
    artist_display_name = get_artist_display_name(artist)

    # 聚合情感计数
    sent_dist = stats_data.get('sentiment_distribution', [])
    pos_count = sum(it['count'] for it in sent_dist if it.get('polarity') == 'positive')
    neg_count = sum(it['count'] for it in sent_dist if it.get('polarity') == 'negative')
    neu_count = sum(it['count'] for it in sent_dist if it.get('polarity') == 'neutral')

    # 整理原始记录（如果有的话）
    recs = records or []

    # 构建各区块数据
    area_stats = build_area_stats(recs)
    theme_dist = build_theme_distribution(stats_data)
    sent_dist_text = build_sentiment_distribution(stats_data)
    feat_words = build_feature_words(stats_data)
    layout_form = build_layout_form_distribution(stats_data)
    seal_data = build_seal_data(recs)
    typical_examples = build_typical_examples(recs)
    position_dist = build_position_distribution(recs)
    
    # 画材标签相关
    material_tags_text = build_material_tags(recs)
    material_theme_cross_text = build_material_theme_cross(recs)
    material_period_cross_text = build_material_period_cross(recs)

    # 尺寸数据相关
    size_distribution_text = build_size_distribution(recs)
    period_size_distribution_text = build_period_size_distribution(recs)

    chi2 = corr_data.get('chi2_statistic', 0) if corr_data else 0
    p_val = corr_data.get('p_value', 1) if corr_data else 1
    sig = corr_data.get('significant', False) if corr_data else False
    inv_data = build_invasive_data(corr_data)

    # 填充模板
    prompt = INSIGHT_USER_PROMPT_TEMPLATE.format(
        artist_name=artist_display_name,
        artist_context=artist_context,
        total_count=stats_data.get('total_count', 0),
        period_stats=build_period_stats(stats_data),
        area_stats=area_stats,
        theme_distribution=theme_dist,
        sentiment_distribution=sent_dist_text,
        pos_count=pos_count,
        neg_count=neg_count,
        neu_count=neu_count,
        feature_words=feat_words,
        typical_examples=typical_examples,
        layout_form_distribution=layout_form,
        position_distribution=position_dist,
        seal_data=seal_data,
        chi2=chi2,
        p_value=p_val,
        significant=sig,
        invasive_data=inv_data,
        material_tags=material_tags_text,
        material_theme_cross=material_theme_cross_text,
        material_period_cross=material_period_cross_text,
        size_distribution=size_distribution_text,
        period_size_distribution=period_size_distribution_text,
    )

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(300.0, connect=30.0)) as client:
            response = await client.post(
                f"{base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": INSIGHT_SYSTEM_PROMPT.format(artist_name=artist_display_name)},
                        {"role": "user", "content": prompt}
                    ],
                    "max_tokens": 4000,
                    "temperature": 0.6
                }
            )
            response.raise_for_status()
            result = response.json()
            content = result.get("choices", [{}])[0].get("message", {}).get("content", "")

            # 解析三幕结构
            sections = {}
            current_section = "其他"
            current_content = []
            for line in content.split('\n'):
                if '【第一幕' in line or line.startswith('### 【第一幕'):
                    if current_content:
                        sections[current_section] = '\n'.join(current_content).strip()
                    current_section = "发现"
                    current_content = []
                elif '【第二幕' in line or line.startswith('### 【第二幕'):
                    if current_content:
                        sections[current_section] = '\n'.join(current_content).strip()
                    current_section = "故事"
                    current_content = []
                elif '【第三幕' in line or line.startswith('### 【第三幕'):
                    if current_content:
                        sections[current_section] = '\n'.join(current_content).strip()
                    current_section = "规律"
                    current_content = []
                else:
                    current_content.append(line)
            if current_content:
                sections[current_section] = '\n'.join(current_content).strip()

            return InsightResult(success=True, report=content.strip(), sections=sections)

    except httpx.HTTPStatusError as e:
        return InsightResult(success=False, error=f"API调用失败: {e.response.status_code}")
    except Exception as e:
        return InsightResult(success=False, error=str(e))