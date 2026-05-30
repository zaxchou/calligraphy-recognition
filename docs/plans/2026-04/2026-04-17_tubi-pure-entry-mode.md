---
name: tubi-pure-entry-mode
overview: 在题跋分析上传流程中增加「纯录入」模式：拖入图片后，点确认时弹出选项「AI 分析（默认）」或「仅录入（后续手动标注）」。纯录入不入队 AI，缩略图和文件名解析（标题/作者/时间）正常进行。
todos:
  - id: backend-mode-param
    content: 后端 tubi.py：upload_image + upload_multiple 加 mode=Form("analyze") 参数，manual 时跳过入队逻辑
    status: completed
  - id: frontend-api-param
    content: 前端 api/index.js：tubiApi.uploadImage 透传 mode 参数
    status: completed
    dependencies:
      - backend-mode-param
  - id: frontend-dialog
    content: 前端 TubiAnalysis.vue：上传成功后弹窗让用户选"AI分析"或"仅录入"
    status: completed
    dependencies:
      - frontend-api-param
---

## 用户需求

在题跋分析上传流程中增加"纯录入"模式：

- 拖入图片后，点**确认**时弹出让用户选择
- **AI 分析**（默认行为）：上传后自动入队 AI 分析题跋区域
- **仅录入**：上传后不入队 AI，只生成缩略图和元数据（标题/作者/时间）入库，后续在标注工具手工完成区域标注
- 文件名自动解析（标题/作者/时间）由后端 `_parse_calligraphy_filename` 实现，无需改动

## 核心功能

- 上传确认时弹出选项对话框
- "仅录入"模式：快速入库，无 AI 调用，速度快
- "AI 分析"模式：保持现有行为不变
- 两种模式都正常生成缩略图

## 技术方案

### 改动概述

纯录入模式复用在上传 API 的文件保存 + 缩略图生成逻辑，只在"是否入队 AI"这一步加分支。后端 `_parse_calligraphy_filename` 和缩略图生成代码已完整实现，无需改动。

### 后端改动

**文件**: `backend/app/api/tubi.py`

`POST /tubi/upload`（第459行）和 `POST /tubi/upload-multiple`（第600行）各加一个 `mode` Form 参数：

- `mode="analyze"`（默认）：status=`queued`，调用 `auto_analyze` 入队 AI
- `mode="manual"`：status=`uploaded`，**不入队**，缩略图正常生成

API 签名变化示例：

```python
async def upload_image(
    ...
    mode: str = Form("analyze"),  # [NEW] "analyze" | "manual"
    db: Session = Depends(get_db)
):
    ...
    if mode == "analyze":
        # 入队逻辑（现有 auto_analyze 逻辑）
        ...
    else:
        db_analysis.status = "uploaded"
        db.commit()
        return {"success": True, "data": {...}}
```

### 前端 API 改动

**文件**: `frontend/src/api/index.js`

`tubiApi.uploadImage(file, {title, mode})` 透传 `mode` 参数（默认 `"analyze"`）。

### 前端上传弹窗改动

**文件**: `frontend/src/views/TubiAnalysis.vue`

在 `confirmUpload` 函数（或对应确认按钮点击处理）中，上传成功后弹出一个选择对话框：

- 默认选项：**AI 分析**（调用 `batchAutoAnalyze`）
- 第二选项：**仅录入**（不调用 `batchAutoAnalyze`，直接完成）

使用 Element Plus `ElMessageBox.confirm` 或自定义弹窗组件实现。

对话框弹出时机：文件上传成功后、调用 `batchAutoAnalyze` 之前。

### 数据流对比

| 步骤 | AI 分析模式 | 纯录入模式 |
| --- | --- | --- |
| 保存原图 | ✅ | ✅ |
| 生成缩略图 | ✅ | ✅ |
| 解析文件名填入元数据 | ✅ | ✅ |
| 入库 status | queued | uploaded |
| 入队 AI 分析 | ✅ | ❌ |
| 手工标注入口 | - | InscriptionAnnotator.vue |


### 数据库

无需改动，`status="uploaded"` 已在 `TubiAnalysis` 表中存在。