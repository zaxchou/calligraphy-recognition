---
name: tubi-verify-search-merge
overview: 合并数字定位与搜索功能：删除旧 jumpToId，将搜索框移到 VerifyPanel filter-row，搜索同时支持关键词和数字ID
todos:
  - id: remove-contentverify-search
    content: 删除 ContentVerify 头部搜索框、弹窗及所有搜索相关脚本/样式
    status: completed
  - id: add-verifypanel-props
    content: VerifyPanel 新增 apiBase + artist prop，ContentVerify 模板中传入对应值
    status: completed
  - id: move-search-to-verifypanel
    content: VerifyPanel 删除 jump-to-group，在原位置新增搜索框 + 搜索弹窗 + 搜索脚本 + 样式
    status: completed
    dependencies:
      - remove-contentverify-search
      - add-verifypanel-props
  - id: merge-id-search
    content: 数字ID搜索合并：纯数字输入时本地精确匹配 id 优先跳转，同时触发 API 搜索作为后备
    status: completed
    dependencies:
      - move-search-to-verifypanel
  - id: build-verify
    content: 构建验证与 lint 检查
    status: completed
    dependencies:
      - merge-id-search
---

## 产品概述

重构题跋校对页面的搜索定位功能：将 ContentVerify 顶部的搜索框下移到 VerifyPanel 的 filter-row 中（替换原有的"跳转定位"输入框），同时把旧数字ID定位功能合并进新搜索中，使搜索框同时支持作品名、年份、题跋文字和数字ID四种搜索维度。

## 核心功能

- **删除旧功能**：移除 VerifyPanel 中的 jumpToId 输入框和"定位"按钮；移除 ContentVerify 头部搜索框和搜索弹窗
- **新搜索框位置**：VerifyPanel filter-row 中原 jump-to-group 的位置
- **搜索维度**：作品名(title)、年份(year)、题跋文字(inscription_content)、数字ID(id) 四项模糊/精确匹配
- **结果弹窗**：弹窗展示搜索结果列表，点击后自动跳转定位
- **数字ID特殊处理**：纯数字输入时，除走 API keyword 搜索外，同时尝试在当前 records 中精确匹配 id 并直接跳转

## Tech Stack

- 前端：Vue 3 + Element Plus（沿用现有技术栈）
- 后端：FastAPI + SQLite（无需改动，keyword 参数已支持）
- 样式：沿用 `claude-design.css` 设计系统

## Implementation Approach

### 策略

将搜索能力从 ContentVerify 下放到 VerifyPanel，VerifyPanel 直接持有搜索框、调用搜索 API、展示结果弹窗、处理跳转。ContentVerify 只需给 VerifyPanel 新增 `apiBase` 和 `artist` 两个 prop。数字ID搜索走后端 keyword 接口，同时 VerifyPanel 本地尝试精确匹配 id 作为快捷路径。

### 关键决策

- **VerifyPanel 直接调 API**：减少父子组件 prop/event 传递复杂度，VerifyPanel 内聚搜索-结果-跳转完整闭环
- **数字ID双重路径**：纯数字输入时，先本地 `filteredRecords.find(r => r.id === Number(keyword))` 快速跳转；同时触发 API 搜索作为后备（应对目标记录不在当前 records 中的情况）
- **弹窗内嵌 VerifyPanel**：搜索结果弹窗作为 VerifyPanel 内部组件，选中后直接调用自身 `jumpToRecordById`

### 性能与可靠性

- 本地 id 匹配优先，毫秒级响应
- API 搜索带 limit=50，避免大数据量
- 若目标记录被当前分期/状态筛选过滤，jumpToRecordById 会自动清除筛选并重试

## Implementation Notes

- **VerifyPanel 新增 prop**：`apiBase: String`（API 根地址）、`artist: String`（当前作者）
- **删除 ContentVerify 搜索相关代码**：searchKeyword、showSearchDialog、searchResults、searchLoading、searchDialogTitle、doSearch、onSelectSearchResult、getThumbnailUrl 及模板中的搜索框/弹窗/样式
- **保留 VerifyPanel 的 jumpToRecordById**：被新搜索选中结果复用
- **Blast radius**：ContentVerify 到 VerifyPanel 的 prop 接口增加两个字段，无破坏性变更