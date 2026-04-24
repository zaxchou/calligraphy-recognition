# 批量上传图片标准流程

## 概述

本文档描述如何使用 `batch_process_tubi.py` 批量处理新上传的图片，完成题跋区域分析、面积统计、标注图生成等步骤。

---

## 第一步：上传图片到服务器

### 1.1 准备图片

将图片放入 `data/uploads/` 目录，建议：
- 使用 **UUID 命名**（如 `a1b2c3d4-e5f6-7890-abcd-ef1234567890.jpg`）
- 或使用原文件名（系统会自动处理）
- 支持格式：`.jpg`, `.jpeg`, `.png`, `.webp`

### 1.2 创建数据库记录

运行 `_import_new_images.py`：

```bash
cd backend
python _import_new_images.py
```

**输入**：图片目录路径（例如 `E:\下载\0413`）
**处理**：
1. 复制图片到 `data/uploads/`，生成缩略图到 `data/thumbnails/`
2. 创建数据库记录（`image_id`, `filepath`, `thumbnail_path`, `filename`, `title`）
3. 自动入队到 Redis 队列 `tubi:queue:pending`

**输出**：
- 图片文件已复制到 `data/uploads/`
- 缩略图已生成到 `data/thumbnails/`
- 数据库 `tubi_analyses` 表新增记录，状态为 `pending`

---

## 第二步：批量分析图片

### 2.1 运行 batch_process_tubi.py

```bash
cd backend
python batch_process_tubi.py
```

**输入**：数据库中所有 `status='pending'` 的记录
**处理**：
1. 读取图片实际尺寸并更新 `image_width` 和 `image_height`（**关键**：避免面积统计使用默认值）
2. 调用 LLM（Qwen VL Plus）分析图片，识别题跋/绘画/留白区域
3. 计算面积百分比（`inscription_percent`, `painting_percent`, `blank_percent`）
4. 生成题跋 mask 并精确计算题跋面积
5. 生成热力图数据（可选，已在 2026-04-14 删除）
6. OCR 识别题跋文本（**注意**：已校对的记录不会覆盖 `inscription_content`）
7. 生成标注图 `data/annotated/annotated_<image_id>.jpg`
8. 更新数据库记录，状态改为 `analyzed`

**关键特性**：
- ✅ **保护已校对文本**：只有 `inscription_verified=0` 的记录才会被 AI 覆盖
- ✅ **精确面积计算**：使用实际图片尺寸，避免 800x600 默认值导致的错误
- ✅ **断点续传**：可随时中断，已处理的记录不会重复处理

**输出**：
- 标注图已生成
- 数据库已更新（区域数据、面积、OCR 内容等）

---

## 第三步：校对题跋文本（前端操作）

### 3.1 打开校对页面

访问 `http://localhost:3000/tubi/verify`

### 3.2 逐张校对

对每张图片：
1. 检查 `inscription_content`（题跋文本）是否正确
2. 检查 `seal_content`（印章内容）是否正确
3. 如有错误，修正后点击"保存并下一条"
4. 系统会自动标记 `inscription_verified=1` 或 `seal_verified=1`

### 3.3 批量保存印章内容

如需批量更新印章内容，可使用 `ContentVerify.vue` 的批量编辑功能。

---

## 第四步：触发内容分析（统计分析）

### 4.1 触发批量分析

```bash
curl -X POST "http://localhost:8001/api/v1/content-analysis/batch?force_reanalyze=true"
```

**输入**：所有 `inscription_verified=1` 的记录
**处理**：
1. 读取 `inscription_content` 文本
2. 调用 LLM 分析主题、情感
3. 更新 `theme_tags` 和 `content_analysis` 字段

**重要**：
- 如果 `force_reanalyze=false`（默认），已分析的记录不会重新分析
- 建议在完成所有校对后，触发一次 `force_reanalyze=true`

---

## 常见问题

### Q1: 图片面积统计为 0

**原因**：数据库中 `image_width` 和 `image_height` 为 0
**解决**：batch_process_tubi.py 会自动读取实际尺寸并更新，但需要确保图片可读

### Q2: 题跋文本被 AI 覆盖

**原因**：之前校对后，worker 重新处理了该记录
**解决**：2026-04-14 已修复，现在只有 `inscription_verified=0` 的记录才会被覆盖

### Q3: 标注图没有红框

**原因**：题跋 mask 生成失败（图片质量问题或尺寸异常）
**解决**：检查 `inscription_mask` 是否正确生成，或手动调整 OCR 结果

### Q4: 批量处理中断

**解决**：可随时重新运行 `batch_process_tubi.py`，已处理的记录不会重复处理

---

## 脚本清单

| 脚本 | 用途 | 运行环境 |
|------|------|----------|
| `_import_new_images.py` | 导入新图片，创建数据库记录，入队 | 后端 |
| `batch_process_tubi.py` | 批量分析图片（LLM + 面积 + 标注图） | 后端 |
| `_check_queue.py` | 检查 Redis 队列状态 | 后端 |

---

## 数据库关键字段说明

| 字段 | 说明 |
|------|------|
| `status` | `pending`=待处理, `analyzing`=处理中, `analyzed`=已完成, `error`=失败 |
| `inscription_verified` | 0=未校对, 1=已校对 |
| `seal_verified` | 0=未校对, 1=已校对 |
| `inscription_percent` | 题跋面积百分比 |
| `painting_percent` | 画面面积百分比 |
| `blank_percent` | 留白面积百分比 |
| `image_width` / `image_height` | 图片实际尺寸（必须准确） |

---

## 注意事项

1. **百度同步盘**：运行大批量处理时，建议关闭百度同步盘，避免文件锁导致写入失败
2. **Redis**：确保 Redis 服务正常运行，否则队列功能不可用
3. **uvicorn**：修改后端代码后需重启 uvicorn 加载新代码
4. **tubi_worker**：如修改 tubi_worker.py，需重启 worker 加载新代码