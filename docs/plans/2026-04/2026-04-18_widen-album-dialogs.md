---
name: widen-album-dialogs
overview: 调整 AlbumManager.vue 弹窗和选择区域尺寸，方便多选作品：新建/添加作品弹窗 500/600px→900px，选择区域高度 300→500px，缩略图 80→100px，item 最小宽 120→160px
design:
  architecture:
    framework: vue
  styleKeywords:
    - Claude风格
    - 大尺寸布局
    - 多选优化
todos:
  - id: adjust-dialog-widths
    content: 调整 AlbumManager.vue 所有弹窗宽度为 900px
    status: completed
  - id: adjust-selector-height
    content: 调整选择区域高度为 500px，网格列宽为 160px
    status: completed
  - id: adjust-thumbnail-size
    content: 调整缩略图尺寸为 100×100px
    status: completed
---

## 需求概述

优化 AlbumManager.vue 中选择作品区域的布局，解决当前弹窗太窄、选择区域高度不够、列宽太小的问题，方便用户一览多选作品。

## 核心功能

- 增大所有相关弹窗宽度（新建册页、添加作品、查看详情）
- 提高选择作品区域高度，便于浏览更多作品
- 增大作品缩略图和卡片尺寸，改善视觉效果

## 技术方案

### 涉及文件

- `frontend/src/views/AlbumManager.vue` - 仅修改此文件

### 具体改动

1. **弹窗宽度调整**：

- 新建册页弹窗：500px → 900px
- 添加作品弹窗：600px → 900px
- 查看册页详情弹窗：700px → 900px

2. **选择区域尺寸**：

- `.record-selector`/`.add-items-selector` 最大高度：300px → 500px
- 网格列最小宽度：120px → 160px

3. **缩略图尺寸**：

- `.record-thumb` 宽高：80px → 100px

## 设计调整

保持 Claude 风格设计不变，仅调整尺寸参数以提供更好的多选体验：

- **弹窗宽度**：统一调整为 900px，提供更宽敞的布局
- **选择区域高度**：从 300px 增加到 500px，便于同时浏览更多作品
- **作品卡片**：最小宽度从 120px 增加到 160px，显示更舒适
- **缩略图**：从 80×80px 增加到 100×100px，视觉更清晰

所有调整均保持原有的交互逻辑和视觉风格不变。