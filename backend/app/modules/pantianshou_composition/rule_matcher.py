from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence

import numpy as np

from app.modules.pantianshou_composition.analyzer import ImageMetrics
from app.modules.pantianshou_composition.composition_cv import AdvancedMetrics
from app.modules.pantianshou_composition.knowledge_ingest import PanRule, parse_pan_rules, load_panplus_rules, _read_text

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Issue:
    code: str
    title: str
    severity: int
    keywords: List[str]
    hint: str
    # Extra data for downstream consumers
    extra: Dict[str, Any] = None

    def __post_init__(self):
        if self.extra is None:
            object.__setattr__(self, "extra", {})


def derive_issues(
    metrics: ImageMetrics,
    adv: Optional[AdvancedMetrics] = None,
) -> List[Issue]:
    """Derive composition issues from basic + advanced CV metrics.

    Returns a list of Issue objects, each with keywords that are matched
    against rule text in rule_matcher._score_rule().
    """
    issues: List[Issue] = []
    blank_pct = int(round(metrics.blank_ratio * 100))
    dense_pct = 100 - blank_pct

    # ------------------------------------------------------------------
    # === LEGACY ISSUES (from original 6 metrics) ===
    # ------------------------------------------------------------------

    # 1. Parallel / stiff
    if metrics.parallel_warning or metrics.dominant_orientation_ratio >= 0.55:
        sev = 80 if metrics.parallel_warning else 55
        issues.append(Issue(
            code="parallel",
            title="破平行与破板滞",
            severity=sev,
            keywords=["平行", "呆板", "破势", "穿插", "角度", "承转", "起结", "等距", "边平行"],
            hint="画面主线条关系偏平行或主方向过于单一，建议用穿插、角度变化与小起结打破。",
        ))

    # 2. Too void
    if blank_pct >= 55:
        issues.append(Issue(
            code="too_void",
            title="留白过大",
            severity=min(90, blank_pct),
            keywords=["留白", "虚实", "空白", "题款", "印章", "呼应", "补实", "虚中有物", "空而不空", "虚中无物", "宁空毋实"],
            hint="留白偏大，建议让留白\"成形\"，并用题款/印章或小物补实形成呼应。",
        ))

    # 3. Too dense
    if blank_pct <= 20:
        issues.append(Issue(
            code="too_dense",
            title="画面过满",
            severity=min(90, (25 - blank_pct) * 4),
            keywords=["留白", "虚实", "疏密", "透气", "主次", "删繁", "实中求虚", "密处留气", "以白破实", "密处透气", "宁空毋实"],
            hint="画面偏满，建议压缩次要笔触与重复信息，留出透气空隙以强化主次。",
        ))

    # 4. Flat rhythm
    if metrics.edge_density_std < 0.05:
        issues.append(Issue(
            code="flat_rhythm",
            title="疏密节奏偏平",
            severity=60,
            keywords=["疏密", "节奏", "聚散", "密处", "疏处", "对比", "大虚小虚", "等距"],
            hint="疏密分布偏平均，建议密处更聚、疏处更透，形成明确节奏对比。",
        ))

    # 5. Inscription missing
    x, y, w, h = metrics.inscription_box
    if w <= 0 or h <= 0:
        issues.append(Issue(
            code="inscription",
            title="题款经营不足",
            severity=45,
            keywords=[
                "题款", "印章", "落款", "呼应", "对角", "留白",
                "款补空白", "穷款", "长款", "款印风格", "款印补充",
                "排比", "款识", "款印配合", "款印", "风格", "一致性",
                "淡墨", "画石", "包石", "避免包石", "长干包短石",
                "石款", "石出边", "石补疏散", "石外露",
            ],
            hint="题款与印章落点需要结合留白重新经营，使辅助元素与主体形成对角或呼应。",
        ))

    # ------------------------------------------------------------------
    # === ADVANCED ISSUES (from composition_cv metrics) ===
    # ------------------------------------------------------------------
    if adv is None:
        return issues

    r = adv.region
    c = adv.crossings
    el = adv.elements
    tr = adv.trends
    tri = adv.triangle
    g = adv.gaps

    # --- Region density issues ---

    # 6. Top/bottom imbalance (avoid头重脚轻)
    if r.top_bot_ratio > 1.5:
        issues.append(Issue(
            code="top_heavy",
            title="头重脚轻",
            severity=int(min(80, 50 + (r.top_bot_ratio - 1.5) * 80)),
            keywords=["头重脚轻", "上下平衡", "重量", "起结", "上部", "下部"],
            hint=f"上部墨色偏重（上/下比={r.top_bot_ratio:.1f}），建议下方加浓或增补元素以平衡。",
            extra={"top_bot_ratio": round(r.top_bot_ratio, 2)},
        ))
    elif r.top_bot_ratio < 0.67:
        issues.append(Issue(
            code="bottom_heavy",
            title="脚重头轻",
            severity=int(min(75, 50 + (0.67 - r.top_bot_ratio) * 80)),
            keywords=["头重脚轻", "上下平衡", "重量", "起结", "上部", "下部"],
            hint=f"下部墨色偏重（上/下比={r.top_bot_ratio:.1f}），建议上方加浓或增补元素以平衡。",
            extra={"top_bot_ratio": round(r.top_bot_ratio, 2)},
        ))

    # 7. Left/right symmetry (avoid对称空白)
    lr = r.left_right_ratio
    if 0.8 <= lr <= 1.25:
        issues.append(Issue(
            code="lr_symmetric",
            title="左右对称倾向",
            severity=55,
            keywords=["对称", "空白", "左虚右实", "右虚左实", "等距", "呆板"],
            hint="左右墨色分布偏对称，建议打破均衡，形成一侧偏虚一侧偏实的布局。",
            extra={"lr_ratio": round(lr, 2)},
        ))

    # 8. Center too heavy (避免蜂腰 - actually middle empty, but center dense is also notable)
    if r.center_vs_avg < 0.4:
        issues.append(Issue(
            code="honeycomb_waist",
            title="蜂腰毛病",
            severity=75,
            keywords=["蜂腰", "中间空虚", "承转", "连贯", "过渡"],
            hint="画面中间区域墨色明显偏少，上下有物中间空，犯了蜂腰毛病，建议在中间区域添加过渡元素。",
            extra={"center_vs_avg": round(r.center_vs_avg, 2)},
        ))

    # 9. Start area too sparse (起处不散)
    # Check corners + edges
    corner_avg = (r.top_left + r.top_right + r.bot_left + r.bot_right) / 4
    center_avg = (r.mid_center + r.top_center + r.bot_center) / 3
    if corner_avg < center_avg * 0.4 and corner_avg < 0.15:
        issues.append(Issue(
            code="start_scattered",
            title="起处偏散",
            severity=65,
            keywords=["起处", "疏散", "起结", "边角", "材料", "补散"],
            hint="画面边角区域墨色偏少，起处感觉疏散，建议在边角起处加竹石或题款填补。",
            extra={"corner_avg": round(corner_avg, 3), "center_avg": round(center_avg, 3)},
        ))

    # 10. Elements touching bottom (元素不触底边)
    if r.bottom_edge_density > 0.3:
        issues.append(Issue(
            code="touching_bottom",
            title="主体触底边",
            severity=50,
            keywords=["底边", "脚部", "画边", "触底", "元素不触底边"],
            hint=f"底部边缘墨色较浓（密度={r.bottom_edge_density:.2f}），主体元素紧贴底边，建议留出底部空间。",
            extra={"bottom_edge_density": round(r.bottom_edge_density, 2)},
        ))

    # --- Line crossing issues ---

    # 11. Too many single-point crossings (避免一点交叉 / 编篱)
    if c.single_point_crossings > 0:
        issues.append(Issue(
            code="single_point_cross",
            title="多线交于一点",
            severity=70,
            keywords=["一点交叉", "交叉", "编篱", "凤眼", "女字"],
            hint=f"存在{c.single_point_crossings}处多线交于一点的构图问题，建议分散交叉点或采用女字形交叉。",
            extra={"single_point_count": c.single_point_crossings},
        ))

    # 12. Too many HV crosses (避免十字交叉)
    if c.horizontal_vertical_crosses >= 3:
        issues.append(Issue(
            code="cross_crossings",
            title="十字形交叉偏多",
            severity=70,
            keywords=["十字交叉", "碍势", "圈势", "气势", "收梢", "十字"],
            hint=f"画面中有{c.horizontal_vertical_crosses}处十字形交叉，会妨碍气势流动，建议调整线条角度避免正交。",
            extra={"hv_crosses": c.horizontal_vertical_crosses},
        ))

    # 13. Too many parallel line pairs
    if c.parallel_line_pairs > el.element_count:
        issues.append(Issue(
            code="many_parallel",
            title="平行线过多",
            severity=int(min(80, 50 + c.parallel_line_pairs * 5)),
            keywords=["平行", "线平行", "边平行", "呆板", "等距", "近树不平行", "芭蕉"],
            hint=f"检测到{c.parallel_line_pairs}对近似平行线，建议调整线条角度增加变化。",
            extra={"parallel_pairs": c.parallel_line_pairs},
        ))

    # --- Element issues ---

    # 14. Too few elements (最少三元素)
    if el.element_count <= 1:
        issues.append(Issue(
            code="too_few_elements",
            title="元素过少",
            severity=75,
            keywords=["最少三元素", "避免单一", "避免成双", "三数原则", "疏密", "元素数量", "款印补充"],
            hint="画面元素过少（仅{0}个），难以形成疏密关系，建议增加画材或利用款印补充为三元素以上。".format(el.element_count),
            extra={"element_count": el.element_count},
        ))
    elif el.element_count == 2:
        issues.append(Issue(
            code="only_two_elements",
            title="仅有两元素",
            severity=60,
            keywords=["避免成双", "三数原则", "疏密", "元素数量", "款印补充", "排比"],
            hint="画面仅两个主要元素，难以形成丰富疏密，建议增加第三元素或款印补充排比。",
            extra={"element_count": 2},
        ))

    # 15. Isolated elements (疏不孤)
    if el.isolated_elements >= 1 and el.element_count >= 3:
        issues.append(Issue(
            code="isolated_element",
            title="疏而成孤",
            severity=65,
            keywords=["疏不孤", "孤", "小组不孤", "孤立", "疏散"],
            hint=f"有{el.isolated_elements}个元素与其他元素距离过远，形成孤立感，建议调整位置使其与主组呼应。",
            extra={"isolated_count": el.isolated_elements},
        ))

    # 16. Evenly spaced (避免等距)
    if el.spacing_uniformity < 0.15 and el.element_count >= 3:
        issues.append(Issue(
            code="evenly_spaced",
            title="元素等距排列",
            severity=60,
            keywords=["等距", "距离有远近", "间距", "呆板", "变化", "疏密"],
            hint="元素间距过于均匀，缺乏远近变化，建议调整部分元素位置打破等距排列。",
            extra={"spacing_uniformity": round(el.spacing_uniformity, 2)},
        ))

    # 16b. Stone enclosure / light ink issues (for FZ-05-01, FZ-05-04)
    if el.element_count >= 3 and el.area_ratio_max_min > 10:
        issues.append(Issue(
            code="size_imbalance",
            title="元素大小悬殊",
            severity=45,
            keywords=["淡墨", "画石", "包石", "避免包石", "石款", "长干包短石", "石出边", "石补疏散"],
            hint="画面元素大小差异悬殊，注意大元素可能包围小元素（长干包短石），建议调整让小元素外露。",
            extra={"area_ratio": round(el.area_ratio_max_min, 1)},
        ))

    # --- Direction trend issues ---

    # 17. Major conflict (楚汉对垒)
    if tr.has_major_conflict:
        issues.append(Issue(
            code="trend_conflict",
            title="气势对冲",
            severity=85,
            keywords=["对冲", "楚汉对垒", "气势", "冲突", "对立", "趋势", "主导趋势", "小势服从"],
            hint="画面存在两个以上强度相近且方向对立的趋势，形成楚汉对垒的局面，建议统一主导方向。",
            extra={"opposing": tr.opposing_trends},
        ))

    # 18. Too horizontal/vertical (避免平板)
    if tr.horizontal_vertical_ratio > 0.6 and tr.diagonal_ratio < 0.3:
        issues.append(Issue(
            code="too_flat_direction",
            title="气势平板",
            severity=60,
            keywords=["平板", "水平", "垂直", "斜势", "气势", "直率", "歪斜取势"],
            hint="画面线条以水平/垂直为主，缺乏斜势，气势偏平板，建议增加斜向元素以增强动感。",
            extra={"hv_ratio": round(tr.horizontal_vertical_ratio, 2), "diag_ratio": round(tr.diagonal_ratio, 2)},
        ))

    # 19. Direction too concentrated (避免分散的反面: 也需要适度集中)
    # Not an issue if concentrated - that's good. Only flag if TOO scattered.
    if tr.dominant_strength < 0.2 and el.element_count >= 3:
        issues.append(Issue(
            code="direction_scattered",
            title="方向分散",
            severity=50,
            keywords=["分散", "气势", "趋势", "主导趋势", "集中"],
            hint="画面线条方向过于分散，缺乏主导趋势，建议统一主要元素的方向感。",
            extra={"dom_strength": round(tr.dominant_strength, 2)},
        ))

    # --- Triangle issues ---

    # 20. Equilateral triangle (避免等边三角形)
    if tri.is_equilateral and tri.has_triangle:
        issues.append(Issue(
            code="equilateral_triangle",
            title="等边三角形布局",
            severity=55,
            keywords=["等边三角形", "三角形", "不等边", "齐而不齐", "呆板"],
            hint="三主元素形成近似等边三角形布局，显得呆板，建议调整为不等边三角形以增加变化。",
            extra={"side_ratio": round(tri.side_ratio_min_max, 2)},
        ))

    # 21. Three points collinear (三点成直线)
    if not tri.has_triangle and tri.collinearity_score < 0.03 and el.element_count >= 3:
        issues.append(Issue(
            code="collinear_points",
            title="三主元素近似共线",
            severity=60,
            keywords=["共线", "直线", "三角形", "三点", "齐而不齐"],
            hint="画面三个主要元素近似排列在一条直线上，缺乏三角构图的变化感。",
            extra={"collinearity": round(tri.collinearity_score, 4)},
        ))

    # --- Dense area gap issues ---

    # 22. Dense area no breathing room (密不闷 / 密处透气)
    if g.dense_area_ratio > 0.3 and g.dense_internal_blank_ratio < 0.15:
        issues.append(Issue(
            code="dense_no_gap",
            title="密处欠透气",
            severity=65,
            keywords=["密不闷", "透气", "密处透气", "实不闷", "密中见疏", "密中有疏", "密处留气"],
            hint="密集区域内部缺少空白间隙，有闷塞感，建议在密处留出小空白使画面灵动。",
            extra={"dense_blank_ratio": round(g.dense_internal_blank_ratio, 2)},
        ))

    # 23. No rhythm (gaps rhythm too flat)
    if g.rhythm_score < 0.05 and el.element_count >= 3:
        issues.append(Issue(
            code="no_rhythm",
            title="疏密节奏不足",
            severity=50,
            keywords=["疏密", "节奏", "聚散", "对比", "密处", "疏处", "大虚小虚"],
            hint="画面疏密交替不够明显，建议强化密处更密、疏处更疏的对比节奏。",
            extra={"rhythm": round(g.rhythm_score, 2)},
        ))

    # ------------------------------------------------------------------
    # === COMPOSITE ISSUES ===
    # ------------------------------------------------------------------

    # 24. Over-dense for landscape (宁空毋实)
    if dense_pct > 75:
        issues.append(Issue(
            code="landscape_too_dense",
            title="画面实部偏多",
            severity=int(min(80, 50 + (dense_pct - 75) * 3)),
            keywords=["宁空毋实", "实", "虚", "丘壑", "山水", "删繁", "留白"],
            hint=f"画材覆盖率约{dense_pct}%，实部占比偏高。\"山水之要，宁空毋实\"，建议删减次要笔触，留出呼吸空间。",
            extra={"coverage_pct": dense_pct},
        ))

    # 25. Weak start zone (起于边角)
    if tr.start_zone_density < 0.1 and el.element_count >= 2:
        issues.append(Issue(
            code="weak_start",
            title="起处偏弱",
            severity=50,
            keywords=["起于边角", "起点", "起结", "边角", "气势", "起部"],
            hint="画面边缘区域墨色较少，起势不够明确，建议在边角处安排明确的主导元素起笔。",
            extra={"start_density": round(tr.start_zone_density, 2)},
        ))

    # ------------------------------------------------------------------
    # === PANPLUS ISSUES (from panplus.md JH/CC/BJ dimensions) ===
    # ------------------------------------------------------------------

    # 26. L/R corner balance (JH-01-04: 四角不等量)
    corners = [r.top_left, r.top_right, r.bot_left, r.bot_right]
    corner_cv = float(np.std(corners)) if len(corners) >= 4 else 0.0
    if corner_cv < 0.02 and el.element_count >= 3:
        issues.append(Issue(
            code="corners_uniform",
            title="四角留白偏均匀",
            severity=45,
            keywords=["四角", "留白", "不等量", "变化", "金边银角", "角"],
            hint="画面四角墨色分布过于均匀，建议拉开四角留白的大小差异，体现金边银角的变化。",
            extra={"corner_cv": round(corner_cv, 4)},
        ))

    # 27. Diagonal layout check (JH-04-05: 对角呼应)
    # Check if there's content in diagonal corners (top-left + bot-right, or top-right + bot-left)
    diag1 = max(r.top_left, r.bot_right)
    diag2 = max(r.top_right, r.bot_left)
    min_diag = min(diag1, diag2)
    if min_diag < 0.05 and el.element_count >= 3 and dense_pct > 20:
        issues.append(Issue(
            code="no_diagonal",
            title="缺乏对角呼应",
            severity=40,
            keywords=["对角", "呼应", "斜势", "对角线", "交叉"],
            hint="画面对角方向缺乏呼应，建议在对角区域增加元素或用款印形成对角平衡。",
            extra={"diag_strength": round(min_diag, 3)},
        ))

    # 28. Size uniformity (JH-03-01: 大小三级变化)
    if el.area_ratio_max_min < 1.5 and el.element_count >= 4:
        issues.append(Issue(
            code="size_uniform",
            title="元素大小偏均匀",
            severity=50,
            keywords=["大小", "三级变化", "大小相间", "变化", "攒三聚五", "面积"],
            hint="画面中元素大小差异不足，建议拉开大小对比，形成攒三聚五的大小节奏。",
            extra={"size_ratio": round(el.area_ratio_max_min, 2)},
        ))

    # 29. Crossing structure (CC-01-03: 避免十字交叉 / CC-02-03: 避免直角)
    if c.horizontal_vertical_crosses >= 1 and el.element_count <= 5:
        issues.append(Issue(
            code="stiff_crossing",
            title="交叉结构偏板",
            severity=50,
            keywords=["交叉", "女字", "十字", "直角", "穿插", "凤眼", "鼓架", "正交", "破势"],
            hint="线条交叉角度接近直角，显得呆板。建议调整线条角度形成女字交叉或不齐弧三角形。",
            extra={"hv_crosses": c.horizontal_vertical_crosses},
        ))

    # 30. Edge touching / frame usage (BJ-01-02: 占边取势 / BJ-01-03/04: 露梢露根)
    if r.bottom_edge_density < 0.02 and corner_avg < 0.05 and el.element_count >= 3:
        issues.append(Issue(
            code="no_edge_touch",
            title="画材远离边框",
            severity=40,
            keywords=["占边", "取势", "露梢", "露根", "出入画幅", "画框", "边界", "金边"],
            hint="画材远离边框，画面有悬浮感。可让部分元素延伸至画边或出画，增加画外延伸感。",
            extra={"bot_edge": round(r.bottom_edge_density, 3), "corner_avg": round(corner_avg, 3)},
        ))

    # ------------------------------------------------------------------
    # === COMPOSITION PARADIGM ISSUES (from GF rules) ===
    # ------------------------------------------------------------------

    # 31. S-shaped / zigzag composition detection (GF-01-01)
    # Detect if main elements follow an S-curve pattern
    if tr.diagonal_ratio > 0.3 and el.element_count >= 3 and not tri.is_equilateral:
        # Multiple diagonal elements suggest zigzag/S-curve potential
        issues.append(Issue(
            code="zigzag_pattern",
            title="之字形构图特征",
            severity=15,  # Low severity = informational, not a problem
            keywords=["之字形", "S形", "蛇形", "蜿蜒", "转折点", "起伏", "蓄势"],
            hint="画面呈现之字形/S形蜿蜒趋势，这是经典的构图范式之一。",
            extra={"diag_ratio": round(tr.diagonal_ratio, 2)},
        ))

    # 32. Diagonal composition detection (GF-01-02)
    if tr.diagonal_ratio > 0.4 and el.element_count >= 2:
        diag1_density = max(r.top_left, r.bot_right)
        diag2_density = max(r.top_right, r.bot_left)
        max_diag = max(diag1_density, diag2_density)
        if max_diag > 0.1:
            issues.append(Issue(
                code="diagonal_pattern",
                title="对角线构图特征",
                severity=15,
                keywords=["对角线", "斜向", "对角", "呼应", "取势", "斜势"],
                hint="画面画材沿对角线方向分布，形成对角线构图范式。",
                extra={"diag_strength": round(max_diag, 3)},
            ))

    # 33. Corner composition detection (GF-01-04)
    # If most material is concentrated in one corner with large blank area
    max_corner = max(r.top_left, r.top_right, r.bot_left, r.bot_right)
    if blank_pct >= 50 and max_corner > 0.15 and el.element_count <= 4:
        issues.append(Issue(
            code="corner_pattern",
            title="边角构图特征",
            severity=15,
            keywords=["边角", "偏居一角", "大面积留白", "疏简", "简约"],
            hint="画材偏居一角，大面积留白，属于典型的边角构图范式。",
            extra={"blank_pct": blank_pct, "max_corner": round(max_corner, 3)},
        ))

    # 34. Grid/cross composition detection (GF-01-06)
    # Multiple H-V crossings suggest grid/cross layout
    if c.horizontal_vertical_crosses >= 2 and tr.horizontal_vertical_ratio > 0.3:
        issues.append(Issue(
            code="grid_pattern",
            title="纵横构图特征",
            severity=15,
            keywords=["纵横", "经纬", "交叉", "骨架", "杆石"],
            hint="画面存在纵横交织的线条骨架，属于纵横构图范式。",
            extra={"hv_crosses": c.horizontal_vertical_crosses},
        ))

    # 35. Full-coverage composition detection (GF-01-07)
    if dense_pct > 60 and g.rhythm_score > 0.1:
        issues.append(Issue(
            code="full_pattern",
            title="全景构图特征",
            severity=15,
            keywords=["全景", "遍布", "密不透风", "有序", "满构图"],
            hint="画材遍布画面但有序不乱，属于全景构图范式。",
            extra={"coverage_pct": dense_pct},
        ))

    # ------------------------------------------------------------------
    # === MATERIAL-SPECIFIC ISSUES (from MC rules) ===
    # ------------------------------------------------------------------

    # 36. Bamboo/orchid parallel lines (MC-01-03)
    if c.parallel_line_pairs >= 2 and el.element_count >= 3:
        issues.append(Issue(
            code="bamboo_parallel",
            title="兰竹线条平行",
            severity=55,
            keywords=["兰竹", "避平行", "线条", "平行", "竹枝", "穿插", "兰叶"],
            hint="若画面含兰竹画材，线条过于平行需要穿插变化破之。",
            extra={"parallel_pairs": c.parallel_line_pairs},
        ))

    # 37. Bird-stone diagonal呼应 detection (MC-03-01)
    # Check if there are elements in opposing diagonal quadrants
    if el.element_count >= 2:
        diag1_density = r.top_left + r.bot_right
        diag2_density = r.top_right + r.bot_left
        if abs(diag1_density - diag2_density) > 0.1 and max(diag1_density, diag2_density) > 0.15:
            issues.append(Issue(
                code="bird_stone_diagonal",
                title="鸟石对角呼应",
                severity=15,
                keywords=["鸟", "石", "呼应", "对角", "鸟石", "禽鸟"],
                hint="画面存在对角方向上的元素分布，可形成鸟石对角呼应的构图关系。",
                extra={"diag1": round(diag1_density, 3), "diag2": round(diag2_density, 3)},
            ))

    # 38. Lotus-stone void-solid detection (MC-02-01)
    if blank_pct >= 40 and blank_pct <= 75 and el.element_count >= 2 and el.area_ratio_max_min > 3:
        issues.append(Issue(
            code="lotus_stone_void",
            title="荷石虚实特征",
            severity=15,
            keywords=["荷", "石", "虚实", "大实", "大虚", "虚实互补", "荷叶"],
            hint="画面存在大面积实部与大虚留白的对比，符合荷石虚实的构图特征。",
            extra={"blank_pct": blank_pct, "area_ratio": round(el.area_ratio_max_min, 1)},
        ))

    return issues


def _score_rule(rule: PanRule, issues: Sequence[Issue]) -> float:
    """Score a rule based on keyword overlap with detected issues."""
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


def select_rules(
    pan_md_path: str,
    metrics: ImageMetrics,
    adv: Optional[AdvancedMetrics] = None,
    limit: int = 12,
    panplus_md_path: str | None = None,
) -> Dict[str, Any]:
    """Select the most relevant composition rules for the given image metrics.

    Searches both pan.md and panplus.md rules, returning top matches.
    Ensures at least 1 rule per dimension (KH/XS/SM/FZ/JH/CC/BJ) for coverage.
    """
    if not os.path.exists(pan_md_path):
        return {"issues": [], "rules": []}
    text = _read_text(pan_md_path)
    rules = parse_pan_rules(text)
    # Load panplus rules (JH/CC/BJ + supplementary KH/XS/SM/QS/FZ)
    panplus_rules = load_panplus_rules(panplus_md_path)
    # Merge: panplus rules override pan.md if same rule_id
    seen_ids: set = set()
    all_rules: list[PanRule] = []
    for r in rules:
        seen_ids.add(r.rule_id)
        all_rules.append(r)
    for r in panplus_rules:
        if r.rule_id not in seen_ids:
            seen_ids.add(r.rule_id)
            all_rules.append(r)
        # If rule_id exists in both, skip pan.md version (panplus is newer)
    issues = derive_issues(metrics, adv)
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
    for r in all_rules:
        s = _score_rule(r, issues)
        if s > 0:
            scored.append((s, r))
    scored.sort(key=lambda x: x[0], reverse=True)

    # --- Dimension mapping: rule_id prefix -> dimension name ---
    DIM_PREFIXES = {
        "KH-": "开合之势",
        "XS-": "虚实相生",
        "SM-": "疏密有致",
        "QS-": "气势趋向",
        "FZ-": "辅助元素",
        "JH-": "均衡节奏",
        "CC-": "穿插结构",
        "BJ-": "边角空间",
        "GF-": "构图范式",
        "MC-": "画材特定",
    }
    # Map rule prefixes to the 7 scoring dimensions for coverage tracking
    # QS (气势趋向) maps to 开合之势 (20分) since QS rules contribute to that score
    # GF (构图范式) maps to 开合之势 since paradigm identification guides the overall analysis
    # MC (画材特定) maps to 疏密有致 since material-specific rules often relate to spacing
    DIM_SCORE_GROUP = {
        "KH-": "开合之势",
        "QS-": "开合之势",  # QS rules contribute to 开合之势 scoring
        "GF-": "开合之势",  # 构图范式识别引导整体分析
        "XS-": "虚实相生",
        "SM-": "疏密有致",
        "MC-": "疏密有致",  # 画材特定规则常与疏密相关
        "FZ-": "辅助元素",
        "JH-": "均衡节奏",
        "CC-": "穿插结构",
        "BJ-": "边角空间",
    }
    # 7 scoring dimensions that need coverage
    SCORING_DIMS = {"开合之势", "虚实相生", "疏密有致", "辅助元素", "均衡节奏", "穿插结构", "边角空间"}

    picked: List[Dict[str, Any]] = []
    used: set = set()
    # Track which scoring dimensions have at least one rule picked
    dim_covered: dict[str, int] = {d: 0 for d in SCORING_DIMS}

    # Ensure at least 2 panplus rules (JH/CC/BJ) are included
    # so that bird_flower_tutorial images appear in example_images
    min_panplus = 2
    panplus_picked = 0

    # First pass: pick top rules
    for s, r in scored:
        if r.rule_id in used:
            continue
        used.add(r.rule_id)
        is_pp = any(r.rule_id.startswith(p) for p in ("JH-", "CC-", "BJ-"))
        if is_pp:
            panplus_picked += 1
        # Track dimension coverage
        for prefix, dim_name in DIM_SCORE_GROUP.items():
            if r.rule_id.startswith(prefix):
                dim_covered[dim_name] = dim_covered.get(dim_name, 0) + 1
                break
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

    # Second pass: fill with panplus rules if under minimum
    if panplus_picked < min_panplus:
        for s, r in scored:
            if r.rule_id in used:
                continue
            is_pp = any(r.rule_id.startswith(p) for p in ("JH-", "CC-", "BJ-"))
            if not is_pp:
                continue
            if not r.reference_figures:
                continue
            used.add(r.rule_id)
            panplus_picked += 1
            for prefix, dim_name in DIM_SCORE_GROUP.items():
                if r.rule_id.startswith(prefix):
                    dim_covered[dim_name] = dim_covered.get(dim_name, 0) + 1
                    break
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
            if panplus_picked >= min_panplus:
                break

    # Third pass: ensure each of the 7 scoring dimensions has at least 1 rule
    uncovered = [d for d in SCORING_DIMS if dim_covered.get(d, 0) == 0]
    if uncovered and len(picked) < limit + 4:  # Allow up to 4 extra rules for coverage
        for dim_name in uncovered:
            # Find the highest-scoring rule for this dimension
            best_for_dim = None
            best_score = 0.0
            for s, r in scored:
                if r.rule_id in used:
                    continue
                for prefix, dname in DIM_SCORE_GROUP.items():
                    if r.rule_id.startswith(prefix) and dname == dim_name:
                        if s > best_score:
                            best_score = s
                            best_for_dim = (s, r)
                        break
            if best_for_dim:
                s, r = best_for_dim
                used.add(r.rule_id)
                dim_covered[dim_name] = dim_covered.get(dim_name, 0) + 1
                is_pp = any(r.rule_id.startswith(p) for p in ("JH-", "CC-", "BJ-"))
                if is_pp:
                    panplus_picked += 1
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

    # Sort picked rules by relevance (descending) for better prompt ordering
    picked.sort(key=lambda x: x.get("relevance", 0), reverse=True)

    return {
        "issues": [
            {
                "code": i.code, "title": i.title,
                "severity": i.severity, "hint": i.hint,
                "extra": i.extra,
            }
            for i in issues
        ],
        "rules": picked,
    }
