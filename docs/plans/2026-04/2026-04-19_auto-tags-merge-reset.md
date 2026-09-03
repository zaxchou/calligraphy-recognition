---
name: auto-tags-merge-reset
overview: 自动标签持久化到tags + 一键清空 + 标签可点击筛选
todos:
  - id: backend-auto-tags-persist
    content: 分析完成时调用 compute_tags() 结果追加写入 db_analysis.tags（tubi.py）
    status: completed
  - id: backend-reset-all-tags-api
    content: 新增 DELETE /tubi/tags/all 接口，清空所有作品的 tags 字段（tubi.py）
    status: completed
    dependencies:
      - backend-auto-tags-persist
  - id: frontend-tagmanager-reset-btn
    content: TagManager.vue header-actions 增加「清空所有标签」按钮
    status: completed
    dependencies:
      - backend-reset-all-tags-api
  - id: frontend-clickable-tags
    content: .detail-tag 绑定点击事件 filterByTag(tag)（TubiAnalysis.vue）
    status: completed
  - id: frontend-gallery-filter
    content: displayedHistoryList 增加 filterTag 过滤逻辑（TubiAnalysis.vue）
    status: completed
    dependencies:
      - frontend-clickable-tags
  - id: frontend-filter-indicator
    content: 画廊上方增加筛选指示条 + 清除按钮（TubiAnalysis.vue）
    status: completed
    dependencies:
      - frontend-gallery-filter
---

## 用户需求

1. **自动标签持久化**：分析完成时，`compute_tags()` 结果追加写入 `tubi_analyses.tags` 字段，与手动标签合并管理，之后可在 TagManager 中统一增删
2. **一键清空所有标签**：TagManager 增加「清空所有标签」按钮，清除所有作品的 `tags` 字段，重新生成时干净
3. **详情页标签可点击**：点击标签后自动滚动到画廊区域，仅显示包含该标签的作品，带筛选指示条和清除按钮

## 产品说明

- 自动标签（时期/尺幅/情感/画材/主题）和手动标签共用同一套 `tags` 字段，TagManager 中不可区分来源
- 清空操作针对所有作品全部标签，不是仅清空自动标签
- 重新分析时自动标签追加到已有 tags，不覆盖现有标签

## 技术方案

基于现有代码修改，新增 1 个 API 接口，修改 3 个文件。

### 后端修改

#### `backend/app/api/tubi.py`

1. **自动标签持久化** — 在分析完成处（`db_analysis.status = "analyzed"` 附近），调用 `compute_tags()` 并将结果追加到 `db_analysis.tags`（JSON 数组，合并追加不去重）
2. **新增 `DELETE /tubi/tags/all`** — 遍历所有 `tubi_analyses` 记录，将 `tags` 字段置为空数组 `[]`，返回清空数量

#### `backend/app/services/auto_tags.py`

- 无需修改，只作为纯函数被调用

### 前端修改

#### `frontend/src/views/TagManager.vue`

- 在 header-actions 区域新增「清空所有标签」按钮（红色 danger 类型），调用 `DELETE /tubi/tags/all`，清空后刷新标签列表并弹出确认提示

#### `frontend/src/views/TubiAnalysis.vue`

- **标签点击**：`.detail-tag` 绑定 `@click="filterByTag(tag)"`，设置 `filterTag` 并滚动到画廊
- **画廊筛选**：`displayedHistoryList` computed 增加 `filterTag` 过滤（基于 `tags` 字段匹配）
- **筛选指示条**：画廊 grid 上方增加 `v-if="filterTag"` 指示条，含标签名 + 清除按钮
- **函数**：`filterByTag(tag)`、`clearTagFilter()`、`filterTag` ref
- `getItemAllTags` / `getDetailAllTags` 可简化为只读 `tags`，但保留合并逻辑向下兼容