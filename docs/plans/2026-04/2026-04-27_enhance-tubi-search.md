---
name: enhance-tubi-search
overview: 扩展Tubi搜索功能，后端新增inscription_content/inscription_modern/seal_content/theme_tags/material_tags/year字段搜索，前端搜索结果增加匹配维度标签
todos:
  - id: backend-search
    content: 后端tubi.py搜索API新增6个字段搜索条件
    status: completed
  - id: frontend-search-dialog
    content: TubiSearchDialog新增题跋列和匹配标签
    status: completed
    dependencies:
      - backend-search
  - id: frontend-gallery-filter
    content: TubiGallery本地筛选增加题跋和印章字段
    status: completed
  - id: test-push
    content: 测试并推送
    status: completed
    dependencies:
      - frontend-search-dialog
      - frontend-gallery-filter
---

## 产品概述

扩展题跋搜索功能，从只能搜索作品名/作者，增加题跋文字、印章、标签、年份等搜索维度

## 核心功能

- 后端搜索API新增6个字段：inscription_content（题跋原文）、inscription_modern（现代文翻译）、seal_content（印章内容）、theme_tags（主题标签）、material_tags（画材标签）、year（年份精确匹配）
- 前端搜索结果弹窗新增"题跋"预览列，增加题跋/印章/标签/年份匹配标签
- 前端本地筛选增加 inscriptionContent 和 sealContent 字段
- 搜索提示文案更新，引导用户搜索题跋内容

## 技术栈

- 后端：FastAPI + SQLAlchemy（现有项目）
- 前端：Vue 3 + Element Plus（现有项目）

## 实现方案

### 核心思路

在后端 `/tubi/search` API 的 SQL WHERE 条件中新增6个字段的 ilike 模糊匹配（year 用等值匹配），前端同步更新本地筛选和搜索结果展示。

### 关键技术决策

1. **year 字段特殊处理**：keyword 尝试转为整数，成功则加 `TubiAnalysis.year == int_year` 等值匹配（OR），因为 year 是 Integer 类型不能用 ilike
2. **inscription_modern 也加入搜索**：用户可能用白话文搜索题跋内容
3. **theme_tags/material_tags 用 ilike**：虽然是逗号分隔字符串，ilike 可以匹配子串
4. **搜索结果返回数据无需改动**：已有 inscription_content 和 seal_content 字段

## 修改文件

### [MODIFY] `backend/app/api/tubi.py`（第1600-1608行）

在 search_images 的 query.filter 中新增6个字段搜索条件：

```python
keyword_filter = f"%{keyword}%"
year_condition = []
try:
    year_val = int(keyword)
    year_condition = [TubiAnalysis.year == year_val]
except (ValueError, TypeError):
    pass

filters = [
    TubiAnalysis.title.ilike(keyword_filter),
    TubiAnalysis.artist.ilike(keyword_filter),
    TubiAnalysis.period.ilike(keyword_filter),
    TubiAnalysis.notes.ilike(keyword_filter),
    TubiAnalysis.analysis_note.ilike(keyword_filter),
    TubiAnalysis.inscription_content.ilike(keyword_filter),
    TubiAnalysis.inscription_modern.ilike(keyword_filter),
    TubiAnalysis.seal_content.ilike(keyword_filter),
    TubiAnalysis.theme_tags.ilike(keyword_filter),
    TubiAnalysis.material_tags.ilike(keyword_filter),
]
if year_condition:
    filters.extend(year_condition)

query = query.filter(or_(*filters))
```

需要从 sqlalchemy 导入 `or_`

### [MODIFY] `frontend/src/components/tubi/TubiSearchDialog.vue`

1. 搜索结果表格新增"题跋"列（显示 inscription_content 截断预览，最多30字）
2. 匹配标签增加：题跋匹配、印章匹配、年份匹配
3. 搜索提示文案从"试试搜索：竹、梅、兰、菊"改为"试试搜索：竹、梅、兰、菊、题跋内容、印章文字"

### [MODIFY] `frontend/src/components/tubi/TubiGallery.vue`

本地筛选（第160-171行）增加 inscriptionContent 和 sealContent 字段匹配

## 实现细节

- 后端需要从 sqlalchemy 导入 `or_`（当前代码用 `|` 运算符，但字段多了用 or_ 更清晰）
- year 匹配是精确匹配（如搜索"1750"匹配 year=1750），不是模糊匹配
- TubiSearchDialog 中 inscription_content 预览截断30字，避免表格过宽