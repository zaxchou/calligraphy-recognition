from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, List, Sequence

from app.modules.pantianshou_composition.analyzer import ImageMetrics
from app.modules.pantianshou_composition.knowledge_ingest import PanRule, parse_pan_rules, _read_text


@dataclass(frozen=True)
class Issue:
    code: str
    title: str
    severity: int
    keywords: List[str]
    hint: str


def derive_issues(metrics: ImageMetrics) -> List[Issue]:
    issues: List[Issue] = []
    blank_pct = int(round(metrics.blank_ratio * 100))
    if metrics.parallel_warning or metrics.dominant_orientation_ratio >= 0.55:
        issues.append(
            Issue(
                code="parallel",
                title="破平行与破板滞",
                severity=80 if metrics.parallel_warning else 55,
                keywords=["平行", "呆板", "破势", "穿插", "角度", "承转", "起结"],
                hint="画面主线条关系偏平行或主方向过于单一，建议用穿插、角度变化与小起结打破。",
            )
        )
    if blank_pct >= 55:
        issues.append(
            Issue(
                code="too_void",
                title="留白过大",
                severity=min(90, blank_pct),
                keywords=["留白", "虚实", "空白", "题款", "印章", "呼应", "补实"],
                hint="留白偏大，建议让留白“成形”，并用题款/印章或小物补实形成呼应。",
            )
        )
    if blank_pct <= 20:
        issues.append(
            Issue(
                code="too_dense",
                title="画面过满",
                severity=min(90, 25 - blank_pct) * 4,
                keywords=["留白", "虚实", "疏密", "透气", "主次", "删繁"],
                hint="画面偏满，建议压缩次要笔触与重复信息，留出透气空隙以强化主次。",
            )
        )
    if metrics.edge_density_std < 0.05:
        issues.append(
            Issue(
                code="flat_rhythm",
                title="疏密节奏偏平",
                severity=60,
                keywords=["疏密", "节奏", "聚散", "密处", "疏处", "对比"],
                hint="疏密分布偏平均，建议密处更聚、疏处更透，形成明确节奏对比。",
            )
        )
    x, y, w, h = metrics.inscription_box
    if w <= 0 or h <= 0:
        issues.append(
            Issue(
                code="inscription",
                title="题款经营不足",
                severity=45,
                keywords=["题款", "印章", "落款", "呼应", "对角", "留白"],
                hint="题款与印章落点需要结合留白重新经营，使辅助元素与主体形成对角或呼应。",
            )
        )
    return issues


def _score_rule(rule: PanRule, issues: Sequence[Issue]) -> float:
    text = " ".join(
        [
            rule.rule_name,
            rule.condition,
            rule.quantitative_standard,
            rule.category_name,
            rule.subcategory_name,
        ]
    )
    hits = 0
    best_sev = 0
    for issue in issues:
        for kw in issue.keywords:
            if kw and kw in text:
                hits += 1
                best_sev = max(best_sev, issue.severity)
                break
    if hits == 0:
        return 0.0
    return hits * 10.0 + float(rule.weight or 0.0) * 100.0 + best_sev * 0.1


def select_rules(pan_md_path: str, metrics: ImageMetrics, limit: int = 12) -> Dict[str, Any]:
    if not os.path.exists(pan_md_path):
        return {"issues": [], "rules": []}
    text = _read_text(pan_md_path)
    rules = parse_pan_rules(text)
    issues = derive_issues(metrics)
    if not issues:
        issues = [
            Issue(
                code="general",
                title="综合推敲",
                severity=30,
                keywords=["开合", "虚实", "疏密", "起结", "呼应"],
                hint="整体关系基本成立，建议围绕开合、虚实、疏密三条主线再做精细推敲。",
            )
        ]
    scored: List[tuple[float, PanRule]] = []
    for r in rules:
        s = _score_rule(r, issues)
        if s > 0:
            scored.append((s, r))
    scored.sort(key=lambda x: x[0], reverse=True)
    picked: List[Dict[str, Any]] = []
    used = set()
    for s, r in scored:
        if r.rule_id in used:
            continue
        used.add(r.rule_id)
        picked.append(
            {
                "rule_id": r.rule_id,
                "rule_name": r.rule_name,
                "category": r.category_name,
                "subcategory": r.subcategory_name,
                "condition": r.condition,
                "quantitative_standard": r.quantitative_standard,
                "weight": r.weight,
                "reference_figures": list(r.reference_figures),
                "relevance": float(s),
            }
        )
        if len(picked) >= limit:
            break
    return {
        "issues": [
            {"code": i.code, "title": i.title, "severity": i.severity, "hint": i.hint} for i in issues
        ],
        "rules": picked,
    }

