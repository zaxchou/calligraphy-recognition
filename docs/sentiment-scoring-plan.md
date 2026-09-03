# 情感评分系统完整改造计划

> 目标：建立一套有学术依据、可校准、可追溯的情感评分体系
> 当前状态：VADER 归一化已接入，但底层词典仍是人工设定

---

## 已完成

- [x] VADER 归一化公式（α=8，阈值 ±0.10）
- [x] 三维度置信度加权融合（text 0.354 / spatial 0.388 / seal 0.259）
- [x] 50 幅作品校准（MAE 0.372 → 0.042）
- [x] 推理文字完整显示三维度
- [x] 前端 VADER 徽章 + 学术引用

## 未完成（按优先级排序）

### Phase 1: 建立情感词典（核心）

**问题**：现在 `EMOTION_SCORING` 里每个词的分数是人工设的（怒 = -2.5, 愁 = -1.8），没有数据支撑。

**方案**：
1. 从现有规则中提取所有情感词（约 100 个）
2. 用 DeepSeek 在书画语境下给每个词打分（-4 到 +4，对齐 VADER 标度）
3. 生成 `emotion_lexicon.json`，每个词有：
   - `score`: 情感分数
   - `category`: 词性分类
   - `source`: "llm_rated"
   - `confidence`: LLM 的置信度
4. 替换 `tibi_analysis_rules.py` 中的硬编码分数

**验证**：用新词典重新跑 50 幅校准作品，对比 MAE

### Phase 2: 空间情绪量化

**问题**：现在空间情绪只有定性标签（"压抑宣泄""狂放不羁"），没有量化分数。

**方案**：
1. 为 8 种空间布局类型定义基准分数（基于论文数据）
2. 留白比例、题跋占比作为修正因子
3. 生成 `spatial_lexicon.json`

### Phase 3: 印章情绪量化

**问题**：印章情感只有简单分类，没有精细化分数。

**方案**：
1. 按印章类型（名印/闲章/鉴藏印）定义基准分
2. 用 LLM 给已知印章打分
3. 生成 `seal_lexicon.json`

### Phase 4: 端到端验证

**问题**：没有独立的验证集，无法证明泛化能力。

**方案**：
1. 从校准数据中留出 10 幅作为验证集
2. 用新词典 + VADER 跑验证集
3. 对比 LLM 参考分数
4. 输出验证报告（MAE、相关系数、极性准确率）

### Phase 5: 前端展示优化

**问题**：用户看不到分数来源和计算过程。

**方案**：
1. 情绪解读卡片显示各维度原始分 + 归一化分
2. 推导过程展示词典命中详情
3. 添加"方法论"弹窗，解释计算流程

### Phase 6: 文档和可复现性

**问题**：方法论没有系统文档。

**方案**：
1. 写方法论文档（算法、校准流程、验证结果）
2. 词典版本管理（每次更新记录变更）
3. 校准脚本可重复运行

---

## 执行顺序

```
Phase 1 → Phase 4（验证）→ Phase 2 → Phase 3 → Phase 4（再次验证）→ Phase 5 → Phase 6
```

每个 Phase 完成后：
1. 跑一次端到端验证（Phase 4）
2. 对比改进幅度
3. 记录到 changelog
4. commit + push

---

## 词典格式标准

```json
{
  "version": "1.0",
  "generated_at": "2026-05-27T12:00:00",
  "method": "llm_rating",
  "model": "deepseek-v4-flash",
  "entries": {
    "怒": {
      "score": -2.8,
      "category": "negative_strong",
      "confidence": 0.9,
      "source": "llm_rated",
      "note": "强烈愤怒，在书画语境中多指对世态的愤懑"
    }
  }
}
```

---

## 学术依据

1. **VADER**: Hutto & Gilbert (2014), "VADER: A Parsimonious Rule-based Model for Sentiment Analysis of Social Media Text", ICWSM
2. **情感词典构建**: Mohammad & Turney (2010), "Emotions Evoked by Common Words and Phrases", Emotion
3. **书法情感分析**: 相关中文书法情感计算论文（待补充具体引用）
