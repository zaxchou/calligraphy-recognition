"""
内容-形式关联分析服务
主题（五大类） × 题跋形式（8种类型）交叉列联表 + 卡方检验
"""
from typing import Dict, List, Any
import json
import numpy as np
from scipy.stats import chi2_contingency

from app.services.inscription_content_analyzer import THEMES
from app.services.inscription_position_analyzer import FORM_TYPES


# 侵入式形式类型名称（重点分析对象）
INVASIVE_FORMS = {"侵入画位/喧宾夺主式"}


def build_contingency_table(records: List[Dict]) -> Dict[str, Any]:
    """
    从记录列表构建主题×形式列联表

    records: [{
        "content_analysis": JSON(str),
        "position_analysis": JSON(str),
        "period_phase": str,
    }, ...]
    """
    # 初始化列联表：themes × form_types
    all_themes = [v["name"] for v in THEMES.values()]
    all_forms = [f["name"] for f in FORM_TYPES]

    # 二维计数字典
    table: Dict[str, Dict[str, int]] = {}
    for theme in all_themes:
        table[theme] = {form: 0 for form in all_forms}

    # 侵入式专项统计
    invasive_stats: Dict[str, Dict[str, int]] = {}
    for theme in all_themes:
        invasive_stats[theme] = {"侵入": 0, "非侵入": 0}

    total_count = 0

    for record in records:
        content_str = record.get("content_analysis")
        position_str = record.get("position_analysis")

        if not content_str or not position_str:
            continue

        try:
            content = json.loads(content_str) if isinstance(content_str, str) else content_str
            position = json.loads(position_str) if isinstance(position_str, str) else position_str
        except:
            continue

        # 提取主题列表
        themes_in_record = []
        for t in content.get("themes", []):
            name = t.get("name", "")
            if name in table:
                themes_in_record.append(name)

        # 提取匹配的形式类型
        form_types_matched = set()
        form_types_data = position.get("form_types", [])
        if isinstance(form_types_data, list):
            for ft in form_types_data:
                if ft.get("matched") and ft.get("name") in all_forms:
                    form_types_matched.add(ft["name"])

        # 侵入式判定
        is_invasive = bool(form_types_matched & INVASIVE_FORMS)

        # 填充列联表（一幅作品×主题可多标签，形式取主要形式）
        if themes_in_record and form_types_matched:
            # 取第一个形式类型作为该作品的主要形式
            primary_form = list(form_types_matched)[0]
            for theme in themes_in_record:
                table[theme][primary_form] += 1

            # 侵入式专项
            for theme in themes_in_record:
                if is_invasive:
                    invasive_stats[theme]["侵入"] += 1
                else:
                    invasive_stats[theme]["非侵入"] += 1

            total_count += 1

    return {
        "table": table,
        "invasive_stats": invasive_stats,
        "total_count": total_count,
        "all_themes": all_themes,
        "all_forms": all_forms,
    }


def chi_square_test(contingency: Dict[str, Any]) -> Dict[str, Any]:
    """
    对列联表执行卡方检验，返回统计结果和显著性标注
    """
    table = contingency["table"]
    all_themes = contingency["all_themes"]
    all_forms = contingency["all_forms"]

    # 构建 numpy 数组（移除全0行和全0列）
    row_labels = []
    matrix = []
    for theme in all_themes:
        row = [table[theme][form] for form in all_forms]
        if sum(row) > 0:
            row_labels.append(theme)
            matrix.append(row)

    if len(matrix) < 2 or len(matrix[0]) < 2:
        return {
            "chi2": 0.0,
            "p_value": 1.0,
            "significant": False,
            "message": "样本量不足，无法进行卡方检验",
            "dof": 0,
        }

    # 移除全0列（某形式在所有主题下计数均为0）
    matrix = np.array(matrix, dtype=float)
    col_sums = matrix.sum(axis=0)
    active_cols = col_sums > 0
    matrix = matrix[:, active_cols]
    active_forms = [f for f, active in zip(all_forms, active_cols) if active]

    if matrix.shape[1] < 2 or matrix.shape[0] < 2:
        return {
            "chi2": 0.0,
            "p_value": 1.0,
            "significant": False,
            "message": "样本量不足，无法进行卡方检验",
            "dof": 0,
        }
    chi2, p_value, dof, expected = chi2_contingency(matrix)

    return {
        "chi2": round(float(chi2), 4),
        "p_value": round(float(p_value), 6),
        "dof": int(dof),
        "significant": bool(p_value < 0.05),
        "highly_significant": bool(p_value < 0.01),
        "expected": expected.tolist(),
    }


def compute_correlation_stats(contingency: Dict[str, Any]) -> List[Dict]:
    """
    计算每对(主题, 形式)的共现强度：支持度、置信度
    """
    table = contingency["table"]
    all_themes = contingency["all_themes"]
    all_forms = contingency["all_forms"]
    total = contingency["total_count"] or 1

    results = []
    for theme in all_themes:
        for form in all_forms:
            observed = table[theme][form]
            support = observed / total if total > 0 else 0
            # 置信度：P(形式|主题)
            theme_total = sum(table[theme].values())
            confidence = observed / theme_total if theme_total > 0 else 0

            results.append({
                "theme": theme,
                "form": form,
                "observed": int(observed),
                "support": round(support, 4),
                "confidence": round(confidence, 4),
            })

    return results


def get_invasive_analysis(contingency: Dict[str, Any]) -> Dict[str, Any]:
    """
    侵入式布局专项分析
    """
    invasive = contingency["invasive_stats"]
    all_themes = contingency["all_themes"]
    total = contingency["total_count"] or 1

    results = []
    for theme in all_themes:
        inv_count = invasive[theme]["侵入"]
        non_inv_count = invasive[theme]["非侵入"]
        theme_total = inv_count + non_inv_count
        inv_rate = inv_count / theme_total if theme_total > 0 else 0

        results.append({
            "theme": theme,
            "invasive_count": inv_count,
            "non_invasive_count": non_inv_count,
            "invasive_rate": round(inv_rate, 4),
        })

    return {
        "invasive_items": results,
        "total": total,
    }
