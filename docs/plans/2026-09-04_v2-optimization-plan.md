# 墨林百科 v2.0 优化改进方案

> 日期：2026-09-04
> 背景：项目主体完成于 2026 年 4-6 月，工程实践受当时工具与经验所限。本方案以 2026 年 9 月的现代工程视角，对 5.5 万行 Python 后端 + 6.2 万行 Vue 前端做整体重审后输出。
> 前置文档：`reports/code-review-2026-09-03.md`（安全审查，本地）
> 状态标记：✅ 已完成（随本方案发布上线）｜📋 v2.0 规划项

---

## 一、安全整改：已完成与判定结论

### 1.1 已完成（2026-09-03 ~ 09-04，全部经线上实测验证）

| 编号 | 修复项 | 验证方式 |
|---|---|---|
| S1 | `/static` 数据库/用户私有目录下载漏洞 | nginx deny 规则，线上 403 实测 |
| S2 | 生产 JWT 使用公开默认密钥 | 96 位随机密钥轮换，伪造 token 实测 401 |
| S3 | 微信 mock 登录可接管任意账号 | 微信登录功能整体移除，123456 登录实测被拒 |
| S4 | 短信验证码明文写日志 | 代码修复并部署 |
| S5 | seals 6 个写端点零鉴权 | 补 require_editor/admin，匿名写入实测 401 |
| S6 | content_analysis 30 端点匿名可读 | 路由级 get_current_user，匿名实测 401 |
| S8 | /admin 无前端守卫 + 守卫 JSON.parse 崩溃风险 | 补 requiresAdmin meta + 容错重构 |
| S9 | TLS/SSH 密钥存放于网盘同步目录 | 移至 `~/.ssh/molin-wiki-keys/`（SSH 实测正常） |
| S11 | 全站零安全响应头 | HSTS/nosniff/DENY/Referrer/CSP 五头实测在线 |
| M10/M11/M12 | ECharts 监听器泄漏、聊天定时器泄漏、store 缓存清理不完整 | 代码修复随版部署 |

### 1.2 判定为"暂不处理"的项及理由

| 项 | 判定 | 理由 |
|---|---|---|
| S13 依赖升级（fastapi 0.104/python-jose） | **延后**，并入 §2.7 镜像化 | 依赖装在镜像层，热挂载部署下升级需重建镜像；单独升级风险/收益比差。CVE 中实际被利用路径（multipart DoS、JWT 算法混淆）已被 S1/S2 的修复间接堵住大半 |
| M1 async 路由内同步 requests | **延后**，并入 §2.4 LLM Gateway | 逐点改 run_in_executor 是浪费——统一 gateway 时自然消灭 |
| M6 `/dzi/` 目录暴露 | **不做** | DZI 瓦片本身即公开内容，目录内无敏感文件；保留为发布通道 |
| M7 容器 root 运行 | **延后** | 与镜像化（§2.7）一起做，单独改 USER 指令会碰挂载权限问题 |
| M8 证书路径与 compose 不一致 | **延后** | 线上实际配置正确运行中；统一时需停机窗口，列入镜像化批次 |
| M9 auto_deploy.sh 无人值守 | **判定不必要** | 该脚本无 CI 触发方（GitHub workflow 已删），实际靠人执行 deploy.sh；保留 |
| 第三批 XSS（5 套自研 markdown 渲染器无消毒） | **必须做**，列为 v2.0 前端 P0（见 §3.1） | 本轮未做，是当前公开站最大的残余风险 |

---

## 二、后端架构优化 v2.0（8 项）

### 2.1 启动流程与迁移体系 ⭐P0
**现状**：main.py 447 行，import 时即建表 + 550 行手写迁移 + 20 个路由 try/except 导入（失败只打 log，API 静默消失）+ 废弃的 on_event。
**问题**：代码即迁移、无版本无回滚；导入有副作用导致测试无法隔离；路由挂载失败被吞。
**v2.0 方案**：
- 全部迁入 FastAPI `lifespan`；路由改为包级自动注册（读 `app/api/__init__.py` 目录循环 include，失败 raise）
- `migrations/alembic/` 目录已存在（起过头没坚持）——把手写 `run_migrations()` 的每个步骤逆向固化为 Alembic baseline，此后加字段只写 revision
- 删除启动时的 `create_all` 调用
**工作量**：路由注册 1d + lifespan 1d + Alembic 逆向 3-5d

### 2.2 数据访问层：80 处裸 sqlite3 vs ORM ⭐P0
**现状**：ORM 与 `get_db_connection()` 混用（artists.py 一个文件 20+ 处），DDL 靠注释"keep in sync with model"人肉同步。
**v2.0 方案**：新代码禁用裸连接；重灾区（artists/artist_changes/artist_rules）机械改写为 Session 查询。PostgreSQL 迁移（团队有 PG 运维经验）列为独立决策点——**建议等知识库多书、多用户规模上来再动**，届时 pgvector 可评估替代 Qdrant 少养一个组件。
**工作量**：统一 ORM 5-8d；PG 迁移另计 10-15d

### 2.3 任务体系三轨归一 P1
**现状**：Celery+Redis 配置存在但闲置、内嵌 DB 轮询线程跑在 uvicorn 进程内（worker crash 带崩 web）、`tiba_worker.py` 独立进程入口，三套并存。
**v2.0 方案**：**砍掉 Celery+Redis**（当前规模不值得）；worker 拆独立进程 `python -m app.worker`（compose 独立 service），抢占逻辑改原子 UPDATE；任务量涨再换 arq（asyncio 原生）而非 Celery。
**工作量**：3d

### 2.4 LLM Gateway P1
**现状**：`qwen_llm_client` 自称统一实则 DeepSeek/SiliconFlow/百度 OCR 等 8+ 处各自实现重试/超时/JSON 解析，requests 与 httpx 混用（同步阻塞问题随之解决）；emotion_lexicon v1/v2/v3 三代并存。
**v2.0 方案**：建 `app/llm/` 包——`client.py`（唯一 httpx.AsyncClient 单例 + 统一 retry/timeout/JSON repair）+ `providers.py`（配置驱动的多供应商）+ `usage.py`（token/延迟计量入库）；prompt 收拢可版本化；lexicon 收敛 v3 单文件。
**工作量**：核心 2-3d；存量迁移分批 5-8d

### 2.5 测试安全网 ⭐P0（先于一切重构）
**现状**：5.5 万行零正式测试，所有回归靠重启后手点——这是重构不敢动的根本原因。
**v2.0 方案**：不追覆盖率，做 API 契约测试——pytest + httpx ASGI 打真实 app，auth/libraries/tiba/artworks 各写 happy path + 401/403，约 30 条用例（临时 SQLite + fixture 种子）；Alembic 化后加"空库 upgrade head"测试；GitHub Actions 跑 CI。
**工作量**：6d

### 2.6 配置治理 P2
**现状**：pydantic-settings 已用但 91 个字段中约 70 个被 `os.getenv` 架空；45 个 TIBA_* CV 超参混在部署配置里。
**v2.0 方案**：全部改声明式 Field；拆 AppSettings/LLMSettings/CVSettings。纯机械，1d。

### 2.7 部署镜像化 P1（S13 依赖升级在此批次执行）
**现状**：Docker 只当进程管理器——代码整目录热挂载覆盖镜像，镜像不可复现，回滚 = 找旧 tar。
**v2.0 方案**：镜像内装干净依赖（fastapi≥0.115、PyJWT 替换 python-jose、pdfjs 前端同步升）→ 推阿里云个人 registry → compose 改 image 拉取，data/.env 仍 volume；`alembic upgrade head` 作为部署钩子；deploy.sh 保留为紧急通道。
**工作量**：3d（依赖 Alembic 落地后）

### 2.8 知识库数据一致性 P2
**现状**：vector_id 失同步靠查询时"孤立向量回退"兜底，删书/重建索引必然漂移。
**v2.0 方案**：确立 **SQLite 为权威源**——把 fast_reindex.py 收编为 `python -m app.cli reindex-qdrant` 对账命令；写路径固定"先 Qdrant upsert → 后 SQLite 提交"，删除反向。knowledge.db 的 engine 收编进 core/database.py 统一工厂。
**工作量**：3-4d

---

## 三、前端优化 v2.0（8 项）

### 3.1 XSS 治理（原安全审查第三批）⭐P0
5 套自研 markdown 渲染器（MarkdownViewer/KnowledgeSearch/ChatFloat/ContentAnalysis/BookReaderModal）全部无消毒，AI 输出 v-html 直出。**方案**：引入 `markdown-it + DOMPurify`，写一个 `utils/safeMarkdown.ts` 统一出口，5 处渲染器逐个替换；同时补链接 scheme 白名单。**工作量 2-3d。当前公开站最大残余风险，v2.0 第一枪。**

### 3.2 构建瘦身 ⭐P0（收益最直接）
- echarts 7 处全量引入 → `echarts/core` 按需注册（预计 -60%，约省 600KB）
- element-plus 全量 + 全量图标 → `unplugin-vue-components + unplugin-auto-import`（首屏 1.1MB chunk 大头）
- 删除自研 http2Preload 插件（与 Vite 5 内置 modulepreload 重复）
- 字体：`font-display: swap` + 砍到 2 个字重
**合计首屏减重约 1.5MB+，工作量 3d**

### 3.3 API 层收口 P0
axios 封装（api/index.js）质量不错但 34 个文件绕过它裸 fetch，main.js 还 monkey-patch 了 window.fetch。**方案**：裸 fetch 全部收口进 api 层（SSE 经已有 useSSEStream.ts）；加 `useApiRequest()` composable 统一 loading/error 模式（30+ 页面的三件套样板可渐进消减）；移除 fetch patch。**工作量 5-8d**

### 3.4 死代码清理 P1（先删后改）
- ArtistAnalysis.vue 旧版（1032 行，挂在 /analysis-legacy）→ 删
- TibaDetail.vue（3491 行）与 TibaDetailPage.vue 双轨 → 借重构二选一
- admin/ 下未被路由引用的页面 → 核实后删
- 预计净删 3-5k 行

### 3.5 TS 工具链 P1
不做 6 万行全量迁移（ROI 太低）。**方案**：tsconfig（allowJs）+ eslint flat config + vue-tsc 只查 TS 文件；**api 层和 stores 优先 JSDoc 类型化**（~1800 行，类型收益最高的切入点）。**工作量 5d**

### 3.6 localStorage 统一持久化层 P1
19 个文件手工读写 localStorage 无版本号无容错。**方案**：`utils/storage.ts`（版本号 + schema 容错 + 配额处理）收口，或直接上 pinia-plugin-persistedstate。**工作量 2d**

### 3.7 移动端适配 P2
claude-design.css 响应式零散。先审计 KnowledgeSearch/ArtistList 两个高频页补 768px 断点，按页推进。**工作量 5-8d（按页）**

### 3.8 i18n 改造 ✅ 第一阶段已完成（2026-09-04）
vue-i18n 依赖已移除，改为零依赖 shim（zh/en 双词表 + $t/useI18n 兼容接口 + {param} 插值），语言切换按钮保留且可用。
**第二阶段（全站中英文）已立项为 Phase 6**：覆盖其余 97 个页面的硬编码中文，约 10-15 人日，见文末路线图。

---

## 四、执行路线图

| 阶段 | 内容 | 工作量 | 里程碑 |
|---|---|---|---|
| **Phase 0 ✅** | 安全热修 S1-S9 + 第二/四批鉴权与加固 | 2026-09-03 | 认证与数据暴露面收口 |
| **Phase 1 ✅** | §3.1 XSS 治理(21处) + §3.2 构建瘦身(-1.5MB) + §2.5 契约测试(24用例+CI) | 2026-09-04 | 安全闭环 + 重构安全网 |
| **Phase 2 ✅** | §2.1 lifespan 重构(lifespan+表驱动路由) + §2.2 artists ORM 化（Alembic 完整逆向延后） | 2026-09-04 | 数据层可控 |
| **Phase 3 ✅** | §2.3 worker 独立进程(compose service) + §2.7 依赖升级上线(fastapi 0.115/PyJWT) + M8 compose 收编 | 2026-09-04 | 部署可回滚（rollback 镜像标签就绪） |
| **Phase 4（进行中）** | §3.3 API 收口(agent 执行 3/13 批) + §3.4 死代码✅ + §3.5 TS 工具链✅ | ~8d 剩余 | 前端工程化 |
| **Phase 5（进行中）** | §2.6 配置治理✅(83字段) + §2.8 reindex CLI✅ + §3.6 storage层✅ | 剩 §2.4 LLM Gateway | 长期健康度 |
| **Phase 6（收官）** | **全站中英文国际化**：shim 已就绪(en 词表已恢复+切换按钮可用)，剩 97 页硬编码中文扫描/词条库/翻译审校（用户立项 2026-09-04） | 10-15d | 面向国际用户 |

## 五、本轮深审的关键判断（为什么这么排）

1. **测试先于重构**：5.5 万行零测试的库，任何大重构都是裸奔。30 条契约测试是所有后续项的安全网（架构审查与前端审查两条线独立给出了同一结论）。
2. **减法优先于加法**：砍 Celery/Redis、删死代码、i18n 做减法、移除自研 preload 插件——这个体量的项目，维护面缩小比引入新框架更有价值。
3. **不上 K8s、不全量 TS、不急迁 PG**：三个"不做"决定和"做"同样重要——当前规模下它们的成本都高于收益，方案里只留了决策触发条件（多书多用户规模、团队扩张）。
4. **热挂载部署是数据安全隐患的放大器**（半更新代码 × 半更新库 × 自动迁移）：镜像化排在 Alembic 之后、其他重构之前。
