# 后端代码审查报告

> 审查时间：2026-05-27  
> 审查范围：backend/app/ 核心模块  
> 审查方式：静态代码分析

---

## 一、确认 Bug（需尽快修复）

### 🔴 Bug 1：`tubi.py` 中 `year` 可能为 `None` 导致 TypeError

**文件**：`app/api/tubi.py`  
**行号**：第 79 行  
**严重程度**：🔴 高 — 会导致 500 错误

```python
# 当前代码（有 bug）
elif year <= 1745:   # year 可能为 None → TypeError
    period = "中期"
```

**问题**：当文件名无法解析出年份时，`year = None`，此时 `year <= 1745` 会抛出 `TypeError: '<=' not supported between instances of 'NoneType' and 'int'`。

**修复方案**：
```python
elif year is not None and year <= 1745:
    period = "中期"
elif year is not None:
    period = "晚期"
```

---

### 🔴 Bug 2：`database.py` 中 SQLite 保留字转义语法错误

**文件**：`app/core/database.py`  
**行号**：第 440-441 行  
**严重程度**：🔴 高 — 迁移脚本会抛异常

```python
# 当前代码（有 bug）
escaped = f'[{col}]' if col in ('references',) else col
conn.execute(f"ALTER TABLE artists ADD COLUMN {escaped} {col_type}")
```

**问题**：`[references]` 是 **SQL Server** 的转义语法，SQLite 需要用双引号：`"references"`。这行代码在执行到 `references` 字段时会报 SQL 语法错误。

**修复方案**：
```python
# SQLite 用双引号转义保留字
escaped = f'"{col}"' if col in ('references',) else col
```

---

### 🟡 Bug 3：`main.py` 静态文件目录挂载路径错误

**文件**：`app/main.py`  
**行号**：第 123 行  
**严重程度**：🟡 中 — 静态资源（图片）可能 404

```python
# 当前代码
app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "..", "data")), name="static")
```

**问题**：`__file__` 是 `backend/app/main.py`，`os.path.dirname(__file__)` = `backend/app`，`".."` = `backend`，最终指向 `backend/data/`。但实际数据目录在**项目根目录** `calligraphy-recognition/data/`。

**修复方案**：
```python
import os
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
app.mount("/static", StaticFiles(directory=os.path.join(PROJECT_ROOT, "data")), name="static")
```

---

### 🟡 Bug 4：首页统计缓存无 TTL 过期机制

**文件**：`app/api/tubi.py`  
**行号**：第 186-193 行  
**严重程度**：🟡 中 — 数据更新后缓存不失效

```python
# 当前代码 — 无 TTL 检查
def _get_stats_cache():
    try:
        if os.path.exists(_STATS_CACHE_FILE):
            with open(_STATS_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return None
```

**问题**：`_RESULTS_CACHE_FILE` 有 300s TTL 检查，但 `_STATS_CACHE_FILE` 没有任何过期逻辑，会导致统计数据永远不更新。

**修复方案**：参照 `_get_results_cache()` 加上 TTL 检查（建议 300s）。

---

### 🟡 Bug 5：`auth.py` 内存验证码在重启后丢失

**文件**：`app/api/auth.py`  
**行号**：第 29 行  
**严重程度**：🟡 中 — 开发环境体验问题，生产环境需用 Redis

```python
# 当前代码
_verify_codes: dict = {}  # 内存存储，重启即丢失
```

**问题**：目前 `_verify_codes` 是内存字典，服务器重启后所有待验证的验证码全部丢失。开发环境尚可接受，但生产环境必须使用 Redis。

**建议**：在 `.env` 中配置 `WECHAT_MOCK_MODE=false` 时，强制检查 Redis 是否可用，否则拒绝启动。

---

### 🟢 Bug 6：`content_analysis.py` 中 `artist` 参数 SQL 注入风险

**文件**：`app/api/content_analysis.py`  
**行号**：第 55 行  
**严重程度**：🟢 低 — 当前为内部系统，但需养成好习惯

```python
# 当前代码（字符串拼接）
return "(artist LIKE ? OR artist LIKE ?)", (f"%{artist}%", f"%{artist}%")
```

**问题**：虽然用了 `LIKE ?` 参数化（安全），但 `artist` 直接拼接进 f-string 做了两次，代码不够整洁。建议统一用参数化查询，并加 `sanitize` 函数。

---

## 二、安全漏洞

### 🔴 Security 1：JWT 默认 Secret 硬编码

**文件**：`backend/.env.example`（及运行时 `.env`）  
**问题**：`config.py` 中 `JWT_SECRET_KEY` 默认值为 `"calligraphy-jwt-secret-change-in-production"`，如果 `.env` 中未覆盖，所有 instances 共用同一个可预测的 secret，攻击者可伪造任意用户 Token。

**修复方案**：
1. 启动时检查是否为默认 secret，是则拒绝启动并报警
2. 生成随机 secret 写入 `.env`（首次启动脚本）

```python
# 建议在 main.py 启动时加入
if settings.JWT_SECRET_KEY == "calligraphy-jwt-secret-change-in-production":
    logger.critical("FATAL: JWT_SECRET_KEY 使用默认值，请在 .env 中修改！")
    raise SystemExit(1)
```

---

### 🟡 Security 2：`allow_credentials=False` 但 CORS 未限制具体 Origin

**文件**：`app/main.py` 第 108-117 行  

```python
_cors = settings.CORS_ALLOW_ORIGINS
origins = [o.strip() for o in _cors.split(",") if o.strip()] if _cors != "*" else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,   # 若为 "*" 则允许所有来源
    allow_credentials=False,   # 与 "*" 同时使用时浏览器会报错
    ...
)
```

**问题**：如果 `.env` 中 `CORS_ALLOW_ORIGINS=*`（默认值），则任何网站都可以跨域访问 API。生产环境应明确指定前端域名。

---

### 🟡 Security 3：PBKDF2 迭代次数可配置但未校验最小值

**文件**：`app/core/security.py` 第 25 行  

```python
iterations = 600000  # 硬编码，建议移到 config.py 并加最小值校验
```

**建议**：移到 `config.py` 作为 `PBKDF2_ITERATIONS` 配置项，启动时校验 ≥ 100000。

---

## 三、性能问题

### 🟡 Perf 1：分页查询缺失 — `list_seals` 全表扫描

**文件**：`app/api/seals.py` 第 138-192 行  

```python
# 当前代码：先查出所有 rows，再手动分页
rows = conn.execute(query, params).fetchall()
# ... 构建 seals 列表 ...
paginated = seals[skip:skip + limit]  # 内存中切片
return {"success": True, "seals": paginated, "total": total}
```

**问题**：
1. `fetchall()` 把全表数据拉到内存，印章数量大时很慢
2. `usage_count` 计算对每个印章都做一次全文扫描（`SELECT seal_content FROM tubi_analyses WHERE ...`），是 O(N×M) 复杂度

**修复方案**：
1. 改用在 SQL 中 `LIMIT ? OFFSET ?` 分页
2. `usage_count` 考虑用物化字段或后台异步更新

---

### 🟡 Perf 2：`_file_exists_cache` 无限增长无淘汰

**文件**：`app/api/tubi.py` 第 114-129 行  

```python
_file_exists_cache = {}  # 全局字典，无上限，无淘汰
```

**问题**：每次调用 `_cached_exists()` 都会往里写条目，但没有任何 LRU 淘汰或最大容量限制，长时间运行后内存会持续增长。

**修复方案**：用 `functools.lru_cache` 或设置最大容量（如 1000 条）+ TTL 双重淘汰。

---

### 🟡 Perf 3：`auth.py` 登录时多字段顺序扫描

**文件**：`app/api/auth.py` 第 316 行  

```python
for field, value in [("uid", account), ("phone", account), ("email", account), ("nickname", account)]:
    user = db.query(User).filter(getattr(User, field) == value).first()
    if user:
        break
```

**问题**：每个登录请求最多触发 4 次数据库查询。建议在 `uid`、`phone`、`email` 上建索引（目前只有 `phone` 可能有），并把查询合并为一次 `or_()`。

---

## 四、代码质量问题

### 🟢 Code 1：`run_migrations()` 函数过长（450 行）

**文件**：`app/core/database.py` 第 30-448 行  

**问题**：所有数据库迁移逻辑全写在一个函数里，可读性差，出错时难以定位。

**建议**：按版本拆分成 `migrations/v001.py`、`v002.py` 等，用 Alembic 管理。

---

### 🟢 Code 2：`main.py` 使用已弃用的 `@app.on_event()`

**文件**：`app/main.py` 第 404-417 行  

```python
@app.on_event("startup")   # FastAPI 已弃用，推荐用 lifespan
def _start_embedded_worker():
    ...

@app.on_event("shutdown")
def _stop_embedded_worker():
    ...
```

**建议**：迁移到 FastAPI 的 Lifespan 事件（ASGI 标准），更优雅且面向未来。

---

### 🟢 Code 3：多处使用 `print()` 而非 `logger`

**文件**：`tubi_worker.py` 第 144 行等  

```python
print(f"[tubi_worker] VL: {image_id}")  # 应使用 logger
```

**建议**：统一用 `logger.info/warning/error()`，方便生产环境集中收集日志。

---

### 🟢 Code 4：`config.py` 中模型名称大小写不一致

**文件**：`app/core/config.py`  

```python
SILICONFLOW_MODEL: str = "Pro/moonshotai/Kimi-K2.5"  # 模型名大小写？
QWEN_MODEL: str = os.getenv("QWEN_MODEL", "qwen3-vl-plus")
QWEN_TRANSLATION_MODEL: str = os.getenv("QWEN_TRANSLATION_MODEL", "qwen3.5-plus")
```

**建议**：集中在一个地方（如 `.env.example`）记录所有模型名称的正确拼写，并在启动时校验。

---

### 🟢 Code 5：`AUTHOR_DEFAULT_SEAL` 硬编码画家默认印章

**文件**：`app/api/tubi.py` 第 32-35 行  

```python
AUTHOR_DEFAULT_SEAL = {
    "李鱓": "作者印：复堂，李鱓，李鱓印、鱓印、宗杨、懊道人",
    "刘海勇": "作者印：刘氏、海勇、紫苑小学堂、东欧刘氏、海勇之玺、长乐",
}
```

**问题**：硬编码，新增画家时需要改代码。建议存到数据库 `artist_rules` 表或单独的配置表。

---

## 五、架构改进建议

### 💡 Arch 1：迁移到 Alembic 管理数据库迁移

目前 `run_migrations()` 是手写 SQL 幂等迁移，维护成本高，容易出错。建议：
1. 引入 Alembic
2. 用 `alembic revision --autogenerate` 生成迁移脚本
3. 保留现有迁移作为基线（Baseline）

---

### 💡 Arch 2：Redis 连接池化

**文件**：`tubi.py` 第 287-296 行、`tubi_worker.py` 第 51-60 行  

目前每次调用 `_get_redis()` 都新建连接，高并发时 Redis 连接数会暴增。

**建议**：用 `redis.ConnectionPool` 单例，所有调用共享连接池。

---

### 💡 Arch 3：Celery Worker 与 Embedded Worker 双模式并存 — 有歧义

**文件**：`main.py`（embedded worker）vs `start_all.ps1`（Celery worker）

目前系统同时存在两种 Worker 模式：
1. `main.py` 内嵌线程 Worker（DB 轮询模式）
2. `start_all.ps1` 启动的独立 Celery Worker

**问题**：如果两者同时开启，同一个任务可能被处理两次。

**建议**：明确二选一，或加分布式锁（`redis.setnx`）防止重复处理。

---

### 💡 Arch 4：Pydantic V1 vs V2 兼容性问题

代码中混用了 V1 和 V2 的语法：
- `class Config: from_attributes = True` → Pydantic V1
- `model_config = ConfigDict(from_attributes=True)` → Pydantic V2

**建议**：统一升级到 Pydantic V2，并运行 `pydantic-migrate` 工具检查兼容性。

---

## 六、优先级建议

| 优先级 | 项目 | 理由 |
|--------|------|------|
| 🔴 P0 | Bug #1：`year is None` 检查 | 会抛 500，影响用户上传 |
| 🔴 P0 | Bug #2：SQLite 保留字转义 | 迁移脚本报错，`references` 字段无法添加 |
| 🔴 P0 | Security #1：JWT Secret 检查 | 安全风险，可被伪造 Token |
| 🟡 P1 | Bug #3：静态文件挂载路径 | 图片 404，影响前端展示 |
| 🟡 P1 | Perf #1：分页查询缺失 | 数据量大时接口超时 |
| 🟡 P1 | Arch #3：双 Worker 去重 | 可能导致重复处理 |
| 🟢 P2 | 其他代码质量改进 | 可安排在后续迭代中处理 |

---

## 七、总结

| 类别 | 数量 |
|------|------|
| 确认 Bug | 4 个 |
| 安全隐患 | 3 个 |
| 性能问题 | 3 个 |
| 代码质量 | 5 个 |
| 架构改进 | 4 个 |

**最关键行动项**：
1. 修复 `tubi.py` 中 `year is None` 的判断
2. 修复 `database.py` 中 SQLite 保留字转义语法
3. 加入 JWT Secret 默认值启动检查
4. 修正静态文件挂载路径
5. 为 `list_seals` 添加数据库层分页
