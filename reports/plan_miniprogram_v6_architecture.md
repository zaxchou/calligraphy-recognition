# 微信小程序 · V6 架构重构方案

> 日期：2026-05-04 | 阶段：纯规划讨论 | `/plan` 模式

## 一、当前架构诊断

### 1.1 现状

```
用户点击"开始分析"
  │
  ├─→ POST /composition/upload  (传图片)
  │     └─ 轮询 GET /task/{id} → 2s 间隔
  │        └─ GET /report/{id}  → 拿到评分+雷达+LLM报告
  │
  └─→ POST /composition/qichengzhuanhe-analyze  (传同一张图片)
        └─ 同步等待 50-70s
           └─ 拿到 preview_image + llm_analysis

  _tryMerge()  ← 两路都完成才渲染
```

### 1.2 痛点

| 问题 | 表现 | 根因 |
|------|------|------|
| 🔴 卡死风险 | 页面一直转圈 | `_tryMerge` 等两路全完成，任一路失败/超时都导致另一端结果也看不到 |
| 🔴 合并逻辑脆弱 | 反复修 `_reportDone`/`_qczhDone` 标记 | 客户端手工管理两路异步状态机 |
| 🟡 用户等待时间长 | 50-70s+ 才看到任何内容 | 两条路中最慢的决定体验 |
| 🟡 无渐进渲染 | 全或无 | 不能先显评分后补图片 |
| 🟡 代码膨胀 | `startAnalyze` 已经 60+ 行，`_tryMerge` 40+ 行 | 两条管线的状态管理混在一个文件 |

---

## 二、四种替代方案

### 方案 A：渐进式渲染（推荐 ⭐⭐⭐）

```
上传图片后，两条请求照常发出。
  评分先回来 → 立即展示评分+雷达+报告
  qczh 后回来 → 再 setData 追加曲线图卡片+起承转合章节
```

| 维度 | 评价 |
|------|------|
| **改动量** | 极小，只改 `analyze.js` |
| **后端改动** | 零 |
| **用户体验** | 评分 ~30s 就能看到，曲线 ~50s 后自己补上 |
| **复杂度** | 极低 —— 删掉 `_tryMerge`，评分完成直接 `_renderResult(report)`；qczh 完成调 `_appendQczh(res)` |
| **失败容错** | 天然解耦：评分失败不影响曲线展示，曲线失败不影响评分展示 |

**流程：**
```
startAnalyze()
  │
  ├─→ api.upload() → 轮询 → report 就绪
  │       └─→ _renderResult(report)   ← 立即展示评分+雷达+报告
  │             同时保留 _taskId 用于后续
  │
  └─→ api.uploadQczh() → 拿到结果
          └─→ _appendQczh(res)          ← 追加曲线图卡片
                如果已展示 report → 把 qczh 文字也追加到 rich-text
```

### 方案 B：后端统一端点（最优雅但最重 ⭐⭐）

```
POST /composition/analyze-all  (一张图片)
  Celery 任务：
    ├── Step 1: 构图评分 (compose)
    ├── Step 2: 起承转合 (qczh)
    ├── Step 3: 合并报告
    └── 全程通过 WebSocket 推送进度
```

| 维度 | 评价 |
|------|------|
| **改动量** | 大：后端新 endpoint + Celery 重编排 + WebSocket |
| **用户体验** | 最优：单一进度条，实时推送 |
| **维护** | 两条管线在后端解耦，前端逻辑极简 |
| **成本** | 2-3 天后端开发 |

**适用场景**：后端已经用 Celery + Redis，架构基础好，改造成本可控。

### 方案 C：qczh 也改成异步任务 ⭐⭐

```
POST /composition/upload  → task_id
  后端 Celery 内部分两步：
    Step 1: 构图评分 → 存 report
    Step 2: 起承转合 → 存到 report.assets.qczh_image + report.qczh_analysis

前端：一次上传 → 一个 task_id → 一次轮询 → 一个 report
```

| 维度 | 评价 |
|------|------|
| **前端改动** | 几乎回到原始版（一个上传+轮询），加一个 `qczhImage` 字段展示 |
| **后端改动** | 中等：Celery 任务里串行调 qczh，存到 report 里 |
| **体验** | 等待时间不变（就是两个加起来），但逻辑干净 |

### 方案 D：保持双请求但用 Promise.all ⭐

不上传两次图片，而是：

```
POST /composition/upload → task_id
  先存图片到后端，拿到 task_id

然后并行：
  Promise.all([
    pollAndGetReport(task_id),    ← 轮询 /task/{id} 直到 done
    waitForQczh(task_id)          ← 新端点 POST /task/{id}/qczh（后端已有图片）
  ])
```

| 维度 | 评价 |
|------|------|
| **避免重复上传** | 只传一次图，省带宽 |
| **需要新端点** | 后端需要加一个"对已有 task 跑 qczh"的接口 |

---

## 三、推荐：方案 A（渐进式渲染）

### 3.1 理由

1. **改动最小** —— 只改 `analyze.js`，不碰后端，不碰 WXML
2. **天然解耦** —— 评分和曲线各自独立，互不阻塞
3. **体验立刻提升** —— 用户 30s 就能看到评分，不用干等
4. **失败容错** —— 任何一边挂了不影响另一边
5. **后续可升级** —— 如果未来后端统一，前端只需删掉第二个请求

### 3.2 改动清单

| 文件 | 改动 |
|------|------|
| `analyze.js` | 删掉 `_tryMerge` / `_reportDone` / `_qczhDone` / `_pendingReport` / `_pendingQczh` / `_mergeTimeout` |
| `analyze.js` | `_loadReport` 直接调 `_renderResult(report)`（恢复到 qczh 加入之前的原始行为） |
| `analyze.js` | 新增 `_appendQczh(res)` — 两件事：① setData({qczhImage, hasQczh:true})  ② 拿到当前 llmHtml，追加 qczh 章节后重新 setData |
| `analyze.js` | `startAnalyze` 上传成功后直接发起两个独立请求，各自完成各自渲染 |
| `analyze.wxml` | 不用改（`hasQczh` 控制曲线卡片显隐，现有的条件渲染已经支持） |
| `analyze.wxss` | 不用改 |

### 3.3 `_appendQczh` 伪代码

```js
_appendQczh: function (res) {
  if (this.data.state !== 'done' && this.data.state !== 'analyzing') return

  var img = res.preview_image || ''
  var text = res.llm_analysis || res.qwen_analysis || ''

  // 追加到已有报告
  var currentLl = this.data.llmHtml || ''
  if (text && currentLl) {
    // 重新生成完整 HTML（加分割线+起承转合章节）
    currentLl = md.blocksToHtml(this._fullLlText + '\n\n---\n\n## 起承转合分析\n\n' + text)
  } else if (text && !currentLl) {
    currentLl = md.blocksToHtml(text)
  }

  this.setData({
    qczhImage: img,
    hasQczh: !!img,
    pathType: res.path_type || '',
    llmHtml: currentLl
  })
}
```

### 3.4 进度条简化

去掉假进度条（假进度条本身也是复杂度的来源）。改为真实的阶段提示：

```
"正在上传图片..."
"图片已上传，正在创建分析任务..."
[轮询阶段 — 显示后端返回的 stage_text]
[收到 report] → 立即渲染评分页
[qczh 完成] → 追加曲线图
```

---

### 3.5 UX：占位卡片 + 完成 Toast（用户确认 ✅）

评分报告展示后，如果 qczh 还在跑，在结果页显示一张**浅色占位卡片**：

```
┌──────────────────────────┐
│  起承转合 · 曲线分析       │
│                          │
│  ⟳  正在分析中，请稍候...  │
│  预计还需 ~40 秒          │
│                          │
│  您可先阅读上方专家分析     │
└──────────────────────────┘
```

qczh 完成后：占位卡替换为真实曲线图 + weui toast "起承转合分析完成"。

### 3.6 最终决议

| # | 问题 | 决议 |
|---|------|------|
| A | 方案选择 | **方案 A（渐进渲染）** |
| B | 假进度条 | **去掉**，用真实轮询 `stage_text` |
| C | 渐进渲染体验 | **接受**，评分先出，曲线后出，用占位卡衔接 |
| D | 占位提示 | **加**，用户可边看报告边等曲线
