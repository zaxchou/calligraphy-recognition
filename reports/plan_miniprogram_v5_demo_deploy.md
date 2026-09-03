# 微信小程序转化方案 · V5 Demo 构建 + 部署调研

> 日期：2026-05-01 | 阶段：纯规划讨论 | 不执行

**前置参考：**
- [v1](file:///z:/BaiduSync/BaiduSyncdisk/calligraphy-recognition/reports/plan_miniprogram_v1_research.md) — 全量调研
- [v2](file:///z:/BaiduSync/BaiduSyncdisk/calligraphy-recognition/reports/plan_miniprogram_v2_twomods.md) — 策略决议
- [v3](file:///z:/BaiduSync/BaiduSyncdisk/calligraphy-recognition/reports/plan_miniprogram_v3_pantianshou_tech.md) — 技术选型讨论稿
- [v4](file:///z:/BaiduSync/BaiduSyncdisk/calligraphy-recognition/reports/plan_miniprogram_v4_decisions_guide.md) — 技术决议 + 注册指南

---

## 一、Demo 已搭建完成 ✅

### 1.1 文件清单

```
miniprogram/
├── app.js                              ← 小程序入口
├── app.json                            ← 全局配置（注册 analyze 页面）
├── app.wxss                            ← 全局样式
├── sitemap.json                        ← 站点地图
├── project.config.json                 ← 微信开发者工具配置
├── utils/
│   └── api.js                          ← wx.request/uploadFile 封装
└── pages/
    └── analyze/
        ├── analyze.js                  ← 页面逻辑（状态机）
        ├── analyze.json                ← 页面配置
        ├── analyze.wxml                ← 页面模板
        └── analyze.wxss                ← 页面样式
```

### 1.2 Demo 功能

**范围：** 最简潘天寿构图 — 上传图片 → 轮询进度 → 展示 LLM 文字分析

**不在 demo 中：**
- ❌ 雷达图（等 echarts-for-weixin 验证后加）
- ❌ 起承转合覆层图（后端已支持，前端 `<image>` 一行即可，后续再加）
- ❌ 评分圆环样式（总评分数字已展示）
- ❌ Markdown 渲染（当前用纯文本分段展示，等 mp-html 验证后加）
- ❌ 图片裁剪（等第二步）
- ❌ echarts-for-weixin / mp-html 引入（不阻塞核心流程验证）

### 1.3 状态机

```
idle ─→ preview ─→ analyzing ─→ done
              │           │
              └─ reset ──→ error
```

| 状态 | 说明 |
|------|------|
| `idle` | "选择图片 / 拍照"按钮 |
| `preview` | 预览图 + "开始分析"/"重新选择" |
| `analyzing` | 缩略图 + 进度条 + `stage_text` + ETA |
| `done` | 评分 + LLM 分析文段落 |
| `error` | 错误信息 + 重试按钮 |

### 1.4 API 调用链

```
wx.chooseImage → wx.uploadFile(POST /api/v1/composition/upload, name='file')
  → 拿到 task_id
  → setInterval(2s) GET /api/v1/composition/task/{task_id}
  → status='done' → GET /api/v1/composition/report/{task_id}
  → report.llm.text → 显示
```

### 1.5 调试方式

- **微信开发者工具**：打开 `miniprogram/` 目录，AppID 先用 `touristappid`（测试号）
- **后端地址**：`utils/api.js` 第 1 行 `BASE_URL`，默认 `http://localhost:8001`
- **不校验域名**：`project.config.json` 已设置 `"urlCheck": false`

### 1.6 如何运行

```
1. 启动后端: cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8001
2. 打开微信开发者工具
3. 导入项目 → 选择 miniprogram/ 目录
4. AppID 填 touristappid（或你自己的测试号）
5. 点击"编译"即可预览
```

---

## 二、服务类目建议

### 2.1 微信小程序个人主体可选的类目

微信小程序的个人主体受限较大，不能选需要企业资质的类目（如教育需要办学许可证、文娱需要文化经营许可证等）。

**个人主体可以选的主要类目：**

| 一级类目 | 二级类目 | 是否需要资质 | 我们的匹配度 |
|----------|---------|:-----------:|:-----------:|
| **工具** | 信息查询 | ❌ 不需要 | ⭐⭐⭐ 最安全 |
| **工具** | 图片处理 | ❌ 不需要 | ⭐⭐ |
| **教育** | 教育信息服务 | ❌ 不需要 | ⭐⭐ |
| **文娱** | 其他文娱 | ⚠️ 可能需要 | ⭐（不建议冒险） |

> ⭐ **建议：「工具 > 信息查询」** — 最安全，无资质要求，审核最快。我们的功能本质就是"上传图片获取 AI 分析信息"。

### 2.2 注册/审核时的注意事项

- 小程序名称不要带「教育」「培训」等敏感词（会触发资质审查）
- 服务描述聚焦"中国画构图分析工具"
- 备案需要实名（个人主体就是你的身份证）

---

## 三、腾讯云部署方案

### 3.1 推荐：轻量应用服务器 (Lighthouse)

| 配置 | 价格 | 够用吗 |
|------|------|:---:|
| 2核2G / 40G SSD / 4M 带宽 | ~38-68元/年（新用户） | ✅ 够用 |
| 2核4G / 60G SSD / 5M 带宽 | ~100-150元/年 | ✅ 更稳 |
| 4核8G / 80G SSD / 8M 带宽 | ~300-500元/年 | 🏆 推荐（跑 AI 模型） |

> ⚠️ 当前后端依赖 PyTorch、OpenCV、Qdrant 等重量库，**2核2G 可能不够**。建议至少 2核4G，理想 4核8G。

### 3.2 推荐部署架构

```
                          ┌─────────────────────────┐
  微信小程序                │ 腾讯云轻量服务器 Ubuntu     │
  wx.request ──────────→  │                         │
                          │  Nginx (HTTPS :443)     │
                          │    ↓ proxy_pass         │
                          │  Uvicorn (:8001)        │
                          │    ↓                    │
                          │  FastAPI App            │
                          │    ↓                    │
                          │  SQLite + Redis         │
                          │  (Qdrant 可选)           │
                          └─────────────────────────┘
```

### 3.3 部署步骤概览

```
1. 购买腾讯云轻量服务器 → 选 Ubuntu 22.04
2. SSH 登录，安装基础环境
   ├── apt update && apt install python3.12 nginx certbot python3-certbot-nginx
   ├── git clone 项目代码
   ├── pip install -r requirements.txt
   └── 配置 .env（API keys 等）
3. 配置 Uvicorn systemd 服务
   └── /etc/systemd/system/composition.service
4. 配置 Nginx 反向代理
   └── /etc/nginx/sites-available/composition
5. 配置 HTTPS（Let's Encrypt 免费证书）
   └── certbot --nginx -d your-domain.com
6. 防火墙开放 443 端口
7. 微信小程序后台配置服务器域名
   └── request 合法域名: https://your-domain.com
   └── uploadFile 合法域名: https://your-domain.com
```

### 3.4 Nginx 参考配置

```nginx
server {
    listen 443 ssl;
    server_name your-domain.com;

    ssl_certificate     /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;

    client_max_body_size 50m;

    location / {
        proxy_pass http://127.0.0.1:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### 3.5 Systemd 服务参考

```ini
[Unit]
Description=Composition API
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/home/ubuntu/calligraphy-recognition/backend
Environment=PATH=/home/ubuntu/venv/bin
ExecStart=/home/ubuntu/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8001
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### 3.6 域名 + 备案

小程序要求 HTTPS + 已备案域名。流程：

```
购买域名（腾讯云 DNSPod，~30元/年）
  → 实名认证（1-3天）
  → 工信部备案（腾讯云代提交，7-20天）
  → 腾讯云 SSL 证书（免费，自动续期）
  → 配置 DNS 解析到服务器 IP
```

> ⚠️ 备案是最耗时的步骤（7-20天），建议提前开始。

---

## 四、当前待办与下一步

### 4.1 已完成

| 项目 | 状态 |
|------|:--:|
| ① 全量技术调研 | ✅ v1 |
| ② 两模块策略决议（6项） | ✅ v2 |
| ③ 潘天寿技术选型决议（7项） | ✅ v3/v4 |
| ④ 微信注册流程文档 | ✅ v4 |
| ⑤ 后端轮询接口确认（11字段完美） | ✅ v4 |
| ⑥ arrow_overlay_url 确认（可null，容错即可） | ✅ v4 |
| ⑦ 原生小程序 Demo 搭建 | ✅ v5 |

### 4.2 待办（按优先级）

| # | 事项 | 阻塞因素 | 备注 |
|---|------|---------|------|
| 1 | 注册小程序账号 → 拿 AppID | 需要你的微信扫码 | 参考 v4 注册指南 |
| 2 | 微信开发者工具安装 + Demo 跑通 | 后端需启动 | 本地先调试 |
| 3 | 服务类目决策 | 注册时就要选 | 建议"工具>信息查询" |
| 4 | 小程序名称决策 | 注册时就要填 | 改名字有次数限制 |
| 5 | 域名购买 + 备案 | 上架必须 | 提前启动，耗时最长 |
| 6 | 腾讯云服务器购买 + 部署 | 域名备案后 | 参考本文第三节 |
| 7 | Demo 增强：裁剪 + echarts + mp-html | Demo 跑通后 | 逐步加 |
| 8 | 李鱓题跋「精选」规划 | 潘天寿上线后 | 另开 plan |

---

## 五、待讨论

| # | 问题 |
|---|------|
| M | 小程序名称有想法吗？（4-30字符，改了有次数限制） |
| N | 服务类目用「工具 > 信息查询」可以吗？ |
| O | 后端服务器预算范围？我根据预算推荐腾讯云具体配置 |
| P | 当前后端跑在哪台机器上？有 GPU 吗？如果迁到腾讯云，PyTorch/OpenCV 依赖要重新装 |
| Q | Demo 你看一眼文件结构，有没有想调整的？还是先这样等注册完直接跑？ |