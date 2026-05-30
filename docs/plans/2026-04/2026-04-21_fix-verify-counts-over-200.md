---
name: fix-verify-counts-over-200
overview: 修复校对页面统计数超过200条时只统计前200条的问题，后端单独返回 verified_count/translated_count/analyzed_count。
todos:
  - id: backend-counts
    content: 后端 /content-analysis/records 新增 verified/translated/analyzed_count
    status: completed
  - id: frontend-counts
    content: 前端 ContentVerify 使用后端返回的 count 字段
    status: completed
    dependencies:
      - backend-counts
  - id: verify
    content: 验证修复后数字正确
    status: completed
    dependencies:
      - frontend-counts
---

## 问题现象

校对页面显示「152 / 251 已校对」，数字不对，用户回忆之前已有约 205 条已校对；点击「未校对」时显示 48 条。

## 根因分析

前端 `verifiedCount` / `translatedCount` / `analyzedCount` 是在返回的 `records` 数组上 filter 计算的，而 API 默认只返回前 200 条（`limit=200`），导致统计不完整。后端返回的 `total=251` 是数据库总条数，但 `verifiedCount` 只统计了前 200 条。

## 核心需求

后端 `GET /content-analysis/records` 接口在返回 `records` 的同时，额外返回三个统计字段：`verified_count`、`translated_count`、`analyzed_count`（基于相同 WHERE 条件，不考虑 limit/offset）；前端直接使用这三个字段。

## 技术方案

### 后端修改（content_analysis.py）

在 `get_records` 函数中，在获取主查询结果后、返回前，再执行三个 COUNT 查询：

- `verified_count`: WHERE 条件相同，`inscription_verified = 1`
- `translated_count`: WHERE 条件相同，`inscription_modern IS NOT NULL AND LENGTH(inscription_modern) > 0`
- `analyzed_count`: WHERE 条件相同，`content_analysis IS NOT NULL AND content_analysis != '' AND content_analysis != '{}'`

三个 COUNT 都复用主查询的 `where_clauses` 和 `params[:-2]`（去掉 limit/offset），确保统计范围与记录列表一致。

### 前端修改（ContentVerify.vue）

- 移除本地 filter 计算逻辑
- 直接赋值：`verifiedCount.value = data.verified_count || 0`，其他两个同理
- 保持 `totalCount` 不变

## 涉及文件

- `backend/app/api/content_analysis.py` — 新增三个 count 字段
- `frontend/src/views/ContentVerify.vue` — 使用后端返回的 count 字段