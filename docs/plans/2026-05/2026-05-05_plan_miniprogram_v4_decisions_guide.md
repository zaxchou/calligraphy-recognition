# 微信小程序转化方案 · V4 技术决议 + 注册指南

> 更新：2026-05-01 — AppID 已获取 `wxe82e9be51ac260e7`，已填入 project.config.json

**前置参考：**
- [v1](file:///z:/BaiduSync/BaiduSyncdisk/calligraphy-recognition/reports/plan_miniprogram_v1_research.md) — 全量调研
- [v2](file:///z:/BaiduSync/BaiduSyncdisk/calligraphy-recognition/reports/plan_miniprogram_v2_twomods.md) — 两模块规划 + 6项策略决议
- [v3](file:///z:/BaiduSync/BaiduSyncdisk/calligraphy-recognition/reports/plan_miniprogram_v3_pantianshou_tech.md) — 潘天寿构图技术选型（讨论稿）

---

## 一、全部已决议汇总

| # | 决策项 | 决议 | 来源 |
|---|--------|------|------|
| 1 | 小程序角色 | 纯前端消费端，管理全部在网页端 | V2 |
| 2 | 后端改动 | 极少，所有 API 已存在 | V2 |
| 3 | 进度反馈 | **纯轮询** GET /task/{id}，1.5-2s 间隔 | V3 |
| 4 | 李鱓题跋范围 | **精选展示**（后续再规划） | V3 |
| 5 | 架构 | **一个小程序**（原生开发 + 分包隔离两模块） | V3 |
| 6 | 开发顺序 | **先做潘天寿构图** | V3 |
| 7 | 用户体系 | **免登录** | V3 |
| 8 | 上传来源 | **本地相册 + 拍照** | V3 |
| 9 | 开发框架 | **原生小程序** | V4 |
| 10 | 雷达图 | **echarts-for-weixin** | V4 |
| 11 | Markdown | **mp-html**（轻量富文本组件） | V4 |
| 12 | 裁剪功能 | **加**，选图后裁剪再上传 | V4 |
| 13 | SVG 覆层 | **后端保证生成 PNG**，小程序只 `<image>` 显示 | V4 |
| 14 | Canvas 区域标注 | **后端渲染 PNG** | V4 |
| 15 | 轮询字段 | ✅ 后端接口已返回全部所需字段 | V4 |

---

## 二、后端调研结论与建议

### 2.1 轮询接口 `GET /task/{id}` — ✅ 完美

**返回字段**（[progress.py:L46-L59](file:///z:/BaiduSync/BaiduSyncdisk/calligraphy-recognition/backend/app/modules/pantianshou_composition/progress.py#L46-L59)）：

| 字段 | 类型 | 用在哪 |
|------|------|--------|
| `task_id` | str | 任务标识 |
| `status` | str | `"pending"` / `"started"` / `"processing"` / `"done"` / `"failed"` |
| `progress` | int | 进度 0-100，轮询进度条 |
| `stage` | str | 阶段代码（queued/preprocess/detect/.../done/failed） |
| `stage_text` | str | 阶段中文文本，如"正在归一化与提取元数据" |
| `message` | str | 当前状态消息 |
| `eta_seconds` | int\|null | 预计剩余秒数 |
| `eta_confidence` | float\|null | ETA 置信度 |
| `queue_eta_seconds` | int\|null | 排队预计秒数 |
| `error_code` | str\|null | 失败时错误代码 |
| `error_message` | str\|null | 失败时错误详情 |

> **建议：纯轮询直接用此接口，1.5-2 秒间隔。后端零改动。**

### 2.2 `arrow_overlay_url` 生成逻辑 — ⚠️ 需要小改后端

当前逻辑（[stages.py:L398-L477](file:///z:/BaiduSync/BaiduSyncdisk/calligraphy-recognition/backend/app/modules/pantianshou_composition/stages.py#L398-L477)）：

- 起承转合覆层图在 `arrow_analysis` 阶段由 `draw_qczh_from_llm()` 生成
- 通过 GLM 视觉模型（优先）或 LLM 文本正则解析（降级）获取 qi/cheng/zhuan/he 坐标
- 如果两套方案都未获取到坐标 → `arrow_overlay_url = None`
- 如果绘图过程中抛异常 → `arrow_overlay_url = None`

**结论**：`arrow_overlay_url` 可能为 `None` 是正常的业务状态（部分图片确实无法分析起承转合），不是 bug。

> **建议：小程序端处理 `null` 的情况——如果 `arrow_overlay_url` 为 null，结果页不显示覆层图区域，只显示原图 + 雷达图 + LLM 分析文。后端不需要改。**

### 2.3 后端部署现状 — ⚠️ 需要了解

小程序强制要求后端 HTTPS。需要确认：
- 当前后端服务跑在哪台服务器上？
- 有没有域名 + SSL 证书？
- 能不能对外暴露 HTTPS 端口？

> 这个是开发前必须解决的，但可以先在微信开发者工具里用"不校验合法域名"调试。

---

## 三、原生小程序技术栈确认

| 层 | 技术 | 说明 |
|---|------|------|
| **框架** | 原生小程序（WXML + WXSS + JS/TS） | 不用 uni-app |
| **图表** | echarts-for-weixin | 官方维护，Canvas 2D 渲染 |
| **Markdown** | mp-html | ~100KB，支持 Markdown 插件 |
| **HTTP** | wx.request 封装 | 替代 Axios |
| **图片上传** | wx.chooseImage + wx.uploadFile | 支持相册/拍照 |
| **裁剪** | wx.cropImage（需插件）或 image-cropper 组件 | 选图后裁剪 |
| **分包** | 原生分包机制 | 主包 + 潘天寿分包 + 李鱓分包 |

---

## 四、潘天寿构图：单页面状态机

```
┌──────┐  wx.chooseImage   ┌─────────┐  wx.cropImage    ┌─────────┐
│ IDLE │ ────────────────→ │ PREVIEW │ ──────────────→ │ CROPPED │
│ 空状态 │                   │ 图片预览  │                  │ 裁剪完成  │
└──────┘                   └────┬────┘                  └────┬────┘
                                │  wx.uploadFile              │
                                ▼                             │
                          ┌──────────┐                        │
                          │UPLOADING │ ←──────────────────────│
                          │ 上传中    │                        │
                          └────┬─────┘                        │
                               │ 上传成功                      │
                               ▼                              │
                          ┌──────────┐                        │
                   ┌─────│ POLLING  │ setInterval 1.5s       │
                   │     │ 进度轮询  │ GET /task/{id}          │
                   │     └────┬─────┘                        │
                   │          │ status=done                   │
                   │          ▼                              │
                   │     ┌──────────┐                        │
                   │     │  RESULT  │ GET /report/{id}       │
                   │     │ 结果展示  │                        │
                   │     └──────────┘                        │
                   │          ▲                              │
                   │     status=failed                        │
                   │          │                              │
                   │          ▼                              │
                   │     ┌──────────┐                        │
                   └────│  ERROR   │ 显示错误信息             │
                         └──────────┘                        │
```

### 4.1 结果页展示元素

| 元素 | 实现 | 备注 |
|------|------|------|
| 总评分 | `/100` 大字 + 圆形进度环 (CSS) | 数据来自 `report.summary.total_score` |
| LLM 分析文 | mp-html 渲染 Markdown | 来自 `report.llm.text` |
| 原图 | `<image>` 可放大 | `report.assets.thumb_url` |
| 起承转合覆层 | `<image>` 可放大 | `report.assets.arrow_overlay_url`，可能 null |
| 七维雷达图 | echarts-for-weixin | `report.dimensions` + `report.checks` |

### 4.2 调用的 API

| API | 方式 | 说明 |
|-----|------|------|
| `POST /api/v1/composition/upload` | `wx.uploadFile` | 上传图片，返回 `task_id` |
| `GET /api/v1/composition/task/{id}` | `wx.request` | 轮询进度 |
| `GET /api/v1/composition/report/{id}` | `wx.request` | 获取完整报告 |

---

## 五、微信小程序注册流程指南

> 来源：微信公众平台官方 + 掘金/CSDN 2025 实操教程

### 5.1 注册步骤

| 步骤 | 操作 | 需要准备 |
|------|------|---------|
| **1. 访问平台** | 打开 [mp.weixin.qq.com](https://mp.weixin.qq.com/) | — |
| **2. 选择类型** | 账号分类选「**小程序**」→ 点「前往注册」 | — |
| **3. 填写信息** | 邮箱 + 密码 + 验证码 | **未被占用的邮箱**（未注册过微信公众平台/开放平台，未绑定个人微信）|
| **4. 邮箱激活** | 去邮箱点击激活链接 | — |
| **5. 信息登记** | 选「**个人**」主体 → 填身份证姓名/号码/手机号 | 身份证、手机 |
| **6. 微信扫码** | 管理员微信扫码确认身份 | 扫码微信号将成为永久管理员 |
| **7. 完成** | 进入小程序后台 | — |

### 5.2 完善信息（上架前必须）

| 项目 | 说明 |
|------|------|
| **小程序名称** | 4-30 字符，需想好（改名字有次数限制） |
| **小程序头像** | 144px×144px，可为后续准备 |
| **小程序介绍** | 不超过 120 字符 |
| **服务类目** | 选「教育服务 > 在线教育」或「工具 > 信息查询」等 |

### 5.3 获取 AppID（开发必须）

**路径**：后台左侧菜单 →「开发管理」→「开发设置」→「开发者 ID」

- **AppID**：明文展示，直接复制
- **AppSecret**：点击生成，微信扫码后出现，**仅展示一次，立即保存**

> ⚠️ AppSecret 后续忘记只能重置，无法再次查看。

### 5.4 微信开发者工具

下载地址：[developers.weixin.qq.com/miniprogram/dev/devtools/download.html](https://developers.weixin.qq.com/miniprogram/dev/devtools/download.html)

新建项目时填入 AppID，勾选不使用云服务。

### 5.5 调试期注意事项

| 阶段 | 说明 |
|------|------|
| **开发阶段** | 无需备案，无需 HTTPS。在开发者工具中勾选「不校验合法域名...」即可调试 |
| **真机调试** | 同样可跳过 HTTPS 校验，用手机扫码预览 |
| **提交审核** | 需要备案 + HTTPS + 类目完善 |

---

## 六、当前阶段执行计划

### Phase 0：开发环境准备（等 AppID 后）

```
□ 注册小程序账号 → 获取 AppID
□ 安装微信开发者工具
□ 原生小程序项目初始化
□ 分包结构搭建
□ wx.request 封装（API 层）
□ echarts-for-weixin 引入验证
□ mp-html 引入验证
```

### Phase 1：潘天寿构图（2-3 周）

```
□ 图片选择 + 预览 (wx.chooseImage)
□ 图片裁剪 (wx.cropImage / image-cropper)
□ 上传文件 (wx.uploadFile)
□ 轮询进度组件 (setInterval + GET /task/{id})
□ 结果页面布局
   ├── 总评分圆环
   ├── mp-html Markdown 渲染
   ├── 原图展示
   ├── 起承转合覆层图展示 (null 时隐藏)
   └── echarts-for-weixin 雷达图
□ 错误处理 + 超时
□ 样式打磨
```

---

## 七、待下一轮讨论

| # | 问题 |
|---|------|
| H | **小程序名称**有什么想法？ |
| I | **服务类目**选什么？教育工具类还是其他？ |
| J | 李鱓题跋「精选」——具体保留哪些展示内容？（后续可专门规划） |
| K | 当前后端部署在哪里？有域名 + HTTPS 吗？还是需要一个部署方案？ |
| L | 要不要我先准备一个**原生小程序的最小 demo**（不含业务逻辑，纯粹验证 echarts-for-weixin + mp-html + wx.uploadFile 技术栈能跑通）？这个 demo 可以跑通后直接作为潘天寿构图的基础架子 |