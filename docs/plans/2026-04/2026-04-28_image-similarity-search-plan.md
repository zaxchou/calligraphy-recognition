# 以图搜图 · 作品查重方案

## 背景

用户需要在上传新作品时，快速确认库里是否已有相同/相似作品（防止重复上传）。通过上传一张截图/照片片段，搜索库中匹配作品。集成到管理后台（`ContentVerify` 页面）。

---

## 技术调研

### ReMarker / GME-Qwen2-VL

你说的 "ReMarker" 大概率是指 **GME (General Multimodal Embedding)** 系列模型，即阿里开源的 `Alibaba-NLP/gme-Qwen2-VL-*B-Instruct`。它是基于 Qwen2-VL 的多模态 embedding 模型，支持：

- Image → Image（以图搜图）✅
- Text → Image（文字搜图）
- Text → Text

提供 2B 和 7B 两种尺寸，输出固定维度向量（通过余弦相似度比较）。

### 现有基础设施

| 组件 | 现状 | 可直接复用？ |
|------|------|:---:|
| **DashScope 多模态 Embedding** | `embedding_service.py` 已集成 `multimodal-embedding-v1`（1024 维）| ✅ |
| **FAISS** | `faiss-cpu 1.7.4` 已在 `requirements.txt` | ✅ |
| **缩略图** | 每张上传作品自动生成 300px 缩略图，路径 `data/thumbnails/{id}_thumb.jpg` | ✅ |
| **管理后台** | `ContentVerify.vue`，10 个标签页 | 需新增 Tab |
| **B/C 端差异** | `tubi_analyses` 表存所有数据，`title`, `artist`, `thumbnail_path` 等一应俱全 | ✅ |

### 方案选择

| 方案 | 描述 | GPU需求 | 精度 | 集成复杂度 |
|------|------|:---:|------|:---:|
| **A: DashScope API**（推荐） | 复用现有 `multimodal-embedding-v1`，生成 embedding 后存 FAISS | 无 | 中 | ★☆☆ |
| B: GME-Qwen2-VL 本地 | 下载 2B 模型本地推理 | 需 GPU（~4GB） | 高 | ★★★ |
| C: OpenCLIP 本地 | 已有 `open-clip-torch`，直接本地推理 | CPU 可用 | 低 | ★★☆ |

**推荐方案 A**：你已经为 DashScope API 付费，且已有 `embedding_service.py` 完整封装（含缓存、重试），无需额外部署。如果需要更高精度，可以后续切换方案 B。

---

## 实现计划

### Phase 1：后端 — 构建图像索引

**目标**：为全部已有作品生成 embedding 并存入 FAISS 索引

**步骤**：
1. 新建 `backend/app/services/image_search.py`
   - `ImageSearchEngine` 类
   - `build_index(artist="all")` — 遍历 `tubi_analyses`，取缩略图，调 `embedding_service.embed_image()`，用 FAISS `IndexFlatIP`（内积=余弦相似度）建索引
   - `save_index()` / `load_index()` — 持久化到 `data/.image_index/` 目录
   - `search(image_bytes, top_k=10)` — 接受上传图片，embed 后检索，返回 id + score + title + artist + thumbnail_url
   - `find_duplicates(threshold=0.95)` — 扫描索引，返回相似度 > threshold 的作品对

2. 新建脚本 `backend/scripts/build_image_index.py`
   - 一次性构建/重建索引
   - 支持 `--artist` 参数过滤

3. 索引更新机制：每次上传新作品后自动追加到索引（在 `tubi.py` 的上传端点末尾调用 `index.add_vector()`）

**新增依赖**：无（FAISS 已有）

---

### Phase 2：后端 — API 端点

**目标**：提供 HTTP 接口给前端调用

**位置**：新增 `backend/app/api/image_search.py`

```
POST /api/v1/image-search/rebuild-index
  → 重建全部索引（手动触发，返回耗时）

POST /api/v1/image-search/search
  Body: multipart/form-data { image: File, top_k: int=10 }
  → 返回 [{ id, title, artist, score, thumbnail_url, year, album_name }]

GET  /api/v1/image-search/duplicates?threshold=0.95
  → 返回 [{ pair: [作品A, 作品B], score }]
```

在 `main.py` 中注册路由。

---

### Phase 3：前端 — 管理后台新增 Tab

**目标**：在 `ContentVerify.vue` 中新增"作品查重"标签页

**组件**：新建 `frontend/src/components/tubi/ImageSearchPanel.vue`

**布局**：
```
┌─────────────────────────────────────────────┐
│  [  拖拽或点击上传截图/照片  ]              │
│  支持 jpg/png，建议裁切后上传              │
├─────────────────────────────────────────────┤
│  搜索结果（Top 10）                         │
│  ┌──────┬────────┬───────┬──────┐          │
│  │ 缩略图│ 作品名  │ 作者  │ 相似度│          │
│  │  □   │ 杂画册  │ 李鱓  │ 98.5%│          │
│  │  □   │ 花卉册  │ 李鱓  │ 87.2%│          │
│  └──────┴────────┴───────┴──────┘          │
├─────────────────────────────────────────────┤
│  潜在重复作品（相似度 > 95%）               │
│  牡丹图 ↔ 花卉册之牡丹   99.1%   → 查看     │
│  杂画册四 ↔ 杂画册五     96.3%   → 查看     │
├─────────────────────────────────────────────┤
│  [ 重建索引 ]  共 394 幅作品已索引          │
└─────────────────────────────────────────────┘
```

**交互**：
- 上传图片后自动搜索，显示 loading
- 点击搜索结果缩略图 → 打开 TubiDetail
- "重建索引"按钮 → 弹确认框 → 调 API → 显示进度
- 重复作品列表可点击展开对比

---

### Phase 4（可选）— 上传时自动查重

在作品上传流程中增加自动检测：
- 上传后自动 embed → 检索索引 → 若相似度 > 0.90 → 提示"可能重复，库里已有：{作品名}，是否继续上传？"

---

## 执行顺序

1. **Phase 1** — 构建索引后端（`image_search.py` + `build_image_index.py`）
2. **Phase 2** — API 端点（`image_search.py` 路由）
3. **Phase 3** — 前端 Tab（`ImageSearchPanel.vue`）
4. **Phase 4** — 上传自动查重（可选，后续再做）

---

## 验证标准

- [ ] 脚本 `build_image_index.py` 成功为全部 394 幅作品建索引
- [ ] `POST /search` 上传同一作品的截图能返回该作品（相似度 > 0.90）
- [ ] `GET /duplicates` 返回合理结果（不误报、不漏报）
- [ ] 前端 Tab 功能完整：上传 → 搜索 → 展示结果
- [ ] 新上传作品后索引自动更新
