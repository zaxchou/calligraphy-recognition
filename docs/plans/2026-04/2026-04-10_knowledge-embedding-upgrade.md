---
name: knowledge-embedding-upgrade
overview: 升级知识库图像 embedding：从零向量改为 DashScope multimodal-embedding-v1 真实图像向量，提升搜索准确性和完整性
todos:
  - id: add-config-and-env
    content: 在 config.py 新增 DASHSCOPE_MULTIMODAL_ENABLED 配置项，.env 新增开关默认 true
    status: completed
  - id: impl-dashscope-embed
    content: 在 embedding_service.py 新增 embed_image_dashscope() 方法，修改 embed_image() 调用逻辑，带降级开关和缓存
    status: completed
    dependencies:
      - add-config-and-env
  - id: add-image-search
    content: 修改 knowledge_api.py 搜索接口，额外查询 knowledge_images 集合并合并结果
    status: completed
    dependencies:
      - impl-dashscope-embed
  - id: test-verify
    content: 编写 test_multimodal_embed.py 测试脚本，验证图像 embedding 维度、缓存、跨模态搜索效果，运行确认无报错
    status: completed
    dependencies:
      - add-image-search
---

## 用户需求

知识库搜索"起承转合"时配图不准，根因是 `knowledge_images` 集合中图像向量全是零向量。需要接入 DashScope multimodal-embedding-v1 API 获取真实图像 embedding，实现跨模态语义检索（文本搜图）。

## 产品概述

改进知识库的图像搜索能力，使文本查询（如"起承转合"）能通过跨模态 embedding 精准匹配相关图片，而非依赖 BM25 关键词精确匹配。

## 核心功能

- 在 `embedding_service.py` 中新增 DashScope 多模态 API 调用，替换零向量为真实图像 embedding
- 在搜索 API 中同时检索 `knowledge_texts` 和 `knowledge_images` 两个集合
- 降级开关：`.env` 中 `DASHSCOPE_MULTIMODAL_ENABLED=false` 可零代码回退
- 写测试脚本验证 5 张图的 embedding 质量和跨模态搜索效果

## Tech Stack

- Python 3.14 + requests + asyncio（项目已有依赖，不引入新依赖）
- DashScope multimodal-embedding-v1 API（阿里云百炼，现有 QWEN_API_KEY 直接可用）
- Qdrant 向量数据库（现有集合 knowledge_images 已是 1024 维，无需改结构）

## Implementation Approach

### 核心策略：最小侵入 + 降级保护

1. **`embedding_service.py`**：新增 `embed_image_dashscope()` 方法，调用 DashScope 原生 multimodal API，复用现有缓存和重试逻辑。`embed_image()` 方法改为：开启时调新方法，关闭时返回零向量。
2. **`knowledge_api.py`**：搜索时额外查询 `knowledge_images` 集合，将图像结果合并到搜索结果中，标记 `type=image`。
3. **`config.py` + `.env`**：新增 `DASHSCOPE_MULTIMODAL_ENABLED` 开关。
4. **测试脚本**：写 `test_multimodal_embed.py`，验证单图 embedding 维度 + 跨模态搜索（文本搜图）。

### API 调用格式

```
POST https://dashscope.aliyuncs.com/api/v1/services/embeddings/multimodal-embedding/multimodal-embedding
Authorization: Bearer sk-xxx (现有 QWEN_API_KEY)
Content-Type: application/json

{
  "model": "multimodal-embedding-v1",
  "input": {
    "messages": [{
      "role": "user",
      "content": [
        {"image": "data:image/jpeg;base64,..."},
        {"text": "描述"}
      ]
    }]
  },
  "parameters": {"output_type": "dense"}
}
```

输出：1024 维 dense vector，与现有 Qdrant 集合维度一致。

### 性能与成本

- 图像 embedding：~1-2秒/张（API 调用），一次性入库后永久缓存
- 费用：¥0.003/张图，50 张图约 ¥0.15
- 搜索延迟：无变化（Qdrant 查询不变，向量搜索 ~50ms）
- 搜索质量：从纯 BM25 关键词匹配 → 向量语义匹配 + BM25 混合，质的飞跃

## Implementation Notes

- `embed_image()` 当前被 `analyzer.py` 的 `to_feature_vector_1024()` 通过 `embed_image_sync()` 调用，改动后自动生效
- DashScope 原生 API 不走 OpenAI 兼容模式，需单独的 HTTP 请求逻辑
- 图片需 base64 编码传入，numpy 数组需先转临时文件再编码（analyzer.py 已有此逻辑）
- 缓存 key 使用 `multimodal-v1:` 前缀区分，避免与智谱文本 embedding 缓存冲突
- 降级逻辑：API 调用失败时返回零向量，不影响现有功能
- 搜索结果合并时需去重（same vector_id），图像结果标记 `type=image` 和 `image_url`

## Architecture Design

```mermaid
graph TD
    A[用户搜索"起承转合"] --> B[EmbeddingService.embed_text]
    B --> C[智谱 API → 1024维文本向量]
    C --> D[hybrid_search: knowledge_texts]
    C --> E[search_knowledge_images: knowledge_images]
    D --> F[RRF 融合]
    E --> F
    F --> G[heuristic_rerank 精排]
    G --> H[返回: 文本段落 + 匹配图片]

    subgraph 入库流程
        I[PDF 图片] --> J[EmbeddingService.embed_image_dashscope]
        J --> K[DashScope multimodal API → 1024维图像向量]
        K --> L[upsert knowledge_images]
    end
```

## Directory Structure

```
backend/
├── app/
│   ├── core/
│   │   └── config.py                    # [MODIFY] 新增 DASHSCOPE_MULTIMODAL_ENABLED 配置项
│   └── modules/pantianshou_composition/
│       ├── embedding_service.py          # [MODIFY] 新增 embed_image_dashscope() 方法，修改 embed_image() 调用新方法
│       └── knowledge_api.py             # [MODIFY] 搜索时额外查询 knowledge_images 集合并合并结果
├── .env                                 # [MODIFY] 新增 DASHSCOPE_MULTIMODAL_ENABLED=true
└── scripts/
    └── test_multimodal_embed.py         # [NEW] 测试脚本：验证图像 embedding 和跨模态搜索
```

## Key Code Structures

```python
# config.py 新增
DASHSCOPE_MULTIMODAL_ENABLED: bool = os.getenv("DASHSCOPE_MULTIMODAL_ENABLED", "true").lower() in ("1", "true", "yes", "y")

# embedding_service.py 新增方法签名
async def embed_image_dashscope(self, image_path: str, text_hint: str = "") -> EmbeddingResult:
    """调用 DashScope multimodal-embedding-v1 获取图像向量"""

def embed_image_dashscope_sync(self, image_path: str, text_hint: str = "") -> EmbeddingResult:
    """同步版本"""
```

## SubAgent

- **code-explorer**: 用于验证改动后其他文件（bird_flower_ingest.py, knowledge_ingest.py）是否自动兼容新的 embed_image() 逻辑，确认没有遗漏的调用点