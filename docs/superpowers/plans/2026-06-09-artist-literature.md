# 画家专属文献库实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 为每个画家建立专属文献库，支持 PDF 上传、在线阅读、RAG 问答，复用现有知识库 pipeline。

**架构：** 在现有 `pdf_books` 表加 `artist_id`/`document_type` 字段，Qdrant chunk metadata 加对应标签。画家文献 CRUD 为独立 API 模块，搜索和聊天复用现有端点加 `artist_id` filter。前端重写 `ArtistLiterature.vue`，集成 PDF.js 沉浸式阅读和 ChatFloat 画家专家模式。

**技术栈：** FastAPI / SQLAlchemy / Qdrant / MinerU / DeepSeek / Vue 3 / Element Plus / PDF.js

**设计规格：** `docs/superpowers/specs/2026-06-09-artist-literature-design.md`

---

## 文件结构

### 后端（修改/创建）

| 文件 | 职责 | 操作 |
|------|------|------|
| `backend/app/modules/pantianshou_composition/models.py` | PdfBook/ChatSession 模型加字段 | 修改 |
| `backend/app/modules/pantianshou_composition/knowledge_books.py` | 书籍 CRUD endpoint（从 knowledge_api.py 搬出） | 创建 |
| `backend/app/modules/pantianshou_composition/knowledge_search.py` | 搜索相关 endpoint（从 knowledge_api.py 搬出） | 创建 |
| `backend/app/modules/pantianshou_composition/knowledge_tasks.py` | 任务管理 endpoint（从 knowledge_api.py 搬出） | 创建 |
| `backend/app/modules/pantianshou_composition/artist_literature.py` | 画家文献 CRUD API（新增） | 创建 |
| `backend/app/modules/pantianshou_composition/knowledge_api.py` | 精简：保留统计/规则/杂项 + router 汇总注册 | 修改 |
| `backend/app/modules/pantianshou_composition/knowledge_chat.py` | 加 artist_id filter + 画家专家 system prompt | 修改 |
| `backend/app/modules/pantianshou_composition/knowledge_ingest_v2.py` | process_pdf 支持 artist_id 传参 | 修改 |
| `backend/app/modules/pantianshou_composition/metadata_extractor.py` | LLM 元数据自动提取 | 创建 |

### 前端（修改/创建）

| 文件 | 职责 | 操作 |
|------|------|------|
| `frontend/src/views/artist/ArtistLiterature.vue` | 画家文献列表页（重写） | 修改 |
| `frontend/src/components/LiteratureReader.vue` | 沉浸式文献阅读弹窗 | 创建 |
| `frontend/src/components/LiteratureUpload.vue` | 文献上传组件 | 创建 |
| `frontend/src/components/ChatFloat.vue` | 加 artist expert 模式支持 | 修改 |
| `frontend/src/stores/chatStore.js` | 加 artistExpertSessionId | 修改 |

---

## 任务 1：数据库迁移 — PdfBook 加字段

**文件：**
- 修改：`backend/app/modules/pantianshou_composition/models.py:24-40`

- [ ] **步骤 1：在 PdfBook 模型加 5 个字段**

在 `models.py` 的 `PdfBook` 类中，`visibility` 字段（第 40 行）之后添加：

```python
artist_id = Column(Integer, ForeignKey('artists.id'), nullable=True, index=True)
document_type = Column(String(20), default='book', nullable=False)
journal = Column(String(255), nullable=True)
publish_year = Column(Integer, nullable=True)
doi = Column(String(255), nullable=True)
```

需要在文件顶部添加 ForeignKey import（如果尚未导入）：
```python
from sqlalchemy import ForeignKey
```

- [ ] **步骤 2：在 ChatSession 模型加 2 个字段**

在 `models.py` 的 `ChatSession` 类中，`message_count` 字段之后添加：

```python
session_type = Column(String(20), default='global', nullable=False)
artist_id = Column(Integer, ForeignKey('artists.id'), nullable=True, index=True)
```

- [ ] **步骤 3：运行数据库迁移验证**

```bash
cd Z:/molin-wiki/backend && python -c "
from app.modules.pantianshou_composition.models import PdfBook, ChatSession
# Verify new columns exist
assert hasattr(PdfBook, 'artist_id')
assert hasattr(PdfBook, 'document_type')
assert hasattr(PdfBook, 'journal')
assert hasattr(PdfBook, 'publish_year')
assert hasattr(PdfBook, 'doi')
assert hasattr(ChatSession, 'session_type')
assert hasattr(ChatSession, 'artist_id')
print('All new fields verified')
"
```

预期：`All new fields verified`

- [ ] **步骤 4：Commit**

```bash
git add backend/app/modules/pantianshou_composition/models.py
git commit -m "feat(db): pdf_books加artist_id/document_type/journal/publish_year/doi字段，chat_sessions加session_type/artist_id"
```

---

## 任务 2：代码拆分 — 搬出 knowledge_tasks.py

**文件：**
- 创建：`backend/app/modules/pantianshou_composition/knowledge_tasks.py`
- 修改：`backend/app/modules/pantianshou_composition/knowledge_api.py:509-605`

先拆最简单的 tasks 模块（4 个 endpoint，~100 行，无复杂依赖）。

- [ ] **步骤 1：创建 knowledge_tasks.py**

从 `knowledge_api.py` 中搬出以下函数到新文件：
- `list_tasks`（line 509）
- `get_task`（line 543）
- `retry_task`（line 567）
- `cancel_task`（line 591）

创建 `backend/app/modules/pantianshou_composition/knowledge_tasks.py`：

```python
from fastapi import APIRouter, HTTPException
from ...database import get_db
from .models import KnowledgeTask

router = APIRouter()

@router.get("/tasks")
def list_tasks():
    db = next(get_db())
    try:
        tasks = db.query(KnowledgeTask).order_by(KnowledgeTask.created_at.desc()).limit(50).all()
        return [task_to_dict(t) for t in tasks]
    finally:
        db.close()

@router.get("/tasks/{task_id}")
def get_task(task_id: str):
    db = next(get_db())
    try:
        task = db.query(KnowledgeTask).filter(KnowledgeTask.id == task_id).first()
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        return task_to_dict(task)
    finally:
        db.close()

@router.post("/tasks/{task_id}/retry")
def retry_task(task_id: str):
    # ... (exact copy from knowledge_api.py line 567-589)
    pass

@router.post("/tasks/{task_id}/cancel")
def cancel_task(task_id: str):
    # ... (exact copy from knowledge_api.py line 591-605)
    pass

def task_to_dict(task: KnowledgeTask) -> dict:
    return {
        "id": task.id,
        "book_id": task.book_id,
        "task_type": task.task_type,
        "status": task.status,
        "progress": task.progress,
        "stage": task.stage,
        "message": task.message,
        "result": task.result,
        "error_message": task.error_message,
        "created_at": task.created_at.isoformat() if task.created_at else None,
    }
```

**注意**：上面是骨架。实际搬出时必须原封不动复制函数体，包括所有 import。`task_to_dict` 如果原文件里有对应的序列化逻辑就搬过来，没有则根据 `TaskResponse` 模型（line 139-153）实现。

- [ ] **步骤 2：从 knowledge_api.py 删除已搬出的函数**

删除 `list_tasks`、`get_task`、`retry_task`、`cancel_task` 四个函数定义。

- [ ] **步骤 3：在 knowledge_api.py 注册子 router**

在 `knowledge_api.py` 顶部 import 区添加：
```python
from .knowledge_tasks import router as tasks_router
```

在 `router = APIRouter()` 之后添加：
```python
router.include_router(tasks_router, tags=["tasks"])
```

- [ ] **步骤 4：验证 import 和 endpoint**

```bash
cd Z:/molin-wiki/backend && python -c "
from app.modules.pantianshou_composition.knowledge_tasks import router
print(f'Tasks router has {len(router.routes)} routes')
"
```

预期：`Tasks router has 4 routes`

- [ ] **步骤 5：Commit**

```bash
git add backend/app/modules/pantianshou_composition/knowledge_tasks.py backend/app/modules/pantianshou_composition/knowledge_api.py
git commit -m "refactor: 拆出knowledge_tasks.py（4个endpoint）"
```

---

## 任务 3：代码拆分 — 搬出 knowledge_books.py

**文件：**
- 创建：`backend/app/modules/pantianshou_composition/knowledge_books.py`
- 修改：`backend/app/modules/pantianshou_composition/knowledge_api.py:183-508, 607-790, 1766-1849`

搬出书籍相关 endpoint（upload/list/delete/reingest + chunks/images/outline/markdown/pdf）。

- [ ] **步骤 1：创建 knowledge_books.py**

从 `knowledge_api.py` 搬出以下函数：
- `upload_pdf`（line 183-293）
- `list_books`（line 295-321）
- `get_book`（line 323-341）
- `delete_book`（line 343-403）
- `reingest_book`（line 405-507）
- `get_book_chunks`（line 607-669）
- `get_book_images`（line 671-695）
- `get_book_pdf`（line 781-810）
- `get_book_outline`（line 1766-1822）
- `get_book_markdown`（line 1824-1849）

同时搬出相关 Pydantic 模型：
- `BookCreateResponse`（line 120-123）
- `BookResponse`（line 126-137）

以及辅助函数：
- `_parse_caption_for_display`（line 37-110）—— 仅被 `get_book_images` 使用

文件结构：
```python
"""书籍管理 API — 从 knowledge_api.py 拆出"""
import os
import uuid
import threading
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Query
from ...database import get_db
from ...config import settings
from .models import PdfBook, KnowledgeTask, TextChunk, ExtractedImage
from .knowledge_storage import save_book_upload
from .knowledge_ingest_v2 import process_pdf_file_sync
from .qdrant_client import delete_points, scroll_collection

router = APIRouter()

# Pydantic models
class BookCreateResponse(BaseModel):
    # ... (exact copy from line 120-123)

class BookResponse(BaseModel):
    # ... (exact copy from line 126-137)

# Helper
def _parse_caption_for_display(caption: str) -> str:
    # ... (exact copy from line 37-110)

# Endpoints (exact copies)
@router.post("/books/upload")
async def upload_pdf(...):
    # ... (exact copy from line 183-293)

# ... 其余 endpoint 原封不动搬出
```

- [ ] **步骤 2：从 knowledge_api.py 删除已搬出的函数和模型**

- [ ] **步骤 3：在 knowledge_api.py 注册子 router**

```python
from .knowledge_books import router as books_router
router.include_router(books_router, tags=["books"])
```

- [ ] **步骤 4：验证**

```bash
cd Z:/molin-wiki/backend && python -c "
from app.modules.pantianshou_composition.knowledge_books import router
print(f'Books router has {len(router.routes)} routes')
"
```

- [ ] **步骤 5：Commit**

```bash
git add backend/app/modules/pantianshou_composition/knowledge_books.py backend/app/modules/pantianshou_composition/knowledge_api.py
git commit -m "refactor: 拆出knowledge_books.py（书籍CRUD endpoint）"
```

---

## 任务 4：代码拆分 — 搬出 knowledge_search.py

**文件：**
- 创建：`backend/app/modules/pantianshou_composition/knowledge_search.py`
- 修改：`backend/app/modules/pantianshou_composition/knowledge_api.py:931-1707`

搬出搜索相关 endpoint（search + search history + tables search + images + related chunks）。

- [ ] **步骤 1：创建 knowledge_search.py**

搬出以下函数：
- `search`（line 931-1647）—— 最大的函数，~716 行
- `get_search_history`（line 1649-1668）
- `delete_search_history_item`（line 1670-1685）
- `clear_search_history`（line 1687-1699）
- `search_tables`（line 1708-1764）
- `get_image_related_chunks`（line 697-737）
- `get_image`（line 739-762）
- `get_image_by_id`（line 764-779）

同时搬出：
- `SearchRequest`（line 156-160）
- `TableSearchRequest`（line 1701-1705）
- `_clear_summary_cache`（line 175-181）
- `_truncate_to_sentence_boundary`（line 812-851）
- `_should_include_in_search`（line 854-880）
- `_extract_book_title`（line 883-924）

- [ ] **步骤 2：从 knowledge_api.py 删除已搬出的函数和模型**

- [ ] **步骤 3：在 knowledge_api.py 注册子 router**

```python
from .knowledge_search import router as search_router
router.include_router(search_router, tags=["search"])
```

- [ ] **步骤 4：验证**

```bash
cd Z:/molin-wiki/backend && python -c "
from app.modules.pantianshou_composition.knowledge_search import router
print(f'Search router has {len(router.routes)} routes')
"
```

- [ ] **步骤 5：Commit**

```bash
git add backend/app/modules/pantianshou_composition/knowledge_search.py backend/app/modules/pantianshou_composition/knowledge_api.py
git commit -m "refactor: 拆出knowledge_search.py（搜索endpoint）"
```

---

## 任务 5：精简 knowledge_api.py + 验证完整拆分

**文件：**
- 修改：`backend/app/modules/pantianshou_composition/knowledge_api.py`

此时 `knowledge_api.py` 应只剩：统计、规则、figures、graph、private documents、chat、db/reindex 等 endpoint + router 汇总。

- [ ] **步骤 1：确认 knowledge_api.py 剩余内容**

```bash
cd Z:/molin-wiki/backend && python -c "
from app.modules.pantianshou_composition.knowledge_api import router
print(f'Main router has {len(router.routes)} routes (including sub-routers)')
"
```

- [ ] **步骤 2：验证所有端点仍可访问**

启动后端并测试关键端点：
```bash
cd Z:/molin-wiki/backend && python -c "
from app.modules.pantianshou_composition.knowledge_api import router
from app.modules.pantianshou_composition.knowledge_books import router as books_r
from app.modules.pantianshou_composition.knowledge_search import router as search_r
from app.modules.pantianshou_composition.knowledge_tasks import router as tasks_r
print(f'Main: {len(router.routes)}, Books: {len(books_r.routes)}, Search: {len(search_r.routes)}, Tasks: {len(tasks_r.routes)}')
total = len(books_r.routes) + len(search_r.routes) + len(tasks_r.routes)
print(f'Sub-total: {total}')
"
```

- [ ] **步骤 3：Commit**

```bash
git add backend/app/modules/pantianshou_composition/knowledge_api.py
git commit -m "refactor: knowledge_api.py精简完成，拆分为books/search/tasks三个子模块"
```

---

## 任务 6：Qdrant chunk metadata 传播 artist_id

**文件：**
- 修改：`backend/app/modules/pantianshou_composition/knowledge_ingest_v2.py:87-138, 437-457`
- 修改：`backend/app/modules/pantianshou_composition/knowledge_books.py`（upload_pdf endpoint）

确保上传文献时，`artist_id` 和 `document_type` 写入 Qdrant chunk metadata。

- [ ] **步骤 1：修改 KnowledgeIngestV2.process_pdf 接受 artist_id 和 document_type**

在 `knowledge_ingest_v2.py` 的 `process_pdf` 方法签名（line 87）加参数：

```python
async def process_pdf(self, 
                      pdf_path: str, 
                      task_id: Optional[str] = None,
                      book_id: Optional[str] = None,
                      artist_id: Optional[int] = None,
                      document_type: str = 'book') -> Dict[str, Any]:
```

- [ ] **步骤 2：在 _create_book_record 中设置 artist_id 和 document_type**

修改 `_create_book_record`（line 437），在创建 `PdfBook()` 时传入：

```python
book.artist_id = self._artist_id  # 从 __init__ 或 process_pdf 传入
book.document_type = self._document_type
```

需要在 `__init__` 中加 `_artist_id` 和 `_document_type` 属性，或直接在 `process_pdf` 中设置。

- [ ] **步骤 3：在 chunk embedding 时将 artist_id 写入 Qdrant payload**

找到 `process_pdf` 中调用 `upsert_points` 写入 Qdrant 的位置，在 payload dict 中添加：

```python
payload['artist_id'] = artist_id
payload['document_type'] = document_type
```

- [ ] **步骤 4：验证**

```bash
cd Z:/molin-wiki/backend && python -c "
from app.modules.pantianshou_composition.knowledge_ingest_v2 import KnowledgeIngestV2
import inspect
sig = inspect.signature(KnowledgeIngestV2.process_pdf)
assert 'artist_id' in sig.parameters
assert 'document_type' in sig.parameters
print('process_pdf signature verified')
"
```

- [ ] **步骤 5：Commit**

```bash
git add backend/app/modules/pantianshou_composition/knowledge_ingest_v2.py
git commit -m "feat: process_pdf支持artist_id和document_type参数，写入Qdrant chunk metadata"
```

---

## 任务 7：创建 artist_literature.py — 画家文献 CRUD API

**文件：**
- 创建：`backend/app/modules/pantianshou_composition/artist_literature.py`
- 修改：`backend/app/modules/pantianshou_composition/knowledge_api.py`（注册 router）

- [ ] **步骤 1：创建 artist_literature.py**

```python
"""画家文献管理 API"""
import os
import uuid
import threading
from typing import Optional
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Query, Depends
from pydantic import BaseModel
from ...database import get_db
from ...config import settings
from ...auth import get_current_user, require_editor_role
from .models import PdfBook, KnowledgeTask, TextChunk
from .knowledge_storage import save_book_upload
from .knowledge_ingest_v2 import process_pdf_file_sync

router = APIRouter(prefix="/artists/{artist_id}/literature")

class LiteratureResponse(BaseModel):
    id: str
    title: Optional[str]
    author: Optional[str]
    journal: Optional[str]
    publish_year: Optional[int]
    doi: Optional[str]
    status: str
    total_pages: Optional[int]
    chunk_count: int = 0
    created_at: Optional[str]

class LiteratureDetailResponse(LiteratureResponse):
    outline: Optional[list]
    file_name: str
    stored_url: str
    document_type: str

class MetadataUpdateRequest(BaseModel):
    title: Optional[str] = None
    author: Optional[str] = None
    journal: Optional[str] = None
    publish_year: Optional[int] = None
    doi: Optional[str] = None
```

- [ ] **步骤 2：实现 upload endpoint**

```python
@router.post("/upload")
async def upload_literature(
    artist_id: int,
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    journal: Optional[str] = Form(None),
    publish_year: Optional[int] = Form(None),
    doi: Optional[str] = Form(None),
    current_user = Depends(require_editor_role),
):
    db = next(get_db())
    try:
        # 验证画家存在
        from .models import Artist  # 需确认实际 import 路径
        artist = db.query(Artist).filter(Artist.id == artist_id).first()
        if not artist:
            raise HTTPException(status_code=404, detail="Artist not found")

        # 保存文件
        file_path, file_url = save_book_upload(file, prefix="literature")

        # 创建 book 记录
        book_id = str(uuid.uuid4())
        book = PdfBook(
            id=book_id,
            file_name=file.filename,
            stored_path=file_path,
            stored_url=file_url,
            artist_id=artist_id,
            document_type='literature',
            title=title,
            journal=journal,
            publish_year=publish_year,
            doi=doi,
            status='processing',
        )
        db.add(book)

        # 创建 task 记录
        task_id = str(uuid.uuid4())
        task = KnowledgeTask(
            id=task_id,
            book_id=book_id,
            task_type='pdf_ingest',
            status='queued',
            progress=0,
            stage='queued',
        )
        db.add(task)
        db.commit()

        # 后台处理
        def _process():
            process_pdf_file_sync(
                pdf_path=file_path,
                task_id=task_id,
                book_id=book_id,
                artist_id=artist_id,
                document_type='literature',
            )
        threading.Thread(target=_process, daemon=True).start()

        return {"book_id": book_id, "task_id": task_id}
    finally:
        db.close()
```

- [ ] **步骤 3：实现 list/detail/delete/chunks/pdf/metadata endpoints**

按照规格实现剩余 6 个 endpoint，关键点：
- `GET /` — 查询 `PdfBook.artist_id == artist_id AND document_type == 'literature'`，支持分页和排序
- `GET /{book_id}` — 返回详情 + outline + chunk_count
- `DELETE /{book_id}` — 删除 PdfBook + 关联 chunks/images + Qdrant 向量（复用现有 `delete_book` 的清理逻辑）
- `PATCH /{book_id}` — 更新元数据字段
- `GET /{book_id}/chunks` — 查询 TextChunk 表
- `GET /{book_id}/pdf` — 返回 PDF 文件流（复用现有 `get_book_pdf` 的逻辑）

- [ ] **步骤 4：在 knowledge_api.py 注册 router**

```python
from .artist_literature import router as literature_router
router.include_router(literature_router, tags=["artist-literature"])
```

- [ ] **步骤 5：验证**

```bash
cd Z:/molin-wiki/backend && python -c "
from app.modules.pantianshou_composition.artist_literature import router
print(f'Literature router has {len(router.routes)} routes')
print([r.path for r in router.routes])
"
```

- [ ] **步骤 6：Commit**

```bash
git add backend/app/modules/pantianshou_composition/artist_literature.py backend/app/modules/pantianshou_composition/knowledge_api.py
git commit -m "feat: 新增画家文献CRUD API（upload/list/detail/delete/metadata/chunks/pdf）"
```

---

## 任务 8：搜索和聊天加 artist_id filter

**文件：**
- 修改：`backend/app/modules/pantianshou_composition/knowledge_search.py`（search endpoint 加 artist_id 参数）
- 修改：`backend/app/modules/pantianshou_composition/knowledge_chat.py:188-235, 377-598`

- [ ] **步骤 1：knowledge_search.py 的 search endpoint 加 artist_id 参数**

在 `SearchRequest` 模型中加 `artist_id: Optional[int] = None`。

在 `search` 函数中，如果 `artist_id` 有值，构建 Qdrant filter：

```python
query_filter = None
if request.artist_id:
    query_filter = {
        "must": [
            {"key": "artist_id", "match": {"value": request.artist_id}}
        ]
    }
```

将 `query_filter` 传入 `hybrid_search` 调用（该函数已支持 `query_filter` 参数，但从未被使用过）。

- [ ] **步骤 2：knowledge_chat.py 的 chat_stream 加 artist_id 参数**

修改 `chat_stream` 签名（line 377）：

```python
async def chat_stream(
    query: str,
    history: Optional[List[Dict[str, str]]] = None,
    user_id: Optional[int] = None,
    session_id: Optional[str] = None,
    artist_id: Optional[int] = None,
    artist_name: Optional[str] = None,
) -> AsyncGenerator[str, None]:
```

- [ ] **步骤 3：修改 _search_for_chat 支持 artist_id filter**

修改 `_search_for_chat`（line 188）签名加 `artist_id` 参数：

```python
async def _search_for_chat(query: str, limit: int = 10, artist_id: Optional[int] = None) -> List[Dict]:
```

在调用 `do_hybrid_search` 时传入 filter：

```python
query_filter = None
if artist_id:
    query_filter = {"must": [{"key": "artist_id", "match": {"value": artist_id}}]}

results = await do_hybrid_search(
    query_text=query,
    query_vector=q_embedding,
    collection=qdrant_client.KNOWLEDGE_TEXTS_COLLECTION,
    limit=limit,
    query_filter=query_filter,
)
```

在 `chat_stream` 中调用 `_search_for_chat` 时传入 `artist_id`。

- [ ] **步骤 4：修改 system prompt 支持画家专家模式**

在 `chat_stream` 中，如果 `artist_id` 和 `artist_name` 有值，替换 system prompt：

```python
if artist_id and artist_name:
    system_prompt = ARTIST_EXPERT_PROMPT.format(artist_name=artist_name)
else:
    system_prompt = SYSTEM_PROMPT
```

新增 `ARTIST_EXPERT_PROMPT` 常量：

```python
ARTIST_EXPERT_PROMPT = """你是一位专注于{artist_name}研究的学术专家。
你的知识基于该画家相关的学术文献和研究资料。
回答时请引用具体文献来源，标注书名和页码。
使用 [1], [2] 等标记引用来源。
回答使用 Markdown 格式，300-600 字。
如果你不确定，坦诚说明而非编造。"""
```

- [ ] **步骤 5：修改 knowledge_api.py 的 chat endpoint 传参**

在 `rag_chat` endpoint 中，从 `ChatRequest` 读取 `artist_id` 并传入 `chat_stream`。

- [ ] **步骤 6：验证**

```bash
cd Z:/molin-wiki/backend && python -c "
from app.modules.pantianshou_composition.knowledge_chat import chat_stream, ARTIST_EXPERT_PROMPT
import inspect
sig = inspect.signature(chat_stream)
assert 'artist_id' in sig.parameters
assert 'artist_name' in sig.parameters
print('chat_stream signature verified')
print(ARTIST_EXPERT_PROMPT[:50])
"
```

- [ ] **步骤 7：Commit**

```bash
git add backend/app/modules/pantianshou_composition/knowledge_search.py backend/app/modules/pantianshou_composition/knowledge_chat.py backend/app/modules/pantianshou_composition/knowledge_api.py
git commit -m "feat: 搜索和聊天支持artist_id filter，画家专家system prompt"
```

---

## 任务 9：元数据自动提取

**文件：**
- 创建：`backend/app/modules/pantianshou_composition/metadata_extractor.py`
- 修改：`backend/app/modules/pantianshou_composition/knowledge_ingest_v2.py:135-138`

- [ ] **步骤 1：创建 metadata_extractor.py**

```python
"""从 PDF 内容中用 LLM 提取结构化元数据"""
import json
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

EXTRACTION_PROMPT = """分析以下学术文献内容，提取结构化元数据。
只返回 JSON，不要其他文字。

返回格式：
{
  "title": "文献标题",
  "authors": ["作者1", "作者2"],
  "journal": "期刊/出版社名",
  "publish_year": 2019,
  "doi": "10.xxxx/xxxxx",
  "abstract": "摘要内容（100字以内）"
}

如果某字段无法确定，设为 null。

文献内容：
{content}
"""

async def extract_metadata(full_md: str) -> Dict[str, Any]:
    """从 Markdown 内容中提取元数据"""
    if not full_md:
        return {}

    # 取前 2 页内容（约 3000 字符）
    content = full_md[:3000]

    try:
        import httpx
        from ...config import settings

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{settings.DEEPSEEK_BASE_URL}/chat/completions",
                headers={"Authorization": f"Bearer {settings.DEEPSEEK_API_KEY}"},
                json={
                    "model": settings.DEEPSEEK_TEXT_MODEL,
                    "messages": [
                        {"role": "user", "content": EXTRACTION_PROMPT.format(content=content)}
                    ],
                    "temperature": 0.1,
                    "max_tokens": 500,
                },
            )
            resp.raise_for_status()
            text = resp.json()["choices"][0]["message"]["content"]

        # 解析 JSON
        # 处理 markdown code block 包裹的情况
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]

        result = json.loads(text.strip())
        return result
    except Exception as e:
        logger.warning(f"Metadata extraction failed: {e}")
        return {}
```

- [ ] **步骤 2：在 process_pdf 完成后调用元数据提取**

在 `knowledge_ingest_v2.py` 的 `process_pdf` 中，MinerU 解析完成后（line 135-138 之后），如果 `document_type == 'literature'`，调用 LLM 提取：

```python
if self._document_type == 'literature' and book.full_md:
    from .metadata_extractor import extract_metadata
    meta = await extract_metadata(book.full_md)
    if meta:
        if not book.title and meta.get('title'):
            book.title = meta['title']
        if not book.author and meta.get('authors'):
            book.author = ', '.join(meta['authors'])
        if not book.journal and meta.get('journal'):
            book.journal = meta['journal']
        if not book.publish_year and meta.get('publish_year'):
            book.publish_year = meta['publish_year']
        if not book.doi and meta.get('doi'):
            book.doi = meta['doi']
        self.db.commit()
```

注意：只在字段为空时填充（用户手动上传时可能已提供）。

- [ ] **步骤 3：Commit**

```bash
git add backend/app/modules/pantianshou_composition/metadata_extractor.py backend/app/modules/pantianshou_composition/knowledge_ingest_v2.py
git commit -m "feat: LLM元数据自动提取（title/authors/journal/year/doi）"
```

---

## 任务 10：前端 — 安装 PDF.js

**文件：**
- 修改：`frontend/package.json`

- [ ] **步骤 1：安装 pdfjs-dist**

```bash
cd Z:/molin-wiki/frontend && npm install pdfjs-dist
```

- [ ] **步骤 2：Commit**

```bash
git add frontend/package.json frontend/package-lock.json
git commit -m "deps: 安装pdfjs-dist"
```

---

## 任务 11：前端 — 重写 ArtistLiterature.vue

**文件：**
- 修改：`frontend/src/views/artist/ArtistLiterature.vue`（完全重写）
- 创建：`frontend/src/components/LiteratureUpload.vue`
- 创建：`frontend/src/components/LiteratureReader.vue`

- [ ] **步骤 1：重写 ArtistLiterature.vue 基础结构**

保留现有 `av-header`/`av-sub-nav` 模式，重写核心内容区：

```vue
<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/authStore'
import LiteratureUpload from '@/components/LiteratureUpload.vue'
import LiteratureReader from '@/components/LiteratureReader.vue'
import ChatFloat from '@/components/ChatFloat.vue'

const route = useRoute()
const authStore = useAuthStore()
const artistName = route.params.name
const artistId = ref(null)
const literature = ref([])
const loading = ref(false)
const viewMode = ref('grid')
const searchQuery = ref('')
const sortBy = ref('upload_time')
const showUpload = ref(false)
const readingBook = ref(null) // 当前阅读的文献
const currentPage = ref(1)
const pageSize = 20
const total = ref(0)

const canUpload = computed(() => authStore.isEditor || authStore.isAdmin)

async function fetchArtistId() {
  const API = import.meta.env.VITE_API_BASE || '/api/v1'
  const res = await fetch(`${API}/artists/by-name/${encodeURIComponent(artistName)}`)
  const data = await res.json()
  artistId.value = data.artist?.id
}

async function fetchLiterature() {
  if (!artistId.value) return
  loading.value = true
  const API = import.meta.env.VITE_API_BASE || '/api/v1'
  const params = new URLSearchParams({
    page: currentPage.value,
    page_size: pageSize,
    sort_by: sortBy.value,
  })
  if (searchQuery.value) params.set('keyword', searchQuery.value)
  try {
    const res = await fetch(`${API}/artists/${artistId.value}/literature?${params}`)
    const data = await res.json()
    literature.value = data.items || []
    total.value = data.total || 0
  } finally {
    loading.value = false
  }
}

function openReader(book) { readingBook.value = book }
function closeReader() { readingBook.value = null }
function onUploaded() { showUpload.value = false; fetchLiterature() }

onMounted(async () => {
  await fetchArtistId()
  await fetchLiterature()
})
</script>
```

- [ ] **步骤 2：实现模板 — 列表区域**

复用 `ArtistWorks.vue` 的视图切换模式：

```html
<template>
  <!-- av-header / av-sub-nav 保持不变（和现有 ArtistLiterature.vue 一样） -->

  <div class="al-toolbar">
    <div class="al-search">
      <el-input v-model="searchQuery" placeholder="搜索文献..." @keyup.enter="fetchLiterature" clearable />
    </div>
    <div class="al-controls">
      <el-select v-model="sortBy" @change="fetchLiterature" size="small">
        <el-option label="按上传时间" value="upload_time" />
        <el-option label="按年份" value="publish_year" />
        <el-option label="按标题" value="title" />
      </el-select>
      <el-button-group>
        <el-button :type="viewMode === 'grid' ? 'primary' : 'default'" @click="viewMode = 'grid'" size="small">
          <el-icon><Grid /></el-icon>
        </el-button>
        <el-button :type="viewMode === 'list' ? 'primary' : 'default'" @click="viewMode = 'list'" size="small">
          <el-icon><List /></el-icon>
        </el-button>
      </el-button-group>
      <el-button v-if="canUpload" type="primary" @click="showUpload = true" size="small">
        上传文献
      </el-button>
    </div>
  </div>

  <!-- Grid 视图 -->
  <div v-show="viewMode === 'grid'" class="al-grid">
    <div v-for="doc in literature" :key="doc.id" class="al-card" @click="openReader(doc)">
      <div class="al-card-icon">📄</div>
      <div class="al-card-body">
        <div class="al-card-title">{{ doc.title || '未命名文献' }}</div>
        <div class="al-card-meta">
          <span v-if="doc.author">{{ doc.author }}</span>
          <span v-if="doc.journal"> · {{ doc.journal }}</span>
          <span v-if="doc.publish_year"> · {{ doc.publish_year }}</span>
        </div>
        <el-tag v-if="doc.status !== 'completed'" size="small" :type="doc.status === 'failed' ? 'danger' : 'warning'">
          {{ doc.status === 'processing' ? '处理中' : doc.status === 'failed' ? '处理失败' : doc.status }}
        </el-tag>
      </div>
    </div>
  </div>

  <!-- List 视图 -->
  <div v-show="viewMode === 'list'" class="al-table-wrap">
    <table class="al-table">
      <thead>
        <tr><th>标题</th><th>作者</th><th>期刊</th><th>年份</th><th>状态</th></tr>
      </thead>
      <tbody>
        <tr v-for="doc in literature" :key="doc.id" @click="openReader(doc)">
          <td>{{ doc.title || '未命名' }}</td>
          <td>{{ doc.author || '-' }}</td>
          <td>{{ doc.journal || '-' }}</td>
          <td>{{ doc.publish_year || '-' }}</td>
          <td>{{ doc.status }}</td>
        </tr>
      </tbody>
    </table>
  </div>

  <el-empty v-if="!loading && literature.length === 0" description="暂无文献" />

  <!-- 上传弹窗 -->
  <el-dialog v-model="showUpload" title="上传文献" width="500px">
    <LiteratureUpload :artist-id="artistId" @uploaded="onUploaded" />
  </el-dialog>

  <!-- 沉浸式阅读弹窗 -->
  <LiteratureReader v-if="readingBook" :book="readingBook" :artist-name="artistName" @close="closeReader" />

  <!-- 画家专家 ChatFloat -->
  <ChatFloat :artist-id="artistId" :artist-name="artistName" />
</template>
```

- [ ] **步骤 3：实现样式**

复用现有 `al-` 前缀和暖色调配色。卡片样式参考 `ArtistWorks.vue` 的 `.aw-card`。

- [ ] **步骤 4：Commit**

```bash
git add frontend/src/views/artist/ArtistLiterature.vue
git commit -m "feat: 重写ArtistLiterature.vue（文献列表+卡片/列表视图+搜索排序+上传入口）"
```

---

## 任务 12：前端 — LiteratureUpload 组件

**文件：**
- 创建：`frontend/src/components/LiteratureUpload.vue`

- [ ] **步骤 1：实现上传组件**

```vue
<script setup>
import { ref } from 'vue'
import { useAuthStore } from '@/stores/authStore'

const props = defineProps({ artistId: Number })
const emit = defineEmits(['uploaded'])
const authStore = useAuthStore()
const file = ref(null)
const title = ref('')
const journal = ref('')
const publishYear = ref(null)
const uploading = ref(false)
const progress = ref(0)

async function handleUpload() {
  if (!file.value) return
  uploading.value = true
  const API = import.meta.env.VITE_API_BASE || '/api/v1'
  const form = new FormData()
  form.append('file', file.value)
  if (title.value) form.append('title', title.value)
  if (journal.value) form.append('journal', journal.value)
  if (publishYear.value) form.append('publish_year', publishYear.value)

  try {
    const res = await fetch(`${API}/artists/${props.artistId}/literature/upload`, {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${authStore.token}` },
      body: form,
    })
    if (!res.ok) throw new Error('Upload failed')
    emit('uploaded')
  } finally {
    uploading.value = false
  }
}
</script>

<template>
  <div class="lu-form">
    <el-upload drag :auto-upload="false" :on-change="(f) => file = f.raw" accept=".pdf">
      <el-icon><Upload /></el-icon>
      <div>拖拽 PDF 文件到此处，或点击选择</div>
    </el-upload>
    <el-form label-width="80px" style="margin-top: 16px">
      <el-form-item label="标题">
        <el-input v-model="title" placeholder="留空则自动提取" />
      </el-form-item>
      <el-form-item label="期刊/出版社">
        <el-input v-model="journal" placeholder="留空则自动提取" />
      </el-form-item>
      <el-form-item label="发表年份">
        <el-input-number v-model="publishYear" :min="1900" :max="2030" placeholder="留空则自动提取" />
      </el-form-item>
    </el-form>
    <el-button type="primary" @click="handleUpload" :loading="uploading" :disabled="!file">
      上传并处理
    </el-button>
  </div>
</template>
```

- [ ] **步骤 2：Commit**

```bash
git add frontend/src/components/LiteratureUpload.vue
git commit -m "feat: LiteratureUpload组件（PDF上传+可选元数据）"
```

---

## 任务 13：前端 — LiteratureReader 沉浸式阅读弹窗

**文件：**
- 创建：`frontend/src/components/LiteratureReader.vue`

- [ ] **步骤 1：实现阅读弹窗**

全屏弹窗，左侧目录 + 右侧正文，支持 Markdown/PDF 切换。

```vue
<script setup>
import { ref, onMounted, onUnmounted } from 'vue'

const props = defineProps({ book: Object, artistName: String })
const emit = defineEmits(['close'])

const mode = ref('markdown') // 'markdown' | 'pdf'
const outline = ref([])
const chunks = ref([])
const activeChapter = ref('')
const pdfUrl = ref('')
const pdfLoading = ref(false)

const API = import.meta.env.VITE_API_BASE || '/api/v1'

async function fetchContent() {
  // 获取 chunks
  const res = await fetch(`${API}/artists/${props.book.artist_id}/literature/${props.book.id}/chunks`)
  const data = await res.json()
  chunks.value = data.chunks || data || []

  // 获取 outline
  if (props.book.outline) {
    outline.value = typeof props.book.outline === 'string' ? JSON.parse(props.book.outline) : props.book.outline
  }
}

async function loadPdf() {
  pdfLoading.value = true
  // PDF.js 动态加载
  const pdfjsLib = await import('pdfjs-dist')
  pdfjsLib.GlobalWorkerOptions.workerSrc = `//cdnjs.cloudflare.com/ajax/libs/pdf.js/${pdfjsLib.version}/pdf.worker.min.js`
  pdfUrl.value = `${API}/artists/${props.book.artist_id}/literature/${props.book.id}/pdf`
  pdfLoading.value = false
}

function switchToPdf() {
  mode.value = 'pdf'
  if (!pdfUrl.value) loadPdf()
}

function switchToMarkdown() {
  mode.value = 'markdown'
}

function scrollToChapter(title) {
  activeChapter.value = title
  const el = document.getElementById(`chunk-${title}`)
  if (el) el.scrollIntoView({ behavior: 'smooth' })
}

// ESC 关闭
function onKeydown(e) {
  if (e.key === 'Escape') emit('close')
}

onMounted(() => {
  fetchContent()
  document.addEventListener('keydown', onKeydown)
})
onUnmounted(() => {
  document.removeEventListener('keydown', onKeydown)
})
</script>

<template>
  <div class="lr-overlay" @click.self="emit('close')">
    <div class="lr-panel">
      <!-- 头部 -->
      <div class="lr-header">
        <div class="lr-title">{{ book.title || '未命名文献' }}</div>
        <div class="lr-controls">
          <el-button-group size="small">
            <el-button :type="mode === 'markdown' ? 'primary' : 'default'" @click="switchToMarkdown">Markdown</el-button>
            <el-button :type="mode === 'pdf' ? 'primary' : 'default'" @click="switchToPdf">原版 PDF</el-button>
          </el-button-group>
          <el-button @click="emit('close')" text>✕</el-button>
        </div>
      </div>

      <!-- 内容区 -->
      <div class="lr-body">
        <!-- 目录侧栏 -->
        <div class="lr-sidebar" v-if="outline.length > 0">
          <div v-for="item in outline" :key="item.title"
               class="lr-toc-item" :class="{ active: activeChapter === item.title }"
               @click="scrollToChapter(item.title)">
            {{ item.title }}
          </div>
        </div>

        <!-- 正文 -->
        <div class="lr-content" v-if="mode === 'markdown'">
          <div v-for="chunk in chunks" :key="chunk.id"
               :id="'chunk-' + chunk.chapter_title"
               class="lr-chunk">
            <div class="lr-chapter-title" v-if="chunk.chapter_title">{{ chunk.chapter_title }}</div>
            <div class="lr-chunk-text">{{ chunk.content }}</div>
          </div>
        </div>

        <!-- PDF 查看器 -->
        <div class="lr-pdf" v-if="mode === 'pdf'">
          <iframe v-if="pdfUrl" :src="pdfUrl" class="lr-pdf-frame" />
          <div v-else class="lr-pdf-loading">加载中...</div>
        </div>
      </div>
    </div>
  </div>
</template>
```

- [ ] **步骤 2：添加样式**

全屏覆盖层、左侧目录栏（200px 宽）、右侧正文（scrollable）、暖色调配色。

- [ ] **步骤 3：Commit**

```bash
git add frontend/src/components/LiteratureReader.vue
git commit -m "feat: LiteratureReader沉浸式阅读弹窗（Markdown+PDF双模式+目录导航）"
```

---

## 任务 14：前端 — ChatFloat 支持画家专家模式

**文件：**
- 修改：`frontend/src/components/ChatFloat.vue:173-230`
- 修改：`frontend/src/stores/chatStore.js`

- [ ] **步骤 1：chatStore 加 artistExpertSessionId**

在 `chatStore.js` 中添加：

```javascript
const artistExpertSessionId = ref(null)

function setArtistExpertSession(sessionId) {
  artistExpertSessionId.value = sessionId
}
```

导出 `artistExpertSessionId` 和 `setArtistExpertSession`。

- [ ] **步骤 2：ChatFloat 接受 artistId 和 artistName props**

修改 `ChatFloat.vue` 添加 props：

```javascript
const props = defineProps({
  artistId: { type: Number, default: null },
  artistName: { type: String, default: null },
})

const isExpertMode = computed(() => props.artistId && props.artistName)
```

- [ ] **步骤 3：修改 send 函数**

在 `send` 函数的请求 body 中，如果有 `artistId`，添加：

```javascript
if (props.artistId) {
  body.artist_id = props.artistId
  body.artist_name = props.artistName
  // 使用独立的专家会话
  if (chatStore.artistExpertSessionId) {
    body.session_id = chatStore.artistExpertSessionId
  }
} else {
  // 使用全局小墨会话
  if (chatStore.floatSessionId) {
    body.session_id = chatStore.floatSessionId
  }
}
```

在收到响应 `d.session_id` 后，根据模式存储到不同 session：

```javascript
if (d.session_id) {
  if (props.artistId) {
    chatStore.setArtistExpertSession(d.session_id)
  } else {
    chatStore.setFloatSession(d.session_id)
  }
}
```

- [ ] **步骤 4：修改 header 显示**

如果 `isExpertMode`，显示画家专家标题：

```html
<div class="cf-header-title">
  {{ isExpertMode ? `${artistName}研究专家` : '小墨 · 知识问答' }}
</div>
```

- [ ] **步骤 5：Commit**

```bash
git add frontend/src/components/ChatFloat.vue frontend/src/stores/chatStore.js
git commit -m "feat: ChatFloat支持画家专家模式（独立session+专属提示词）"
```

---

## 任务 15：端到端验证

- [ ] **步骤 1：启动后端，验证所有 API endpoint 可访问**

```bash
cd Z:/molin-wiki/backend && python -c "
from app.main import app
routes = [r.path for r in app.routes if hasattr(r, 'path')]
literature_routes = [r for r in routes if 'literature' in r]
print(f'Total routes: {len(routes)}')
print(f'Literature routes: {literature_routes}')
"
```

- [ ] **步骤 2：启动前端，验证编译无报错**

```bash
cd Z:/molin-wiki/frontend && npm run build 2>&1 | tail -5
```

- [ ] **步骤 3：手动测试完整流程**

1. 打开 `/artist/李鱓/literature`
2. 点击"上传文献"，上传一篇 PDF
3. 等待处理完成，验证文献出现在列表中
4. 点击文献 → 弹出沉浸式阅读弹窗
5. 验证 Markdown 渲染正常
6. 切换到 PDF 模式
7. 关闭弹窗
8. 使用 ChatFloat 提问（应显示"李鱓研究专家"）
9. 全局知识库搜索应能搜到该文献内容

- [ ] **步骤 4：Commit 最终状态**

```bash
git add -A
git commit -m "feat: 画家专属文献库功能完成"
```
