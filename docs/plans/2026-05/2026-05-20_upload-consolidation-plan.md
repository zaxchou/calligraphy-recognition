# 作品上传流程合并计划 v2

## 摘要

1. 管理后台"作品上传"Tab 移除；TubiUploadInline 移植到作品库详情页替代单幅弹窗
2. 移除上传后的 AI 模式选择，上传完直接入库
3. 管理后台「作者下拉 + 翻译 + 批量重跑」按钮全部移到作品库详情页
4. 每个批量操作都设增量/全量选择，所有操作均针对当前作品库
5. 上传区域上方加文件名格式提示
6. 作品卡片新增 4 个细粒度状态标记（译/析/校/注），一眼看出完成情况
7. 卡片新增「校对」「标注」按钮，直接跳转到指定作品的校对页/标注编辑页

---

## 当前状态

### 两处上传入口

| 位置 | 路径 | 组件 | 特征 |
|:--|:--|:--|:--|
| 管理后台 | `/admin` → "作品上传" Tab | TubiUploadInline | 批量 + ModeSelection + 轮询 |
| 作品库 | `/libraries/:id` → 按钮 | el-dialog + el-upload | 单幅 + 手动表单 |

### 管理后台工具栏（ContentVerify.vue L9-L39）

```
[作者下拉] [翻译 按钮] [批量重跑 按钮]
```

- 翻译 → 弹窗：仅翻译未翻译的 / 重新翻译全部 → SSE 进度
- 批量重跑 → 弹窗：增量重跑 / 全部重跑 → SSE 进度

### 后端文件名解析

`_parse_calligraphy_filename` (tubi.py L52-L92)：按下划线 `_` 分割，格式 `朝代_作者_作品名_年份.jpg`，自动提取 title/artist/year/period。前端不需要参与。

---

## 目标流程

```
用户 → /libraries → 创建/选择作品库 → 库详情页
  ├─ [上传作品] → TubiUploadInline 上传 → 直接入库 → 刷新列表
  ├─ [作者下拉] → 筛选作品库内作品 → 翻译/重跑都针对该作者
  ├─ [翻译] → 增量/全量选择 → SSE 进度弹窗
  ├─ [批量重跑] → 增量/全量选择 → SSE 进度弹窗
  ├─ 卡片状态点: 译(绿/灰) 析(绿/灰) 校(绿/灰) 注(绿/灰)
  ├─ [校对] → /admin?tab=verify&image_id=xxx 定位该作品
  └─ [标注] → 新标签页 /annotate/:id 标注编辑器
```

所有操作永远处于作品库上下文（有明确的 `library_id`），不再有「不知道目录」的问题。

---

## 具体改动

### 1. TubiUploadInline.vue — 纯上传（移除 AI 模式选择）

**文件**: `frontend/src/components/tubi/TubiUploadInline.vue`

**1a. Props 新增**
```js
const props = defineProps({
  libraryId: { type: [Number, String], default: null }
})
```

**1b. API 分支** (`startBatchUpload`)

```js
// 原来
const result = await tubiApi.uploadImage(item.rawFile, {})

// 改为（有 libraryId 时走作品库接口）
let result
if (props.libraryId) {
  result = await artworkApi.upload(props.libraryId, item.rawFile, {})
} else {
  result = await tubiApi.uploadImage(item.rawFile, {})
}
```

**1c. 上传完成直接结束（移除 mode 选择）**

删除 `showModeSelectionDialog` 相关逻辑：
- 上传完不再弹出模式选择弹窗
- 删除 `confirmUploadMode` 函数
- 删除 `startPolling` 轮询逻辑
- 删除 `_pollTimer` 相关代码
- 删除 `pendingUploadedIds` 相关代码
- 步骤指示器删除第 3 步「AI 分析」和第 4 步「完成」

上传完成后直接：
```js
// 原来：上传完 → showModeSelectionDialog = true
// 改为：上传完 → emit refresh → 状态回到 idle
uploadStore.phase = 'idle'
emit('refresh')
ElMessage.success(`已上传 ${completed.length} 件`)
```

**1d. 步骤指示器简化**

原来 4 步：选择图片 / 上传 / AI 分析 / 完成  
改为 2 步：选择图片 / 上传完成

**1e. 简洁化子组件引用**

移除不再需要的：
- `TubiModeSelectionDialog` import
- `UploadPhaseProcessing` 引用
- `UploadPhaseCompleted` 引用

保留：
- `UploadPhaseIdle`
- `UploadPhaseUploading`

**1f. import 新增**
```js
import { artworkApi } from '../../api'
```

---

### 2. LibraryDetail.vue — 替换上传 + 新增工具栏

**文件**: `frontend/src/views/LibraryDetail.vue`

**2a. 模板：上传区域**

删除原 `showUploadDialog` el-dialog 块（L286-L330），替换为：

```vue
<!-- 文件名格式提示 -->
<el-alert v-if="showUploadArea" type="info" :closable="false" show-icon class="filename-tip">
  <template #title>
    推荐文件名格式：<code>清_李鱓_兰竹图_1750.jpg</code>
    按下划线分割：朝代_作者_作品名_年份，系统将自动提取元数据
  </template>
</el-alert>

<!-- 上传区域 -->
<div v-if="showUploadArea" class="inline-upload-area">
  <div class="upload-area-header">
    <h3>批量上传作品</h3>
    <el-button size="small" text @click="showUploadArea = false">
      <el-icon><Close /></el-icon> 收起
    </el-button>
  </div>
  <TubiUploadInline
    :library-id="libraryId"
    @refresh="onUploadRefresh"
  />
</div>

<!-- 按钮：展开上传 -->
<el-button v-else type="primary" @click="showUploadArea = true" :disabled="!canEdit">
  <el-icon><Upload /></el-icon> {{ artworkCount > 0 ? '继续上传' : '上传作品' }}
</el-button>
```

**2b. 模板：工具栏（作者下拉 + 翻译 + 批量重跑）**

在作品列表上方（`toolbar` 区域附近）新增：

```vue
<div class="toolbar batch-toolbar">
  <el-select v-model="selectedArtist" size="small" style="width: 140px" @change="onArtistChange">
    <el-option label="全部作者" value="all" />
    <el-option v-for="a in artistList" :key="a" :label="a" :value="a" />
  </el-select>
  <el-button plain size="small" @click="showTranslateModeDialog = true" :loading="batchTranslating">
    <el-icon><Bottom /></el-icon>翻译
  </el-button>
  <el-button plain size="small" @click="showAnalyzeModeDialog = true" :loading="analyzing">
    <el-icon><Refresh /></el-icon>批量重跑
  </el-button>
</div>
```

**2c. 模板：翻译模式弹窗（从 ContentVerify 搬来）**

```vue
<el-dialog v-model="showTranslateModeDialog" title="批量翻译选项" width="420px">
  <div class="translate-mode-options">
    <div class="mode-option" @click="startBatchTranslate('untranslated')">
      <div class="mode-icon"><el-icon><Bottom /></el-icon></div>
      <div class="mode-info">
        <div class="mode-title">仅翻译未翻译的</div>
        <div class="mode-desc">跳过已有翻译的记录</div>
      </div>
      <el-icon class="mode-arrow"><Right /></el-icon>
    </div>
    <div class="mode-option" @click="startBatchTranslate('all')">
      <div class="mode-icon warning"><el-icon><RefreshRight /></el-icon></div>
      <div class="mode-info">
        <div class="mode-title">重新翻译全部</div>
        <div class="mode-desc">覆盖已有翻译</div>
      </div>
      <el-icon class="mode-arrow"><Right /></el-icon>
    </div>
  </div>
</el-dialog>
```

**2d. 模板：批量重跑模式弹窗（从 ContentVerify 搬来）**

```vue
<el-dialog v-model="showAnalyzeModeDialog" title="解析文字" width="420px">
  <div class="translate-mode-options">
    <div class="mode-option" @click="startBatchAnalyze('incremental')">
      <div class="mode-icon"><el-icon><Refresh /></el-icon></div>
      <div class="mode-info">
        <div class="mode-title">增量重跑</div>
        <div class="mode-desc">仅处理未分析/已过期的作品</div>
      </div>
      <el-icon class="mode-arrow"><Right /></el-icon>
    </div>
    <div class="mode-option" @click="startBatchAnalyze('full')">
      <div class="mode-icon warning"><el-icon><RefreshRight /></el-icon></div>
      <div class="mode-info">
        <div class="mode-title">全部重跑</div>
        <div class="mode-desc">重新分析所有作品（覆盖已有结果）</div>
      </div>
      <el-icon class="mode-arrow"><Right /></el-icon>
    </div>
  </div>
</el-dialog>
```

**2e. 模板：翻译/分析进度弹窗（从 ContentVerify 搬来）**

两套进度弹窗（翻译进度 + 分析进度），结构与 ContentVerify L71-L169 相同，SSE 进度条展示。

**2f. Script 新增**

```js
// imports
import TubiUploadInline from '@/components/tubi/TubiUploadInline.vue'
import { Close, Bottom, Right, Refresh, RefreshRight } from '@element-plus/icons-vue'

// 状态
const showUploadArea = ref(false)
const artworkCount = computed(() => artworks.value.length)

// 作者筛选
const selectedArtist = ref('all')
const artistList = ref([])

// 批量操作
const showTranslateModeDialog = ref(false)
const showTranslateProgress = ref(false)
const batchTranslating = ref(false)
const translateProgress = ref({ current: 0, total: 0, status: '', percent: 0 })

const showAnalyzeModeDialog = ref(false)
const showAnalyzeProgress = ref(false)
const analyzing = ref(false)
const analyzeProgress = ref({ current: 0, total: 0, status: '', percent: 0 })
```

**2g. Script 函数**

```js
// 作者列表
async function fetchArtistList() {
  const res = await fetch(`${API_BASE}/content-analysis/artists`)
  const data = await res.json()
  artistList.value = data.artists || []
}

function onArtistChange() {
  loadArtworks()
}

// 翻译 & 分析（委托给 useBatchOperations composable，传入 libraryId）
```

关键差异：调用 `useBatchOperations` 时传入当前作品库的 `libraryId`，确保翻译/重跑仅作用于本库作品。

**2h. 删除的代码**

| 变量/函数 | 原因 |
|:--|:--|
| `showUploadDialog`, `uploading`, `uploadFileList`, `uploadFile`, `uploadForm` | 被 TubiUploadInline 替代 |
| `handleFileChange`, `handleUpload` | 同上 |
| `el-dialog` 整个上传弹窗块 (L286-L330) | 同上 |
| `Upload` icon（已有） | 保留 |

**2i. 样式新增**

```css
.filename-tip { margin-bottom: 16px; }
.filename-tip code { background: #fdf6f0; color: #c45a3c; padding: 1px 6px; border-radius: 3px; font-size: 12px; }
.batch-toolbar { margin-top: 0; gap: 8px; }
.inline-upload-area { background: #fff; border: 1px solid #e8e3da; border-radius: 12px; padding: 20px; margin-bottom: 16px; }
.upload-area-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
.upload-area-header h3 { margin: 0; font-size: 16px; font-weight: 600; }
```

---

### 3. ContentVerify.vue — 移除上传 Tab + 工具栏按钮迁移

**文件**: `frontend/src/views/ContentVerify.vue`

**3a. 删除模板**

删除以下整段：

```vue
<!-- 作品上传 Tab（L424-L432） -->
<el-tab-pane label="作品上传" name="upload">...</el-tab-pane>

<!-- 工具栏：作者下拉 + 翻译按钮 + 批量重跑按钮（L9-L39） -->
<div class="header-center">
  <el-select v-model="selectedArtist">...</el-select>
</div>
<el-button @click="showTranslateModeDialog = true">翻译</el-button>
<el-button @click="openBatchReanalyze">批量重跑</el-button>

<!-- 翻译模式弹窗（L44-L69） -->
<!-- 翻译进度弹窗（L71-L100） -->
<!-- 批量重跑模式弹窗（L102-L138） -->
<!-- 批量重跑进度弹窗（L140-L169） -->
```

**3b. 删除 Script**

- `selectedArtist`, `artistList` refs
- `fetchArtistList` 函数
- `onArtistChange` 函数
- `onTranslate` 函数（保留给侧边栏单条翻译触发用）
- `onAnalyze`, `onReanalyze` 函数（保留给单条操作）
- `startBatchTranslate`, `startBatchAnalyze`, `openBatchReanalyze` 函数
- `showTranslateModeDialog`, `showTranslateProgress`, `showAnalyzeModeDialog`, `showAnalyzeProgress` 等弹窗状态
- 删除 `TubiUploadInline` import
- 删除 `useBatchOperations` composable 引用或精简为仅保留单条操作

**3c. 保留**

- 侧边栏批量操作触发 watch——改为只保留「侧边栏→重跑」逻辑但重跑入口在库详情
- 单条翻译/分析（表格行内按钮）：`onTranslate`, `onAnalyze`, `onReanalyze` 保留，因为管理员仍需在审核列表中对单条操作
- `Bottom`, `Right`, `Refresh`, `RefreshRight` icons：如仅被删除的弹窗使用则移除

---

### 4. useBatchOperations composable — 简化

**文件**: `frontend/src/composables/useBatchOperations.ts`

确保 `startBatchTranslate` 和 `startBatchAnalyze` 在接收 `libraryId` 参数时不依赖 ContentVerify 的 `selectedArtist` 全局状态。改为从调用方传入 `{ libraryId, artist? }` 参数。

---

## 文件改动清单

| 文件 | 变更 | 说明 |
|:--|:--|:--|
| `backend/app/api/artworks.py` | 修改 | `_artwork_to_dict` 补充 seal_verified/is_manual_annotated/work_type |
| `TubiUploadInline.vue` | 修改 | 加 libraryId prop + API 分支 + 移除 mode 选择/轮询 |
| `LibraryDetail.vue` | 修改 | 替换上传弹窗 + 新增工具栏 + 文件名提示 + 卡片状态点 + 校对/标注入口 |
| `ContentVerify.vue` | 修改 | 移除上传 Tab + 移除工具栏按钮/弹窗 |
| `useBatchOperations.ts` | 可能修改 | 确保接收 libraryId 参数 |

---

## 验证步骤

1. `npm run build` 无报错
2. 进入 `/libraries/:id` → 看到文件名格式提示 → 点击「上传作品」→ TubiUploadInline 展开
3. 拖拽/选择多张图片 → 完成 → 列表刷新
4. 上传完直接回到 idle，无 AI 模式弹窗
5. 工具栏翻译/批量重跑按预期工作
6. 进入 `/admin` → "作品上传" Tab 消失
7. 卡片每个作品显示 4 个状态点（译/析/校/注），完成=绿色，未完成=灰色
8. 鼠标悬停状态点 → tooltip 显示说明
9. 点击「校对」→ 跳转 `/admin?tab=verify&image_id=xxx`
10. 点击「标注」→ 新标签页 `/annotate/:id`

---

## 不改变的部分

- 后端 API：复用现有 `POST /libraries/:id/artworks`、`SSE batch-translate`、`SSE batch-reanalyze`
- 文件名解析：后端 `_parse_calligraphy_filename` 不变
- 单条翻译/分析（审核列表行内按钮）：保留在 ContentVerify
- uploadStore：保持不变（仅移除 mode/轮询消费端代码）

---

## 补充模块：作品卡片状态标记 + 校对入口

### 背景

作品库卡片目前只展示 `status` (analyzed/analyzing/待分析)，缺少细粒度状态提示。
管理员需要一眼看出每个作品：翻译是否完成、文字分析是否完成、是否已校对。
还需要从卡片直接跳转到该作品的校对页面。

### 5. 后端：_artwork_to_dict 补充返回字段

**文件**: `backend/app/api/artworks.py`

在 `_artwork_to_dict` 中补充以下字段（当前缺失）：

```python
"seal_verified": a.seal_verified,          # 印章是否已校对
"is_manual_annotated": a.is_manual_annotated,  # 是否手动标注区域
"work_type": a.work_type,                  # 作品类型：画作/书法/篆刻
```

---

### 6. LibraryDetail.vue — 卡片上新增状态标记

**文件**: `frontend/src/views/LibraryDetail.vue`

在卡片信息区（`artwork-info` L75-L84），将原来简单的「已分析/分析中/待分析」标签替换为更丰富的状态徽章：

```vue
<div class="artwork-info" @click="openArtworkDetail(artwork)">
  <h4 class="artwork-title">{{ artwork.title || artwork.filename || '未命名' }}</h4>
  <p class="artwork-meta">
    <span v-if="artwork.artist">{{ artwork.artist }}</span>
    <span v-if="artwork.year">({{ artwork.year }})</span>
  </p>
  <div class="artwork-status-tags">
    <el-tooltip :content="artwork.inscription_modern ? '翻译已完成' : '待翻译'" placement="top">
      <span class="status-dot" :class="artwork.inscription_modern ? 'done' : 'pending'">译</span>
    </el-tooltip>
    <el-tooltip :content="artwork.content_analysis ? '文字分析已完成' : '待文字分析'" placement="top">
      <span class="status-dot" :class="artwork.content_analysis ? 'done' : 'pending'">析</span>
    </el-tooltip>
    <el-tooltip :content="artwork.inscription_verified ? '题跋已校对' : '题跋待校对'" placement="top">
      <span class="status-dot" :class="artwork.inscription_verified ? 'done' : 'pending'">校</span>
    </el-tooltip>
    <el-tooltip :content="artwork.is_manual_annotated ? '标注已完成' : '标注待定'" placement="top">
      <span class="status-dot" :class="artwork.is_manual_annotated ? 'done' : 'pending'">注</span>
    </el-tooltip>
  </div>
</div>
```

状态点颜色：
- `.done`：绿色背景 (`#5a8c7a`)，表示已完成
- `.pending`：灰色背景 (`#d0ccc0`)，表示待处理

---

### 7. 卡片按钮增加校对入口

**文件**: `frontend/src/views/LibraryDetail.vue`

在卡片底部按钮区（`artwork-card-footer` L85-L92）新增校对链接：

```vue
<div class="artwork-card-footer" v-if="canEdit">
  <el-button link size="small" @click.stop="openProofread(artwork)">
    <el-icon><EditPen /></el-icon> 校对
  </el-button>
  <el-button link size="small" @click.stop="openAnnotate(artwork)">
    <el-icon><Crop /></el-icon> 标注
  </el-button>
  <el-button link size="small" @click.stop="handleTriggerAnalyze(artwork)">
    <el-icon><VideoPlay /></el-icon> AI分析
  </el-button>
  <el-button link size="small" type="danger" @click.stop="handleDeleteArtwork(artwork)">
    <el-icon><Delete /></el-icon> 删除
  </el-button>
</div>
```

对应的 script 函数：

```js
// 跳转到该作品的题跋校对页（ContentVerify 的 verify tab）
function openProofread(artwork) {
  const imageId = artwork.image_id || artwork.id
  if (imageId) {
    router.push({ name: 'Admin', query: { tab: 'verify', image_id: imageId } })
  }
}

// 跳转到该作品的标注编辑器
function openAnnotate(artwork) {
  const imageId = artwork.image_id || artwork.id
  if (imageId) {
    const resolved = router.resolve({ name: 'InscriptionAnnotator', params: { id: imageId } })
    window.open(resolved.href, '_blank')
  }
}
```

---

### 8. 样式新增

```css
/* 状态标记点 */
.artwork-status-tags {
  display: flex; gap: 4px; margin-top: 4px;
}
.status-dot {
  width: 18px; height: 18px; border-radius: 4px;
  display: flex; align-items: center; justify-content: center;
  font-size: 10px; font-weight: 600; color: #fff;
  flex-shrink: 0; cursor: default;
}
.status-dot.done { background: #5a8c7a; }
.status-dot.pending { background: #d0ccc0; }
```
