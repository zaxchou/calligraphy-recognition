---
name: clickable-detail-tags
overview: 作品详情页标签可点击，点击后筛选/搜索包含该标签的所有作品
todos:
  - id: add-filter-tag-ref
    content: 在 TubiAnalysis.vue 中新增 filterTag ref 和相关状态变量
    status: pending
  - id: modify-gallery-filter
    content: 修改 displayedHistoryList computed，增加 filterTag 过滤逻辑
    status: pending
    dependencies:
      - add-filter-tag-ref
  - id: add-tag-click-handler
    content: 在详情页 .detail-tag 上绑定点击事件，调用 filterByTag()
    status: pending
  - id: add-filter-indicator
    content: 在画廊区域顶部增加筛选指示条（显示当前标签 + 清除按钮）
    status: pending
---

## 需求

详情页标签（目前只显示）需要可点击，点击后自动滚动到作品库画廊视图，并筛选显示所有包含该标签的作品。用户可以清除筛选回到全量展示。

## 功能点

1. 标签点击 → 设置标签筛选状态 → 滚动到画廊 → 画廊仅显示匹配标签的作品
2. 画廊顶部显示"当前筛选: xxx 标签名"指示条，带清除按钮
3. 点击清除按钮 → 恢复全量展示，指示条消失
4. 筛选同时包含自动标签（computed_tags）和手动标签（tags）的并集匹配

## 技术方案

基于现有 `TubiAnalysis.vue` 实现，无需新增文件。

### 修改点

1. **新增 ref**：`filterTag` 存储当前筛选的标签名（初始 null）
2. **修改 `displayedHistoryList`**：`computed` 中增加标签过滤逻辑——当 `filterTag` 非空时，仅保留 `getItemAllTags(item)` 包含该标签的作品
3. **标签点击事件**：在详情页 `.detail-tag` 上绑定 `@click="filterByTag(tag)"`，触发设置 `filterTag` 并滚动到画廊顶部
4. **画廊筛选指示条**：在画廊 grid 上方增加 `v-if="filterTag"` 指示条，显示当前标签名 + 清除按钮；清除按钮调用 `clearTagFilter()`
5. **清除函数**：`clearTagFilter()` 将 `filterTag` 置 null

### 关键代码

- `filterByTag(tag)`：设置 `filterTag = tag`，然后 `document.querySelector('.gallery-section')?.scrollIntoView()`
- `displayedHistoryList` 增加条件：`if (filterTag.value) return historyList.value.filter(i => getItemAllTags(i).includes(filterTag.value))`