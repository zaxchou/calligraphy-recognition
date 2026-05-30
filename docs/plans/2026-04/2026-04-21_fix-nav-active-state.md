---
name: fix-nav-active-state
overview: 修复顶部导航菜单在子路由页面下的高亮状态，确保访问作品详情页等子路由时，对应的父级菜单项正确高亮。
todos:
  - id: fix-nav-active
    content: 修改 App.vue 中题跋分析和构图分析导航链接的 active 高亮逻辑
    status: completed
---

## 需求概述

修复顶部导航菜单在子路由访问时无法正确高亮的问题。

## 问题详情

当前 `frontend/src/App.vue` 顶部导航使用 Vue Router 的 `router-link` 的 `active-class="active"` 属性控制菜单高亮。但在访问子路由（如 `/tubi/:id` 作品详情页）时，"题跋分析"菜单项没有保持高亮状态。

## 需要修复的菜单项

- **题跋分析** (`/tubi`)：子路由包括 `/tubi/:id`（作品详情）、`/tubi/ranking`（数据排行）、`/tubi/dimensions`（尺寸录入）
- **潘天寿教你构图** (`/composition`)：子路由包括 `/composition/print/:taskId`（构图报告）、`/composition/arrow-demo`（箭头演示）

## 解决方案

将 `router-link` 的自动 `active-class` 高亮机制，替换为手动基于当前路由路径前缀判断的 `:class` 绑定，确保访问子路由时父级菜单始终保持高亮。

## 预期效果

访问 `/tubi/xxx` 时，顶部导航"题跋分析"保持高亮（显示 active 样式：文字变为深色 + 底部出现红色下划线）。
访问 `/composition/print/xxx` 或 `/composition/arrow-demo` 时，"潘天寿教你构图"保持高亮。

## 技术方案

### 实现策略

修改 `frontend/src/App.vue` 中的顶部导航 `router-link`，将 `active-class="active"` 替换为手动绑定的 `:class="{ active: $route.path.startsWith('/prefix') }"`。

### 具体改动

- `/tubi` 的 `router-link`：`:class="{ active: $route.path.startsWith('/tubi') }"`
- `/composition` 的 `router-link`：`:class="{ active: $route.path.startsWith('/composition') }"`

### 为什么这样改

Vue Router 4 的 `router-link` 默认 active 匹配在某些子路由场景下（如动态路由参数 `/tubi/:id`）可能不会正确触发父级链接的 `active-class`。手动基于 `$route.path.startsWith()` 判断是最可靠的方式，不受路由匹配算法的影响。

### 影响范围

仅修改 `frontend/src/App.vue` 文件，无其他依赖改动。首页 (`/`) 保留 `exact-active-class` 不变，其他无子路由的菜单项保持不变。