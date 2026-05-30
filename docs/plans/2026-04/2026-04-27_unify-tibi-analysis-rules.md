---
name: unify-tibi-analysis-rules
overview: 将题跋分析的主题/情感算法规则从 inscription_content_analyzer.py 抽离到独立规则中心模块，修复懊道人残留问题，确保所有调用方单一来源。
todos:
  - id: create-rules-module
    content: 新建 tibi_analysis_rules.py 并迁移全部24个规则常量
    status: completed
  - id: refactor-analyzer-imports
    content: 修改 inscription_content_analyzer.py 从 rules 模块导入并重新导出常量
    status: completed
    dependencies:
      - create-rules-module
  - id: fix-aodaoren-rules
    content: 在 tibi_analysis_rules.py 中移除"懊道人"情感扣分、修正LLM引导与基线注释
    status: completed
    dependencies:
      - create-rules-module
  - id: verify-compatibility
    content: 验证所有8个调用方导入无报错，运行 rebatch 脚本对比前后情感分布
    status: completed
    dependencies:
      - refactor-analyzer-imports
      - fix-aodaoren-rules
---

## 产品概述

将题跋内容分析器的所有算法规则集中到一个独立的规则配置文件中，确保任何重新分析、全部分析情感或主题的流程都使用同一套规则，避免版本升级时改不全的问题。

## 核心问题

1. `inscription_content_analyzer.py` 同时包含24个规则常量和2200+行分析逻辑，规则分散在文件中各处
2. v5.3 主题分类已移除"懊道人"，但情感词典 `EMOTION_SCORING`、LLM 提示词 `_get_artist_sentiment_note`、画家基线 `ARTIST_EMOTION_BASELINE` 三处仍有残留，导致本地规则与LLM规则不统一
3. 外部脚本（rebatch、诊断、学术报告等共8个文件）直接导入常量或函数，规则修改时容易遗漏
4. 具体案例：作品 `1aac7535-5689-4d11-9a0f-3a75518629bb` 因落款"懊道人"被错误扣 -1.8 分，叠加"寒"(-1.0) 得 -2.8，与题跋实际情绪（中性偏傲骨）不符

## 核心需求

- 新建单一规则配置文件 `tibi_analysis_rules.py`，集中管理所有主题分类规则、情感评分词典、画家基线、尺寸规则、LLM Prompt 模板
- `inscription_content_analyzer.py` 作为统一入口，从规则文件导入并重新导出常量，保持现有调用方零改动
- 同步修复"懊道人"残留问题（情感词典移除、LLM提示词修正、基线注释修正）
- 保证所有调用方（API、rebatch脚本、诊断脚本、worker、报告生成器）通过同一套规则运行

## Tech Stack

- Python（现有 FastAPI 后端）
- 无新增依赖

## Implementation Approach

### 核心策略：Facade + 集中规则模块

采用"集中规则定义 + 兼容门面导出"的架构：

1. 新建 `tibi_analysis_rules.py` 作为唯一规则数据源，包含所有常量字典和 Prompt 模板
2. `inscription_content_analyzer.py` 保留所有分析逻辑，仅从 `tibi_analysis_rules` 导入规则常量，并重新导出以维持调用方兼容性
3. 外部8个调用方无需修改 import 语句，天然统一

### 为什么选这个方案

- **零破坏**：外部脚本如 `rebatch_analyze_li_shan.py` 导入的 `classify_inscription_v4`、`THEMES` 等路径不变
- **单一数据源**：以后升级 v6.0/v10.0，规则只需改 `tibi_analysis_rules.py` 一处
- **逻辑清晰**：分析引擎和规则配置物理分离，代码审查时一目了然

### 规则迁移范围（24个常量）

全部从 `inscription_content_analyzer.py` 迁移到 `tibi_analysis_rules.py`：

- `THEMES`、`THEME_NAME_MIGRATION`、`TEXT_SCORING_RULES`、`EMOTION_SCORING`、`THEME_SENTIMENT_OVERRIDE`
- `ARTIST_EMOTION_BASELINE`、`LIFE_STAGE_TABLE`、`PAINTING_MATERIAL_RULES`
- `SIZE_CATEGORIES`、`SIZE_THEME_RULES`、`SIZE_PERIOD_MOOD_RULES`、`SIZE_INTERPRETATION`
- `STOP_WORDS`、`FEATURE_WORDS`、`POSITIVE_WORDS`、`NEGATIVE_WORDS`
- `MATERIAL_KEYWORDS`、`GENERIC_SINGLE_CHARS`
- `LLM_SENTIMENT_PROMPT`、`LLM_SENTIMENT_PROMPT_V3`、`LLM_THEME_PROMPT`、`LLM_COMBINED_PROMPT_V1`、`LLM_CONFLICT_RETRY_PROMPT`、`LLM_THEME_PROMPT_V3`

### 已知问题修复

1. `EMOTION_SCORING["negative_life"]` 移除 `"懊道人"`（落款署名不承载正文情感）
2. `_get_artist_sentiment_note` 中移除"懊道人"相关负面引导，改为客观描述
3. `ARTIST_EMOTION_BASELINE` 中李鱓注释修正，不再以"懊道人"作为偏阴依据

### Performance Considerations

- 纯模块重构，无运行时额外开销
- Python 模块导入缓存保证性能不变

## Architecture Design

```
tibi_analysis_rules.py          ← 唯一规则源（修改只改这里）
         │
         ▼
inscription_content_analyzer.py  ← 分析引擎 + 门面导出（兼容现有调用方）
         │
    ┌────┼────┬────────┬────────┐
    ▼    ▼    ▼        ▼        ▼
 content_analysis.py  rebatch脚本  diagnose脚本  generate_academic_report.py  tubi_worker.py
```

## Directory Structure

```
backend/app/services/
├── tibi_analysis_rules.py              # [NEW] 集中规则配置文件。包含所有主题/情感/尺寸/画家基线/Prompt模板常量。这是唯一需要修改规则的地方。
│                                        #     同步修复：移除 EMOTION_SCORING 中 "懊道人"；修正 LLM prompt 引导；修正 ARTIST_EMOTION_BASELINE 注释。
├── inscription_content_analyzer.py     # [MODIFY] 分析引擎。删除所有规则常量定义（移至 rules 模块），改为从 tibi_analysis_rules 导入并重新导出。
│                                        #     保留所有分析逻辑函数（classify_inscription_v4、analyze_tiba_content、analyze_tiba_content_dual 等）。
│                                        #     _get_artist_sentiment_note 函数保留在此，但 prompt 内容修正。
└── ...                                 # 其他8个调用方文件无需修改（import 路径不变）
```

## Implementation Notes

- 迁移规则常量时，保持所有字典/列表/Prompt 字符串内容完全一致，仅移动位置
- `inscription_content_analyzer.py` 顶部添加 `from .tibi_analysis_rules import *` 或显式导入并重新导出全部24个常量
- 由于 `extract_material_tags` 函数依赖 `MATERIAL_KEYWORDS`，该函数继续留在 analyzer.py 中，但规则常量来自 rules 模块
- 重新导出方式：`THEMES = tibi_analysis_rules.THEMES` 或 `from .tibi_analysis_rules import THEMES as THEMES`，确保外部 `from app.services.inscription_content_analyzer import THEMES` 仍然有效
- 修改后立即运行 `rebatch_analyze_li_shan.py` 验证情感分布变化，确认"懊道人"不再系统性扣分