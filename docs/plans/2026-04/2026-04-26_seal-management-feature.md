---
name: seal-management-feature
overview: 新增印章管理功能：后端新建 seals 表 + CRUD API + 图片上传 + 数据迁移脚本；前端新增 SealManager.vue 印章管理 Tab；改造 VerifyPanel 印章输入为标签插入模式。
design:
  architecture:
    framework: vue
    component: tdesign
  styleKeywords:
    - Claude Design
    - 朱砂红印章
    - 标签插入
    - 悬停预览
  fontSystem:
    fontFamily: Noto Sans SC
    heading:
      size: 18px
      weight: 600
    subheading:
      size: 15px
      weight: 500
    body:
      size: 14px
      weight: 400
  colorSystem:
    primary:
      - "#c96442"
      - "#c45c48"
    background:
      - "#fafaf8"
      - "#FFFFFF"
    text:
      - "#141413"
      - "#6b6b66"
    functional:
      - "#c45c48"
      - "#5a7d5a"
      - "#4a7ab8"
todos:
  - id: db-migration
    content: 创建 seals 表迁移脚本 + Seal 模型 + 注册
    status: pending
  - id: backend-api
    content: 实现 seals.py CRUD + 提取 + 图片上传 API，注册路由
    status: pending
    dependencies:
      - db-migration
  - id: frontend-api
    content: 在 api/index.js 新增 sealsApi 封装
    status: pending
  - id: seal-manager
    content: 创建 SealManager.vue 印章管理组件（表格+弹窗+图片上传）
    status: pending
    dependencies:
      - frontend-api
  - id: integrate-tab
    content: ContentVerify.vue 新增印章管理 Tab + 副标题更新
    status: pending
    dependencies:
      - seal-manager
  - id: verify-panel-reform
    content: Use [subagent:code-explorer] 改造 VerifyPanel 印章区域为标签插入模式
    status: pending
    dependencies:
      - frontend-api
  - id: extract-data
    content: 实现从 seal_content 提取印章的迁移逻辑并验证
    status: pending
    dependencies:
      - backend-api
---

## 产品概述

在管理后台新增「印章管理」功能模块，将印章从自由文本升级为结构化实体，支持按画家管理印章、上传印章图片、以及在题跋校对时快速插入印章。

## 核心功能

- **印章 CRUD**：新增/编辑/删除印章，每个印章包含文字内容、所属画家、印章类型、多张图片
- **数据迁移**：从现有 `tubi_analyses.seal_content` 按顿号/逗号提取印章，自动关联画家，去除"作者印："前缀
- **印章图片上传**：每个印章支持上传多张图片，后续手动补充
- **印章管理 Tab**：在 ContentVerify 新增「印章管理」标签页，表格展示 + 编辑弹窗 + 图片上传
- **印章插入改造**：VerifyPanel 的印章内容从 textarea 改为标签式插入，从印章库选择，鼠标悬停显示印章图片
- **去除前缀**：自动去除"作者印："等前缀文字

## 技术栈

- 后端：FastAPI + SQLite（沿用现有架构）
- 前端：Vue 3 + Element Plus（沿用现有架构）
- 图片存储：本地文件系统 `backend/data/seals/`，通过 static 挂载访问

## 实现方案

### 数据库设计

新建 `seals` 表，通过 `artist_id` 关联 `artists` 表，`images` 字段用 JSON 数组存储多张图片路径：

```sql
CREATE TABLE seals (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  artist_id INTEGER REFERENCES artists(id),
  seal_type TEXT DEFAULT '名章',
  images TEXT DEFAULT '[]',
  description TEXT,
  created_at TEXT,
  updated_at TEXT
);
```

### 后端 API

沿用 `artists.py` 的 CRUD 模式，新建 `seals.py`：

- `GET /seals` — 列表，支持 `artist` 参数按画家名过滤
- `POST /seals` — 新建印章
- `PUT /seals/{id}` — 编辑印章
- `DELETE /seals/{id}` — 删除印章
- `POST /seals/extract` — 从 `tubi_analyses.seal_content` 提取印章并入库
- `POST /seals/{id}/upload-image` — 上传印章图片（multipart/form-data）

### 前端改造

1. **SealManager.vue**：参照 `ArtistInfoManager.vue` 的 CRUD 模式，表格列（印章文字、画家、类型、图片数、操作）+ 编辑弹窗 + 图片上传区
2. **VerifyPanel.vue**：将印章 textarea 改为标签插入模式——显示已插入的印章标签（el-tag），点击"添加印章"弹出选择器，选择器中按当前画家过滤，鼠标悬停标签显示印章图片 popover
3. **sealsApi**：在 `api/index.js` 新增

### 数据迁移策略

`POST /seals/extract` 端点逻辑：

1. 查询所有 `seal_content IS NOT NULL` 的记录
2. 按顿号(、)、逗号(,)、中文逗号(，)分割
3. 去除"作者印："、"收藏印："等前缀
4. 去除空白、去重
5. 根据 `artist` 字段匹配 `artists` 表获取 `artist_id`
6. 批量 INSERT（ON CONFLICT SKIP 防重复）

### 图片存储

- 上传目录：`backend/data/seals/`
- 文件名：`{seal_id}_{timestamp}.{ext}`
- 访问方式：通过 FastAPI StaticFiles 挂载 `/static/seals/`
- `seals` 表 `images` 字段存储相对路径 JSON 数组

## 目录结构

```
project-root/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   └── seals.py              # [NEW] 印章 CRUD + 提取 + 图片上传 API
│   │   ├── models/
│   │   │   ├── seal.py               # [NEW] Seal SQLAlchemy 模型
│   │   │   └── __init__.py           # [MODIFY] 注册 Seal 模型
│   │   ├── main.py                   # [MODIFY] 注册 seals 路由 + 挂载 seals 静态目录
│   │   └── api/
│   │       └── content_analysis.py   # [MODIFY] verify 端点兼容 seal_content 新格式
│   ├── data/
│   │   └── seals/                    # [NEW] 印章图片存储目录
│   └── migrations/
│       └── create_seals_table.py     # [NEW] 建表迁移脚本
├── frontend/
│   └── src/
│       ├── api/
│       │   └── index.js              # [MODIFY] 新增 sealsApi
│       └── views/
│           ├── SealManager.vue        # [NEW] 印章管理组件
│           ├── ContentVerify.vue      # [MODIFY] 新增印章管理 Tab + 导入
│           └── VerifyPanel.vue        # [MODIFY] 印章区域改为标签插入模式
```

## 实现要点

- **el-input-number 在 dialog 内的渲染 bug**：本项目已确认该问题，出生年份已改用 `el-input type="number"`，印章管理中也应避免使用 `el-input-number`
- **图片上传**：使用 `el-upload` 组件，限制格式为 jpg/png/webp，单文件不超过 2MB
- **印章插入格式**：VerifyPanel 中选择印章后，`seal_content` 存储格式改为逗号分隔的印章名（如 "刘氏,海勇"），与现有格式兼容
- **悬停预览**：使用 `el-popover` 包裹印章标签，hover 触发显示图片
- **路由顺序**：FastAPI 中 `/seals/extract`、`/seals/{id}/upload-image` 等具体路由必须定义在 `/{id}` 通配符路由之前

## 设计风格

沿用管理后台现有的 Claude Design System 风格（暖色调 #c96442 为主色），印章管理 Tab 与作者信息 Tab 保持一致的视觉语言。

## 印章管理页面

- **顶部工具栏**：「新增印章」+「从库中提取」+「刷新」三个按钮
- **印章表格**：列含 印章文字、所属画家、类型、图片数、操作（编辑/删除）
- **编辑弹窗**（900px 宽）：表单含印章文字、画家选择（下拉）、类型选择、描述、图片上传区（el-upload 多图拖拽上传）
- **图片上传区**：缩略图网格展示已上传图片，每张带删除按钮

## VerifyPanel 印章插入区改造

- 原 textarea 改为：已插入印章标签行 + 「添加印章」按钮
- 印章标签使用 el-tag，样式为朱砂红底色（--seal-red: #c45c48），白字
- 鼠标悬停标签弹出 el-popover 显示印章图片（如有）
- 点击「添加印章」弹出选择器弹窗，按当前画家过滤，支持搜索，点击即插入
- 保留手动输入入口（可折叠），兼容旧数据编辑

## 印章标签悬停效果

- el-popover 宽度 200px，显示印章图片（最大宽 180px）
- 无图片时显示"暂无图片"占位
- 延迟 300ms 显示，避免快速划过时闪烁

## SubAgent

- **code-explorer**: 探索 VerifyPanel.vue 完整代码结构，确保印章插入改造不破坏现有保存逻辑；探索 content_analysis.py 的 verify 端点确认 seal_content 兼容性