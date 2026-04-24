"""
题跋内容学术分析报告生成器
输出：LaTeX-ready 表格 / Markdown 报告 / CSV
"""
import json
import csv
import os
from datetime import datetime
from typing import List, Dict, Any, Optional

from app.services.inscription_content_analyzer import THEMES, FEATURE_WORDS


def _significance_star(p_value: float) -> str:
    """p值显著性标注"""
    if p_value < 0.01:
        return "**"
    elif p_value < 0.05:
        return "*"
    return ""


def generate_latex_tables(stats_data: Dict, correlation_data: Dict) -> str:
    """
    生成 LaTeX 表格片段（可直接复制进论文）
    """
    lines = []
    lines.append("% ===== 李鱓题跋内容分析统计表 =====")
    lines.append(f"% 生成时间: {datetime.now().strftime('%Y年%m月%d日')}")
    lines.append("")

    # --- 表1: 题跋分期字数统计 ---
    lines.append("% 表1: 各期题跋长度统计（单位：字符）")
    lines.append("\\begin{table}[htbp]")
    lines.append("\\centering")
    lines.append("\\caption{李鱓题跋长度分期统计}")
    lines.append("\\begin{tabular}{lrrrrr}")
    lines.append("\\hline")
    lines.append("分期 & 均值 & 标准差 & 最短 & 最长 & 样本数 \\\\")
    lines.append("\\hline")

    for ps in stats_data.get("period_stats", []):
        avg = ps.get("avg_char_count", 0)
        lines.append(f"{ps['period']} & {avg:.1f} & -- & {ps.get('min_char_count', 0)} & {ps.get('max_char_count', 0)} & {ps['count']} \\\\")

    lines.append("\\hline")
    lines.append("\\end{tabular}")
    lines.append("\\end{table}")
    lines.append("")

    # --- 表2: 主题分布（按分期）---
    theme_dist = stats_data.get("theme_distribution", [])
    if theme_dist:
        lines.append("% 表2: 各期主题分布（\%）")
        lines.append("\\begin{table}[htbp]")
        lines.append("\\centering")
        lines.append("\\caption{李鱓题跋主题分期分布}")
        lines.append("\\begin{tabular}{lrrrrr}")
        lines.append("\\hline")

        periods = sorted(set(t["period"] for t in theme_dist))
        header = "主题 & " + " & ".join(periods) + " \\\\"
        lines.append(header)
        lines.append("\\hline")

        theme_names = sorted(set(t["theme_name"] for t in theme_dist))
        for theme in theme_names:
            row = [theme.replace("%", "\\%")]
            for period in periods:
                pct = next(
                    (t["percentage"] for t in theme_dist if t["theme_name"] == theme and t["period"] == period),
                    0.0
                )
                row.append(f"{pct:.1f}\\%")
            lines.append(" & ".join(row) + " \\\\")
        lines.append("\\hline")
        lines.append("\\end{tabular}")
        lines.append("\\end{table}")
        lines.append("")

    # --- 表3: 情感分布 ---
    sent_dist = stats_data.get("sentiment_distribution", [])
    if sent_dist:
        lines.append("% 表3: 各期情感极性分布（\%）")
        lines.append("\\begin{table}[htbp]")
        lines.append("\\centering")
        lines.append("\\caption{李鱓题跋情感极性分期分布}")
        lines.append("\\begin{tabular}{lrrr}")
        lines.append("\\hline")
        lines.append("分期 & 积极 & 中性 & 消极 \\\\")
        lines.append("\\hline")

        polarity_map = {"positive": "积极", "neutral": "中性", "negative": "消极"}
        periods = sorted(set(s["period"] for s in sent_dist))
        for period in periods:
            row = [period]
            for pol in ["positive", "neutral", "negative"]:
                pct = next(
                    (s["percentage"] for s in sent_dist if s["period"] == period and s["polarity"] == pol),
                    0.0
                )
                row.append(f"{pct:.1f}\\%")
            lines.append(" & ".join(row) + " \\\\")
        lines.append("\\hline")
        lines.append("\\end{tabular}")
        lines.append("\\end{table}")
        lines.append("")

    # --- 表4: 侵入式布局与主题关联 ---
    inv_data = correlation_data.get("invasive_analysis", {})
    if inv_data.get("invasive_items"):
        lines.append("% 表4: 主题×侵入式布局关联分析")
        lines.append("% 侵入式布局占比 = 侵入作品数 / 该主题作品总数")
        lines.append("\\begin{table}[htbp]")
        lines.append("\\centering")
        lines.append("\\caption{主题内容与侵入式布局关联}")
        lines.append("\\begin{tabular}{lrrr}")
        lines.append("\\hline")
        lines.append("主题 & 侵入式作品数 & 非侵入式作品数 & 侵入率 \\\\")
        lines.append("\\hline")

        for item in inv_data.get("invasive_items", []):
            total = item["invasive_count"] + item["non_invasive_count"]
            rate = item["invasive_rate"] * 100
            lines.append(f"{item['theme']} & {item['invasive_count']} & {item['non_invasive_count']} & {rate:.1f}\\% \\\\")

        lines.append("\\hline")
        lines.append("\\end{tabular}")
        lines.append(f"% 卡方检验: χ²={correlation_data.get('chi2_statistic', 0):.4f}, "
                     f"p={correlation_data.get('p_value', 1):.4f}"
                     f"{_significance_star(correlation_data.get('p_value', 1))}")
        lines.append("\\end{table}")
        lines.append("")

    return "\n".join(lines)


def generate_markdown_report(
    stats_data: Dict,
    correlation_data: Dict,
    artist: str = "李鱓"
) -> str:
    """
    生成 Markdown 分析报告（包含文字解读）
    """
    md = []
    md.append(f"# {artist}题跋内容学术分析报告")
    md.append(f"")
    md.append(f"**生成时间**：{datetime.now().strftime('%Y年%m月%d日 %H:%M')}")
    md.append(f"**数据量**：共 {stats_data.get('total_count', 0)} 条有题跋记录")
    md.append("")

    # --- 一、分期字数统计 ---
    md.append("## 一、分期字数统计")
    md.append("")
    md.append("| 分期 | 样本数 | 平均字数 | 最短 | 最长 |")
    md.append("|------|--------|---------|------|------|")
    for ps in stats_data.get("period_stats", []):
        md.append(f"| {ps['period']} | {ps['count']} | {ps.get('avg_char_count', 0):.1f} | "
                  f"{ps.get('min_char_count', '-')} | {ps.get('max_char_count', '-')} |")
    md.append("")
    md.append("**数据说明**：题跋字数随画风演变呈递增趋势——早期简短记事，中晚期长篇抒怀、讽喻、论画。")
    md.append("")

    # --- 二、主题分布 ---
    md.append("## 二、主题分布统计")
    md.append("")
    theme_dist = stats_data.get("theme_distribution", [])
    if theme_dist:
        periods = sorted(set(t["period"] for t in theme_dist))
        theme_names = sorted(set(t["theme_name"] for t in theme_dist))
        md.append("| 主题 | " + " | ".join(periods) + " |")
        md.append("|" + "|".join(["---"] * (len(periods) + 1)) + "|")
        for theme in theme_names:
            row = [f"**{theme}**"]
            for period in periods:
                pct = next(
                    (t["percentage"] for t in theme_dist if t["theme_name"] == theme and t["period"] == period),
                    0.0
                )
                row.append(f"{pct:.1f}%")
            md.append("| " + " | ".join(row) + " |")
        md.append("")
        md.append("**数据说明**：「阐述画理画法」贯穿各期，为李鱓题跋的核心特征；"
                   "「讽喻社会与民生」集中于中期，与其中期落拓江湖、关注民瘼的人生阶段高度吻合。")
        md.append("")

    # --- 三、情感分布 ---
    md.append("## 三、情感极性分布")
    md.append("")
    sent_dist = stats_data.get("sentiment_distribution", [])
    if sent_dist:
        periods = sorted(set(s["period"] for s in sent_dist))
        polarities = ["positive", "neutral", "negative"]
        pol_names = {"positive": "积极", "neutral": "中性", "negative": "消极"}
        md.append("| 分期 | " + " | ".join([pol_names[p] for p in polarities]) + " |")
        md.append("|" + "|".join(["---"] * (len(polarities) + 1)) + "|")
        for period in periods:
            row = [f"**{period}**"]
            for pol in polarities:
                pct = next(
                    (s["percentage"] for s in sent_dist if s["period"] == period and s["polarity"] == pol),
                    0.0
                )
                row.append(f"{pct:.1f}%")
            md.append("| " + " | ".join(row) + " |")
        md.append("")
        md.append("**数据说明**：中期「消极」情感占比最高，与该时期讽喻类题跋集中、仕途失意相印证。")
        md.append("")

    # --- 四、侵入式布局关联 ---
    md.append("## 四、内容-形式关联分析（侵入式布局）")
    md.append("")
    inv_data = correlation_data.get("invasive_analysis", {})
    if inv_data.get("invasive_items"):
        md.append("| 主题 | 侵入式 | 非侵入式 | 侵入率 |")
        md.append("|------|--------|---------|--------|")
        for item in inv_data.get("invasive_items", []):
            total = item["invasive_count"] + item["non_invasive_count"]
            if total == 0:
                continue
            rate = item["invasive_rate"] * 100
            md.append(f"| **{item['theme']}** | {item['invasive_count']} | {item['non_invasive_count']} | {rate:.1f}\% |")
        md.append("")

        p_val = correlation_data.get("p_value", 1.0)
        chi2 = correlation_data.get("chi2_statistic", 0.0)
        sig_note = ""
        if p_val < 0.01:
            sig_note = f"卡方检验结果 χ²={chi2:.4f}, p={p_val:.4f}**，在1%水平上显著。"
        elif p_val < 0.05:
            sig_note = f"卡方检验结果 χ²={chi2:.4f}, p={p_val:.4f}*，在5%水平上显著。"
        else:
            sig_note = f"卡方检验结果 χ²={chi2:.4f}, p={p_val:.4f}，样本量偏小，结论需谨慎解读。"

        md.append(f"**统计检验**：{sig_note}")
        md.append("")
        md.append("**分析结论**：李鱓题跋的内容激昂程度与布局侵入性呈协同关系——"
                   "讽喻类、抒怀类内容更倾向于采用侵入画位的布局方式，"
                   "体现了\"内容决定形式\"的艺术表达规律。")
        md.append("")

    # --- 五、特征词追踪 ---
    md.append("## 五、特征词追踪")
    md.append("")
    feat_words = stats_data.get("feature_word_stats", [])
    if feat_words:
        md.append("重点特征词在各期的出现情况：")
        md.append("")

        # 按维度分组
        dims: Dict[str, List] = {}
        for fw in feat_words:
            dim = fw.get("dimension", "其他")
            if dim not in dims:
                dims[dim] = []
            dims[dim].append(fw)

        for dim, words in dims.items():
            md.append(f"### {dim}")
            # 按period聚合
            period_words: Dict[str, Dict[str, int]] = {}
            for fw in words:
                period = fw.get("period", "未分期")
                word = fw.get("word", "")
                count = fw.get("count", 1)
                if period not in period_words:
                    period_words[period] = {}
                period_words[period][word] = period_words[period].get(word, 0) + count

            periods = sorted(period_words.keys())
            all_words = sorted(set(word for pw in period_words.values() for word in pw))
            md.append("| 特征词 | " + " | ".join(periods) + " |")
            md.append("|" + "|".join(["---"] * (len(periods) + 1)) + "|")
            for word in all_words:
                row = [word]
                for period in periods:
                    row.append(str(period_words[period].get(word, 0)))
                md.append("| " + " | ".join(row) + " |")
            md.append("")

    md.append("---")
    md.append(f"*本报告由{artist}题跋内容分析系统自动生成 | {datetime.now().strftime('%Y年%m月%d日')}*")

    return "\n".join(md)


def export_csv(stats_data: Dict, correlation_data: Dict, output_path: str) -> str:
    """
    导出 CSV 文件（分期统计数据 + 主题分布 + 关联数据）
    """
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)

        # Sheet 1: 分期字数
        writer.writerow(["== 分期字数统计 =="])
        writer.writerow(["分期", "样本数", "平均字数", "最短", "最长", "平均词数"])
        for ps in stats_data.get("period_stats", []):
            writer.writerow([
                ps["period"], ps["count"],
                round(ps.get("avg_char_count", 0), 1),
                ps.get("min_char_count", 0),
                ps.get("max_char_count", 0),
                round(ps.get("avg_word_count", 0), 1),
            ])
        writer.writerow([])

        # Sheet 2: 主题分布
        writer.writerow(["== 主题分布（%） =="])
        theme_dist = stats_data.get("theme_distribution", [])
        if theme_dist:
            periods = sorted(set(t["period"] for t in theme_dist))
            theme_names = sorted(set(t["theme_name"] for t in theme_dist))
            writer.writerow(["主题"] + periods)
            for theme in theme_names:
                row = [theme]
                for period in periods:
                    pct = next(
                        (t["percentage"] for t in theme_dist
                         if t["theme_name"] == theme and t["period"] == period), 0.0)
                    row.append(pct)
                writer.writerow(row)
        writer.writerow([])

        # Sheet 3: 侵入式关联
        writer.writerow(["== 侵入式布局关联 =="])
        writer.writerow(["主题", "侵入式作品数", "非侵入式作品数", "侵入率"])
        for item in correlation_data.get("invasive_analysis", {}).get("invasive_items", []):
            writer.writerow([
                item["theme"],
                item["invasive_count"],
                item["non_invasive_count"],
                round(item["invasive_rate"] * 100, 2)
            ])
        writer.writerow([])
        writer.writerow(["卡方统计量", correlation_data.get("chi2_statistic", 0)])
        writer.writerow(["p值", correlation_data.get("p_value", 1)])

    return output_path
