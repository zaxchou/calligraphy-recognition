---
name: fix-batch-incremental-and-verify-count
overview: 修复增量分析筛选条件（应对齐已校对+已翻译），并修复前端limit:200导致VerifyPanel校对数与顶部统计不一致的问题。
todos:
  - id: fix-incremental-analyze-filter
    content: 修复增量分析筛选条件，要求已校对且已翻译
    status: completed
  - id: fix-frontend-limit
    content: 将前端 fetchRecords 的 limit 从 200 改为 500，确保记录不截断
    status: completed
  - id: fix-port-conflict
    content: 解决 8001 端口被旧进程占用问题，确保前端代理连到正确后端
    status: completed
---

## 用户原始需求

修复两个 bug：

1. **增量分析数量与增量翻译不一致** — 增量翻译17条，增量分析12条，之前也发生过类似情况
2. **校对数字显示不一致** — VerifyPanel 显示"已校对 1/156"，但 ContentVerify 顶部统计显示"已校对 207/251"

## 补充澄清

用户明确工作流顺序：校对 → 翻译 → 分析。增量分析的前置条件应该是"已校对 + 已翻译"。

## 问题根因

### Bug 1：增量分析筛选条件与增量翻译不一致

- **增量翻译** (`/translate/batch/stream`)：要求 `inscription_verified = 1 AND inscription_modern IS NULL`（已校对但未翻译）
- **增量分析** (`/reclassify/stream`)：仅检查 `content_analysis IS NULL`，**不要求已校对，也不要求已翻译**
- 导致已校对+已分析+未翻译的记录会被翻译端点包含，但不会被分析端点包含，两者基数不同

### Bug 2：VerifyPanel 校对数 156 ≠ 顶部统计 207

- `ContentVerify.vue` 的 `fetchRecords()` 请求 `limit: 200`
- 后端排序：`ORDER BY (CASE WHEN inscription_verified = 1 THEN 1 ELSE 0 END) ASC` — 未校对的排前面
- 总数251，已校对207，未校对44。前200条 = 44条未校对 + 156条已校对
- VerifyPanel 的 `filteredRecords` 仅在前200条中前端筛选，所以"已校对"只能看到156条
- ContentVerify 顶部显示的是后端 `verified_count`（全部207条）

## Tech Stack

- 后端：FastAPI + Python + SQLite
- 前端：Vue 3 + TypeScript + Element Plus

## 实现方案

### Bug 1：对齐增量分析的筛选条件

在 `/reclassify/stream` 端点中，增量模式（`force_reanalyze=False`）的 SQL 追加两个条件：

- `AND inscription_verified = 1` — 确保只处理已校对的记录
- `AND inscription_modern IS NOT NULL AND LENGTH(inscription_modern) > 0` — 确保只处理已翻译的记录

这样增量分析与增量翻译的前置条件完全一致：都是"已校对 + 未做某事"。

### Bug 2：消除前端 limit 导致的截断

将 `ContentVerify.vue` 中 `fetchRecords()` 的 `limit: 200` 改为一个足够大的值（如 `limit: 500`），或者直接去掉 limit 参数（后端默认50，需要同步调整）。

**更优方案**：前端请求 `limit: 500`（后端最大允许500），确保251条记录全部加载到前端。这是最稳妥且改动最小的方案。

### 额外修复：端口问题

8001 端口被旧 Python 进程占用，前端 vite.config.js 代理指向 8001 但旧进程返回 500 错误。需要在计划中包含：杀掉旧进程并在 8001 启动新后端。

## Agent Extensions

无需使用扩展。