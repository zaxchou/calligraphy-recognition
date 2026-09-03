# Plan: 合并作品上传到作品库

## 目标

将项目里两处上传入口（管理后台独立上传 + 作品库上传）合并为**唯一入口**：只有进入作品库后才能上传，所有上传均绑定库 ID。去掉管理后台的"作品上传"Tab，用成熟的 TubiUploadInline 批量上传组件替换作品库现有简陋的单张 el-upload。

### 用户期望的 workflow

```
创建作品库 → 进入作品库 → 批量上传作品 → 选择 AI 分析模式 → 入库 + 分析
```

## 当前状态

| 入口 | 页面 / 组件 | 上传模式 | AI 分析 |
|------|-----------|---------|--------|
| `/admin` Tab "作品上传" | ContentVerify.vue → TubiUploadInline.vue | 批量（并发×3，最多50张） | 上传后弹出模式选择（直接入库 / AI文本分析 / AI标注图分析）+ 5秒轮询 |
| `/libraries/:id` | LibraryDetail.vue → 内置 el-upload | 单张（仅1张） | 用户手动点"AI分析"按钮 |

### 后台 API

- `tubiApi.uploadImage(file, fields)` → `POST /tubi/upload` — TubiUploadInline 当前调用的单文件上传
- `artworkApi.upload(libraryId, file, fields)` → `POST /libraries/:id/artworks` — 作品库当前调用的上传

## 方案设计

### 1. TubiUploadInline 通用化改造

**现状问题：** TubiUploadInline 硬编码调用 `tubiApi.uploadImage()`，无法区分是否来自作品库。

**改造方案：**
- TubiUploadInline 新增 prop: `libraryId?: number`
- 当 `libraryId` 存在时：`uploadImage` 的 FormData 自动附加 `library_id` 字段
- AI 分析触发逻辑不变（模式选择弹窗 + 轮询）
- uploadStore 状态管理保持不变

**改动文件：**
- [TubiUploadInline.vue](file:///z:/BaiduSync/BaiduSyncdisk/calligraphy-recognition/frontend/src/components/tubi/TubiUploadInline.vue) — 新增 `libraryId` prop，startBatchUpload 中附加 library_id
- [uploadStore.js](file:///z:/BaiduSync/BaiduSyncdisk/calligraphy-recognition/frontend/src/stores/uploadStore.js) — 新增 `libraryId` 字段，用于重启时恢复上下文

### 2. LibraryDetail.vue 接入 TubiUploadInline

**替换前（当前）：**
```
el-button "上传作品" → el-dialog → el-upload (单张) → POST /libraries/:id/artworks
```

**替换后：**
```
el-button "上传作品" → el-dialog → TubiUploadInline (批量) → POST /tubi/upload (带 library_id)
```

具体改动：
- 删除现有的 uploadForm、uploadFile、handleUpload 等局部状态
- 删除 el-upload 模板代码
- 在 el-dialog 中嵌入 `<TubiUploadInline :library-id="libraryId" @uploaded="onUploaded" />`
- 上传完成后刷新作品列表

### 3. ContentVerify.vue 移除"作品上传"Tab

- 删除 `<el-tab-pane label="作品上传" name="upload">` 及其内容
- 删除 `TubiUploadInline` 的 import
- 删除 `onUploaded` / `fetchRecords` 相关代码（如果仅此 Tab 使用）

### 4. 表单字段

批量上传时每个文件自动继承：标题（从文件名解析）、画家（从库绑定）、年代（从文件名解析）。

作品库上传对话框不需要额外表单——TubiUploadInline 自带拖拽区 + 进度 + 模式选择，库的基本信息（artist_name）已自动绑定。

---

## 实施步骤

| # | 步骤 | 文件 | 说明 |
|---|------|------|------|
| 1 | TubiUploadInline 加 libraryId prop | TubiUploadInline.vue | 新增 prop，startBatchUpload 中附加 library_id 到 FormData |
| 2 | uploadStore 记录 libraryId | uploadStore.js | 新增 libraryId 字段，localStorage 序列化/反序列化 |
| 3 | LibraryDetail 替换上传为 TubiUploadInline | LibraryDetail.vue | 删除 el-upload 相关代码，嵌入 Tub