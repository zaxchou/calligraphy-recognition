# 画家专属文献库设计规格

**日期：** 2026-06-09
**状态：** 待审查
**模块：** 画家文献（Artist Literature）

---

## 1. 概述

为每个画家建立专属文献库，支持上传学术论文和专著 PDF，提供在线阅读和基于 RAG 的 AI 问答能力。复用现有协议知识库的完整 pipeline（MinerU 解析 → 分块 → 向量化 → Qdrant），通过 `artist_id` 标签实现画家级作用域。

### 核心能力

1. **PDF 管理**：上传、列表、删除文献，自动提取元数据
2. **在线阅读**：Markdown 渲染 + PDF.js 原版查看，沉浸式弹窗
3. **AI 问答**：每画家一个专属"专家"，基于该画家文献范围回答问题
4. **全局兼容**：画家文献对全局小墨也可搜索

---

## 2. 数据模型

### 2.1 `pdf_books` 表新增字段

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `artist_id` | Integer, FK → artists.id | NULL | NULL = 现有知识库书籍，非 NULL = 画家文献 |
| `document_type` | String | 'book' | 可选值：'book'（现有）/ 'literature'（画家文献） |
| `journal` | String | NULL | 期刊/出版社名 |
| `publish_year` | Integer | NULL | 发表年份 |
| `doi` | String | NULL | DOI 编号 |

**迁移策略**：现有数据 `artist_id` 均为 NULL，零迁移成本。

### 2.2 Qdrant chunk metadata 新增字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `artist_id` | Integer | 从 pdf_books 继承，搜索时做 metadata filter |
| `document_type` | String | 'book' 或 'literature' |

存储在现有 `knowledge_texts` collection 中，不新建 collection。

### 2.3 `chat_sessions` 表新增字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `session_type` | String | 'global'（现有小墨）/ 'artist_expert' |
| `artist_id` | Integer, FK → artists.id | 画家专家会话绑定的画家 |

---

## 3. 后端 API

### 3.1 新增端点（`artist_literature.py`）

```
POST   /api/v1/artists/{artist_id}/literature/upload
       上传 PDF，自动关联该画家，触发解析+向量化
       Body: multipart file + optional metadata (title, journal, year, doi)
       返回: { book_id, task_id }
       权限: editor+

GET    /api/v1/artists/{artist_id}/literature
       获取该画家的文献列表
       Query: page, page_size, sort_by(year/title/upload_time), keyword
       返回: { items: [...], total, page, page_size }

GET    /api/v1/artists/{artist_id}/literature/{book_id}
       获取单篇文献详情（含 outline、元数据、chunk_count）

DELETE /api/v1/artists/{artist_id}/literature/{book_id}
       删除文献及关联的 chunks、images、Qdrant 向量
       权限: editor+

PATCH  /api/v1/artists/{artist_id}/literature/{book_id}
       修改元数据（手动查缺补漏）
       Body: { title?, authors?, journal?, publish_year?, doi? }

GET    /api/v1/artists/{artist_id}/literature/{book_id}/chunks
       获取文献全文 chunks（供 Markdown 阅读）

GET    /api/v1/artists/{artist_id}/literature/{book_id}/pdf
       获取原 PDF 文件流（供 PDF.js 渲染）
```

### 3.2 复用现有端点（加 filter 参数）

- `POST /api/v1/knowledge/search` — 加 `artist_id` 查询参数，搜索时做 metadata filter
- `POST /api/v1/knowledge/chat` — 加 `artist_id` 参数，聊天搜索限定画家范围
- `GET /api/v1/knowledge/tasks/{task_id}` — 复用任务状态轮询

---

## 4. 前端 UI

### 4.1 文献列表页

- 路由：复用 `/artist/:name/literature`（已有 `ArtistLiterature.vue`）
- 布局：卡片/列表双视图切换（和作品库 `ArtistWorks.vue` 一致的切换模式）
- 每篇显示：标题、作者、期刊、年份、处理状态
- 搜索框（在当前画家文献范围内搜标题/关键词）
- 排序：按年份 / 上传时间 / 标题
- 上传按钮（editor+ 可见）

### 4.2 沉浸式阅读

- 点击文献 → 弹出全屏弹窗（类似作品大图查看器）
- 弹窗内：左侧目录导航（outline），右侧 Markdown 正文
- "查看原 PDF" 按钮 → 切换 PDF.js 嵌入式渲染
- 支持多个弹窗同时打开（浏览器多标签），方便对比阅读
- 关闭弹窗回到列表

### 4.3 AI 问答（ChatFloat）

- 页面底部保留 ChatFloat 悬浮窗，切换为该画家专属专家模式
- 悬浮窗 = 快速提问入口（小窗）
- 点击展开 → 完整 ChatGPT 样式界面，可查看完整对话记录
- 系统提示词自动切换："你是 [画家名] 研究领域的专家..."
- 独立会话（`session_type='artist_expert'`），和全局小墨历史分开

### 4.4 元数据编辑

- 文献详情页显示元数据卡片（标题、作者、期刊、年份、DOI）
- 点击"编辑"可修改任意字段
- 上传时自动提取，失败则字段留空，用户手动填写

---

## 5. AI 专家实现

### 5.1 搜索过滤

`knowledge_chat.py` 的聊天搜索调用加 `artist_id` filter：

```python
filter_conditions = [{"key": "artist_id", "match": {"value": artist_id}}]
```

### 5.2 系统提示词

根据画家名定制 persona，其余规则和现有小墨一致：

```python
f"""你是一位专注于{artist_name}研究的学术专家。
你的知识基于该画家相关的学术文献和研究资料。
回答时请引用具体文献来源，标注书名和页码。
..."""
```

### 5.3 会话管理

- 画家专家会话：`session_type='artist_expert'` + `artist_id`
- 前端 ChatFloat 根据页面模式切换 session
- 全局小墨会话不受影响

---

## 6. 元数据自动提取

### 流程

1. **MinerU 解析阶段**（已有）：从 PDF 首页提取基础信息
2. **LLM 辅助提取**（新增）：解析完成后，取前 2 页 Markdown 内容发给 LLM
3. LLM 返回结构化 JSON：`{ title, authors, journal, publish_year, doi, abstract }`
4. 自动填入 `pdf_books` 对应字段
5. 用户可在前端手动修改任何字段

---

## 7. 代码拆分计划

### 7.1 `knowledge_api.py` 拆分

| 新文件 | 搬出内容 | 预估行数 |
|--------|---------|---------|
| `knowledge_books.py` | 书籍上传、删除、reingest、列表、详情 | ~300 行 |
| `knowledge_search.py` | 搜索 endpoint、搜索历史、缓存 | ~400 行 |
| `knowledge_tasks.py` | 任务状态查询、取消 | ~100 行 |
| `artist_literature.py` | 画家文献 CRUD（新增） | ~200 行 |
| `knowledge_api.py` | 精简：统计、规则、杂项 + router 汇总 | ~300 行 |

`knowledge_chat.py` 已独立，不需动。

### 7.2 执行策略

1. 每次搬一个文件，验证 import + endpoint 可访问
2. 不改函数体，只改文件位置和 import
3. router 用 `include_router()` 引入子模块
4. 搬之前 git commit（可回滚）
5. 每步做 code review

---

## 8. 改动量估算

| 区域 | 改动 | 预估 |
|------|------|------|
| 后端：数据库迁移 | pdf_books 加 5 字段，chat_sessions 加 2 字段 | ~30 行 |
| 后端：artist_literature.py | 画家文献 CRUD API | ~200 行 |
| 后端：knowledge_chat.py | artist_id filter + prompt 注入 | ~20 行 |
| 后端：knowledge_api.py | search/chat endpoint 加 artist_id 参数 | ~15 行 |
| 后端：元数据提取 | LLM 调用 + JSON 解析 | ~30 行 |
| 后端：代码拆分 | 搬函数（不改逻辑） | ~0 行新代码，纯重构 |
| 前端：ArtistLiterature.vue | 文献列表 + 上传 + 元数据编辑 | ~400 行 |
| 前端：PDF.js 集成 | 沉浸式弹窗 + PDF 渲染 | ~200 行 |
| 前端：ChatFloat 适配 | 模式切换 + 画家专家 session | ~50 行 |
| **合计** | | ~950 行新代码 |

---

## 9. 依赖

- **PDF.js**：前端 PDF 渲染（~400KB gzip），按需加载
- **MinerU**：已有，PDF 解析
- **Alibaba Cloud text-embedding-v3**：已有，文本向量化
- **DeepSeek**：已有，LLM 调用（元数据提取 + AI 问答）
- **Qdrant**：已有，向量存储

---

## 10. 风险与缓解

| 风险 | 缓解 |
|------|------|
| 代码拆分引入 bug | 逐个搬，每步验证+review，git commit 可回滚 |
| PDF.js 体积影响首屏 | 按需加载（import()），仅在打开 PDF 查看时加载 |
| LLM 元数据提取不准确 | 支持手动编辑兜底 |
| 画家文献量大导致搜索变慢 | artist_id filter 在 Qdrant 层面执行，性能有保障 |
