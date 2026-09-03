# 写意知识库分屏重构 + PDF.js 修复计划（含调研增强）

## 一、诊断结论

### 当前烂摊子
- **KnowledgeSearch.vue = 3836 行** — 单文件过大，正常范围 5 倍+
- **布局混乱**：右面板在 split-container 外部 + 左面板内嵌 content-detail-section（与右面板功能重复），用户看 2 套详情
- **PDF.js 报错**：`Cannot read from private field` — esbuild 破坏了 pdfjs-dist 4.8.69 的原生 `#private` 字段
- **BookReaderModal.vue（1662 行）已废弃但保留**

### 决策：推倒重建
3836 行掺杂过多，缝补不如重写。保留成熟组件（store/pdf 组件等），模板/脚本/样式全新写。

---

## 二、行业调研：最佳 RAG+PDF 搜索前端交互模式

### 2.1 调研对象

| 项目 | Stars | 用途 | UI 亮点 |
|------|-------|------|--------|
| **RAG-Anything** (HKUDS) | 1k+ | 多模态文档 RAG，基于 MinerU+LightRAG | 多模态融合搜索、知识图谱、上下文模块 |
| **LightRAG WebUI** | 12k+ | 知识图谱 RAG | 图谱可视化、Documents/Graph/Retrieval 三标签页、citation 标注 |
| **Dify** | 70k+ | LLM 应用平台 | Knowledge Pipeline 可视化编排、inline citation + source attribution |
| **Open WebUI** | 60k+ | 本地 LLM 界面 | 工作区管理、文档对话、引用溯源 |
| **buzzi.ai 设计指南** | — | RAG UX 最佳实践 | Answer-first 布局、side-by-side chat+sources、clickable citations |

### 2.2 核心发现：RAG 搜索 UX 金三角

经过对 5 个项目 + 行业设计指南的调研，公认的最佳交互模式是三个层次：

```
┌─────────────────────────────────────────┐
│  层次 1: AI 摘要 (Answer-First)          │ ← 用户最想看的答案直接放顶部
│  ┌─────────────────────────────────┐    │
│  │ 「气韵生动」指写意画中笔墨与...    │    │
│  │  详见《教程》第14页 [1] ...       │    │
│  └─────────────────────────────────┘    │
├─────────────────────────────────────────┤
│  层次 2: 出处引用 (Inline Citations)     │ ← 每句话标注来源，点击跳转原文
│  [1] 《中国写意花鸟画教程》p.14 → 📄    │
│  [2] 《潘天寿构图法则》p.78    → 📄     │
├─────────────────────────────────────────┤
│  层次 3: 原文对照 (Source Viewer)        │ ← 右侧 PDF 高亮原文位置
│  ┌─────────────┐ ┌──────────────────┐   │
│  │ 搜索结果列表 │ │  PDF Viewer      │   │
│  │  + 关联概念  │ │  (滚动到对应页)   │   │
│  │  + 关联配图  │ │  + bbox 高亮     │   │
│  └─────────────┘ └──────────────────┘   │
└─────────────────────────────────────────┘
```

### 2.3 RAG-Anything 可借鉴的具体点

**✅ 我们已有（MinerU 已接入）：**
- MinerU PDF 解析 → 文本块 + 图像提取 + bbox 空间位置
- Qdrant 向量搜索（texts/images/tables 三个集合）
- AI 摘要（带置信度分数）
- 混合搜索（BM25 + Vector）

**🔧 可加强的点：**

| RAG-Anything 功能 | 对我们项目的价值 | 实现难度 |
|---|---|---|
| **多模态上下文注入** | 搜索配图时，把图片 caption+描述 注入 LLM 上下文 | ⭐ 低（已有 caption 数据） |
| **跨模态知识图谱** | 画家→作品→技法→构图法则，可视化关系图 | ⭐⭐⭐ 高（需新增图计算） |
| **VLM 增强查询** | 上传画作照片，VLM 分析画面特征 → 匹配技法描述 | ⭐⭐ 中（类似以图搜图） |
| **Context Prepending** | 搜索时增强 chunk 上下文（前文+后文+章节标题） | ⭐ 低（已有此功能） |
| **Inline Citation [1][2]** | AI 答案中嵌入来源编号，点击跳转原文 | ⭐⭐ 中 |
| **自适应分块** | 技法类型/人物传记/理论 不同 chunk 策略 | ⭐⭐ 中 |

**🎯 本次重建重点采纳：Inline Citation + Answer-First 布局**

---

## 三、重建后的交互设计

### 3.1 三种视图（一颗组件树）

不再区分「搜索模式」和「专家模式」为两套独立 UI，而是三种连贯视图：

| 视图 | 触发条件 | 左面板 | 右面板 |
|------|----------|--------|--------|
| **搜索视图** | 默认 / 清空搜索 | 搜索框 + 书库 + 历史 | —（折叠） |
| **结果视图** | 执行搜索后 | AI摘要 + 结果列表 + inline citation | —（折叠） |
| **详情视图** | 点击某条结果 | 结果列表（收窄） | PDF 高亮页 + 大纲 + Markdown |

### 3.2 关键交互流程

```
用户输入"气韵生动"
  → 搜索（BM25+向量混合）
  → AI 摘要卡片出现在顶部
    「气韵生动」是谢赫六法之首... [1][2]
    → 每个 [N] 可点击 → 右侧展开 PDF + bbox高亮对应文本
  → 下方结果列表（文本/配图/表格卡片）
  → 点击结果卡片 → 右侧面板滑出：
    ┌──────────────────────────────────┐
    │  《中国写意花鸟画教程》    [📋] [✕]│
    ├──────────────────────────────────┤
    │  PDF 查看器（翻到对应页）         │
    │  ┌─────────────────────────┐     │
    │  │    [bbox 高亮区域]       │     │
    │  └─────────────────────────┘     │
    ├──────────────────────────────────┤
    │  大纲导航（折叠）                 │
    │  Markdown 原文（标签页切换）       │
    │  关联配图（图文对照）             │
    └──────────────────────────────────┘
```

### 3.3 Inline Citation 实现方案

AI 答案生成时增加 `require_citations: true`，返回结构化结果：

```json
{
  "answer": "「气韵生动」是谢赫六法之首，指... [1]",
  "citations": [
    { "id": 1, "chunk_id": "xxx", "book_title": "中国写意花鸟画教程", "page": 14 }
  ]
}
```

前端渲染时把 `[1]` 变成可点击的 `<sup>` 标签，点击触发右面板展开 + PDF 跳转。

---

## 四、执行计划

### Phase 1: 修复 PDF.js（1 个文件，~5 行改动）

**文件：** `frontend/src/components/PdfViewer.vue`
1. 将 `workerUrl` 从本地 `/pdf.worker.min.mjs` → CDN `https://cdnjs.cloudflare.com/ajax/libs/pdf.js/4.8.69/pdf.worker.min.mjs`
2. 保留本地 `/cmaps/`（cMap 不涉及 esbuild）
3. `optimizeDeps.exclude: ['pdfjs-dist']` 不变

**验证：** 重启 dev server 后 PDF 正常渲染

---

### Phase 2: 推倒重建 KnowledgeSearch.vue（~1500 行）

#### 2.1 模板结构

```
<template>
<div class="ks-root">
  <!-- 顶部：搜索栏 + 模式切换 + 统计 -->
  <header class="ks-header">
    <div class="ks-brand">写意知识库</div>
    <div class="ks-search-bar">搜索框 + 搜索按钮</div>
    <div class="ks-mode-tabs">[名词搜索] [专家模式]</div>
    <div class="ks-stats">X 本书 · Y 文本块 · Z 配图</div>
  </header>

  <!-- 主体分屏 -->
  <div class="ks-body" :class="{ 'has-right': rightPanelOpen }">
    <!-- 左面板 -->
    <div class="ks-left">
      <!-- AI 摘要卡片（answer-first） -->
      <div v-if="aiSummary" class="ks-summary-card">
        <div class="ks-summary-content" v-html="renderAnswerWithCitations(aiSummary)"></div>
        <div class="ks-summary-citations">
          <button v-for="c in aiSummary.citations" @click="openCitation(c)">
            [{{ c.id }}] {{ c.book_title }} p.{{ c.page }}
          </button>
        </div>
      </div>

      <!-- 搜索结果列表 -->
      <div v-if="results.length" class="ks-results">
        <ResultCard v-for="r in results" :result="r" @click="openDetail(r)" />
      </div>

      <!-- 专家模式：聊天区 -->
      <div v-if="mode === 'chat'" class="ks-chat">...</div>

      <!-- 书库管理（可折叠） -->
      <div class="ks-library-panel">...</div>
    </div>

    <!-- 右面板（PDF 对照查看） -->
    <transition name="slide-right">
      <div v-if="rightPanelOpen" class="ks-right">
        <div class="ks-right-header">
          <span>{{ activeResult?.book_title }}</span>
          <button @click="closePanel">✕</button>
        </div>
        <div class="ks-right-body">
          <PdfViewer :pdf-url="pdfUrl" :bboxes="pdfBboxes" :initial-page="pdfPage" />
          <div class="ks-right-tabs">
            <button :class="{ active: rightTab === 'outline' }" @click="rightTab='outline'">大纲</button>
            <button :class="{ active: rightTab === 'markdown' }" @click="rightTab='markdown'">原文</button>
            <button :class="{ active: rightTab === 'images' }" @click="rightTab='images'">配图</button>
          </div>
          <DocumentOutline v-if="rightTab==='outline'" :outline="documentOutline" />
          <MarkdownViewer v-if="rightTab==='markdown'" :markdown="markdownContent" />
          <ImageRelatedChunks v-if="rightTab==='images'" ... />
        </div>
      </div>
    </transition>
  </div>
</div>
</template>
```

#### 2.2 精简后的状态（~12 个，原来 20+）

```javascript
// 搜索
searchInput, hasSearched, selectedBooks, showUploadModal, highlightedIndex

// 分屏
activeResult, rightPanelOpen, rightTab
pdfUrl, pdfBboxes, pdfPage
documentOutline, markdownContent, relatedChunks

// 模式
activeMode  // 'search' | 'chat'

// 聊天
chatMessages, chatInput, chatLoading, chatSessionId

// 预览
previewVisible, previewImageUrl
```

#### 2.3 不再保留的（删除原因）

| 删除项 | 原因 |
|--------|------|
| `content-detail-section` | 右面板 PDF 已承担详情，左面板内嵌详情多余 |
| `activeContentTab`（文本/大纲/Markdown 三标签） | 移到右面板 `rightTab` |
| `loadPrevChunk/loadNextChunk` 翻页 | PDF 查看器自带宽页面翻页，文本翻页场景少 |
| `BookReaderModal.vue` 导入 | 不再使用 |
| 相关 ~200 行 CSS（content-detail-* 系列） | 不再需要 |

#### 2.4 保留不动

- `knowledgeStore.js`（462 行）
- `PdfViewer.vue`（修复 Phase 1）
- `DocumentOutline.vue`、`MarkdownViewer.vue`、`ImageRelatedChunks.vue`
- `UploadModal.vue`、`TableResultCard.vue`
- 所有 store API 调用逻辑

---

### Phase 3: 清理和验证

1. 删除未使用的 imports（`FileText`, `FileCode`, `Hash`, `Layers` 等）
2. 删除 `.isp-footer` CSS 残留
3. 功能验证 10 项确认清单

---

## 五、预估改动量

| 文件 | 改动 |
|------|------|
| `PdfViewer.vue` | ~5 行（CDN worker） |
| `KnowledgeSearch.vue` | **重写**，3836 → ~1500 行 |
| `knowledgeStore.js` | ← 不动 |
| `vite.config.js` | ← 不动 |
| 其他组件 | ← 不动 |
