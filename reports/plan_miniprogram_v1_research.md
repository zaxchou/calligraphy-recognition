# 微信小程序转化方案 · 初步调研报告 v1

> 日期：2026-05-01 | 阶段：纯调研

---

## 一、当前项目概况

| 维度 | 详情 |
|------|------|
| **后端** | Python FastAPI + SQLite + Redis/Celery + Qdrant/FAISS |
| **前端** | Vue 3 (Composition API) + Vite + Element Plus + ECharts 5 + pdfjs-dist 4 |
| **代码规模** | 保守估计 200万行+（后端 60% 前端 40%） |
| **页面数** | 16 个路由页面 + 25 个组件 |
| **外部 AI 依赖** | SiliconFlow(Kimi-K2.5)、Qwen DashScope、DeepSeek、智谱、MinerU云API、百度OCR |

### 页面清单

| 路径 | 页面 | 功能 |
|------|------|------|
| `/` | Home | 首页 |
| `/recognize` | Recognize | 书法字体识别 |
| `/steles` / `/steles/:id` | Steles / SteleDetail | 碑帖数据库 |
| `/tubi` / `/tubi/:id` | TubiAnalysis / TubiDetail | 题跋分析 |
| `/tubi/ranking` | TubiRanking | 数据排行 |
| `/tubi/dimensions` | DimensionInput | 尺寸录入 |
| `/composition` | CompositionAnalyze | 潘天寿教你构图 |
| `/composition/print/:taskId` | CompositionPrint | 构图报告 |
| `/knowledge` | KnowledgeSearch | 写意知识库搜索 |
| `/content-analysis` | ContentAnalysis | 题跋大数据分析 |
| `/content-verify` | ContentVerify | 管理后台 |
| `/annotate/:id` | InscriptionAnnotator | 题跋标注 |
| `/qczh` | ArrowDemo | 起承转合分析 |

### 前端依赖清单

| 类别 | 技术 |
|------|------|
| 框架 | Vue 3 + Composition API + `<script setup>` |
| 构建 | Vite 5 |
| 路由 | Vue Router 4 (Hash 模式) |
| 状态管理 | Pinia 3 |
| UI | Element Plus 2.4 + Element Plus Icons + Lucide Vue Next |
| HTTP | Axios (带自动重试拦截器) |
| 图表 | ECharts 5 |
| PDF | pdfjs-dist 4 |
| 字体 | @fontsource/noto-serif-sc (思源宋体) |

---

## 二、技术栈兼容性分析

### ✅ 后端：几乎不需要改动

FastAPI HTTP API 可直接供 `wx.request` 调用。只需：
- 部署到云服务器 + HTTPS（小程序强制要求）
- 可选添加微信登录鉴权
- 可选加 API 网关限流

### ❌ 前端：完全不能直接复用

| 当前技术 | 小程序兼容情况 | 替代方案 |
|----------|---------------|----------|
| Element Plus | **完全不可用**（基于 DOM） | uni-ui / uView Plus / Vant Weapp |
| ECharts 5 | 需改用 echarts-for-weixin | echarts-for-weixin（Canvas渲染） |
| pdfjs-dist 4 | **完全不可用** | WebView / 服务端渲染为图片 |
| Vue Router 4 | 不可用 | uni-app pages.json 配置式路由 |
| Axios | 不可用 | uni.request / wx.request |
| Vite | 不可用 | uni-app CLI / HBuilderX |
| window/document API | 50+ 处使用了这些 API | 逐处改写为小程序等效 API |

### ⚠️ 部分兼容

| 当前技术 | 兼容性说明 |
|----------|-----------|
| Vue 3 Composition API | uni-app (Vue3模式) **直接支持** |
| Pinia 3 | uni-app 支持，基本无缝 |
| CSS 变量系统 | WXSS 支持 CSS 变量 |
| Canvas 操作 | 小程序有 Canvas 2D API，但 API 不同 |

---

## 三、迁移难度分级与工作量预估（全量）

### 🟢 简单（2-5天/页）— 纯展示/表单

| 模块 | 人天 |
|------|------|
| Home 首页 | 2-3 |
| DimensionInput 尺寸录入 | 1-2 |
| SealManager 印章管理 | 2-3 |
| AlbumManager 册页管理 | 2-3 |
| StripManager 条幅管理 | 2-3 |
| **小计** | **9-14** |

### 🟡 中等（5-10天/页）— 列表+详情+基础图表

| 模块 | 人天 |
|------|------|
| Recognize 书法识别 | 5-7 |
| Steles 碑帖列表/详情 | 5-7 |
| TubiHome 题跋首页 | 7-10 |
| TubiRanking 排行榜 | 7-10 |
| ContentVerify 管理后台 | 7-10 |
| CompositionPrint 构图报告 | 5-7 |
| **小计** | **36-51** |

### 🔴 困难（10-20天/页）— 复杂图表/Canvas/交互

| 模块 | 人天 |
|------|------|
| TubiAnalysis 题跋分析详情 | 15-20 |
| TubiDetail 题跋详情 | 10-15 |
| ContentAnalysis 大数据分析 | 10-15 |
| ArrowDemo 起承转合 | 10-15 |
| **小计** | **45-65** |

### ⚫ 极其困难 — 建议 WebView 兜底

| 模块 | 原生化代价 |
|------|-----------|
| KnowledgeSearch 知识库搜索 | 15-20 人天 |
| CompositionAnalyze 构图分析 | 20-25 人天 |
| InscriptionAnnotator 题跋标注 | 15-20 人天 |

### 🔧 基础设施改造

| 工作 | 人天 |
|------|------|
| API层改写（Axios→uni.request） | 3-5 |
| 路由体系重构 | 3-5 |
| Element Plus→uni-ui 替换 | 10-15 |
| ECharts→echarts-for-weixin | 7-10 |
| CSS→WXSS 适配 | 5-7 |
| 50+ 处 browser API 改写 | 5-7 |
| WebView 页面搭建 | 3-5 |
| uni-app 项目搭建 | 3-5 |
| **小计** | **39-59** |

---

## 四、总体工作量估算（全量）

| 场景 | 人天 | 1人 | 2-3人团队 |
|------|------|-----|----------|
| 核心功能（WebView兜底3个难页） | 180-270 | 8-12个月 | 4-6个月 |
| 全部原生化 | 220-320 | 10-14个月 | 5-7个月 |
| MVP最小版本 | 100-150 | 4.5-7个月 | 2-3个月 |

---

## 五、关键风险

1. **包体积**：主包 2MB / 总包 20MB（含分包），ECharts 完整版过大
2. **Canvas 标注**：InscriptionAnnotator 的小程序原生化极其困难
3. **SSE→WebSocket**：实时进度推送需切换方案
4. **文件上传**：拖拽上传 → wx.chooseImage/wx.chooseMessageFile
5. **AI 内容审核**：微信对 AI 生成内容审核较严
6. **BaiduSync 盘延迟**：开发建议迁到本地 SSD
