# 情绪引擎 v3：词库初筛 + LLM 多维度校验

> 日期: 2026-05-28 | 状态: 计划中 | 作者: zaxchou

## 背景

### 现有问题

当前墨林情绪引擎（v2）的「文字维度」完全依赖单字词库匹配打分：

1. **单字误判严重**：中文单字在不同上下文中情感极性完全不同
   - "枯" 在 "枯木逢春" 中是积极的（重生希望），词库给负分
   - "淋漓" 在 "墨色淋漓" 中是赞美笔法，可能被标负面
   - "不俗" = "脱俗" = 积极，但词库只看到 "不" 给负分
2. **分数与大分析页面脱节**：情绪引擎的输出没有正确对接到 TubiAnalysis 大分析页面
3. **过程不可追溯**：LLM 跑完出结果，中间思考过程全部丢失，无法复盘
4. **无管理界面**：无法从后台查看、重跑、校验分析结果

### 根因

中文书画题跋是高度凝练的文言文，单字情感分析天然不足。需要理解完整句意才能准确判断。

## 目标

1. **准确率提升**：LLM 理解全文语义后校验每个维度的分数，替代纯词库打分
2. **过程可追溯**：LLM 的完整推理过程（每个维度的判断依据）被结构化记录并缓存
3. **前端可展示**：用户能看到「推导过程」—— 不只是 +0.33 这个数字，而是为什么是 +0.33
4. **后台可操作**：管理员能查看所有作品的分析日志、手动触发重分析
5. **数据一致性**：修复情绪分数与 TubiAnalysis 大分析页面的脱节问题

## 方案

### 架构总览

```
作品入库 / 手动触发
       │
       ▼
┌─────────────────────────────────────────────┐
│  Phase 1: 词库快速扫描（瞬间）              │
│  - 现有 analyze_text() 等 7 个函数          │
│  - 输出: 各维度 raw score + has_data        │
│  - 用途: 首屏即时展示 + LLM 不可用时的降级  │
└─────────────────┬───────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────┐
│  Phase 2: LLM 多维度校验（异步，2-5s）      │
│  - 输入: 题跋全文 + 空间信号 + 印章 + 主题  │
│  - 输出: 结构化 JSON（见下方格式）          │
│  - 缓存: 写入 content_analysis 表新字段     │
│  - 日志: 完整推理过程存储到 analysis_log     │
└─────────────────┬───────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────┐
│  Phase 3: 分数融合                          │
│  - 有 LLM 缓存 → 使用 LLM 分数             │
│  - 无 LLM 缓存 → 使用词库分数              │
│  - 同时保留两组分数供对比                    │
└─────────────────┬───────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────┐
│  前端展示                                   │
│  - VADER compound bar（已实现）             │
│  - 推导过程表格（LLM 推理 + 词库对比）     │
│  - 各维度详细分析卡片                        │
└─────────────────────────────────────────────┘
```

### LLM 输出格式设计

这是核心。LLM 返回的不是简单数字，而是一个**结构化的推理记录**：

```json
{
  "version": "v3",
  "model": "claude-sonnet-4-6",
  "analyzed_at": "2026-05-28T14:30:00Z",
  "inscription": "煞性无光黑煞时，菊花开好亦嫌迟...",

  "dimensions": {
    "text": {
      "score": 0.25,
      "confidence": 0.85,
      "polarity": "positive",
      "reasoning": "题跋以菊花为意象，'亦嫌迟'表达惜时之感，整体基调为咏物抒怀，偏积极",
      "key_phrases": [
        {"phrase": "菊花开好", "polarity": "positive", "note": "赞美菊花盛开之美"},
        {"phrase": "亦嫌迟", "polarity": "slightly_negative", "note": "惜时感叹，但非悲伤"},
        {"phrase": "笔墨淋漓", "polarity": "positive", "note": "赞美笔法生动"}
      ],
      "lexicon_comparison": {
        "lexicon_score": -0.15,
        "llm_score": 0.25,
        "discrepancy": "词库将'迟'标为负面，但语境中'嫌迟'是惜时而非悲伤",
        "lexicon_errors": [
          {"word": "迟", "lexicon_polarity": "negative", "actual_polarity": "neutral", "reason": "在'嫌迟'语境中表达遗憾但不构成负面情感"}
        ]
      }
    },
    "spatial": {
      "score": -0.10,
      "confidence": 0.70,
      "polarity": "slightly_negative",
      "reasoning": "题跋位于画面右上方，留白较多，构图偏疏朗，暗示清淡心境",
      "signals_interpreted": ["右上题跋位置", "大面积留白"]
    },
    "seal": {
      "score": 0.05,
      "confidence": 0.60,
      "polarity": "neutral",
      "reasoning": "仅一枚姓名印，无闲章，情感中性",
      "seals_analyzed": [
        {"content": "李鱓", "type": "name", "polarity": "neutral"}
      ]
    },
    "theme": {
      "score": 0.15,
      "confidence": 0.80,
      "polarity": "positive",
      "reasoning": "咏物寄兴主题，借菊花表达高洁品格追求，属积极情感范畴"
    },
    "period": {
      "score": -0.05,
      "confidence": 0.75,
      "polarity": "neutral",
      "reasoning": "李鱓晚年作品（约1750年），风格趋向放逸，情感略带沧桑但不消极"
    },
    "painting": {
      "score": 0.10,
      "confidence": 0.50,
      "polarity": "slightly_positive",
      "reasoning": "写意花卉用笔奔放，墨色淋漓，传递出自由洒脱的情感"
    },
    "brush_ink": {
      "score": 0.20,
      "confidence": 0.55,
      "polarity": "positive",
      "reasoning": "笔触流畅有力，墨色浓淡变化丰富，体现画家充沛的创作激情",
      "observed": ["浓墨主干", "淡墨花瓣", "飞白枝条"]
    }
  },

  "combined": {
    "score": 0.12,
    "normalized": 0.12,
    "polarity": "positive",
    "reasoning_summary": "李鱓晚年咏菊之作，借菊花表达惜时与高洁并存的复杂情感，整体偏积极。笔墨淋漓的写意风格增添了洒脱气韵。"
  },

  "meta": {
    "token_count": 2800,
    "analysis_time_ms": 3200,
    "lexicon_initial_score": -0.05,
    "llm_adjusted_score": 0.12,
    "score_shift": 0.17,
    "primary_correction": "词库低估了咏物类题跋的积极程度，LLM 通过理解完整语义进行了正向修正"
  }
}
```

### 数据库变更

`content_analysis` 表新增字段：

```sql
-- LLM 校验后的结构化分析结果（JSON）
ALTER TABLE content_analysis ADD COLUMN llm_analysis JSON;

-- 词库原始分数（用于对比）
ALTER TABLE content_analysis ADD COLUMN lexicon_scores JSON;

-- 分析日志（完整推理过程）
ALTER TABLE content_analysis ADD COLUMN analysis_log TEXT;

-- 分析方法标记: 'lexicon_only' | 'llm_verified'
ALTER TABLE content_analysis ADD COLUMN analysis_method TEXT DEFAULT 'lexicon_only';

-- LLM 分析的版本号（用于词库更新后重跑）
ALTER TABLE content_analysis ADD COLUMN analysis_version INTEGER DEFAULT 0;
```

### 实现步骤

#### Phase 1: 数据库 + 后端核心

- [ ] 1. 数据库 migration：新增字段 → 验证: SQLite 表结构正确
- [ ] 2. 创建 `backend/app/services/llm_emotion_verifier.py`：
  - `verify_emotion(text, spatial, seal, themes, year, artist) -> dict` 调用 LLM API
  - Prompt 模板：输出上述 JSON 格式
  - 错误处理：LLM 超时/失败时降级到词库分数
  → 验证: 单元测试，传入测试文本返回结构化 JSON
- [ ] 3. 修改 `molin_engine.py`：
  - `analyze()` 增加 `llm_analysis` 参数
  - 当有 LLM 结果时，用 LLM 分数替代词库分数
  - 保留 `lexicon_scores` 用于对比
  → 验证: 传入 LLM 结果时输出正确融合分数
- [ ] 4. 修改 `content_analysis.py` API：
  - 入库分析时异步调用 `llm_emotion_verifier`
  - 将 `llm_analysis`、`lexicon_scores`、`analysis_log` 写入数据库
  → 验证: API 返回包含 `llm_analysis` 字段

#### Phase 2: 管理后台

- [ ] 5. 新增管理员 API：`/api/v1/admin/emotion-analysis`
  - `GET /logs` — 分析日志列表（分页、筛选方法/极性）
  - `GET /logs/{image_id}` — 单件作品完整分析记录
  - `POST /reanalyze/{image_id}` — 手动触发 LLM 重分析
  - `GET /stats` — 分析统计（词库 vs LLM 分数差异分布）
  → 验证: 调用各接口返回正确数据
- [ ] 6. 前端管理页面：分析日志查看器
  - 表格展示：作品名、分析方法、综合分、极性、分析时间
  - 展开详情：LLM 推导过程、词库对比、各维度评分
  → 验证: 页面正常渲染，数据正确

#### Phase 3: 前端展示优化

- [ ] 7. 改造 TubiDetail.vue 的情绪解读卡片：
  - VADER bar 保留
  - 推导表格改造：显示「词库判断 → LLM 校正 → 最终分数」
  - 每个维度可展开：显示 LLM 的推理文本 + 关键词分析
  → 验证: 展开/折叠正常，数据显示正确
- [ ] 8. 修复与 TubiAnalysis 大分析页面的数据对接
  - 确认 emotion_score 字段正确传递
  → 验证: TubiAnalysis 页面显示的情绪分数与 TubiDetail 一致

#### Phase 4: 批量处理

- [ ] 9. 创建批量重分析脚本 `batch_reanalyze.py`：
  - 扫描所有已有 content_analysis 但无 llm_analysis 的作品
  - 批量调用 LLM 校验，带进度显示
  - 支持 `--dry-run` 模式预览
  → 验证: 脚本运行完后所有作品都有 llm_analysis

## 影响范围

- **后端**:
  - `molin_engine.py` — 核心融合逻辑改造
  - `content_analysis.py` — API 新增 LLM 调用 + 缓存
  - 新增 `llm_emotion_verifier.py` — LLM 调用模块
  - 新增 `admin/emotion_analysis.py` — 管理 API
  - 数据库 migration
- **前端**:
  - `TubiDetail.vue` — 情绪卡片改造（推导过程展示）
  - `TubiAnalysis.vue` — 修复数据对接
  - 新增管理页面：分析日志查看器
- **数据库**: content_analysis 表新增 5 个字段

## 风险与备选

| 风险 | 影响 | 缓解方案 |
|------|------|----------|
| LLM API 调用失败或超时 | 中 | 降级使用词库分数，标记 analysis_method='lexicon_only' |
| LLM 分数与词库差异过大 | 低 | 记录差异到 analysis_log，保留两组分数供人工审核 |
| 批量重分析成本 | 中 | 分批执行，每批 50 件，间隔 5s |
| 新字段 migration 影响现有数据 | 低 | 新字段均可为 NULL，现有数据保持词库分数 |

## 完成标准

- [ ] LLM 校验模块可用，能返回结构化 JSON
- [ ] 词库分数与 LLM 分数的对比清晰可见
- [ ] TubiDetail 推导表格展示完整的推理过程
- [ ] TubiAnalysis 大分析页面数据正确对接
- [ ] 管理员可以查看分析日志、手动触发重分析
- [ ] 批量重分析脚本可运行
- [ ] 所有已有作品的 llm_analysis 字段不为空
