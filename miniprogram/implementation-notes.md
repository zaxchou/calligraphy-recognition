# 小程序多板块改造 — 实现笔记

## 2026-05-22 开始实现

### 修复：服务器大图不显示（nginx DZI 路由缺失）

**问题**：`https://124.223.17.29/#/tubi/xxx` 点击大图一直 loading，DZI 文件请求返回 HTML 而非 XML。

**根因**：nginx 配置中缺少 `/dzi/` location 块。后端 FastAPI 挂载了 `/dzi` (StaticFiles)，但前端 nginx 没有对应的路由规则。DZI 请求被 SPA 兜底规则 `location / { try_files $uri $uri/ /index.html; }` 捕获，返回了 index.html。

**修复**：在 `deploy/nginx.conf` 中添加：
```nginx
location ^~ /dzi/ {
    proxy_pass http://backend_upstream;
    proxy_http_version 1.1;
    proxy_set_header Connection "";
    proxy_set_header Host $host;
    expires 7d;
    add_header Cache-Control "public, immutable";
}
```

**注意**：必须 `docker compose restart nginx`（完整重启），`nginx -s reload` 不够。

---

## 2026-05-22 代码 Review：Trae 近期工作质量审计

### 审计范围

最近一周约 50 个 commit，覆盖：Artist 板块重构、印章系统、作品库管理、侧边栏重构、DZI 深度缩放、排行榜、AI 识图、管理后台、知识库搜索、题跋分析等多个模块。

---

## 🔴 CRITICAL：必须立即修复

### C1. 画家列表 N+1 查询（2000 次独立 SQL）

**文件**：`backend/app/api/artists.py:169-172`

```python
for a in artists:
    a["artwork_count"] = conn.execute(
        "SELECT COUNT(*) FROM tubi_analyses WHERE artist = ?", (a["name"],)
    ).fetchone()[0]
```

**影响**：`fetchAll(page_size=2000)` 时，这一行执行 2000 次独立 SQL 查询。每次需要 ~1-5ms 网络/磁盘 I/O，总计额外 2-10 秒。

**修复**：用 JOIN + GROUP BY 替换，1 次查询完成：
```python
rows = conn.execute(
    f"""SELECT a.*, COALESCE(t.cnt, 0) AS artwork_count
        FROM artists a
        LEFT JOIN (SELECT artist, COUNT(*) AS cnt FROM tubi_analyses GROUP BY artist) t
          ON a.name = t.artist
        WHERE {where_clause}
        ORDER BY {sort_sql}
        LIMIT ? OFFSET ?""",
    (*params, page_size, offset)
).fetchall()
```

### C2. SELECT * 返回全部 36 列（包含大文本 JSON）

**文件**：`backend/app/api/artists.py:164`

`SELECT *` 返回 `biography`（Text）、`masterpieces`（JSON）、`tags`（JSON）、`art_chronology`（JSON）、`gallery_images`（JSON）等大字段，而列表页只用 `name`、`dynasty`、`artwork_count`、`avatar_url`、`alias` 这 5-6 个字段。

**影响**：响应体膨胀 80-90%，2000 个画家的 JSON 文本列可有数 MB。

**修复**：只 SELECT 列表页需要的字段。

### C3. ContentAnalysis.vue AI 报告生成永远失败（Auth 断开）

**文件**：`frontend/src/views/ContentAnalysis.vue`（406 行定义 `API_BASE`，539/564 行调用 `/summary`）

整页 12 处 API 调用全部使用原生 `fetch()`，**完全不经过** `@/api` 的 axios 实例（带有 JWT 拦截器）。其中：

- `POST /api/v1/content-analysis/summary` 端点要求 `Depends(require_editor)` 认证（`content_analysis.py:2964`）
- 前端用 `fetch()` 不带 `Authorization: Bearer xxx` header
- 后端返回 401
- 前端 `loadCachedSummary()` 的 catch 块**完全为空**（557-558 行），用户看到空白报告区
- `generateSummary()` 的 catch 块显示"生成报告失败"，用户不知道为什么

**影响**：整个"学术报告"功能完全不可用——无论是否登录。

**修复**：
1. 改用 `api` axios 实例（`import api from '@/api'`）
2. 或手动注入 `Authorization` header
3. `loadCachedSummary()` 需要实际错误处理

---

## 🟠 HIGH：显著影响用户体验

### H1. 画家列表无分页，每次加载全部 2000 条

**文件**：`frontend/src/stores/artistStore.js:69`

```javascript
async function fetchAll(filters = {}) {
    const params = { page: 1, page_size: 2000, ... }
```

- `fetchPage()`（40 条/页）已定义但从未被调用
- `ArtistList.vue:107` 只调用 `store.fetchAll()`
- 页面无分页 UI、无"加载更多"按钮

**影响**：每次进入画家列表页 → 2000 条 + 2000 次 N+1 查询。这是用户感觉"打开 artist 列表页有点慢"的直接原因。

**修复**：将 `ArtistList.vue` 改为调用 `fetchPage()`，添加滚动加载或分页控件。

### H2. 每次筛选/搜索都清空缓存重新拉取

**文件**：`frontend/src/views/ArtistList.vue:145-172`

每个 filter 变更都调用 `store.clear()`（将 `lastFetchTime` 置 0）然后 `doLoad()`。store 中 5 分钟的缓存 TTL（`isStale()` 方法）完全成了死代码。

**影响**：用户来回切换朝代筛选 → 每次都重新发 API 请求，即使 5 分钟前刚拉过同样的数据。

### H3. ArtistTimeline 深度 Watcher + pinyin 重复计算

**文件**：`frontend/src/components/artist/ArtistTimeline.vue:98-100`

```javascript
watch(() => [props.artists, props.autoExpand], () => {
    updateExpanded()
}, { deep: true, immediate: true })
```

`deep: true` 对 2000 个对象的数组做深度遍历。同时 `dynastyGroups` computed（111 行）对每个 artist 调用 `pinyin()` 库做汉字转拼音，2000 次/渲染。

**修复**：
- 去掉 `deep: true`（数组引用变化时已足够）
- 用 `Map` 缓存 pinyin 结果，避免重复转换

### H4. 路由守卫阻塞画家子页面导航

**文件**：`frontend/src/router/index.js:221-251`

```javascript
router.beforeResolve(async (to, _from) => {
    if (artistRoutes.includes(to.name) && to.params.name) {
        const res = await fetch(`${API_BASE}/artists/by-name/${...}`)
```

进入任何 `/artist/:name/*` 页面时，导航被同步 fetch 阻塞。后端慢时（N+1 查询期间），用户看到白屏等待。

**修复**：用 store 中已缓存的 artist list 做本地匹配，只在缓存 miss 时才发请求；或改为非阻塞（导航先完成，数据异步加载）。

### H5. ArtistEditor.vue 上传图片绕过 Auth

**文件**：`frontend/src/views/admin/ArtistEditor.vue:447`

```javascript
fetch(`${API_BASE}/artists/upload-image`, { method: 'POST', body: formData })
```

裸 `fetch()`，无 `Authorization` header。`/artists/upload-image` 端点可能要求 auth。如果不要求，则是安全漏洞。

---

## 🟡 MEDIUM：值得修复

### M1. Artist Claims 和 Artist Changes 模块完全无前端接入

- `backend/app/api/artist_claims.py`：5 个端点（认领申请/审核），前端零调用
- `backend/app/api/artist_changes.py`：4 个端点（信息变更/审核），前端零调用
- `backend/app/api/artwork_artists.py`：4 个端点（作品-画家关联），前端零调用

**影响**：13 个后端端点实现完整但无法使用。要么补齐前端，要么这是 Phase 3 未完成功能（document 说明即可）。

### M2. ContentAnalysis.vue 全部 12 处 fetch 绕过 API 层

除了 C3（/summary）因 auth 完全不可用外，其余 11 个公开端点（/stats、/correlation 等）虽然能工作，但：
- 无 auth token（如果将来加 auth 会全部坏掉）
- 无统一错误处理
- 无请求去重/重试

### M3. 知识库搜索缓存失效

`frontend/src/stores/knowledgeStore.js`：无任何 TTL 缓存、无去重。任务轮询用 `setInterval(1000ms)` 但在 `resetUploadStatus()` 外不清理定时器。

### M4. authStore 重复 return 键

`frontend/src/stores/authStore.js:125-136`：return 对象中 `token`、`userInfo`、`loading`、`isLoggedIn` 等 12 个属性写了两次。Pinia 可能警告，且容易导致维护时去重出错。

### M5. Vite 构建无 chunk 分割

`frontend/vite.config.js`：无 `manualChunks` 配置。所有懒加载路由共享单一 vendor chunk。`main.js:44-46` 全局注册了全部 Element Plus 图标（增加 bundle 体积）。

---

## 🟢 LOW：代码质量

### L1. 全局注册全部 Element Plus 图标

`frontend/src/main.js:44-46`：`for (const [key, component] of Object.entries(ElementPlusIconsVue))` 注册了全部图标。大部分页面只需要 3-5 个图标。

### L2. ArtistOverview.vue 并行 fetch 可优化

`frontend/src/views/artist/ArtistOverview.vue:520-527`：`fetchArtist()` 和 `fetchStats()` 串行执行，等待前者完成才开始后者。可改为 `Promise.all` 或 `loading` 提前释放。

### L3. 前端 config.js 和多个组件各自定义 API_BASE

`config.js`、`ContentAnalysis.vue`、`ArtistEditor.vue` 等多处各自 `const API_BASE = ...`，应统一从 config 或 api 模块导入。

---

## ✅ 已验证正常的流程

| 流程 | 状态 |
|------|------|
| 登录/注册 (JWT) | ✅ 正常 |
| 题跋分析列表/详情 | ✅ 正常（含 DZI 大图） |
| 知识库搜索/AI 摘要/书籍详情 | ✅ 正常 |
| 印章 CRUD + 多图上传 | ✅ 正常 |
| OpenSeadragon 深度缩放 | ✅ 正常 |
| 作品库 CRUD + 批量操作 | ✅ 正常 |
| 大数据分析统计表格 | ✅ 正常 |
| 画像/字画上传+分析 | ✅ 正常 |
| 管理后台权限控制 | ✅ 正常 |
| 服务器部署 (Docker) | ✅ 正常（nginx DZI 已修） |
| API 响应结构统一 `{success, data}` | ✅ 一致 |

---

## 修复优先级路线图

### Phase 1：立刻（阻塞性问题）
1. Fix C1：N+1 查询 → 单次 JOIN（后端 1 行改 5 行）
2. Fix C2：SELECT * → 列白名单（后端 1 行改 1 行）
3. Fix C3：ContentAnalysis summary auth gap（前端改用 api 实例 + 加错误处理）

### Phase 2：今天（性能 + 体验）
4. Fix H1：列表页改用 fetchPage + scroll 加载
5. Fix H2：去掉 clear() 调用，恢复缓存逻辑
6. Fix H3：去掉 deep:true + pinyin 缓存

### Phase 3：本周
7. Fix H4：路由守卫改用本地缓存
8. Fix M2：ContentAnalysis 统一用 api 实例
9. Fix M3：knowledgeStore 定时器清理
10. Fix M4：authStore 去重 return 键
11. Fix M5：Vite chunk 分割

### Phase 4：未来
12. M1：决定 artist claims/changes 模块是否实现前端
13. L1-L3：代码整洁优化

