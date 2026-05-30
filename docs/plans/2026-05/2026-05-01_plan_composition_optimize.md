# Composition 模块优化方案

## 复核说明

第一次报告中有一个误差：我说"知识库文本完全没有接入构图分析"，但 `theory_basis` 实际上已经包含从 `CompositionRule` 表中匹配到的规则条件/量化标准（`condition` + `quantitative_standard`），LLM 能部分引用。但这只是规则元数据，不是原书原文解释。之前说的"完全没有"不够准确，应以"缺少原书上下文"替代。以下是逐条核实后的结论：

---

### 被否定的建议

| 原建议 | 否定原因 |
|--------|---------|
| "规则匹配升级为语义向量搜索 knowledge_texts" | **概念混淆**：`knowledge_texts` 是 PDF 原文文本，不是规则集合。规则在 `CompositionRule` SQLite 表中。把 knowledge_texts 当规则源来搜索是语义错误。真正需要的不是替换规则匹配，而是**在规则匹配之外新增**一段原文搜索，注入 LLM prompt 做上下文增强。两者互补而非替代。 |

---

## 一、可实施优化

### P0-1：LLM Prompt 注入知识库原文上下文

**现状**：`stages.py` `write_llm_narrative()` 传的 `theory_basis` 只有：
```
rule_name / category / subcategory / condition / quantitative_standard
```
这些是规则表的干数据。Qdrant `knowledge_texts` 集合（2092 chunks，含潘天寿《关于构图问题》+ 写意花鸟画教程原文）完全未被构图分析流程引用。

**改动**：基于当前匹配到的规则名称和 issue 关键词，构建搜索 query，搜索 `knowledge_texts` 集合（用 text-embedding-v3 做语义向量搜索），取 top-5 原文段落，传给 prompt 的新字段 `context_knowledge`。

**代码量**：~60 行

**预期效果**：LLM 讲评时能引用原书原文的具体解释和案例，从"规则术语转述"升级为"有原文依据的专业讲评"。

---

### P0-2：扩展相似案例搜索覆盖潘天寿插图

**现状**：`search_cases()` 过滤条件为 `source=uploaded_images`，排除了潘天寿插图（`source=pan.md`）和写意花鸟画教程图（`source=bird_flower_tutorial`）。

**改动**：删除 `source` 过滤条件。统一搜索 `knowledge_images` 全集合（~5 行）。

**预期效果**：相似案例搜索能从"仅用户上传作品"扩展到"用户上传 + 教程插图"，对比参考更丰富。

---

### P1：7 维度 CV 指标扩展

**现状**：`_build_checks()` 只有 4 项（留白/破平行/疏密/题款）。

**缺失维度及新增指标**：

| 维度 | 新增指标 | 来源 |
|------|---------|------|
| 均衡节奏 | 四象限质量分布（质心偏差度） | 新增 |
| 穿插结构 | 交叉类型统计（十字/一点/平行对比例） | 已有 `composition_cv.py` 数据 |
| 边角空间 | 四角空白面积标准差 | 新增 |

**代码量**：~100 行

---

## 二、不改动的部分

| 项 | 说明 |
|----|------|
| 规则关键词匹配 (`_score_rule`) | 精确字符串匹配能正确映射 CV 问题到具体规则 |
| `select_rules()` 三轮选取 | 已有 7 维度覆盖保障 |
| LLM prompt 基础结构 | 7 维度框架 + 审美判断框架完整 |

---

## 三、实施顺序

```
1. P0-2（5行代码，零风险） → 扩展图片搜索范围
2. P0-1（60行代码，核心提升） → 知识库原文注入 LLM prompt
3. P1（100行代码） → CV 指标扩展
```
