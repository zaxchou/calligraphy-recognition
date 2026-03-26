# Calligraphy Recognition

一个面向“书法碑帖识别 / 中国画题跋分析 / 潘天寿构图讲评”的综合实验项目。

当前仓库包含：
- **前端**：Vue 3 + Vite + Element Plus
- **后端**：FastAPI + SQLAlchemy（默认 SQLite）
- **异步任务**：Celery + Redis（用于构图分析等长耗时任务）
- **向量检索（可选）**：Qdrant（用于构图案例/规则检索）
- **AI 能力（按需）**：SiliconFlow / Qwen（OpenAI Compatible）等

---

## 功能概览

- **书法碑帖识别**：上传单字/局部图，匹配碑帖字形，返回相似度与候选。
- **题跋分析（Tubi）**：题跋区域/画面结构的可视化与统计分析（见 [README_TUBI_ANALYSIS.md](README_TUBI_ANALYSIS.md)）。
- **潘天寿教你构图（Composition）**：上传国画作品，异步分析构图特征，生成报告与 PDF，支持进度与 ETA。

---

## 目录结构

```
calligraphy-recognition/
  backend/                          # FastAPI 后端
    app/
      api/                          # 路由聚合（recognition/steles/tubi/composition）
      core/                         # 配置、数据库、Celery
      models/                       # 数据表模型
      modules/
        pantianshou_composition/    # 构图模块（任务、报告、Qdrant、知识库等）
      services/                     # 识别/题跋等服务
    data/                           # SQLite、上传、静态输出（本地运行生成）
    requirements.txt
    .env.example
  frontend/                         # Vue3 前端
    src/
      views/                        # 主页面
      modules/pantianshou-composition/  # 构图模块页面与组件
    vite.config.js
  README.md
  README_TUBI_ANALYSIS.md
```

---

## 架构与端口

本地开发默认端口：
- 前端：`http://localhost:3000`
- 后端：`http://localhost:8003`
- 后端 API 前缀：`/api/v1`

前端通过 Vite 代理访问后端：
- `/api` -> `http://localhost:8003`
- `/static` -> `http://localhost:8003`

---

## 本地启动（推荐流程）

### 1) 后端

```bash
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8003
```

健康检查：`http://localhost:8003/health`

### 2) 前端

```bash
cd frontend
npm install
npm run dev -- --host 0.0.0.0 --port 3000
```

打开：`http://localhost:3000`

---

## 构图模块（潘天寿教你构图）说明

### 进度与 ETA

构图分析为异步任务：
- 上传后生成 `task_id`
- 前端可轮询 `/api/v1/composition/task/{task_id}` 或订阅 SSE `/api/v1/composition/task/{task_id}/events`

服务端实现：
- Celery + Redis 可用时：异步执行 + 进度/ETA 持续更新
- Redis 不可用时：自动降级为线程执行（仍会落库更新状态）

### 关键产物

- 热力图：`/static/composition/overlays/*_heatmap.png`
- 报告 JSON：`/static/composition/reports/*.json`
- PDF：`/static/composition/pdfs/*.pdf`

---

## 环境变量

后端示例见：`backend/.env.example`。

常用配置：
- `REDIS_URL`：Redis 地址（Celery broker/backend、进度 PubSub）
- `QDRANT_URL` / `QDRANT_API_KEY`：启用构图规则/案例检索
- `SILICONFLOW_API_KEY`：题跋分析与识别相关 AI
- `QWEN_API_KEY` / `QWEN_BASE_URL` / `COMPOSITION_LLM_MODEL`：构图讲评 LLM
- `CORS_ALLOW_ORIGINS`：后端 CORS 白名单（逗号分隔；默认 `*`）

---

## 开发约定（建议）

- 使用分支 + PR：避免直接在 `master` 上提交。
- 已提供 `.gitattributes`，用于统一换行与二进制文件处理。


MIT License

## 联系方式

如有问题或建议，欢迎提交Issue。
