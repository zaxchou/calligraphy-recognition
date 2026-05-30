---
name: lishan-analysis-refactor
overview: 李鱓作品分析框架彻底重构：从行为分类改为意图导向分类，修复情感分析通道，批量重跑351幅作品
todos:
  - id: refactor-analyzer-core
    content: 重构inscription_content_analyzer.py核心分类体系：新THEMES定义、重写TEXT_SCORING_RULES/PAINTING_MATERIAL_RULES/EMOTION_SCORING、调整SIZE_THEME_RULES映射
    status: completed
  - id: refactor-analyzer-llm
    content: 重写LLM prompt(LLM_THEME_PROMPT_V3/LLM_SENTIMENT_PROMPT_V3)、修改analyze_tiba_content_dual为LLM优先融合、修复emotion_score缺失、去除classify_inscription_v4兜底逻辑
    status: completed
    dependencies:
      - refactor-analyzer-core
  - id: sync-backend-adapter
    content: 更新auto_tags.py适配新主题编码、更新content_analysis.py统计端点主题名称映射
    status: completed
    dependencies:
      - refactor-analyzer-core
  - id: sync-frontend
    content: Use [subagent:code-explorer]定位并更新前端所有硬编码主题名称( ContentAnalysis.vue等 )及颜色配置
    status: completed
    dependencies:
      - refactor-analyzer-core
  - id: rebatch-compare
    content: 编写并执行批量重跑脚本rebatch_analyze_li_shan.py，重跑351幅李鱓作品，输出新旧主题/情感分布对比报告
    status: completed
    dependencies:
      - refactor-analyzer-llm
      - sync-backend-adapter
---

## 产品概述

对李鱓351幅已分析作品彻底重构题跋内容分析框架，从"行为导向"的旧6分类升级为"意图导向"的新6分类，并以LLM优先策略重建情感分析，最终批量重跑并输出前后对比报告。

## 核心功能

- **主题体系重构**：将旧6类（记录创作信息/即景寄兴/讽喻社会/阐述画理/世俗祈愿/应酬送人）替换为新6类意图导向分类（身世自况/咏物寄兴/时事讽喻/画理自叙/吉语祥瑞/交游赠答）
- **规则引擎重写**：`TEXT_SCORING_RULES`、`PAINTING_MATERIAL_RULES`、`SIZE_THEME_RULES`全部按新主题重新映射关键词和权重
- **情感分析改为LLM优先**：`analyze_tiba_content_dual`中LLM通道作为主力，规则通道退化为矛盾校验器，修复emotion_score缺失问题
- **去除兜底逻辑**：彻底移除"记录创作信息"base_score=1和默认兜底，无明确主题时返回空列表而非硬塞分类
- **画家上下文深化**：李鱓专用配置——"懊道人"等关键词强制映射身世自况，情感基线整体偏阴
- **批量重跑+对比报告**：编写脚本重跑351幅，输出新旧分布对比、偏差作品清单、调整摘要
- **前端同步更新**：`ContentAnalysis.vue`主题名称、颜色配置同步替换

## 用户约束

- 录入的固定数据（图、题跋文字、印章内容、尺寸、创作时间）完全不动
- 作者信息里的提示词可完全重写
- 使用qwen3.5-plus模型，enable_thinking必须放JSON顶层

## Tech Stack

- 后端：FastAPI + SQLite + SQLAlchemy + jieba + httpx
- LLM：qwen3.5-plus（SiliconFlow）
- 前端：Vue 3 + Element Plus + ECharts
- 分析引擎：`inscription_content_analyzer.py` 纯Python规则+LLM双通道

## Implementation Approach

### 核心策略：自下而上重构

不修补旧框架，直接替换底层分类体系、规则引擎、LLM prompt和融合策略，然后批量重跑验证。

### 关键决策

1. **主题编码保持1-6不变，重映射含义**：避免数据库和前端大量编码映射改动，仅替换名称和关键词库

- code 1: 身世自况（原记录创作信息的位置，彻底重新定义）
- code 2: 咏物寄兴（原即景寄兴）
- code 3: 时事讽喻（原讽喻社会）
- code 4: 画理自叙（原阐述画理）
- code 5: 吉语祥瑞（原世俗祈愿）
- code 6: 交游赠答（原应酬送人）

2. **LLM优先的情感融合**：`analyze_tiba_content_dual`中，情感polarity和emotion_score以LLM结果为主，规则通道仅用于检测极端矛盾（如文本含"懊道人"但LLM判positive时触发重试）

3. **去除兜底**：`classify_inscription_v4`中，当所有主题得分<=0时返回空列表`[]`，不再默认塞入"记录创作信息"。`content_analysis.py`中保存逻辑兼容空主题

4. **李鱓专用主题权重**：在`_get_artist_theme_note`中新增关键词→主题强制映射表："懊道人/复堂/落拓/臣非老画师/两革科名"→身世自况(weight+3)，"世味辣/催租/画贱"→时事讽喻(weight+3)

5. **emotion_score修复**：`analyze_tiba_content_dual`的sentiment字典中，emotion_score优先取LLM返回的连续值；若LLM未返回则回退到规则通道计算值，确保每幅作品都有值

### 性能考量

- 351幅批量重跑通过管理后台`/batch`端点异步处理，每幅约1-2秒（LLM调用）
- 规则引擎本地计算，无额外I/O开销
- 重跑脚本支持断点续跑（跳过已更新记录）

### 架构设计

```
┌─────────────────────────────────────────────────────────────┐
│  前端 (Vue3 + ElementPlus)                                  │
│  ContentAnalysis.vue — 主题名称/颜色配置更新                  │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│  FastAPI 路由层                                              │
│  content_analysis.py — batch-analyze / verify / stats      │
│  统计端点适配新主题名称                                       │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│  分析引擎层                                                  │
│  inscription_content_analyzer.py                            │
│  ├─ THEMES (新6类意图定义)                                  │
│  ├─ TEXT_SCORING_RULES (重写关键词库)                        │
│  ├─ PAINTING_MATERIAL_RULES (调整主题映射)                   │
│  ├─ EMOTION_SCORING (调整情感词权重)                         │
│  ├─ classify_inscription_v4 (去掉兜底逻辑)                   │
│  ├─ LLM prompts (重写v3 prompt)                             │
│  └─ analyze_tiba_content_dual (LLM优先融合)                 │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│  标签计算层                                                  │
│  auto_tags.py — compute_tags 适配新主题编码映射              │
└─────────────────────────────────────────────────────────────┘
```

## Directory Structure

```
backend/
├── app/
│   ├── services/
│   │   └── inscription_content_analyzer.py   # [MODIFY] 核心重构：主题体系、规则引擎、prompt、融合策略
│   ├── api/
│   │   └── content_analysis.py               # [MODIFY] 统计端点适配新主题名称
│   └── services/
│       └── auto_tags.py                      # [MODIFY] 标签计算适配新主题
├── scripts/
│   └── rebatch_analyze_li_shan.py            # [NEW] 批量重跑351幅+输出对比报告
└── data/
    └── calligraphy.db                        # [MODIFY] content_analysis字段批量更新
frontend/
└── src/
    └── views/
        └── ContentAnalysis.vue               # [MODIFY] THEMES数组名称颜色更新
```

## Implementation Notes

- **Blast radius control**：主题编码1-6保持不变，仅替换名称和内涵，前端API无需改动编码映射
- **emotion_score兜底**：LLM未返回emotion_score时，用规则通道的emotion_score回退，确保100%覆盖率
- **LLM prompt温度**：temperature=0.1保持不变，确保分类一致性
- **断点续跑**：重跑脚本检查`content_analysis`中是否已有新主题名称（如"身世自况"），有则跳过
- **兼容性**：`theme_tags`字段用逗号分隔主题名，旧数据重跑后自然覆盖为新名称
- **前端颜色映射**：新主题配色沿用原有6色，按新主题语义微调（身世自况用深赭、咏物寄兴用松石、时事讽喻用苍墨、画理自叙用赭石、吉语祥瑞用紫藤、交游赠答用金色）

## Agent Extensions

### SubAgent

- **code-explorer**
- Purpose: 探索frontend/src/views/ContentAnalysis.vue中所有硬编码主题名称的引用位置，以及backend/app/api/content_analysis.py中统计端点的主题相关逻辑，确保前端同步无遗漏
- Expected outcome: 输出完整的主题名称引用清单和需要修改的代码位置