# 墨林百科 (Molin Wiki)

**AI 驱动的中国书画知识平台** — 集艺术家百科、作品收录、题跋分析、书法溯源、构图讲评与知识检索于一体。

**AI-Powered Chinese Painting & Calligraphy Knowledge Platform** — Artist encyclopedia, artwork collection, colophon analysis, calligraphy recognition, composition critique, and semantic knowledge retrieval.

🌐 [molin.wiki](https://molin.wiki)

---

## Screenshots / 截图

> 👉 访问 [molin.wiki](https://molin.wiki) 查看在线演示

---

## Tech Stack / 技术栈

| Layer | Technology |
|-------|-----------|
| **Frontend** | Vue 3 + Vite + Element Plus + OpenSeadragon |
| **Backend** | FastAPI + SQLAlchemy (SQLite) |
| **Async Tasks** | Celery + Redis (composition analysis, batch processing) |
| **Vector Search** | Qdrant (semantic search, composition case retrieval) |
| **AI / LLM** | SiliconFlow API, Qwen (OpenAI-compatible) |
| **Image Viewing** | OpenSeadragon (deep zoom / DZI for high-res scrolls) |
| **Deployment** | Docker (nginx:alpine + Python) on Ubuntu, SCP-based deploy |

---

## Features / 功能模块

### 艺术家百科 / Artist Encyclopedia
历代书画名家的生平、作品、印章、题跋、游历与艺术风格档案，支持多维度浏览与检索。
Life stories, artworks, seals, colophons, travel maps, and stylistic analysis of historical Chinese painting & calligraphy masters.

### 书法识别 / Calligraphy Recognition
上传单字图片，AI 智能匹配碑帖字形来源，返回相似度排名与候选列表。
Upload a character image — AI matches it against rubbing database sources with similarity ranking.

### 题跋空间分析 / Colophon (Tiba) Analysis
AI 自动识别画作中的题跋、绘画、留白区域，生成可视化空间分析图与统计数据。
AI segments colophons, paintings, and empty space in artworks; generates visual spatial analysis.

### 潘天寿构图讲评 / Pan Tianshou Composition Critique
基于潘天寿教学理论，异步分析国画构图特征，生成讲评报告与 PDF（含热力图、起承转合分析）。
Asynchronous composition analysis based on Pan Tianshou's theory — generates critique reports with heatmaps and PDF export.

### 知识语义搜索 / Knowledge Semantic Search
基于 Qdrant 向量检索，支持对题跋、印章、绘画理论进行自然语言搜索，并配备 AI 小墨聊天助手。
Vector-based semantic search over colophons, seals, and painting theory — with AI chat assistant "小墨".

### 情感分析引擎 / Emotion Engine
多维度情感/意境分析，为画作生成情感卡片与可视化雷达图。
Multi-dimensional sentiment & mood analysis — generates emotion cards and radar charts for artworks.

### 印鉴管理 / Seal Management
管理艺术家印鉴库，支持多版本合并、缩略图展示与检索。
Artist seal library with version merging, thumbnails, and search.

### 地图模式 / Map Mode
以地理信息维度呈现艺术家的游历轨迹与创作分布。
Geographic visualization of artists' travel routes and creative distribution.

### 用户与权限 / User & Permissions
5 级 RBAC：`super_admin` / `admin` / `editor` / `reader` / `guest`，JWT 登录，操作审计。
5-tier RBAC: super_admin / admin / editor / reader / guest, JWT auth, audit logging.

---

## Project Structure / 目录结构

```
molin-wiki/
├── backend/
│   ├── app/
│   │   ├── api/              # Routes (artists, artworks, tiba, recognition, knowledge, composition...)
│   │   ├── core/             # Config, database, Celery
│   │   ├── models/           # SQLAlchemy models
│   │   ├── modules/          # Feature modules (composition, etc.)
│   │   └── services/         # Business services
│   └── data/                 # SQLite, uploads, DZI tiles (gitignored)
├── frontend/
│   └── src/
│       ├── views/            # Page components
│       └── modules/          # Feature modules
├── deploy.sh                 # Deployment script
├── deploy/                   # Nginx config, migration scripts
├── start_all.sh              # One-command local startup (Linux/macOS)
└── start_all.ps1             # One-command local startup (Windows)
```

---

## Local Development / 本地开发

### Prerequisites / 前置要求
- Python 3.10+
- Node.js 18+
- Redis (optional, only for composition analysis)

### One-Command Start / 一键启动

**Windows:**
```powershell
.\start_all.ps1
```

**Linux / macOS:**
```bash
chmod +x start_all.sh && ./start_all.sh
```

### Manual Start / 手动启动

```bash
# Backend
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8001

# Frontend (in another terminal)
cd frontend
npm install
npm run dev -- --host 0.0.0.0 --port 8080
```

| Service | URL |
|---------|-----|
| FastAPI Backend | `http://localhost:8001` |
| API Docs (Swagger) | `http://localhost:8001/docs` |
| Frontend | `http://localhost:8080` |
| Redis | `localhost:6379` |

### Environment Variables / 环境变量

See `backend/.env.example`. Key configs:

- `REDIS_URL` — Redis for Celery broker/backend
- `QDRANT_URL` / `QDRANT_API_KEY` — Vector search
- `SILICONFLOW_API_KEY` — AI for colophon/recognition analysis
- `QWEN_API_KEY` / `QWEN_BASE_URL` — LLM for composition critique

---

## Deployment / 部署

```bash
bash deploy.sh
```

Auto-detects changes: frontend build + SCP, backend source hot-mounted (Docker volume, no rebuild needed for code changes).

Production server: Ubuntu + Docker (nginx:alpine + Python).

---

## License

MIT

---

## Contact / 联系方式

- Website: [molin.wiki](https://molin.wiki)
- Issues: [GitHub Issues](https://github.com/zaxchou/molin-wiki/issues)
