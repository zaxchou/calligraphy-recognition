---
name: v5.4-emotion-baseline-tuning
overview: 调整情感基线修正和交游赠答权重，修正rebatch后的摆锤效应和交游赠答虚高
todos:
  - id: adjust-baseline-and-scoring
    content: 修改 tibi_analysis_rules.py 基线值和交游赠答权重
    status: completed
  - id: adjust-baseline-factor
    content: 修改 inscription_content_analyzer.py 基线修正系数按分期差异化
    status: completed
    dependencies:
      - adjust-baseline-and-scoring
  - id: verify-and-rebatch
    content: 验证导入正常，跑 rebatch 对比分布
    status: completed
    dependencies:
      - adjust-baseline-factor
---

## 产品概述

修正 v5.3-fix rebatch 后的情感分布摆锤效应和交游赠答虚高问题

## 核心问题

1. **情感摆锤效应**：移除"懊道人" -1.8 扣分后，ARTIST_EMOTION_BASELINE 的 -0.5 修正力度不足（实际生效仅 -0.15），导致李鱓情感底色几乎消失，positive 从 34.2% 飙升到 49.6%
2. **基线修正不分期**：当前 baseline_factor 对中晚期统一 0.3，但晚期作品情感底色偏阴更明显，应有差异化系数
3. **交游赠答虚高**：TEXT_SCORING_RULES[6] 中"写":2,"作":2,"画":2,"为":2 这些字太泛，几乎每幅题跋都有，导致交游赠答覆盖率 46.2% 虚高

## 核心调整

1. ARTIST_EMOTION_BASELINE 李鱓从 -0.5 调到 -0.7
2. 基线修正系数按分期差异化：晚期 0.6、中期 0.4、早期 0.15
3. TEXT_SCORING_RULES[6] 中"写""作""画""为"从 2 分降到 0.5 分

## Tech Stack

- Python（现有 FastAPI 后端）
- 无新增依赖

## Implementation Approach

只修改两个文件，改动量极小：

### 调整1：tibi_analysis_rules.py

- `ARTIST_EMOTION_BASELINE["李鱓"]` 从 -0.5 改为 -0.7
- `TEXT_SCORING_RULES[6]["keywords"]` 中 `"写":2,"作":2,"画":2,"为":2` 改为 `"写":0.5,"作":0.5,"画":0.5,"为":0.5`

### 调整2：inscription_content_analyzer.py

- 基线修正系数从固定 0.3 改为按分期差异化：
- 晚期（stage 包含"晚期"）：0.6
- 中期（stage 包含"中期"）：0.4
- 早期（stage 包含"早期"）：0.15（不变）

### 预期效果

- 李鱓情感均值从 +0.19 回落到约 -0.1 ~ -0.2
- positive 从 49.6% 回落到约 35-40%
- negative 从 25.4% 回升到约 30-35%
- 交游赠答覆盖率从 46.2% 下降到约 25-30%

## Directory Structure

```
backend/app/services/
├── tibi_analysis_rules.py              # [MODIFY] ARTIST_EMOTION_BASELINE 李鱓 -0.5→-0.7；TEXT_SCORING_RULES[6] 写/作/画/为 2→0.5
├── inscription_content_analyzer.py     # [MODIFY] 基线修正系数按分期差异化（晚期0.6/中期0.4/早期0.15）
```