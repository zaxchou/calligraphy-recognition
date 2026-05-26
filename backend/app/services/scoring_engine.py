"""
情感评分引擎 v1.0 — VADER 风格归一化
────────────────────────────────────────
核心思路：
1. 特征提取（保留领域知识）→ 输出原始分数
2. VADER 归一化 → 映射到 [-1, +1]
3. 置信度加权融合 → 三维度综合判断

设计原则：
- 不预设结论，只定义特征和权重
- 权重可通过校准脚本调整
- 输出可解释（每个维度的贡献清晰可见）
"""

import math
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field


@dataclass
class DimensionScore:
    """单个维度的评分结果"""
    raw: float = 0.0           # 原始分数（无界）
    normalized: float = 0.0    # VADER 归一化后的分数 [-1, +1]
    confidence: float = 1.0    # 置信度 [0, 1]
    signals: List[Dict] = field(default_factory=list)  # 触发的信号明细
    label: str = ""            # 人类可读标签


@dataclass
class SentimentResult:
    """综合情感分析结果"""
    text: DimensionScore = field(default_factory=DimensionScore)
    spatial: DimensionScore = field(default_factory=DimensionScore)
    seal: DimensionScore = field(default_factory=DimensionScore)
    combined_raw: float = 0.0
    combined_normalized: float = 0.0
    polarity: str = "neutral"  # positive / negative / neutral
    reasoning: str = ""
    weights_used: Dict[str, float] = field(default_factory=dict)


# ── 默认权重（可通过校准调整）────────────────────────────────────────
DEFAULT_WEIGHTS = {
    "text": 0.50,      # 文字情感（最强信号）
    "spatial": 0.30,   # 空间布局（中等信号）
    "seal": 0.20,      # 印章（辅助信号）
}

# VADER 平滑常数：控制归一化的"硬度"
# α 越小 → 曲线越陡（小分数就能接近 ±1）
# α 越大 → 曲线越平（需要大分数才能接近 ±1）
# VADER 原文用 α=15，适合 -4~+4 的原始分
# 我们的原始分范围更大（约 -10~+10），用 α=25 更合适
VADER_ALPHA = 25.0


def vader_normalize(raw_score: float, alpha: float = VADER_ALPHA) -> float:
    """
    VADER 风格归一化：任何实数 → [-1, +1]

    公式：compound = raw / sqrt(raw² + α)

    特性：
    - 单调递增
    - 奇函数：normalize(-x) = -normalize(x)
    - 饱和效应：分数越高，增长越慢
    - α 控制"饱和速度"
    """
    if raw_score == 0:
        return 0.0
    return raw_score / math.sqrt(raw_score ** 2 + alpha)


def inverse_vader(normalized: float, alpha: float = VADER_ALPHA) -> float:
    """
    反向 VADER：从 [-1, +1] 反推原始分数
    用于校准：知道期望的 normalized 值，反推需要多少 raw 分
    """
    if normalized == 0:
        return 0.0
    # normalized = raw / sqrt(raw² + α)
    # normalized² * (raw² + α) = raw²
    # raw² * (normalized² - 1) = -normalized² * α
    # raw² = normalized² * α / (1 - normalized²)
    n2 = normalized ** 2
    if n2 >= 1:
        return float('inf') if normalized > 0 else float('-inf')
    return math.copysign(math.sqrt(n2 * alpha / (1 - n2)), normalized)


def classify_polarity(normalized_score: float,
                      positive_threshold: float = 0.15,
                      negative_threshold: float = -0.15) -> str:
    """
    从归一化分数判断极性

    阈值说明：
    - VADER 原文用 ±0.05（太敏感）
    - 我们用 ±0.15（更保守，减少"假阳性"）
    """
    if normalized_score >= positive_threshold:
        return "positive"
    elif normalized_score <= negative_threshold:
        return "negative"
    return "neutral"


def combine_dimensions(
    text: DimensionScore,
    spatial: DimensionScore,
    seal: DimensionScore,
    weights: Dict[str, float] = None,
) -> Tuple[float, float, str]:
    """
    三维度加权融合

    公式：
    combined_raw = Σ(w_i × raw_i × confidence_i) / Σ(w_i × confidence_i)
    combined_normalized = vader_normalize(combined_raw)

    返回：(combined_raw, combined_normalized, polarity)
    """
    if weights is None:
        weights = DEFAULT_WEIGHTS

    dimensions = [
        ("text", text, weights.get("text", 0.5)),
        ("spatial", spatial, weights.get("spatial", 0.3)),
        ("seal", seal, weights.get("seal", 0.2)),
    ]

    weighted_sum = 0.0
    weight_total = 0.0

    for name, dim, w in dimensions:
        # 置信度加权：低置信度的维度自动降权
        effective_weight = w * dim.confidence
        weighted_sum += effective_weight * dim.raw
        weight_total += effective_weight

    if weight_total == 0:
        return 0.0, 0.0, "neutral"

    combined_raw = weighted_sum / weight_total
    combined_normalized = vader_normalize(combined_raw)
    polarity = classify_polarity(combined_normalized)

    return combined_raw, combined_normalized, polarity


def build_reasoning(text: DimensionScore, spatial: DimensionScore,
                    seal: DimensionScore, combined_normalized: float,
                    polarity: str) -> str:
    """生成人类可读的推理说明"""
    parts = []

    # 文字
    if text.label:
        t_polarity = classify_polarity(text.normalized)
        parts.append(f"文字{polarity_to_chinese(t_polarity)}")

    # 空间
    if spatial.label:
        s_polarity = classify_polarity(spatial.normalized)
        parts.append(f"空间{polarity_to_chinese(s_polarity)}")

    # 印章
    if seal.label:
        se_polarity = classify_polarity(seal.normalized)
        parts.append(f"印章{polarity_to_chinese(se_polarity)}")

    if not parts:
        return "无明显情感信号"

    summary = "、".join(parts)
    conclusion = polarity_to_chinese(polarity)

    return f"{summary}，综合{conclusion}"


def polarity_to_chinese(polarity: str) -> str:
    """极性转中文"""
    return {
        "positive": "积极",
        "negative": "消极",
        "neutral": "中性",
    }.get(polarity, "中性")


# ── 校准工具 ──────────────────────────────────────────────────────────

def calibrate_weight(current_normalized: float, target_normalized: float,
                     current_raw: float, dimension_weight: float) -> float:
    """
    校准单个样本的权重

    给定：
    - 当前系统输出：current_normalized
    - 期望输出（LLM/专家）：target_normalized
    - 当前原始分数：current_raw
    - 当前维度权重：dimension_weight

    返回：调整后的权重
    """
    if abs(current_raw) < 0.001:
        return dimension_weight  # 无法校准零分

    # 反推目标 raw 分数
    target_raw = inverse_vader(target_normalized)

    # 计算需要的权重调整比例
    if abs(current_normalized) < 0.001:
        return dimension_weight

    ratio = target_raw / current_raw if current_raw != 0 else 1.0
    new_weight = dimension_weight * ratio

    # 限制权重范围，避免极端值
    return max(0.05, min(0.95, new_weight))


def batch_calibrate(samples: List[Dict],
                    initial_weights: Dict[str, float] = None,
                    learning_rate: float = 0.1) -> Dict[str, float]:
    """
    批量校准：根据样本数据调整权重

    samples: [
        {
            "text_raw": float,
            "spatial_raw": float,
            "seal_raw": float,
            "text_confidence": float,
            "spatial_confidence": float,
            "seal_confidence": float,
            "target_normalized": float,  # LLM/专家给的期望分数
        },
        ...
    ]

    返回：校准后的权重
    """
    if initial_weights is None:
        weights = dict(DEFAULT_WEIGHTS)
    else:
        weights = dict(initial_weights)

    # 梯度下降迭代
    for epoch in range(100):
        total_loss = 0.0
        gradients = {"text": 0.0, "spatial": 0.0, "seal": 0.0}

        for sample in samples:
            text = DimensionScore(
                raw=sample["text_raw"],
                confidence=sample.get("text_confidence", 1.0)
            )
            spatial = DimensionScore(
                raw=sample["spatial_raw"],
                confidence=sample.get("spatial_confidence", 1.0)
            )
            seal = DimensionScore(
                raw=sample["seal_raw"],
                confidence=sample.get("seal_confidence", 1.0)
            )

            _, predicted, _ = combine_dimensions(text, spatial, seal, weights)
            target = sample["target_normalized"]

            # MSE 损失
            loss = (predicted - target) ** 2
            total_loss += loss

            # 简化的梯度（数值微分）
            for dim_name in ["text", "spatial", "seal"]:
                delta = 0.01
                w_plus = dict(weights)
                w_plus[dim_name] += delta
                _, pred_plus, _ = combine_dimensions(text, spatial, seal, w_plus)

                grad = (pred_plus - predicted) / delta
                gradients[dim_name] += grad * (predicted - target)

        # 更新权重
        for dim_name in gradients:
            weights[dim_name] -= learning_rate * gradients[dim_name] / len(samples)
            weights[dim_name] = max(0.05, min(0.95, weights[dim_name]))

        # 归一化权重（确保总和为 1）
        total = sum(weights.values())
        for dim_name in weights:
            weights[dim_name] /= total

        # 收敛检查
        if total_loss / len(samples) < 0.001:
            break

    return weights


# ── 便捷函数 ──────────────────────────────────────────────────────────

def quick_score(text_raw: float, spatial_raw: float, seal_raw: float,
                text_conf: float = 1.0, spatial_conf: float = 1.0,
                seal_conf: float = 1.0,
                weights: Dict[str, float] = None) -> SentimentResult:
    """
    快速评分：给定三个维度的原始分数，返回综合结果

    使用示例：
    >>> result = quick_score(text_raw=-3.0, spatial_raw=-0.5, seal_raw=0.0)
    >>> print(f"综合得分: {result.combined_normalized:.2f}")
    >>> print(f"极性: {result.polarity}")
    """
    text = DimensionScore(raw=text_raw, confidence=text_conf)
    spatial = DimensionScore(raw=spatial_raw, confidence=spatial_conf)
    seal = DimensionScore(raw=seal_raw, confidence=seal_conf)

    # 归一化各维度
    text.normalized = vader_normalize(text_raw)
    spatial.normalized = vader_normalize(spatial_raw)
    seal.normalized = vader_normalize(seal_raw)

    # 融合
    combined_raw, combined_normalized, polarity = combine_dimensions(
        text, spatial, seal, weights
    )

    # 生成推理
    reasoning = build_reasoning(text, spatial, seal, combined_normalized, polarity)

    return SentimentResult(
        text=text,
        spatial=spatial,
        seal=seal,
        combined_raw=combined_raw,
        combined_normalized=combined_normalized,
        polarity=polarity,
        reasoning=reasoning,
        weights_used=weights or DEFAULT_WEIGHTS,
    )


if __name__ == "__main__":
    # 演示：对比不同输入的归一化效果
    print("=== VADER 归一化演示 ===\n")

    test_cases = [
        ("轻微消极", -1.0, 0.0, 0.0),
        ("中等消极", -3.0, -0.3, 0.0),
        ("强烈消极", -6.0, -0.5, -1.0),
        ("中性", 0.0, 0.0, 0.0),
        ("轻微积极", 1.0, 0.2, 0.0),
        ("强烈积极", 5.0, 0.3, 1.0),
        ("矛盾信号", -3.0, 0.3, 1.0),
    ]

    print(f"{'场景':<12} {'文字raw':>8} {'空间raw':>8} {'印章raw':>8} │ {'综合raw':>8} {'综合norm':>8} {'极性':<8}")
    print("─" * 75)

    for name, t, s, se in test_cases:
        result = quick_score(t, s, se)
        print(f"{name:<12} {t:>8.1f} {s:>8.1f} {se:>8.1f} │ "
              f"{result.combined_raw:>8.2f} {result.combined_normalized:>8.2f} {result.polarity:<8}")

    print("\n=== 反向 VADER 验证 ===\n")
    for norm in [0.0, 0.3, 0.5, 0.7, 0.9, -0.5, -0.8]:
        raw = inverse_vader(norm)
        back = vader_normalize(raw)
        print(f"normalized={norm:+.1f} → raw={raw:+.2f} → back={back:+.3f} (误差={abs(back-norm):.6f})")
