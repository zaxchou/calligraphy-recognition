---
name: fix-422-and-wider-selector
overview: 彻底解决 422 错误（移除 @keyup.enter）+ 让选择作品区域真正变宽（移除 el-form-item 宽度限制，调整 label-width）
todos:
  - id: fix-422-error
    content: 移除 @keyup.enter 并给 el-form-item 添加 full-width-item class
    status: completed
  - id: add-css-full-width
    content: 添加 CSS 样式让 full-width-item 真正占满宽度
    status: completed
    dependencies:
      - fix-422-error
  - id: check-tagmanager
    content: 检查并修复 TagManager.vue 类似问题
    status: completed
---

## 用户反馈问题

1. 创建册页时仍然出现 422 (Unprocessable Content) 错误
2. 弹窗宽度调整为 900px 了，但"选择作品"的框还是窄

## 核心需求

- 彻底解决 422 错误
- 让"选择作品"区域真正占满弹窗宽度，方便多选

## 问题分析

### 422 错误根因

`el-input` 上仍然存在 `@keyup.enter="createAlbum"`，可能和 `@submit.prevent` 冲突，导致 Enter 键仍触发额外请求。

### 选择区域宽度问题

Element Plus `el-form-item` 有默认宽度限制，弹窗虽然 900px 了，但内容区没有充分利用。

## 修复方案

1. **移除 `@keyup.enter="createAlbum"`** - 只通过点击按钮创建
2. **给 `el-form-item` 添加自定义 class `full-width-item`** - 选择作品项
3. **添加 CSS 覆盖 Element Plus 默认宽度限制** - `max-width: none`
4. **调整 `label-width` 从 80px 到 70px** - 给内容区更多空间