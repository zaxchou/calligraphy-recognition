# 数据库优化计划

> 适用范围：`calligraphy.db`（主库）+ `knowledge.db`（知识库）
> 当前状态：WAL 已启用，部分索引已建，仍有明显优化空间

---

## 一、PRAGMA 参数调优（优先级：高，风险：低）

### 现状
| 参数 | 当前值 | 问题 |
|------|---------|------|
| `cache_size` | -2000 (~8MB) | 偏小，频繁查询时缓存命中率低 |
| `journal_size_limit` | 未设置 | WAL 文件可能无限增长 |
| `temp_store` | 默认（文件） | 临时表/排序可放内存加速 |
| `mmap_size` | 默认 0（不 mmap） | 大文件读取可零拷贝加速 |
| `wal_checkpoint` | 默认 PASIVE | WAL 可能堆积，影响读取性能 |

### 优化方案

在 `database.py` 的 `init_db()` 连接初始化中加入：

```python
# backend/app/core/database.py  →  get_db() 或 init_db()

PRAGMA_OPTIMIZE = """
PRAGMA journal_size_limit = 67108864;   -- WAL 文件上限 64MB
PRAGMA cache_size = -10000;             -- ~40MB 缓存（当前 ~8MB）
PRAGMA temp_store = MEMORY;             -- 临时表放内存
PRAGMA mmap_size = 268435456;          -- 256MB mmap 加速大文件
PRAGMA wal_checkpoint = RESTART;        -- 连接时做 checkpoint（可选，看写入频率）
"""

def optimize_connection(conn):
    conn.executescript(PRAGMA_OPTIMIZE)
```

**预期效果**：大查询延迟降低 30-50%，WAL 文件大小可控。

---

## 二、缺失索引补充（优先级：高，风险：低）

### 2.1 `calligraphy.db` 缺失索引

| 表 | 缺失索引 | 覆盖查询场景 | 预估收益 |
|----|-----------|-------------|---------|
| `tubi_analyses` | `(artist, status)` | 按艺术家 + 状态过滤（前端列表最常用） | 高 |
| `tubi_analyses` | `(library_id, visibility, status)` | 库内作品列表（分页查询） | 高 |
| `tubi_analyses` | `(artist, library_id)` | 按艺术家查特定库 | 中 |
| `tubi_analyses` | `(updated_at DESC)` | 按更新时间排序/过滤 | 中 |
| `artists` | `(name)` | 按名精确查询（当前只有 PK 索引） | 高 |
| `artists` | `(enabled, featured)` | 前端过滤启用/精选艺术家 | 中 |
| `artist_rules` | `(artist_name)` | 规则查询（当前无索引） | 高 |
| `notifications` | `(user_id, is_read, created_at DESC)` | 未读通知列表（组合索引） | 高 |
| `users` | `(role)` | 权限检查 | 低 |
| `tubi_jobs` | `(status, created_at DESC)` | 失败任务清理 | 中 |

**实施 SQL（`database.py` 的 `_INDEX_SQL` 追加）**：

```sql
-- tubi_analyses 组合索引（覆盖最常用查询）
CREATE INDEX IF NOT EXISTS idx_tubi_artist_status
  ON tubi_analyses(artist, status);

CREATE INDEX IF NOT EXISTS idx_tubi_library_vis_status
  ON tubi_analyses(library_id, visibility, status);

CREATE INDEX IF NOT EXISTS idx_tubi_artist_library
  ON tubi_analyses(artist, library_id);

CREATE INDEX IF NOT EXISTS idx_tubi_updated_at
  ON tubi_analyses(updated_at DESC);

-- artists 查询索引
CREATE INDEX IF NOT EXISTS idx_artists_name
  ON artists(name);

CREATE INDEX IF NOT EXISTS idx_artists_enabled_featured
  ON artists(enabled, featured);

-- artist_rules
CREATE INDEX IF NOT EXISTS idx_artist_rules_name
  ON artist_rules(artist_name);

-- notifications 组合索引（未读列表核心查询）
CREATE INDEX IF NOT EXISTS idx_notif_user_read_time
  ON notifications(user_id, is_read, created_at DESC);

-- users
CREATE INDEX IF NOT EXISTS idx_users_role
  ON users(role);

-- tubi_jobs 清理索引
CREATE INDEX IF NOT EXISTS idx_tubi_jobs_status_time
  ON tubi_jobs(status, created_at DESC);
```

### 2.2 `knowledge.db` 缺失索引

| 表 | 缺失索引 | 覆盖查询场景 | 预估收益 |
|----|-----------|-------------|---------|
| `text_chunks` | `(book_id, chunk_index)` | 按书 + 序号查询（最核心） | 高 |
| `text_chunks` | `(book_id, vector_id)` | Qdrant 同步验证 | 高 |
| `extracted_images` | `(book_id, page)` | 按页查图片 | 高 |
| `pdf_books` | `(owner_id, visibility)` | 用户的书库列表 | 中 |
| `summary_cache` | `UNIQUE(query_key)` | 防止重复缓存条目 | 中 |

**实施 SQL**：

```sql
-- text_chunks 核心查询
CREATE INDEX IF NOT EXISTS idx_text_chunks_book_chunk
  ON text_chunks(book_id, chunk_index);

CREATE INDEX IF NOT EXISTS idx_text_chunks_book_vector
  ON text_chunks(book_id, vector_id);

-- extracted_images 按页查询
CREATE INDEX IF NOT EXISTS idx_extracted_images_book_page
  ON extracted_images(book_id, page);

-- pdf_books 用户库列表
CREATE INDEX IF NOT EXISTS idx_pdf_books_owner_vis
  ON pdf_books(owner_id, visibility);

-- summary_cache 唯一约束（防止重复缓存）
CREATE UNIQUE INDEX IF NOT EXISTS idx_summary_cache_key_unique
  ON summary_cache(query_key);
```

---

## 三、FTS5 全文搜索（优先级：中，风险：低）

### 问题
`text_chunks.content` 目前依赖 Qdrant 向量搜索，但：
- 向量搜索无法精确匹配关键词（如书名、专有名词）
- Qdrant 重建后 `vector_id` 同步问题是已知坑

### 方案
为 `text_chunks.content` 建 FTS5 虚拟表，作为向量搜索的补充：

```sql
-- 创建 FTS5 虚拟表（仅需执行一次）
CREATE VIRTUAL TABLE IF NOT EXISTS text_chunks_fts
  USING fts5(content, content='text_chunks', content_rowid='rowid');

-- 初始填充（一次性）
INSERT INTO text_chunks_fts(rowid, content)
  SELECT rowid, content FROM text_chunks;

-- 触发器的维护（增/改/删同步 FTS）
-- 详见：https://www.sqlite.org/fts5.html#the_triggers
```

**使用场景**：用户搜索精确短语时优先 FTS5，语义搜索走 Qdrant，结果取并集。

---

## 四、`vector_id` 同步加固（优先级：高，风险：低）

### 问题（已知）
Qdrant 重建后 `text_chunks.vector_id` 与 Qdrant 实际 `id` 不一致，导致搜索结果被过滤为 0。

### 方案
在 `knowledge_api.py` 的孤立向量回退逻辑基础上，增加**主动同步脚本**：

```python
# scripts/sync_vector_ids.py
# 在 Qdrant reindex 后自动执行
def sync_vector_ids():
    """
    从 Qdrant scroll 出所有 (id, book_id, chunk_index)
    批量更新 SQLite text_chunks.vector_id
    """
    from qdrant_client import QdrantClient
    client = QdrantClient(url=os.getenv("QDRANT_URL"))
    conn = sqlite3.connect("data/knowledge.db")
    # ... scroll + batch UPDATE ...
```

**写入部署文档**（`.trae/rules/deploy-calligraphy-to-tencent-cloud.md`），要求：
> Qdrant 重建后必须执行 `python scripts/sync_vector_ids.py`

---

## 五、定期维护任务（优先级：中，风险：低）

### 5.1 WAL Checkpoint 定期执行

```python
# 可在 FastAPI 启动事件或定时任务（Celery beat）中执行
def wal_checkpoint(db_path):
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA wal_checkpoint(RESTART)")
    conn.close()
```

### 5.2 定期 `PRAGMA integrity_check`

每月执行一次，结果写入日志：

```python
def check_integrity(db_path):
    conn = sqlite3.connect(db_path)
    result = conn.execute("PRAGMA integrity_check").fetchone()[0]
    conn.close()
    return result  # "ok" = 正常
```

### 5.3 `VACUUM` 回收空间

仅在磁盘空间紧张时手动执行（会锁库）：

```bash
sqlite3 data/calligraphy.db "VACUUM;"
sqlite3 data/knowledge.db "VACUUM;"
```

---

## 六、实施顺序与验证

| 阶段 | 操作 | 验证方法 |
|------|------|----------|
| **Phase 1** | PRAGMA 调优 + 缺失索引 | `EXPLAIN QUERY PLAN SELECT ...` 确认索引命中 |
| **Phase 2** | `vector_id` 同步脚本 | 重建 Qdrant 后跑脚本，验证搜索结果正常 |
| **Phase 3** | FTS5 虚拟表 | 精确关键词搜索返回正确结果 |
| **Phase 4** | 定期维护任务接入 | Celery beat 任务正常执行，日志无报错 |

### Phase 1 验证示例

```sql
-- 验证 tubi_analyses 组合索引
EXPLAIN QUERY PLAN
SELECT * FROM tubi_analyses
WHERE artist = '李鱓' AND status = 'completed'
ORDER BY created_at DESC;

-- 期望看到：SEARCH TABLE tubi_analyses USING INDEX idx_tubi_artist_status
-- 而不是：SCAN TABLE tubi_analyses
```

---

## 七、不需要优化的点（结论）

| 项目 | 理由 |
|------|------|
| `seal_images(seal_id)` | 已有索引，409 行无需进一步优化 |
| `composition_jobs` | 仅 12 行，全表扫描比索引更快 |
| `users` | 仅 4 行，无需额外索引 |
| 外键约束 | SQLite 外键会降低写入性能，当前无 FK 约束是合理的 |
| 分区表 | SQLite 不支持原生分区，且无此需求 |

---

## 附录：当前索引全览（供对照）

### `calligraphy.db`
```
artwork_artists  →  artwork_id, artist_id          [已有]
artist_change_requests → artist_id, status           [已有]
artist_claims  →  user_id, artist_name, status    [已有]
notifications  →  user_id, is_read                [已有，缺组合索引]
seal_images  →  seal_id                            [已有]
tubi_analyses  →  created_at, artist, status, album_name, owner_id, visibility  [已有，缺组合索引]
tubi_jobs  →  image_id(UNIQUE), status, id       [已有]
users  →  uid(UNIQUE)                            [已有，缺 role 索引]
change_requests → artwork_id, submitter_id, library_id  [已有]
```

### `knowledge.db`
```
composition_figures → figure_id, figure_type        [已有]
composition_rules  →  rule_id, category_code, source [已有]
extracted_images  →  book_id, page, vector_id, image_hash  [已有，缺 book_id+page 组合]
pdf_books  →  created_at, status, series_id       [已有，缺 owner_id+visibility]
text_chunks  →  book_id, content_hash, vector_id  [已有，缺 book_id+chunk_index 组合]
knowledge_tasks  →  status, book_id, created_at    [已有]
summary_cache  →  query_key                        [已有，建议加 UNIQUE]
```
