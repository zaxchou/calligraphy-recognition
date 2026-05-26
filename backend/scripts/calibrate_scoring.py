"""
情感评分校准脚本
────────────────────────────────────────
用 LLM 输出作为参考标准，校准 VADER 评分引擎的权重

流程：
1. 从数据库采样 N 幅已分析的作品
2. 对每幅作品，同时运行：
   - 旧评分系统（作为 baseline）
   - 新 VADER 评分引擎（初始权重）
   - LLM 情感分析（作为参考标准）
3. 对比三者输出，找出偏差
4. 用梯度下降优化权重，使 VADER 输出逼近 LLM 参考
5. 输出校准报告

用法：
python -m scripts.calibrate_scoring --sample-size 50 --output calibration_report.json
"""

import asyncio
import json
import sqlite3
import argparse
import os
import sys
from datetime import datetime
from typing import Dict, List, Optional

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import get_settings
from app.services.scoring_engine import (
    DimensionScore, SentimentResult, quick_score,
    vader_normalize, inverse_vader, batch_calibrate,
    DEFAULT_WEIGHTS, VADER_ALPHA
)
from app.services.inscription_content_analyzer import (
    score_text_keywords, analyze_spatial_emotion, analyze_seal_emotion,
    classify_inscription_v4
)
from app.services.inscription_translation import translate_inscription


def get_db_connection():
    """获取数据库连接"""
    settings = get_settings()
    db_path = settings.DATABASE_URL.replace("sqlite:///", "")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def load_sample_artworks(sample_size: int = 50, artist: str = None) -> List[Dict]:
    """
    从数据库加载样本作品

    选择标准：
    - 已有内容分析结果
    - 题跋长度 > 10 字（太短没有分析价值）
    - 优先选择不同主题类型的作品（多样性）
    """
    conn = get_db_connection()

    query = """
        SELECT
            ta.id,
            ta.title,
            ta.artist,
            ta.year,
            ta.inscription_content,
            ta.seal_content,
            ta.content_analysis,
            ta.artwork_width_cm,
            ta.artwork_height_cm
        FROM tubi_analyses ta
        WHERE ta.content_analysis IS NOT NULL
          AND ta.inscription_content IS NOT NULL
          AND LENGTH(ta.inscription_content) > 10
    """
    params = []

    if artist:
        query += " AND ta.artist = ?"
        params.append(artist)

    # 随机采样，确保多样性
    query += " ORDER BY RANDOM() LIMIT ?"
    params.append(sample_size)

    rows = conn.execute(query, params).fetchall()
    conn.close()

    artworks = []
    for row in rows:
        try:
            ca = json.loads(row["content_analysis"])
            if isinstance(ca, str):
                ca = json.loads(ca)

            # 提取旧系统的分数
            old_sentiment = ca.get("sentiment", {})
            old_emotion_score = old_sentiment.get("emotion_score", 0.0)

            # 提取主题
            themes = ca.get("themes", [])
            primary_theme = themes[0]["name"] if themes else "未知"

            artworks.append({
                "id": row["id"],
                "title": row["title"],
                "artist": row["artist"],
                "year": row["year"],
                "inscription": row["inscription_content"],
                "seal_content": row["seal_content"],
                "width_cm": row["artwork_width_cm"],
                "height_cm": row["artwork_height_cm"],
                "old_emotion_score": old_emotion_score,
                "old_polarity": old_sentiment.get("polarity", "neutral"),
                "primary_theme": primary_theme,
                "themes": themes,
                "raw_content_analysis": ca,
            })
        except Exception as e:
            print(f"  跳过作品 {row['id']}: {e}")
            continue

    return artworks


def run_old_scoring(artwork: Dict) -> Dict:
    """
    运行旧评分系统

    返回：{"emotion_score": float, "polarity": str}
    """
    # 直接使用数据库中已有的结果
    return {
        "emotion_score": artwork["old_emotion_score"],
        "polarity": artwork["old_polarity"],
        "normalized": vader_normalize(artwork["old_emotion_score"]),
    }


def run_new_scoring(artwork: Dict, weights: Dict[str, float] = None) -> Dict:
    """
    运行新 VADER 评分引擎

    返回：{"combined_normalized": float, "polarity": str, "text_raw": float, ...}
    """
    text = artwork["inscription"] or ""

    # 文字情感分
    _, text_raw, _ = score_text_keywords(text)

    # 空间情绪分（如果有分析结果）
    ca = artwork.get("raw_content_analysis", {})
    spatial_emotion = ca.get("spatial_emotion", {})
    spatial_raw = 0.0
    if spatial_emotion:
        # 从空间情绪信号中提取分数
        signals = spatial_emotion.get("signals", [])
        if signals:
            # 取第一个信号的分数（简化处理）
            spatial_raw = signals[0].get("score", 0.0)

    # 印章情感分
    seal_content = artwork.get("seal_content", "")
    seal_raw = 0.0
    if seal_content:
        seal_result = analyze_seal_emotion(seal_content)
        seal_raw = seal_result.get("composite_score", 0.0)

    # VADER 评分
    result = quick_score(
        text_raw=text_raw,
        spatial_raw=spatial_raw,
        seal_raw=seal_raw,
        weights=weights,
    )

    return {
        "combined_normalized": result.combined_normalized,
        "combined_raw": result.combined_raw,
        "polarity": result.polarity,
        "text_raw": text_raw,
        "spatial_raw": spatial_raw,
        "seal_raw": seal_raw,
        "reasoning": result.reasoning,
    }


async def run_llm_scoring(artwork: Dict) -> Dict:
    """
    用 LLM 做情感分析（作为参考标准）

    返回：{"polarity": str, "intensity": float, "reasoning": str, "normalized": float}
    """
    text = artwork["inscription"]
    artist = artwork["artist"]

    try:
        # 复用现有的 LLM 分析功能
        from app.services.inscription_content_analyzer import llm_sentiment_analysis_v3
        result = await llm_sentiment_analysis_v3(text, artist)

        polarity = result.get("polarity", "neutral")
        intensity = result.get("intensity", 0.5)
        reasoning = result.get("reasoning", "")

        # 将 polarity + intensity 转换为 [-1, +1] 分数
        if polarity == "positive":
            normalized = intensity
        elif polarity == "negative":
            normalized = -intensity
        else:
            normalized = 0.0

        return {
            "polarity": polarity,
            "intensity": intensity,
            "reasoning": reasoning,
            "normalized": normalized,
            "success": True,
        }
    except Exception as e:
        print(f"  LLM 分析失败 ({artwork['id']}): {e}")
        return {
            "polarity": "neutral",
            "intensity": 0.0,
            "reasoning": f"LLM 分析失败: {str(e)}",
            "normalized": 0.0,
            "success": False,
        }


async def calibrate(sample_size: int = 50, artist: str = None,
                    output_path: str = "calibration_report.json") -> Dict:
    """
    主校准流程

    1. 加载样本
    2. 运行三种评分
    3. 对比分析
    4. 优化权重
    5. 生成报告
    """
    print(f"\n{'='*60}")
    print(f"情感评分校准")
    print(f"样本量: {sample_size}, 画家: {artist or '全部'}")
    print(f"{'='*60}\n")

    # 1. 加载样本
    print("[1/5] 加载样本作品...")
    artworks = load_sample_artworks(sample_size, artist)
    print(f"  加载了 {len(artworks)} 幅作品\n")

    if len(artworks) == 0:
        print("错误：没有找到符合条件的作品")
        return {}

    # 2. 运行三种评分
    print("[2/5] 运行评分系统...")

    results = []
    for i, artwork in enumerate(artworks):
        print(f"  [{i+1}/{len(artworks)}] {artwork['title'][:20]}...", end="", flush=True)

        # 旧系统
        old_result = run_old_scoring(artwork)

        # 新 VADER 系统
        new_result = run_new_scoring(artwork)

        # LLM 参考
        llm_result = await run_llm_scoring(artwork)

        results.append({
            "artwork": artwork,
            "old": old_result,
            "new": new_result,
            "llm": llm_result,
        })

        if llm_result["success"]:
            print(f" ✓ 旧={old_result['normalized']:+.2f} 新={new_result['combined_normalized']:+.2f} LLM={llm_result['normalized']:+.2f}")
        else:
            print(f" ✗ LLM失败")

    # 3. 对比分析
    print(f"\n[3/5] 对比分析...")

    # 筛选 LLM 成功的样本
    valid_results = [r for r in results if r["llm"]["success"]]
    print(f"  有效样本: {len(valid_results)}/{len(results)}")

    if len(valid_results) < 5:
        print("警告：有效样本太少，跳过校准")
        return {"error": "样本不足"}

    # 计算偏差
    old_errors = []
    new_errors = []
    for r in valid_results:
        old_err = abs(r["old"]["normalized"] - r["llm"]["normalized"])
        new_err = abs(r["new"]["combined_normalized"] - r["llm"]["normalized"])
        old_errors.append(old_err)
        new_errors.append(new_err)

    old_mae = sum(old_errors) / len(old_errors)
    new_mae = sum(new_errors) / len(new_errors)

    print(f"  旧系统 MAE: {old_mae:.3f}")
    print(f"  新系统 MAE: {new_mae:.3f}")

    # 4. 优化权重
    print(f"\n[4/5] 优化权重...")

    # 准备校准数据
    calibration_samples = []
    for r in valid_results:
        calibration_samples.append({
            "text_raw": r["new"]["text_raw"],
            "spatial_raw": r["new"]["spatial_raw"],
            "seal_raw": r["new"]["seal_raw"],
            "text_confidence": 1.0,
            "spatial_confidence": 0.8 if r["new"]["spatial_raw"] != 0 else 0.3,
            "seal_confidence": 0.6 if r["new"]["seal_raw"] != 0 else 0.2,
            "target_normalized": r["llm"]["normalized"],
        })

    # 梯度下降优化
    calibrated_weights = batch_calibrate(calibration_samples)
    print(f"  校准后权重: {calibrated_weights}")

    # 用校准后的权重重新计算
    new_calibrated_errors = []
    for r in valid_results:
        recalculated = quick_score(
            text_raw=r["new"]["text_raw"],
            spatial_raw=r["new"]["spatial_raw"],
            seal_raw=r["new"]["seal_raw"],
            weights=calibrated_weights,
        )
        err = abs(recalculated.combined_normalized - r["llm"]["normalized"])
        new_calibrated_errors.append(err)

    new_calibrated_mae = sum(new_calibrated_errors) / len(new_calibrated_errors)
    print(f"  校准后 MAE: {new_calibrated_mae:.3f}")

    # 5. 生成报告
    print(f"\n[5/5] 生成报告...")

    report = {
        "timestamp": datetime.now().isoformat(),
        "sample_size": sample_size,
        "artist": artist,
        "valid_samples": len(valid_results),
        "metrics": {
            "old_system_mae": round(old_mae, 4),
            "new_system_mae_initial": round(new_mae, 4),
            "new_system_mae_calibrated": round(new_calibrated_mae, 4),
            "improvement_vs_old": round((old_mae - new_calibrated_mae) / old_mae * 100, 1),
        },
        "weights": {
            "initial": DEFAULT_WEIGHTS,
            "calibrated": {k: round(v, 4) for k, v in calibrated_weights.items()},
        },
        "vader_alpha": VADER_ALPHA,
        "samples": [],
    }

    # 详细样本数据
    for r in results:
        report["samples"].append({
            "id": r["artwork"]["id"],
            "title": r["artwork"]["title"],
            "artist": r["artwork"]["artist"],
            "theme": r["artwork"]["primary_theme"],
            "inscription_preview": r["artwork"]["inscription"][:50] + "...",
            "old_score": round(r["old"]["normalized"], 3),
            "new_score_initial": round(r["new"]["combined_normalized"], 3),
            "llm_score": round(r["llm"]["normalized"], 3),
            "llm_polarity": r["llm"]["polarity"],
            "llm_reasoning": r["llm"]["reasoning"][:100],
            "new_reasoning": r["new"]["reasoning"],
            "components": {
                "text_raw": round(r["new"]["text_raw"], 2),
                "spatial_raw": round(r["new"]["spatial_raw"], 2),
                "seal_raw": round(r["new"]["seal_raw"], 2),
            },
        })

    # 保存报告
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"\n报告已保存: {output_path}")

    # 打印摘要
    print(f"\n{'='*60}")
    print(f"校准摘要")
    print(f"{'='*60}")
    print(f"样本量: {len(valid_results)} 幅作品")
    print(f"旧系统 MAE: {old_mae:.3f}")
    print(f"新系统 MAE（初始）: {new_mae:.3f}")
    print(f"新系统 MAE（校准后）: {new_calibrated_mae:.3f}")
    print(f"改进幅度: {report['metrics']['improvement_vs_old']:+.1f}%")
    print(f"\n校准后权重:")
    for k, v in calibrated_weights.items():
        print(f"  {k}: {v:.3f}")
    print(f"{'='*60}\n")

    return report


def main():
    parser = argparse.ArgumentParser(description="情感评分校准脚本")
    parser.add_argument("--sample-size", type=int, default=50, help="样本量")
    parser.add_argument("--artist", type=str, default=None, help="指定画家")
    parser.add_argument("--output", type=str, default="calibration_report.json", help="输出路径")

    args = parser.parse_args()

    asyncio.run(calibrate(
        sample_size=args.sample_size,
        artist=args.artist,
        output_path=args.output,
    ))


if __name__ == "__main__":
    main()
