# Plan: 报告插图修复 + 起承转合改版

## 问题1: 报告插图不显示

### 诊断

`backend/data/knowledge/extracted/` 下没有任何 `mapping.json` 文件。
→ `figure_assets._build_cache()` 返回空 dict
→ `figure_image_url("图十四")` 始终返回 None
→ `_build_rules_payload()` 中 `reference_images` 全部为空
→ `write_llm_narrative()` 中 `example_images` 列表为空
→ LLM prompt 中没有可用示例图 URL
→ 即使 LLM 尝试写 ![标题](url)，后处理 whitelist 过滤也全部清除

### 修复方案

不用修复 mapping.json（需要重跑 PDF 插图提取，成本高）。改从 Qdrant `knowledge_images` 直接用 `figure_id` 查图。

**改动点**：
1. `figure_assets.py`：新增 `figure_image_url_from_qdrant(figure_id)`，通过 Qdrant scroll + filter 查图 URL
2. `stages.py` `_build_rules_payload()`：当 `figure_image_url` 返回 None 时回退到 Qdrant 查询

**代码量**: ~30 行

---

## 问题2: 起承转合模块改版

### 现有方案的问题

`qichengzhuanhe.py` (~400 行) 当前流程：
```
CV 生成线稿图 → separate LLM call → 起承转合四点坐标 → 箭头叠加
```

问题：
1. 独立的 LLM call 与主讲评 LLM **不同步**——可能产生矛盾的描述
2. 线稿提取（`generate_lineart` ~100行 CV 逻辑）对国画效果不稳定
3. 复杂的铁律验证经常因 LLM 理解偏差而无效
4. 用户反馈一直不准

### 新方案

让 LLM 同步输出起承转合坐标，然后基于坐标直接绘制箭头。

```
stage 4 (llm_narrative) 扩展:
  ├─ LLM 生成讲评文字（已有）
  └─ 🆕 LLM 同步输出起承转合 JSON

stage 3 (arrow_analysis) 改为:
  └─ 从 LLM 输出中提取坐标 → 绘制箭头
```

### 具体改动

| 改动 | 行数 |
|------|------|
| LLM prompt 追加起承转合坐标输出 | +15 |
| `extract_qczh_coords()` 坐标提取 | +25 |
| `draw_qczh_from_llm()` 从 ctx.llm 取坐标画箭头 | +30 |
| `figure_image_url_from_qdrant()` 插图查询 | +25 |
| 旧 qichengzhuanhe.py 独立 LLM 部分裁剪 | -80 |
| **净增** | **~15 行** |

### 数据流变化

```
改版前:
  upload → CV线稿 → LLM(起承转合) → 箭头 → LLM(讲评)

改版后:
  upload → CV指标 → 规则匹配 → LLM(讲评 + 起承转合JSON) → 从JSON取坐标 → 箭头
                                    ↑ 同一次LLM调用，讲评与箭头完全一致
```

---

## 实施顺序

1. **插图修复** (30行，独立改动)
2. **起承转合 Prompt + 坐标提取** (40行)
3. **stage 3 改为后处理模式** (30行)
4. **旧代码裁剪** (-80行)
