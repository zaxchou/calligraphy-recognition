"""
题跋艺术数据库综合分析 AI 总结服务
使用 Qwen3.6 基于统计数据生成专业学术洞察
支持多画家，根据画家名字自动选择对应的背景上下文
"""

import os
import httpx
from typing import Optional, Dict, Any
from pydantic import BaseModel

from app.core.config import get_settings
from app.services.artist_context_registry import get_artist_context, get_artist_display_name


class SummaryResult(BaseModel):
    """AI 总结结果"""
    success: bool
    summary: str = ""
    error: Optional[str] = None

# 学术风格分析提示词（叙事驱动版）
SUMMARY_PROMPT = """你是一位中国古代书画研究学者，请基于下列{artist_name}题跋数据统计表，结合其生平背景，撰写一段有温度、有洞见的学术性分析。

## 五大主题分类（方便你理解数据）
1. 记录创作信息（纪年、落款、赠予）
2. 即景寄兴与抒怀（感怀、寄兴、观赏）
3. 讽喻社会与民生（民、吏、官、税、租）
4. 阐述画理画法（笔、墨、水、法、师）
5. 世俗祈愿与谐趣（笑、戏、娱、福、寿）

## 数据字段说明
- period_stats: 各时期统计 [时期, 数量, 平均字数, 最大字数, 最小字数, 平均词数]
- theme_distribution: 主题分布 [时期, 主题名, 计数, 百分比]
- sentiment_distribution: 情感分布 [情感极性(积极/消极/中性), 时期, 计数, 百分比]
- layout_form_distribution: 布局形式分布 [形式名称, 计数, 百分比]（如：边角规整式、侵入画位式、穿插式等）
- feature_word_stats: 特征词统计 [维度, 词汇, 计数, 时期]
- total_count: 总作品数
- correlation: 内容-形式关联分析 [卡方值, p值, 显著性]

## 写作策略
**不要写成"数据分析报告"，要写成一个懂画的人给你讲故事。**

请按以下顺序，用3-4个故事性段落来组织你的分析：
1. 先找一个最让你意外的数据发现，以此开篇——比如"晚期题跋变长，但你猜最长的一幅写的是什么情境？"
2. 结合{artist_name}的生平轨迹，解释这个发现——把数据和他的命运转折点对应起来
3. 指出1-2个值得深究的规律或矛盾——比如"他嘴上说归隐，题跋里却时不时冒出一股不甘心"
4. 留一个开放性问题，让读者继续想下去

**行文要求：**
- 禁止使用"研究表明""数据显示""通过上述分析""综上所述"等套话
- 禁止使用"首先、其次、最后、总体而言"等僵硬过渡词
- 允许使用"更有意思的是""这背后其实在说""你可能想不到的是"等口语化连接
- 每个发现都必须引用具体数字（几幅、百分之几、哪个时期）
- 字数控制在500-600字，直接写正文，不需要 markdown

## {artist_name}生平背景
{artist_context}

## 统计数据
{stats_data}

好，开始写："""


def build_stats_summary(stats_data: Dict[str, Any], corr_data: Optional[Dict[str, Any]] = None) -> str:
    """
    将统计数据构建为适合 LLM 读取的文本格式
    """
    lines = []

    # 总体统计
    lines.append(f"【总体规模】总作品数：{stats_data.get('total_count', 0)} 幅")

    # 分期统计
    period_stats = stats_data.get('period_stats', [])
    if period_stats:
        lines.append("\n【分期统计】")
        for p in period_stats:
            lines.append(
                f"  {p.get('period', '未知')}：{p.get('count', 0)}幅，"
                f"平均字数 {p.get('avg_char_count', 0)}，"
                f"平均词数 {p.get('avg_word_count', 0)}"
            )

    # 主题分布（总体）
    theme_dist = stats_data.get('theme_distribution', [])
    if theme_dist:
        lines.append("\n【主题分布（整体）】")
        # 按主题汇总
        theme_totals = {}
        for item in theme_dist:
            name = item.get('theme_name', '未知')
            theme_totals[name] = theme_totals.get(name, 0) + item.get('count', 0)
        for name, count in sorted(theme_totals.items(), key=lambda x: -x[1]):
            pct = count / sum(theme_totals.values()) * 100 if theme_totals else 0
            lines.append(f"  {name}：{count}次（{pct:.1f}%）")

    # 情感分布（总体）
    sent_dist = stats_data.get('sentiment_distribution', [])
    if sent_dist:
        lines.append("\n【情感极性分布（整体）】")
        sent_totals = {}
        for item in sent_dist:
            pol = item.get('polarity', '未知')
            sent_totals[pol] = sent_totals.get(pol, 0) + item.get('count', 0)
        total_sent = sum(sent_totals.values())
        for pol in ['积极', '消极', '中性']:
            en_map = {'积极': 'positive', '消极': 'negative', '中性': 'neutral'}
            en_key = en_map.get(pol, pol)
            count = sent_totals.get(en_key, 0)
            pct = count / total_sent * 100 if total_sent else 0
            lines.append(f"  {pol}：{count}次（{pct:.1f}%）")

    # 布局形式分布
    form_dist = stats_data.get('layout_form_distribution', [])
    if form_dist:
        lines.append("\n【布局形式分布（总体）】")
        for item in form_dist:
            name = item.get('form_name', '未知')
            count = item.get('count', 0)
            pct = item.get('percentage', 0)
            lines.append(f"  {name}：{count}次（{pct:.1f}%）")

    # 特征词（取每个维度 Top5）
    feat_stats = stats_data.get('feature_word_stats', [])
    if feat_stats:
        lines.append("\n【高频特征词】")
        # 按维度分组
        dim_words = {}
        for item in feat_stats:
            dim = item.get('dimension', '其他')
            word = item.get('word', '')
            cnt = item.get('count', 0)
            if dim not in dim_words:
                dim_words[dim] = []
            dim_words[dim].append((word, cnt))
        # 每维度取 Top5
        dim_labels = {
            'core_arts': '核心艺术理念',
            'emotion': '情感心境',
            'social': '社会民生',
            'spacetime': '时空人物',
            'philosophy': '哲学审美',
        }
        for dim, words_cnts in dim_words.items():
            top5 = sorted(words_cnts, key=lambda x: -x[1])[:5]
            dim_name = dim_labels.get(dim, dim)
            words_str = '、'.join([f"{w}({c}次)" for w, c in top5])
            lines.append(f"  {dim_name}：{words_str}")

    # 关联分析
    if corr_data:
        chi2 = corr_data.get('chi2_statistic', 0)
        p_val = corr_data.get('p_value', 1)
        sig = corr_data.get('significant', False)
        highly = corr_data.get('highly_significant', False)
        lines.append("\n【内容-形式关联（卡方检验）】")
        lines.append(f"  χ²={chi2:.3f}，p={p_val:.4f}，{'显著' if sig else '不显著'}{'（高度显著）' if highly else ''}")

    return '\n'.join(lines)


async def generate_summary(stats_data: Dict[str, Any], corr_data: Optional[Dict[str, Any]] = None, artist: str = "李鱓") -> SummaryResult:
    """
    基于统计数据调用 Qwen-plus 生成有洞见的叙事性总结
    
    Args:
        stats_data: 统计数据
        corr_data: 关联数据
        artist: 画家名字，用于选择对应的背景上下文
    """
    settings = get_settings()
    api_key = settings.QWEN_API_KEY
    model = settings.QWEN_INSIGHT_MODEL
    base_url = settings.QWEN_BASE_URL

    if not api_key:
        return SummaryResult(success=False, error="未配置 QWEN_API_KEY")
    
    # 获取画家背景上下文
    artist_context = get_artist_context(artist)
    artist_display_name = get_artist_display_name(artist)

    # 构建统计数据文本
    stats_text = build_stats_summary(stats_data, corr_data)

    # 填充提示词（注入生平上下文）
    prompt = SUMMARY_PROMPT.format(
        artist_name=artist_display_name,
        artist_context=artist_context,
        stats_data=stats_text,
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
                        {"role": "user", "content": prompt}
                    ],
                    "max_tokens": 2000,
                    "temperature": 0.7,
                    "enable_thinking": settings.QWEN_THINKING_ENABLED
                }
            )
            response.raise_for_status()
            result = response.json()
            content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
            return SummaryResult(success=True, summary=content.strip())

    except httpx.HTTPStatusError as e:
        return SummaryResult(success=False, error=f"API调用失败: {e.response.status_code}")
    except Exception as e:
        return SummaryResult(success=False, error=str(e))
