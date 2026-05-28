# 墨林百科 (Molin Wiki)

基于 AI 的中国书画知识平台——集艺术家百科、作品收录、题跋分析、书法溯源、构图讲评与知识检索于一体。

---

## 技术栈

- **前端**：Vue 3 + Vite + Element Plus
- **后端**：FastAPI + SQLAlchemy（SQLite）
- **异步任务**：Celery + Redis（构图分析等长耗时任务）
- **向量检索**：Qdrant（知识库语义搜索、构图案例检索）
- **AI 能力**：SiliconFlow / Qwen（OpenAI Compatible）

---

## 功能模块

### 艺术家百科
历代书画名家的生平、作品、印章、题跋、游历与艺术风格档案，支持多维度浏览与检索。

### 作品收录与管理
支持批量上传、册页关联、作品标签、封面截选（Strip）、作品归属（Artwork-Artist）等，并提供完整的审核与修订历史。

### 题跋空间分析 (Tubi)
AI 自动识别画作中的题跋、绘画、留白区域，生成可视化空间分析图与统计数据。

### 书法字体识别 (Recognition)
上传书法单字，智能匹配碑帖字形来源，返回相似度与候选列表。

### 知识检索 (Knowledge Search)
基于 Qdrant 的语义搜索，支持对历代名家题跋、印章、绘画理论进行自然语言检索。

### 潘天寿构图体系 (Composition)
基于潘天寿教学理论，异步分析国画构图特征，生成讲评报告与 PDF（含热力图、起承转合分析）。

### 起承转合分析 (Qczh)
运用多模态 AI 对国画构图的起承转合进行深度解读。

### 内容大数据分析 (Content Analysis)
批量分析题跋内容，统计主题、情感、时期、艺术家等多维度数据，支持审核流程。

### 情感分析引擎 (Emotion Engine)
多维度情感/意境分析，为画作生成多向量情感卡片。

### 印鉴管理 (Seals)
管理艺术家印鉴库，支持多版本合并与缩略图展示。

### 地图模式 (Map Mode)
以地理信息维度呈现艺术家的游历轨迹与创作分布。

### 用户与权限管理
角色包括 super_admin / admin / editor / reader / guest，支持 JWT 登录，操作审计与通知系统。

---

## 目录结构

```
molin-wiki/
  backend/
    app/
      api/                          # 路由（artists/artworks/tubi/recognition/knowledge/composition/…）
      core/                         # 配置、数据库、Celery
      models/                       # 数据表模型
      modules/
        pantianshou_composition/    # 构图模块（任务、报告、Qdrant、知识库等）
      services/                     # 各业务服务（识别/题跋/情感/内容分析等）
    data/                           # SQLite、上传、静态输出（本地运行生成）
  frontend/
    src/
      views/                        # 主页面（artist/tubi/knowledge/composition/…）
      modules/pantianshou-composition/  # 构图模块页面与组件
  deploy.sh                         # 服务器部署脚本
```

---

## 架构与端口

本地开发默认端口：
- 前端：`http://localhost:3000`
- 后端：`http://localhost:8001`
- Redis：`localhost:6379`（构图分析必需）
- 后端 API 前缀：`/api/v1`

前端通过 Vite 代理访问后端：
- `/api` -> `http://localhost:8001`
- `/static` -> `http://localhost:8001`

---

## 本地启动

### 一键启动（推荐）

所有服务一键拉起，首次运行会自动下载 Redis：

**Windows:**
```powershell
.\start_all.ps1
.\start_all.ps1 -SkipFastAPI      # 只启动 Redis + Celery
.\start_all.ps1 -SkipRedis        # 只启动 Celery + FastAPI
```

**Linux / macOS:**
```bash
chmod +x start_all.sh stop_all.sh
./start_all.sh
./stop_all.sh
```

启动后：

| 服务 | 地址 |
|------|------|
| FastAPI 后端 | `http://localhost:8001` |
| API 文档 (Swagger) | `http://localhost:8001/docs` |
| 前端 | `http://localhost:3000` |
| Redis | `localhost:6379` |

### 手动分步启动

<details>
<summary>点击展开</summary>

#### 1) Redis（构图分析必需）
```powershell
.\start_redis_windows.ps1    # Windows
sudo apt install redis-server && redis-server --daemonize yes   # Linux
```

#### 2) Celery Worker（构图分析必需）
```powershell
.\start_celery_windows.ps1   # Windows
cd backend && celery -A app.core.celery_app worker --loglevel=info --pool=prefork   # Linux
```

#### 3) 后端
```bash
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```

#### 4) 前端
```bash
cd frontend
npm install
npm run dev -- --host 0.0.0.0 --port 3000
```

</details>

---

## 环境变量

后端示例见：`backend/.env.example`。

常用配置：
- `REDIS_URL`：Redis 地址（Celery broker/backend、进度 PubSub）
- `QDRANT_URL` / `QDRANT_API_KEY`：启用知识库语义搜索与构图规则检索
- `SILICONFLOW_API_KEY`：题跋分析、书法识别、内容分析等 AI 调用
- `QWEN_API_KEY` / `QWEN_BASE_URL` / `COMPOSITION_LLM_MODEL`：构图讲评 LLM
- `CORS_ALLOW_ORIGINS`：后端 CORS 白名单（默认 `*`）

---

## 部署

```bash
bash deploy.sh
```

自动检测变更，前端 build + SCP，后端源码热挂载秒级生效。

---

## 开发约定

- 使用分支 + PR：避免直接在 `master` 上提交
- 已提供 `.gitattributes`，统一换行与二进制文件处理

---

MIT License

## 联系方式

如有问题或建议，欢迎提交 Issue。
