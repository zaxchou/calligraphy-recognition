# 情绪引擎 v3：词库增强 + LLM 逐维度校正

> 日期: 2026-05-28 | 状态: 计划中 | 作者: zaxchou

## 架构核心理念

**双引擎并列，词库为基线，LLM 为校正层。**

```
最终分数 = 词库基线分 + LLM 逐维度校正量
```

- 词库不是降级方案——它是独立、完整的评分基线引擎
- LLM 不是替代词库——它是审核词库结果后给出校正量的"复核员"
- 两者缺一不可：词库保证基线质量 + 护城河，LLM 修复词库盲区
- 两组分数全程保留，可追溯可对比

---

## 背景与问题

### 现有词库问题

当前 `emotion_lexicon.json`（385 词，DeepSeek 打分）：

1. **单字为主，多字词组不足** — "枯木逢春"被拆成"枯"(-2)+"木"(0)+"逢"(0)+"春"(+2)≈0，实际是积极
2. **无否定词处理** — "不俗"中"不"(-2)+"俗"(-2)=-4，实际是积极
3. **无程度副词加权** — "十分愁"和"微愁"得分相同
4. **无前缀/后缀修饰** — "莫愁"中的"莫"应中和"愁"
5. **覆盖率低** — 仅 385 词，大量题跋常用词未覆盖

### v2 引擎的缺陷

- 纯词库匹配，无上下文理解
- 分数与 TubiAnalysis 大分析页面脱节
- 无过程追溯，无管理界面

---

## 目标

1. **词库升级为基线引擎**：扩词组 + 加规则层，成为有护城河的独立评分系统
2. **LLM 校正层**：对词库结果做逐维度审核修正，输出结构化推理记录
3. **双源对比透明**：前端展示"词库基线 → LLM 校正 → 最终分数"全过程
4. **可追溯可管理**：管理后台查看/重跑/统计分析
5. **一次性发布 v3**：以上全部做完一起上线

---

## 详细方案

### 整体架构

```
题跋文本 / 空间信号 / 印章 / 主题 / 年代 / 作者
       │
       ▼
┌────────────────────────────────────────────────┐
│  Phase A: 文本预处理（规则层）                   │
│  - 否定词检测 + 反转                            │
│  - 程度副词检测 + 强度加权                       │
│  - 前缀/后缀修饰检测                             │
│  - 输出: 预处理后的标注文本                       │
└──────────────────┬─────────────────────────────┘
                   ▼
┌────────────────────────────────────────────────┐
│  Phase B: 词库引擎（8 维基线计算，< 1ms）       │
│  - 多字词组优先匹配（FCCPSL + 现有词库合并）    │
│  - 8 维度各出 raw score                          │
│  - VADER 归一化 → 基线综合分                     │
│  - 基线分即时展示                                │
└──────────────────┬─────────────────────────────┘
                   ▼
┌────────────────────────────────────────────────┐
│  Phase C: LLM 校正（异步，2-5s）                │
│  - DeepSeek V4 Flash 逐维度审核词库结果          │
│  - 输出: 每维度的校正量 delta                    │
│  - 缓存到 content_analysis.llm_analysis          │
│  - 同时记录完整推理过程                          │
└──────────────────┬─────────────────────────────┘
                   ▼
┌────────────────────────────────────────────────┐
│  Phase D: 分数融合                              │
│  - 各维度最终分 = 词库基线分 + LLM 校正量       │
│  - 加权融合 → 最终综合分                         │
│  - 两组分数同时保留（基线 vs 最终）              │
└──────────────────┬─────────────────────────────┘
                   ▼
┌────────────────────────────────────────────────┐
│  前端展示                                       │
│  - VADER compound bar（显示最终分）             │
│  - 推导表格：词库基线 → LLM 校正 → 最终分      │
│  - 每维度展开：LLM 推理文本 + 关键词分析        │
│  - TubiAnalysis 使用最终分                      │
└────────────────────────────────────────────────┘
```

---

### Lexicon Improvement (词库基线引擎)

#### 1. 外部资源导入

| 资源 | 规模 | 用途 | 获取方式 |
|------|------|------|---------|
| FCCPSL（古典诗歌情感词典） | 14,368 词 | 候选种子，书画重打分 | `github.com/Weiiiing/poetry-sentiment-lexicon` |
| 现有 emotion_lexicon.json | 385 词 | 基础保留 | 项目中已有 |

**流程**：
1. 下载 FCCPSL → 解析为候选词列表
2. 与现有 385 词去重合并 → 初始候选池
3. 用现有 `build_emotion_lexicon.py` 脚本机制，让 DeepSeek 在**书画题跋语境下**给候选词打分（-4 到 +4）
4. 目标：保留 2000-3000 个高质量词条（过滤掉与书画无关的词）
5. 标注 `source: "fccpsl_rerated"` 区分来源

#### 2. 规则引擎（Python 代码规则）

新增 `emotion_text_preprocessor.py`，包含以下处理器类：

```
NegationHandler
  - 否定词表：不、无、未、莫、勿、休、非、弗、毋
  - 规则：否定词后 1-2 个词极性反转
  - 特例："不俗"→ 不+俗 ≠ 否定俗，"不"在此为强调前缀 → 需特例表

AdverbHandler  
  - 程度副词表：十分、非常、极、甚、颇、略、微、稍
  - 规则：修饰后面的形容词/动词，放大/缩小强度系数
  - 系数：十分(×2.0)、甚(×1.5)、颇(×1.3)、略(×0.5)、微(×0.3)

PrefixSuffixHandler
  - 前缀表：可、堪、宜、足、莫、相
  - 规则：前缀 + 词根的复合情感分，通过特例表覆盖
  - 如"可悲"≠ 可 + 悲（悲的程度更强）
  - 如"莫愁"≠ 莫 + 愁（莫中和愁）

MultiWordPriority
  - 预扫描 multi-word 词组（≥2 字）优先匹配
  - 匹配到的多字词占用的字符位置，不再匹配单字
  - 示例："枯木逢春" 整体匹配得分，不再拆字
```

**规则层处理管道**：
```
原始文本 → MultiWordPriority 标注边界 → NegationHandler 标记 → 
AdverbHandler 加权 → PrefixSuffixHandler 处理 → 
词库匹配（跳过已匹配的字符位置）→ 后处理（反转/加权生效）
```

#### 3. 词库评分升级

当前 `analyze_text()` 在 `molin_engine.py` 中——改造为：

- 保留原有函数签名但增加 `use_rules=True` 参数
- 调用 `emotion_text_preprocessor` 预处理文本
- 匹配词库时：多字词组优先于单字
- 应用后处理规则（反转、加权）
- 最终 score = 匹配词基础分之和 × 否定反转 × 副词加权

---

### LLM 校正层

#### 调用方式

- 使用已存在的 `call_qwen_chat_async()`（`qwen_llm_client.py`）
- DeepSeek V4 Flash 模型
- temperature=0.1 保证一致性
- max_tokens=2000

#### Prompt 设计

LLM 接收：
1. 题跋全文
2. 词库引擎输出的各维度基线分数 + 匹配到的词
3. 空间信号、印章、主题、年代等元数据

LLM 输出：
```json
{
  "version": "v3",
  "model": "deepseek-v4-flash",
  "analyzed_at": "2026-05-28T14:30:00Z",
  
  "corrections": {
    "text": {
      "lexicon_base": -0.15,
      "delta": 0.40,
      "adjusted": 0.25,
      "confidence": 0.85,
      "reasoning": "词库将'迟'标为负面，但语境中'嫌迟'是惜时感叹...",
      "key_phrases": [
        {"phrase": "菊花开好", "lexicon_score": 0, "corrected_polarity": "positive", "note": "整体赞美菊花"},
        {"phrase": "亦嫌迟", "lexicon_score": -2, "corrected_polarity": "slightly_negative", "note": "惜时非悲伤"}
      ]
    },
    "spatial": {
      "lexicon_base": -0.10,
      "delta": 0.0,
      "adjusted": -0.10,
      "confidence": 0.70,
      "reasoning": "空间分析由规则完成，LLM 无异议"
    },
    // ... 每个维度类似
  },
  
  "combined": {
    "lexicon_base": -0.05,
    "delta": 0.17,
    "adjusted": 0.12,
    "polarity": "positive",
    "reasoning_summary": "李鱓晚年咏菊之作，词库低估了咏物类题跋的积极程度..."
  },
  
  "meta": {
    "token_count": 2800,
    "analysis_time_ms": 3200,
    "primary_correction": "词库低估了咏物类题跋的积极程度"
  }
}
```

#### 校正量约束

- 每个维度的 delta 范围：[-1.0, +1.0]（基线是 raw score，非归一化）
- 当 LLM 置信度 < 0.5 时：delta 取 0（不校正）
- 当 LLM 调用失败/超时：delta 全为 0（降级到纯词库）
- 记录标注 `analysis_method: 'lexicon_only' | 'llm_corrected'`

---

### 数据库存储

**不新增表，不新增列**——全部存入 `tubi_analyses.content_analysis` JSON 字段。

现有 `content_analysis` 结构：

```json
{
  // 现有字段保持不变
  "char_count": 42,
  "themes": [...],
  "sentiment": {...},
  "combined_sentiment": {
    // 改为使用 LLM 校正后的最终分数
    "polarity": "positive",
    "vader_normalized": 0.12,
    "method": "molin_v3",
    // ... 各维度的最终分数（基线 + delta）
  },
  
  // 新增 v3 字段
  "lexicon_scores": {
    // 各维度基线分数（纯词库结果）
    "text": { "raw": -0.15, "normalized": -0.05, "confidence": 0.8 },
    "spatial": { ... },
    // ... 8 个维度
    "combined_raw": -0.05,
    "combined_normalized": -0.02
  },
  "llm_analysis": {
    // LLM 完整校正输出
    "version": "v3",
    "model": "deepseek-v4-flash",
    "corrections": { ... },
    "combined": { ... }
  },
  "llm_reasoning_log": "LLM 的完整思考过程文本...",
  "analysis_method": "llm_corrected",
  "analysis_version": 3
}
```

---

### 实现步骤

#### Phase 1: 词库基线引擎升级

- [ ] 1. **下载 FCCPSL** — 从 GitHub 克隆 poetry-sentiment-lexicon 仓库，解析 FCCPSL 文件格式
      → 验证: 成功解析全部 14,368 词条，输出候选词列表

- [ ] 2. **候选词合并 + 书画重打分** — 修改 `build_emotion_lexicon.py`，支持从 FCCPSL 导入候选词，并调用 DeepSeek 在书画语境下重新打分
      → 验证: 输出 emotion_lexicon_v3.json，含 2000+ 词条，source 标注清晰

- [ ] 3. **创建 `emotion_text_preprocessor.py`**
      - NegationHandler 类
      - AdverbHandler 类
      - PrefixSuffixHandler 类
      - MultiWordPriority 类
      - `preprocess(text) -> AnnotatedText` 主入口
      → 验证: "不俗" → 分数非负；"十分愁" → 强度放大；"枯木逢春" → 整体匹配

- [ ] 4. **改造 `molin_engine.py` 的 `analyze_text()`**
      - 集成文本预处理器
      - 多字词组优先匹配逻辑
      - 后处理规则应用
      - 保留 `use_rules=False` 开关用于对比测试
      → 验证: 新 analyze_text 输出分数比旧版更合理（抽查 20 条题跋）

#### Phase 2: LLM 校正服务

- [ ] 5. **创建 `llm_emotion_corrector.py`**
      - `correct_dimensions(lexicon_result, inscription, context) -> dict`
      - 使用 `call_qwen_chat_async()` 调用 DeepSeek
      - Prompt 模板：词库结果 + 题跋上下文 → 逐维度校正量
      - 错误处理：超时/失败返回 None（全 0 delta）
      - 解析 LLM JSON 输出的健壮逻辑
      → 验证: 单元测试，传入测试文本返回结构化校正 JSON

- [ ] 6. **修改 `content_analysis.py` 的 `analyze_single_record()`**
      - 在词库引擎跑完后，异步调用 LLM 校正
      - 将 `lexicon_scores`、`llm_analysis` 写入 content_analysis JSON
      - 更新 `combined_sentiment` 使用校正后分数
      → 验证: API 返回包含 `llm_analysis` 字段

#### Phase 3: 管理后台

- [ ] 7. **新增管理员 API**：`/api/v1/admin/emotion-analysis`
      - `GET /logs` — 分析日志列表（分页、筛选方法/极性）
      - `GET /logs/{image_id}` — 单件作品完整分析记录
      - `POST /reanalyze/{image_id}` — 手动触发 LLM 重分析
      - `GET /stats` — 词库 vs LLM 校正量分布统计
      → 验证: 各接口返回正确数据

- [ ] 8. **前端管理页面**：分析日志查看器
      - 表格展示：作品名、分析方法、基线分、校正分、校正量、极性、时间
      - 展开详情：逐维度校正过程、LLM 推理文本
      → 验证: 页面正常渲染，数据正确

#### Phase 4: 前端展示优化

- [ ] 9. **改造 TubiDetail.vue 情绪卡片**
      - 保留 VADER compound bar（显示最终校正分）
      - 推导表格改造：三列「词库基线 → LLM 校正 → 最终分数」
      - 每个维度可展开：显示 LLM 推理文本 + 关键词分析
      → 验证: 展开/折叠正常，数据正确

- [ ] 10. **修复 TubiAnalysis 数据对接**
       - 确保 emotion_score 字段使用最终校正分
       - 情感分布统计使用 `content_analysis.combined_sentiment` 而非 `sentiment`
       → 验证: TubiAnalysis 情绪分布与 TubiDetail 一致

#### Phase 5: 批量处理

- [ ] 11. **创建批量重分析脚本 `batch_reanalyze_v3.py`**
       - 扫描所有已有 content_analysis 但无 `analysis_version=3` 的作品
       - 批量运行词库基线 + LLM 校正
       - 带进度显示，支持 `--dry-run`
       - 限速：每批 10 件，间隔 2s
       → 验证: 脚本运行完所有作品都标记为 analysis_version=3

---

### 涉及文件

| 文件 | 操作 | 说明 |
|------|------|------|
| `backend/app/services/emotion_lexicon.json` | 替换 | v3 新词库，2000+ 词条 |
| `backend/app/services/emotion_text_preprocessor.py` | **新建** | 规则引擎：否定/副词/前缀/多字词组 |
| `backend/app/services/molin_engine.py` | 修改 | analyze_text() 集成规则引擎 |
| `backend/app/services/llm_emotion_corrector.py` | **新建** | LLM 逐维度校正服务 |
| `backend/app/services/qwen_llm_client.py` | 复用 | 已有 LLM 调用客户端 |
| `backend/app/api/content_analysis.py` | 修改 | analyze_single_record 集成 LLM 校正 |
| `backend/app/api/admin/emotion_analysis.py` | **新建** | 管理后台 API |
| `backend/scripts/build_emotion_lexicon.py` | 修改 | 支持 FCCPSL 导入 |
| `backend/scripts/batch_reanalyze_v3.py` | **新建** | 批量重分析 |
| `frontend/src/views/TubiDetail.vue` | 修改 | 三列推导表格 |
| `frontend/src/views/TubiAnalysis.vue` | 修改 | 数据对接修正 |
| `frontend/src/locales/zh.js` | 修改 | 新增 i18n key |
| `frontend/src/locales/en.js` | 修改 | 新增 i18n key |

---

### 完成标准

- [ ] v3 词库含 2000+ 词条，source 标注完整
- [ ] 规则引擎正确处理否定反转、副词加权、多字词组优先
- [ ] LLM 校正服务返回结构化 JSON，含逐维度 delta + 推理
- [ ] API 返回同时包含 `lexicon_scores` 和 `llm_analysis`
- [ ] 前端展示三列推导：基线 → 校正 → 最终
- [ ] TubiAnalysis 情绪数据与 TubiDetail 一致
- [ ] 管理后台可查看日志、手动重分析
- [ ] 批量重分析脚本可运行
- [ ] 全部已有作品完成 v3 分析
