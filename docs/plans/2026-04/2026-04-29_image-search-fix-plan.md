# 以图搜图 · 自验证修复 + Qwen3-VL-Embedding 切换 + UI 重构 Plan

## 诊断结果

### 根因确认

自验证脚本结果：

```
测试1 (直接引擎): 394条索引, 搜缩略图 → 100%自我匹配 ✅
测试2 (HTTP API):  total_indexed=0, hits=0      ❌
```

**原因**：运行中的后端进程内 `get_search_engine()` 返回的 singleton 引擎已被 `build_index()` 摧毁（上次手滑点"重建索引"中途失败）。磁盘索引完好（`image_index.faiss` 394条/1.6MB），但内存中进程持有的实例已损坏。

### Qwen3-VL-Embedding 调研 → 决定

| 维度      | 当前方案 (DashScope v1) | Qwen3-VL-Embedding-8B via SiliconFlow |
| ------- | ------------------- | ------------------------------------- |
| 向量维度    | 1024                | **4096**（8B 模型）                     |
| 精度      | 同画家国画缩略图聚类过密        | 基于 Qwen3-VL，SOTA 视觉理解              |
| 部署方式    | 云端 API（DashScope）   | **SiliconFlow API**（已有 key）         |
| 延迟      | ~2s/张               | ~2s/张（API）                          |
| 费用      | 按调用计费               | 按调用计费（已有余额）                        |

**决定**：直接用 SiliconFlow `Qwen/Qwen3-VL-Embedding-8B`，与现有 `SILICONFLOW_API_KEY` 统一。embedding 维度从 1024 → 4096，需重建索引。

***

## Plan

### Step 1: 修复 singleton 自愈机制（让当前方案立即可用）

**修改文件**：`backend/app/services/image_search.py`

`get_search_engine()` 增加自动恢复：如果引擎 `total_indexed == 0` 但磁盘索引文件存在，自动调用 `_load_index()` 恢复。

```python
def get_search_engine() -> ImageSearchEngine:
    global _engine
    if _engine is None:
        _engine = ImageSearchEngine()
    # 自愈：如果内存中索引为空但磁盘文件存在，重新加载
    if _engine.total_indexed == 0 and os.path.exists(_engine._index_path()):
        _engine._load_index()
    return _engine
```

### Step 2: 切换到 Qwen3-VL-Embedding-2B 本地模型

**修改文件**：`backend/app/services/image_search.py` + `backend/app/modules/pantianshou_composition/embedding_service.py`

**方案**：在 `embedding_service.py` 中新增 `Qwen3VLEmbeddingService` 类，使用本地 Qwen3-VL-Embedding-2B 模型替代 DashScope API。

关键代码：

```python
class Qwen3VLEmbeddingService:
    def __init__(self):
        from transformers import AutoModel, AutoProcessor
        self.model = AutoModel.from_pretrained(
            "Qwen/Qwen3-VL-Embedding-2B",
            torch_dtype=torch.float16,
            device_map="auto",
        )
        self.processor = AutoProcessor.from_pretrained("Qwen/Qwen3-VL-Embedding-2B")

    def embed_image_sync(self, image_path):
        image = Image.open(image_path).convert("RGB")
        inputs = self.processor(images=image, return_tensors="pt")
        inputs = {k: v.to(self.model.device) for k, v in inputs.items()}
        with torch.no_grad():
            outputs = self.model(**inputs)
        vec = outputs.last_hidden_state[:, -1, :].cpu().numpy().flatten()  # 2048维
        return vec
```

**索引重建**：切换后维度从 1024 → 2048，需重建索引（约 3-5 分钟，本地推理更快）。

**降级策略**：保留 DashScope 作为 fallback（`Qwen3VLEmbeddingService` 初始化失败时自动回退到现有 `EmbeddingService`）。

### Step 3: UI 完全重构

**当前问题**：

1. "搜索"和"检测重复"两个按钮功能重叠
2. 页面布局松散，没有设计感
3. 上传区 + 搜索结果 + 重复列表堆叠在一起

**新设计**（Claude 风格）：

```
┌─────────────────────────────────────────────────────┐
│  📷 以图搜图                       394 幅已索引      │
│  上传作品图片，自动匹配库中最相似的作品              │
├─────────────────────────────────────────────────────┤
│                                                     │
│     [  拖拽图片到这里  ]                             │
│     支持 JPG / PNG / WebP                           │
│                                                     │
│     [  开始搜索  ]                                   │
│                                                     │
├─────────────────────────────────────────────────────┤
│  搜索结果                                           │
│  ┌──────┬──────────────┬──────┬───────┬──────┐     │
│  │ 缩略图│ 作品名       │ 作者 │ 年份  │ 相似度│     │
│  │  □   │ 水仙         │ 李鱓 │ 1753  │ 100% │     │
│  │  □   │ 花果册...    │ 李鱓 │ 1738  │ 93%  │     │
│  └──────┴──────────────┴──────┴───────┴──────┘     │
│  共 3 条结果，点击查看详情 →                         │
├─────────────────────────────────────────────────────┤
│  🔗 潜在重复 (1对)                          [展开]   │
│  花鸟草虫册十开之五 · 99.9% · 花鸟草虫册十开之一   │
└─────────────────────────────────────────────────────┘
```

**核心变化**：

1. **去重按钮合并**：去掉"检测重复"按钮 → 页面加载时自动检测重复对，结果折叠在底部
2. **上传区**：精心设计的拖拽区，上传后显示预览缩略图
3. **搜索结果**：表格式展示（缩略图 + 作品名 + 作者 + 年份 + 相似度），更紧凑
4. **重复列表**：折叠在底部，一行一对更简洁

### Step 4: 上传时自动追加索引

修改 `backend/app/api/tubi.py` 上传/替换端点末尾，调用 `engine.add_to_index()` 自动追加新作品的 embedding 到 FAISS 索引（无需完整重建）。

***

## 执行顺序

1. **Step 1**（5分钟）— 修复 singleton 自愈 + 重启后端 → 当前方案立刻能用
2. **Step 2**（15分钟）— 切换 Qwen3-VL-Embedding-2B + 重建索引
3. **Step 3**（20分钟）— UI 全面重构
4. **Step 4**（5分钟）— 上传自动追加索引

***

## 验收标准

* [ ] 用缩略图直接调 API 搜索自身 → 返回自身记录 100% 匹配

* [ ] 新上传图片 → 搜索返回正确结果

* [ ] Qwen3-VL-Embedding 模型启动成功，embedding 维度 2048

* [ ] 重复检测 0.995 阈值 → 合理结果（同画家 1-3 对）

* [ ] UI 只有一个搜索按钮，搜索结果清晰可读

* [ ] 重复列表自动折叠，默认展示概要

