# Composition 模块优化工作总结 · 2026-04-30

## 概览

本次对「潘天寿教你构图」模块进行了两轮优化，涉及 **6 个文件**，**3 次提交**。

---

## 第一轮：知识库注入 + LLM Prompt 增强

**提交**: `13dd078`

### 改动

| 文件 | 改动 |
|------|------|
| `qdrant_client.py` | `search_cases()` 删除 `source=uploaded_images` 过滤，扩展到全 `knowledge_images` 集合 |
| `composition_llm.py` | 新增 `context_knowledge` 参数 + `_safe_knowledge()` 格式化函数；Prompt 新增知识库原文段；`_build_score_table()` 扩展为每维度附带系统分析文本(120字)和建议(100字) |
| `stages.py` | 新增 `_fetch_knowledge_context()`：用匹配规则的关键词组搜索 `knowledge_texts` 取 top-5 原文，注入 LLM prompt |

### 效果

LLM 讲评从「规则术语转述」升级为「有原文依据的专业讲评」，引用潘天寿《关于构图问题》和《中国写意花鸟画教程》的上下文原文。维度评分表从仅有数字变为附带系统分析的文本。

**新增 LLM prompt 数据流**：
```
👖 新增字段
  ├─ 知识库原文 context_knowledge（潘天寿+花鸟教程原文节选）
  └─ 维度评分表扩增（分数 + 系统分析文本 + 建议）
```

---

## 第二轮：插图修复 + 起承转合改版

**提交**: `6e45c0b`

### 问题诊断

1. **报告无插图**：`backend/data/knowledge/extracted/` 下无 `mapping.json`，`figure_image_url()` 始终返回 None
2. **起承转合不准**：独立 CV + LLM pipeline 与主讲评 LLM 不同步

### 改动

| 文件 | 改动 |
|------|------|
| `qdrant_client.py` | 新增 `scroll_by_filter()`：通过 Qdrant scroll API + filter 按 `figure_id` 查图 |
| `figure_assets.py` | 新增 `figure_image_url_from_qdrant()`：当 `figure_image_url()` 失败时从 Qdrant 补图，带进程级缓存 |
| `stages.py` | `_build_rules_payload()` 增加 Qdrant fallback；`analyze_arrow_flow()` 改为空操作；新增 `draw_qczh_from_llm()`：从 LLM 讲评文本提取坐标 → 百分比转换 → 绘制箭头 |
| `composition_llm.py` | Prompt 新增要求 #9：结语后输出起承转合坐标 JSON；新增 `extract_qczh_coords()` 坐标提取函数 |
| `tasks.py` | 旧 arrow_analysis 阶段移除，改到 llm_narrative 之后执行 `draw_qczh_from_llm` |

### 效果

**插图修复**：不依赖 `mapping.json`，直接从 Qdrant 按 `figure_id` 查图 URL。

**起承转合改版前后对比**：
```
改版前: upload → CV线稿 → LLM(独立的起承转合分析) → 箭头 → LLM(讲评)
改版后: upload → CV指标+规则+知识库 → LLM(讲评文字 + 起承转合JSON) → 从JSON取坐标 → 箭头
                                          ↑ 同一次调用，完全一致
```

---

## 不改动部分（保持稳定）

| 模块 | 说明 |
|------|------|
| 规则关键词匹配 (`_score_rule`) | 精确匹配能正确映射 CV 问题到规则，无需替换 |
| `select_rules()` 三轮选取 | 已有 7 维度覆盖保障 |
| 起承转合 CV 工具函数 | `generate_lineart`、`draw_arrows_on_lineart` 保留复用 |
| `qichengzhuanhe.py` 独立 LLM 分析 | 保留文件不动（旧 pipeline 仍可单独调用），仅 composition 主流程改为新方案 |

---

## 相关 Plan 文件

- [plan_composition_optimize.md](./plan_composition_optimize.md)
- [plan_qczh_revamp.md](./plan_qczh_revamp.md)

## 生效方式

**需重启后端**，改动全部在 Python 后端代码。
