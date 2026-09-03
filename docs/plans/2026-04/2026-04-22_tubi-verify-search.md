---
name: tubi-verify-search
overview: 题跋校对页面增加搜索功能：在当前作者范围内按作品名/年份/题跋文字模糊搜索，弹出结果列表选择后跳转定位
design:
  architecture:
    framework: vue
  styleKeywords:
    - Claude Design
    - Minimalist
  fontSystem:
    fontFamily: Noto Serif SC
    heading:
      size: 16px
      weight: 500
    subheading:
      size: 14px
      weight: 500
    body:
      size: 13px
      weight: 400
  colorSystem:
    primary:
      - "#c96442"
    background:
      - "#ffffff"
      - "#faf9f5"
    text:
      - "#141413"
      - "#87867f"
    functional:
      - "#e8e6dc"
      - "#f0eee6"
todos:
  - id: backend-search-api
    content: 扩展后端 records 接口：增加 keyword 参数，支持 title/year/inscription_content 模糊搜索
    status: completed
  - id: verify-panel-jump
    content: VerifyPanel 暴露 jumpToRecordById 方法，支持在 filteredRecords 中定位并跳转
    status: completed
  - id: content-verify-search-ui
    content: ContentVerify 加入搜索框与结果弹窗，调用 API 并集成跳转
    status: completed
    dependencies:
      - backend-search-api
      - verify-panel-jump
  - id: polish-style-test
    content: 搜索弹窗样式调优与功能验证
    status: completed
    dependencies:
      - content-verify-search-ui
---

## 产品概述

为题跋校对页面（ContentVerify.vue / VerifyPanel.vue）增加搜索定位功能，支持在当前作者的作品中通过作品名、年份、题跋文字模糊搜索，弹出结果列表供选择后快速跳转到目标记录进行校对修改。

## 核心功能

- **搜索输入**：在 ContentVerify 页面头部增加搜索框，支持回车/点击触发搜索
- **后端搜索**：`GET /content-analysis/records` 新增 `keyword` 参数，对 `title` / `CAST(year AS TEXT)` / `inscription_content` 做 LIKE 模糊匹配
- **结果弹窗**：弹出 Claude 风格搜索结果列表，每条展示缩略图、标题、年份、题跋摘要
- **一键跳转**：点击搜索结果后，VerifyPanel 自动定位到该记录并切换显示

## Tech Stack

- 前端：Vue 3 + Element Plus（沿用现有技术栈）
- 后端：FastAPI + SQLite（沿用现有技术栈）
- 样式：沿用 `claude-design.css` 设计系统

## Implementation Approach

### 策略

后端扩展 records 接口增加 keyword 参数做 SQL LIKE 模糊匹配；前端在 ContentVerify 头部增加搜索框，点击搜索后调 API 获取匹配记录并弹出结果列表；VerifyPanel 暴露 `jumpToRecordById` 方法供父组件调用实现一键跳转。

### 关键决策

- **后端搜索而非前端过滤**：当前 records 接口 limit=500，若数据量超过此限制前端过滤会遗漏，后端 SQL LIKE 更可靠
- **SQLite 年份处理**：year 字段为 INTEGER，搜索时需 `CAST(year AS TEXT) LIKE ?` 避免类型不匹配
- **跳转机制**：VerifyPanel 通过 `defineExpose` 暴露 `jumpToRecordById(id)`，ContentVerify 通过 ref 直接调用，避免复杂的 prop/event 传递

### 性能与可靠性

- 搜索 API 带 limit=50，避免大量数据返回
- 题跋内容可能较长，结果列表中截断显示前 40 字
- 若目标记录被当前分期/状态筛选条件过滤掉了，给出友好提示

搜索弹窗沿用现有 Claude 风格设计系统，无需新建页面。

### 搜索框位置

ContentVerify 页面头部 `header-center` 区域，作者下拉选择器右侧，新增 `el-input` 搜索框（带 Search 图标 + 搜索按钮），宽度 220px。

### 搜索结果弹窗

- `el-dialog` 弹窗，标题"搜索结果"，宽度 640px
- 列表每条记录为横向卡片：左侧缩略图（56x56，圆角 8px）、中间信息区（标题 Noto Serif SC 16px + 年份标签 + 题跋摘要截断显示）、右侧"跳转"按钮
- 悬停时卡片背景变为 `--ivory`，边框变为 `--cinnabar-light`
- 空结果时显示 el-empty 提示