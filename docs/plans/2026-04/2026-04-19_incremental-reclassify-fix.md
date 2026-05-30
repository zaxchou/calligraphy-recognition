---
name: incremental-reclassify-fix
overview: 修复重分析接口的增量逻辑：当 force_reanalyze=false 时跳过已有分析结果的记录，只分析新增/未分析的记录。
todos:
  - id: fix-incremental-logic
    content: 修改 `content_analysis.py` 第 1345-1350 行，为 `force_reanalyze=False` 添加增量过滤条件
    status: completed
---

## 用户需求

实现真正的增量重分析逻辑。用户点击"增量"选项时，只分析尚未有分析结果的记录，跳过已有结果的记录。

## 问题分析

当前 `force_reanalyze` 参数已定义但从未使用，SQL 查询每次都返回全部记录，导致增量选项毫无意义。

## 核心逻辑

| 模式 | force_reanalyze | 行为 |
| --- | --- | --- |
| 增量 | false | 只分析 `content_analysis` 为空的记录 |
| 全量 | true | 强制重新分析所有记录 |


## 修改点

- 文件：`backend/app/api/content_analysis.py`
- 位置：第 1345-1350 行 SQL 查询
- 逻辑：当 `force_reanalyze=False` 时，在 WHERE 条件中加入增量过滤

## 技术方案

在 SQL WHERE 子句中动态添加增量过滤条件：

```python
# 增量模式：跳过已有分析结果的记录
skip_analyzed = "" if force_reanalyze else """
  AND (content_analysis IS NULL 
       OR content_analysis = '' 
       OR content_analysis = '{}')"""

cur.execute(f"""
    SELECT id, inscription_content, content_analysis, year, title, analysis_note FROM tubi_analyses
    WHERE (artist LIKE ? OR artist LIKE ?)
      AND inscription_content IS NOT NULL
      AND LENGTH(inscription_content) > 0
    {skip_analyzed}
""", (f"%{artist}%", f"%{artist}%"))
```

## 增量判断标准

一条记录被视为"已有分析结果"当且仅当：

- `content_analysis IS NOT NULL`
- `content_analysis != ''`
- `content_analysis != '{}'`

空字典 `{}` 也视为无结果，用于兼容从未分析过的新记录。