# 知识库系统改进方案

> 基于 rag-retrieval、rag-patterns、document-processing 等外部技能的最佳实践

## 一、问题诊断总结

### P0 紧急问题
1. **图像向量化步骤完全缺失** — `knowledge_ingest_v2.py` 保存图像但不生成向量，`knowledge_images` 集合为空
2. **`time.sleep()` 阻塞事件循环** — `embedding_service.py` async 函数中使用同步 sleep
3. **Qdrant 异常全部静默吞掉** — `qdrant_client.py` 中所有 except 块不记录日志

### P1 高优先级
4. **纯向量搜索，无混合搜索** — 精确关键词（如"图十四""留白"）匹配能力差
5. **规则数据使用零向量** — `knowledge_ingest.py` 中规则和插图入库使用 `[0.0]*512`
6. **无 embedding 缓存** — 相同内容重复调用 API
7. **无 HTTP 连接复用** — 每次请求新建 httpx.Client
8. **`delete_book()` 未删除 Qdrant 向量** — TODO 未实现

### P2 中优先级
9. **语义分块实际是按段落边界分块** — 不是基于 embedding 相似度的真正语义分块
10. **overlap 策略不一致** — 语义分块用段落数，固定/滑动用字符数
11. **搜索无 reranking** — 检索质量受限
12. **`EmbeddingService` 每次新建实例** — 重复读取配置

### P3 低优先级
13. **PDF 图像提取不完整** — 无法提取矢量图
14. **图像 bbox 始终为 None** — 影响图号关联精度
15. **无 OCR 支持** — 扫描版 PDF 无法处理

## 二、改进方案（按优先级排序）

### Phase 1: 紧急修复（P0）

#### 1.1 修复 embedding_service.py 中的 time.sleep
```python
# Before
time.sleep(0.1)
# After
import asyncio
await asyncio.sleep(0.1)
```

#### 1.2 修复 qdrant_client.py 异常处理
在所有 except 块中添加 logging：
```python
import logging
logger = logging.getLogger(__name__)
except Exception as e:
    logger.error(f"Qdrant request failed: {e}")
    return None
```

#### 1.3 补全图像向量化步骤
在 `knowledge_ingest_v2.py` 的 `process_pdf()` 中，图像保存后添加：
```python
# 对图像生成向量并存入 Qdrant
image_points = []
for img_record in img_records:
    if img_record.stored_path:
        emb = await self.embedding_service.embed_image(img_record.stored_path)
        image_points.append({
            "id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"img:{img_record.id}")),
            "vector": emb.embedding,
            "caption": img_record.figure_id or "",
            "page_number": img_record.page,
            "image_path": img_record.stored_path,
            "related_chunk_ids": img_record.associated_chunks,
        })
if image_points:
    qdrant_client.upsert_images(image_points, book_id)
```

### Phase 2: 混合搜索（P1）

#### 2.1 实现 RRF 融合搜索
在 `qdrant_client.py` 中添加混合搜索支持：
```python
def reciprocal_rank_fusion(semantic_results, keyword_results, k=60):
    """RRF 融合语义搜索和关键词搜索结果"""
    scores = {}
    for rank, doc in enumerate(semantic_results):
        doc_id = doc["id"]
        scores[doc_id] = scores.get(doc_id, 0) + 1 / (k + rank + 1)
    for rank, doc in enumerate(keyword_results):
        doc_id = doc["id"]
        scores[doc_id] = scores.get(doc_id, 0) + 1 / (k + rank + 1)
    ranked_ids = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)
    return ranked_ids
```

#### 2.2 添加 BM25 关键词搜索
使用 SQLite FTS5 全文搜索实现关键词匹配：
```python
def bm25_search(query, book_ids=None, limit=20):
    """基于 SQLite FTS5 的关键词搜索"""
    # 在 text_chunks 表上创建 FTS5 虚拟表
    # 执行 MATCH 查询
```

### Phase 3: 性能优化（P2）

#### 3.1 添加 Embedding 缓存
```python
class EmbeddingCache:
    def __init__(self, redis_client=None):
        self.cache = {}  # 本地内存缓存（简单实现）
    
    def get(self, text_hash):
        return self.cache.get(text_hash)
    
    def set(self, text_hash, embedding):
        self.cache[text_hash] = embedding
```

#### 3.2 HTTP 连接复用
```python
# 在 qdrant_client.py 中使用模块级连接池
_http_client = httpx.Client(timeout=10.0, headers=_headers())
```

### Phase 4: 搜索增强（P2）

#### 4.1 上下文预填充（Context Prepending）
来自 Anthropic Research 的技术，减少 35% 检索失败：
```python
def contextualize_chunk(document_title, chapter_title, chunk_content):
    """为分块添加文档级上下文"""
    context = f"本文档是《{document_title}》，章节：{chapter_title}。"
    return f"{context}\n{chunk_content}"
```

#### 4.2 上下文充足性检查
```python
async def check_sufficiency(question, context):
    """检查检索到的上下文是否足以回答问题"""
    # 使用 LLM 判断
    prompt = f"以下上下文是否包含足够信息来回答问题？\n问题：{question}\n上下文：{context}"
    # 调用 LLM...
```

## 三、评估标准

### 检索质量指标（参考 rag-patterns）
| 指标 | 说明 | 工具 |
|------|------|------|
| Context Relevance | 检索到的文档是否相关 | RAGAS |
| Faithfulness | 答案是否基于上下文 | RAGAS |
| Answer Relevance | 答案是否回答问题 | RAGAS |
| Retrieval Recall | 正确文档是否被检索到 | 自定义评估集 |

### 改进效果预期
| 改进 | 预期效果 |
|------|---------|
| 混合搜索（BM25+向量） | 精确关键词匹配提升 40% |
| Context Prepending | 检索失败率降低 35% |
| Reranking | Top-10 精确率提升 20% |
| 图像向量化 | 图像搜索功能可用 |

## 四、实施计划

- [ ] Phase 1: P0 紧急修复（1-2小时）
- [ ] Phase 2: 混合搜索（2-4小时）
- [ ] Phase 3: 性能优化（2-3小时）
- [ ] Phase 4: 搜索增强（3-5小时）
