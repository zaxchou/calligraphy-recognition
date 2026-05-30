---
name: tubi-upload-rebuild
overview: 题跋上传可靠性改造：Layer1后端可靠性（Redis降级+Worker看门狗+错误透明化）+ Layer2前端透明化（两阶段上传+分进度条+失败重试）
todos:
  - id: backend-redis-fallback
    content: 改造 backend/app/api/tubi.py 的 auto-analyze 接口：Redis 不可用时 fallback 到 DB 入队，response 增加 via 字段标识来源
    status: completed
  - id: backend-queue-info-fallback
    content: 改造 queue-info 接口：Redis 不可用时从 tubi_jobs 表查询状态，实现 DB fallback
    status: completed
    dependencies:
      - backend-redis-fallback
  - id: backend-error-codes
    content: 增强错误处理：analysis_note 记录详细错误，API 返回增加 error_code 字段
    status: completed
    dependencies:
      - backend-queue-info-fallback
  - id: backend-worker-watchdog
    content: 增强 tubi_worker.py 的 cleanup_stale_jobs：检测 15 分钟未更新的 processing 任务，自动重置为 queued
    status: completed
  - id: backend-worker-idempotent
    content: tubi_worker.py 增强幂等处理：处理前检查 TubiJob 是否已被其他 worker 处理
    status: completed
    dependencies:
      - backend-worker-watchdog
  - id: backend-worker-graceful-shutdown
    content: tubi_worker.py 优雅关闭：收到退出信号时把 processing 任务重置为 queued
    status: completed
    dependencies:
      - backend-worker-idempotent
  - id: backend-tubi-job-model
    content: 修改 tubi_job.py 模型：增加 error_code 和 last_error_detail 字段
    status: completed
  - id: frontend-upload-store
    content: 新增 frontend/src/stores/uploadStore.js：批量上传状态管理、断点续传、失败重试队列
    status: completed
  - id: frontend-axios-interceptor
    content: 修改 frontend/src/api/index.js：增加 axios interceptor，识别网络错误自动重试 1 次
    status: completed
    dependencies:
      - frontend-upload-store
  - id: frontend-batch-upload-two-phase
    content: 大改 TubiAnalysis.vue 批量上传：两阶段模式（快速上传 → 批量入队 → 后台轮询状态）
    status: completed
    dependencies:
      - frontend-upload-store
      - frontend-axios-interceptor
  - id: frontend-single-upload-progress
    content: 增强单张上传进度：显示排队位置 + 预估等待时间 + 分阶段进度条
    status: completed
    dependencies:
      - frontend-batch-upload-two-phase
  - id: frontend-error-display
    content: 增强错误展示：根据 error_code 显示友好提示，失败项显示「重试」按钮
    status: completed
    dependencies:
      - frontend-batch-upload-two-phase
---

## 产品需求

### 背景

用户上传题跋图片时经常遇到以下问题：

1. **Redis 服务挂了**导致 Worker 崩溃、上传/分析流程中断
2. **上传进度不透明** — 用户不知道卡在哪一步
3. **失败原因不明确** — 只显示 generic error，不告诉用户是网络问题还是服务问题
4. **批量上传体验差** — 串行上传+串行分析，一张失败后面全停，没有重试机制

### 目标

彻底解决上传功能的可靠性问题，分两个阶段：

- **Phase 1（后端可靠性）**：Redis fallback、Worker 看门狗、错误透明化
- **Phase 2（前端透明化）**：两阶段上传、分进度条、失败可重试

### 约束

- 不改现有 API 兼容性（新增接口，不改现有接口签名）
- 不需要分片上传（文件通常 <10MB）
- 项目无测试用例

## 核心功能

### Phase 1：后端可靠性

#### 1.1 Redis Fallback 机制

- **目标**：Redis 挂了也能跑队列，不影响上传和分析
- **实现**：
- `auto-analyze` 接口：Redis 不可用时直接操作 DB，将状态改为 `queued`，不再依赖 Redis 入队
- `queue-info` 接口：优先读 Redis，fallback 读 DB 中的 `tubi_jobs` 表
- 后端启动时自动清理 `processing` 状态超过 N 分钟的 stale jobs

#### 1.2 Worker 看门狗

- **目标**：Worker 崩溃/超时后自动恢复，队列状态一致
- **实现**：
- `cleanup_stale_jobs()` 函数增强：检查 `updated_at` 超过 15 分钟的 `processing` 任务，自动重置为 `queued`
- `process_one()` 函数增强：每次处理前检查是否已被其他 worker 处理（幂等）
- 优雅关闭：Worker 收到 SIGTERM 时把 `processing` 状态的任务重置为 `queued`

#### 1.3 错误信息透明化

- **目标**：用户能区分"上传失败"、"入队失败"、"分析失败"
- **实现**：
- `analysis_note` 字段存储详细错误原因（如"Redis连接超时"、"VL模型调用失败"）
- API 返回时在 `status` 之外增加 `error_code` 字段（如 `REDIS_UNAVAILABLE`、`VL_TIMEOUT`）
- 前端根据 error_code 显示友好提示

### Phase 2：前端透明化

#### 2.1 单张上传进度增强

- **目标**：用户知道现在卡在哪一步、预计还要多久
- **实现**：
- 上传完成后轮询 `queue-info` 获取排队位置和预估等待时间
- 状态轮询时显示「排队中 (第3位，预计8分钟)」「AI分析中 (30%)」等明确状态
- 区分上传进度（文件传输）和分析进度（AI处理）

#### 2.2 批量上传两阶段改造

- **目标**：快速完成上传，后续异步分析，用户可关闭页面
- **实现**：
- 阶段一：批量快速上传（并发数=3，不触发分析），收集 uploaded_ids
- 阶段二：批量入队（一次性提交所有 ids），显示入队成功
- 阶段三：后台轮询状态（可关闭页面，结果保存在 DB）
- 新增 `uploadStore`：管理批量上传状态，支持 localStorage 断点续传

#### 2.3 进度条分阶段显示

- **目标**：清晰展示每张图片的处理阶段
- **实现**：
- 每张图片独立显示状态：「上传成功」「排队中 (第2位)」「分析中 45%」「已完成」「失败」
- 总体进度条显示：「已完成 12/100 | 分析中 3/100 | 失败 1/100」
- 失败项显示具体错误原因和「重试」按钮

#### 2.4 错误分类处理

- **目标**：网络错误自动重试，服务器错误提示用户
- **实现**：
- axios interceptor：网络错误自动重试 1 次（5秒后）
- 区分错误类型：
    - `Network Error` → 自动重试
    - `500 Service Error` → 提示"服务器繁忙，稍后重试"
    - `analysis_note` 有内容 → 显示具体错误原因
- 批量上传失败不阻断后续，用户可选择「继续」或「重试失败的」

## 验收标准

### Phase 1 验收

1. Redis 服务停止后，上传仍能成功，分析任务状态改为 `queued`
2. Worker 崩溃重启后，stale jobs 自动重置并重新处理
3. 分析失败时，用户能看到具体错误原因（如「VL模型调用超时」）

### Phase 2 验收

1. 单张上传时能看到「排队中 (第N位，预计X分钟)」
2. 批量上传后关闭页面，再次打开能看到分析进度
3. 失败项显示「重试」按钮，点击后重新处理
4. 网络抖动时自动重试，不显示错误

## 关键文件

| 文件 | 改动类型 | 说明 |
| --- | --- | --- |
| `backend/app/api/tubi.py` | 修改 | Redis fallback、错误码增强、queue-info fallback |
| `backend/tubi_worker.py` | 修改 | 看门狗增强、幂等处理、优雅关闭 |
| `backend/app/models/tubi_job.py` | 修改 | 增加 error_code 字段 |
| `frontend/src/views/TubiAnalysis.vue` | 大改 | 两阶段批量上传、状态轮询增强 |
| `frontend/src/stores/uploadStore.js` | 新增 | 批量上传状态管理、断点续传 |
| `frontend/src/api/index.js` | 小改 | axios interceptor、queue-info API |


## 技术方案

### 架构原则

1. **Redis 是优化，不是依赖** — 所有功能在 Redis 不可用时降级到 DB
2. **状态持久化** — 每一步状态都写到 DB，前端刷新页面也能恢复
3. **错误可追踪** — analysis_note + error_code 双轨记录

### Redis Fallback 实现

```python
# auto-analyze 接口改造
def auto_analyze(image_id: str, db: Session):
    # 尝试 Redis 入队
    try:
        conn = _get_redis()
        conn.lpush(QUEUE_KEY_PENDING, image_id)
        return {"enqueued": True, "via": "redis"}
    except Exception:
        # Fallback：直接操作 DB
        db_analysis = db.query(TubiAnalysis).filter(...).first()
        db_analysis.status = "queued"
        # 写 tubi_jobs 表（作为队列的 DB 版本）
        db_job = TubiJob(image_id=image_id, status="queued", ...)
        db.commit()
        return {"enqueued": True, "via": "db"}
```

### Worker 看门狗实现

```python
# cleanup_stale_jobs 增强
def cleanup_stale_jobs():
    threshold = datetime.now() - timedelta(minutes=15)
    # 重置 stale processing jobs
    stale_jobs = db.query(TubiJob).filter(
        TubiJob.status == "processing",
        TubiJob.updated_at < threshold
    ).all()
    for job in stale_jobs:
        job.status = "queued"
        job.last_error = "Worker超时已重置"
```

### 前端两阶段上传流程

```
用户选择文件
    ↓
阶段一：批量快速上传（Promise.all + 并发控制）
  - 每批3张，串行上传
  - 收集 uploaded_ids
  - 存储到 localStorage
    ↓
阶段二：批量入队（/auto-analyze 批量接口）
  - 显示「已上传N张，正在入队...」
    ↓
阶段三：后台轮询
  - 每5秒轮询已入队 ids 的状态
  - 更新 uploadStore
  - 支持页面关闭后继续轮询（用 localStorage 记录）
    ↓
结果展示
  - 成功/失败统计
  - 失败项「重试」按钮
```

### 错误码体系

| error_code | 含义 | 用户提示 |
| --- | --- | --- |
| `REDIS_UNAVAILABLE` | Redis 连接失败 | "队列服务不可用，已切换到备用模式" |
| `VL_TIMEOUT` | VL 模型调用超时 | "AI分析超时，请重试" |
| `OCR_FAILED` | OCR 识别失败 | "文字识别失败，但图片已上传" |
| `FILE_TOO_LARGE` | 文件超过 50MB | "文件过大，请压缩后重试" |
| `WORKER_CRASHED` | Worker 崩溃 | "分析服务已重启，请等待" |


### 数据库变更

```sql
-- tubi_jobs 表增加字段
ALTER TABLE tubi_jobs ADD COLUMN error_code VARCHAR(50);
ALTER TABLE tubi_jobs ADD COLUMN last_error_detail TEXT;

-- tubi_analyses 表已有 analysis_note 字段存储详细错误
```

### 目录结构

```
backend/
├── app/
│   ├── api/
│   │   └── tubi.py          # [MODIFY] Redis fallback、错误码增强
│   └── models/
│       └── tubi_job.py      # [MODIFY] 增加 error_code 字段
├── tubi_worker.py           # [MODIFY] 看门狗增强、幂等处理
└── data/
    └── calligraphy.db       # SQLite，字段变更

frontend/src/
├── views/
│   └── TubiAnalysis.vue     # [MODIFY] 两阶段批量上传
├── stores/
│   └── uploadStore.js       # [NEW] 批量上传状态管理
├── api/
│   └── index.js             # [MODIFY] axios interceptor
└── tubi/
    └── utils.js             # [MODIFY] 错误码解析
```