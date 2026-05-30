# ArtistWorks 改进 + 画作/书法分类

## 目标
1. `/artist/:name/works` 的图库样式完全照搬 TubiGallery 的尺寸和交互
2. 数据库增加 `work_type` 字段区分画作/书法，全部现有作品默认为"画作"

## 改动概述

### 后端

#### 1. 数据库迁移 — `tubi_analyses` 加 `work_type` 列
- **文件**: `backend/app/core/database.py`
- 在 ensure_database 中添加迁移：
  - `ALTER TABLE tubi_analyses ADD COLUMN work_type TEXT DEFAULT '画作'`
  - 所有已有记录默认 `'画作'`
- `get_db_connection()` 已开启 `PRAGMA foreign_keys=ON`（上次已修复）

#### 2. API 返回字段加 `work_type`
- **文件**: `backend/app/api/tubi.py`
- `GET /tubi/results` 的返回字段中添加 `work_type`（从数据库直接读出）
- 搜索/分页等列表接口也包含此字段
- `GET /tubi/{image_id}` 详情接口同样返回

#### 3. 上传/编辑 API 支持 `work_type`
- **文件**: `backend/app/api/tubi.py`
- 上传接口（`POST /tubi/upload`）接受可选参数 `work_type`，默认 `'画作'`
- 编辑接口（`PUT /tubi/{image_id}`）支持更新 `work_type`

#### 4. 按 work_type 筛选
- `GET /tubi/results` 增加可选查询参数 `work_type`
- ArtistWorks 调用时可按 `work_type` 过滤

### 前端

#### 1. ArtistWorks.vue — 重写网格部分
- **文件**: `frontend/src/views/artist/ArtistWorks.vue`
- 完全照搬 `TubiGallery.vue` 的网格样式：
  - `grid-template-columns: repeat(auto-fill, minmax(130px, 1fr)); gap: 10px; padding: 12px;`
  - `aspect-ratio: 3/4`，图片 `object-fit: cover`
  - 卡片增加：题跋%/绘画%标签（右下角）、状态角标（左上角）、hover 编辑/删除按钮
  - 底部显示：标题、作者·年龄·年代、标签列表
- 移除列表模式（`viewMode` 切换），只保留网格模式（或者保持网格+列表双模式但网格风格统一）
- **决定**: 保留列表模式开关，但仅将**网格模式**重写为 TubiGallery 风格

#### 2. ArtistWorks.vue — 顶部加分类切换标签
- 网格上方加 画作/书法/全部 三个 tab 按钮
- 点击切换时带上 `work_type` 参数重新请求 API

#### 3. 上传对话框 — work_type 选择
- **文件**: 需要确认上传对话框在哪（可能是 `TubiAnalysis.vue` 或独立的 `UploadDialog`）
- 在作品上传/编辑表单中加入 `work_type` 下拉选择器，选项：画作/书法

#### 4. 作品详情页展示 work_type
- **文件**: `frontend/src/views/TubiDetail.vue`
- 在作品信息区域展示作品类型（画作/书法）

## 执行步骤

1. 数据库迁移：加 `work_type` 列，默认 `'画作'`
2. API 后端：列表/详情/上传/编辑接口支持 `work_type`
3. 前端 ArtistWorks.vue：网格照搬 TubiGallery + 分类 tab
4. 前端上传/编辑对话框：加 work_type 选择器
5. 构建验证

## 验证

- [ ] 迁移后所有旧作品 `work_type='画作'`
- [ ] API `/tubi/results?work_type=书法` 只返回书法作品
- [ ] ArtistWorks 网格样式与 TubiGallery 一致（130px 格、百分比标签、hover 操作）
- [ ] 上传新作品时可选择画作/书法
- [ ] 构建无报错
