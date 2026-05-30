---
name: DynamicArtistList
overview: 后端新增作者列表 API（从数据库 DISTINCT 查询），前端4个页面的作者下拉从硬编码改为动态获取
todos:
  - id: backend-artists-api
    content: content_analysis.py 新增 GET /content-analysis/artists 端点
    status: completed
  - id: frontend-content-verify
    content: ContentVerify.vue 作者下拉改为 API 动态获取
    status: completed
    dependencies:
      - backend-artists-api
  - id: frontend-dimension-input
    content: DimensionInput.vue 作者下拉改为 API 动态获取
    status: completed
    dependencies:
      - backend-artists-api
  - id: frontend-content-analysis
    content: ContentAnalysis.vue 作者下拉改为 API 动态获取
    status: completed
    dependencies:
      - backend-artists-api
  - id: frontend-tubi-home
    content: TubiHome.vue 作者下拉改为 API 动态获取
    status: completed
    dependencies:
      - backend-artists-api
  - id: build-and-push
    content: npm run build 验证后 commit + push
    status: completed
    dependencies:
      - frontend-content-verify
      - frontend-dimension-input
      - frontend-content-analysis
      - frontend-tubi-home
---

## 产品概述

为管理后台四个页面（ContentVerify、DimensionInput、ContentAnalysis、TubiHome）的作者下拉列表从硬编码改为从 API 动态获取，新增作者时无需修改前端代码。

## 核心功能

- 后端新增 API 端点，从 `tubi_analyses` 表动态查询所有作者（去重）
- 四个前端页面统一改造：移除硬编码的 `el-option`，改为调用 API 获取作者列表
- 前端保留"全部作者"选项作为第一个选项

## Tech Stack

- 后端：Python / FastAPI / SQLAlchemy
- 前端：Vue 3 + Vite + ElementPlus + `<script setup>` + Composition API

## 实现方法

### 后端改造

**新增端点**：`GET /api/v1/content-analysis/artists`

- 从 `tubi_analyses` 表查询 `DISTINCT artist` 字段，去除空值
- 返回格式：`{"success": true, "artists": ["李鱓", "郑燮", "潘天寿", ...]}`
- 位置：`backend/app/api/content_analysis.py`，放在文件开头的 stats 路由附近
- 参考现有 `/content-analysis/stats` 端点的 SQLAlchemy 用法

### 前端改造（四个页面统一逻辑）

1. 组件 `onMounted` 时调用 `GET /api/v1/content-analysis/artists` 获取作者列表
2. 移除硬编码 `el-option`，用 `v-for` 渲染 API 返回的列表
3. 保留"全部作者"选项（value="all"）
4. 默认选中保持为"李鱓"（如果 API 返回列表中存在）

#### 各页面修改点

- **ContentVerify.vue**：第10-15行移除硬编码 options，新增 `artistList` ref 和 API 调用
- **DimensionInput.vue**：第15-20行同样模式，变量名 `selectedArtist` 在第229行
- **ContentAnalysis.vue**：第15行附近，`selectedArtist` 默认值在第407行
- **TubiHome.vue**：第42行，变量名 `artistFilter`

## 目录结构

```
backend/app/api/
└── content_analysis.py       # [MODIFY] 新增 /artists 端点

frontend/src/views/
├── ContentVerify.vue         # [MODIFY] 作者下拉改为 API 获取
├── DimensionInput.vue         # [MODIFY] 作者下拉改为 API 获取
├── ContentAnalysis.vue        # [MODIFY] 作者下拉改为 API 获取
└── TubiHome.vue              # [MODIFY] 作者下拉改为 API 获取
```