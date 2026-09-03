---
name: verify-panel-single-reanalyze
overview: 在校对页面添加「重新分析」单条按钮，后端新增对应 API。
---

## 用户需求

在校对页面（VerifyPanel）的「重新翻译」按钮旁边添加「重新分析」按钮，可以针对当前作品进行单条重新分析。

## 核心功能

- 在 `VerifyPanel.vue` 的 action-row 添加「重新分析」按钮（条件：`currentRecord.inscription_verified`）
- 点击后调用后端单条分析接口，成功后刷新当前记录
- 保留现有的双轨画廊和视频背景功能不变

## 实现方案

1. **后端**：在 `content_analysis.py` 新增 `POST /content-analysis/analyze/{record_id}` 单条分析接口，复用 `batch_analyze` 中的 `process_record` 逻辑
2. **前端 VerifyPanel**：

- emits 添加 `'analyze'`
- 添加 `handleAnalyze` 方法
- action-row 添加「重新分析」按钮

3. **前端 ContentVerify**：

- 添加 `@analyze="onAnalyze"`
- 添加 `onAnalyze` 方法，调用单条分析 API，成功后刷新记录

4. **编译验证**

## 后端方案

在 `content_analysis.py` 的 `/batch` 接口后新增单条分析接口：

- 路由：`POST /analyze/{record_id}`
- 参数：`record_id: int`，`use_llm: bool = Query(default=True)`
- 逻辑：查询单条记录 → 调用 `process_record` 处理 → 更新数据库 → 返回成功
- 复用 `batch_analyze` 中的 `process_record` 内部函数（提取为独立函数或直接复制）

## 前端方案

- VerifyPanel.vue：
- `defineEmits` 增加 `'analyze'`
- 添加 `handleAnalyze` 函数，emit `{ id, inscription_content, title, year, analysis_note, width_cm, height_cm }`
- 在「重新翻译」按钮旁添加「重新分析」按钮，`:loading="analyzing"`
- ContentVerify.vue：
- `:analyzing="analyzing"` prop 已存在
- 添加 `@analyze="onAnalyze"` 事件监听
- 添加 `onAnalyze` 函数，调用 `POST /content-analysis/analyze/${id}`，成功后调用 `fetchRecords` 刷新

## 涉及文件

- `backend/app/api/content_analysis.py` — 新增单条分析接口
- `frontend/src/views/VerifyPanel.vue` — 添加按钮和 emit
- `frontend/src/views/ContentVerify.vue` — 添加 analyze 事件处理