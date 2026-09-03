# 印章功能增强：来源引用 + 多版本图库 + 前端画廊

## 参考页面
http://g2.ltfc.net/artist_sign_list/5df8a9bb9f601784c17dd5fc （中华珍宝馆·印鉴页，简约白底方格布局）

**借鉴要点**：
- 白底素雅、大量留白、无冗余装饰
- 印章图片以正方形网格排列，突出图案本身
- 名称简洁标注于图下方
- 整体与项目现有 `ArtistSeals.vue` 的 `#faf8f5` 浅灰底色调一致，无需大改现有设计语言

## 目标

为印章模块增加三个能力：

1. **来源字段**：每个印章可记录出处引用（如"上海博物馆编《中国书画家印鉴款识》（文物出版社，1987.12）"），以独立字段存储在数据库
2. **多版本图片 + 说明**：一枚印章可上传多张不同时期的印蜕图片，每张附带文字说明（如"早年使用"、"晚年用印"）
3. **前端画廊**：在 `/artist/:name/seals` 页面点击印章卡片 → 弹出相册式浏览，左右翻页查看不同版本，下方显示对应说明文字

## 当前状态

### 数据库结构 (`seals` 表)

| 列 | 类型 | 说明 |
|:--|:--|:--|
| id | INTEGER PK | |
| name | TEXT | 印章名（如"复堂"） |
| artist_id | INTEGER? | 画家ID |
| artist_name | TEXT? | 画家名 |
| seal_type | TEXT '名章' | 类型 |
| description | TEXT '' | 印章描述 |
| **images** | TEXT, JSON `["/static/..."]` | 图片路径数组 |
| created_at | TIMESTAMP | |
| updated_at | TIMESTAMP | |

现状：`images` 字段存 JSON 路径数组，无来源、无图片级描述。

### 后端 API（`/api/v1/seals`）
- `GET /seals` — 列表（按使用频次排序）
- `GET /seals/{id}` — 单印章
- `POST /seals/{id}/upload-image` — 追加图片到 `images[]`
- `DELETE /seals/{id}/images/{index}` — 按索引删图
- CRUD 其他...

### 前端
- **管理面板** `SealManager.vue` — 卡片网格，弹窗编辑，图片上传/删除
- **公开展示** `ArtistSeals.vue` — 简单网格，无点击放大/翻页

## 设计决策

### 数据模型：新增 `seal_images` 表（而非改 JSON）

| | 新表 | 改JSON格式 |
|:--|:--|:--|
| 查询/排序 | SQL原生 `ORDER BY sort_order` | 需解析JSON |
| 扩展性 | 未来加字段容易 | 需迁移所有JSON |
| 迁移难度 | 一句 CREATE TABLE + 循环旧数据 | 需改写所有行 |

**new `seal_images` 表**：
```sql
CREATE TABLE IF NOT EXISTS seal_images (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    seal_id INTEGER NOT NULL REFERENCES seals(id) ON DELETE CASCADE,
    path TEXT NOT NULL,               -- 图片路径 /static/seals/xxx.png
    description TEXT DEFAULT '',      -- 版本描述，如"早年使用"
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**seals 表新增列**：
```sql
ALTER TABLE seals ADD COLUMN source TEXT DEFAULT '';
```

**旧数据迁移**：读取 `seals.images` JSON 数组，逐条 INSERT INTO seal_images，最后 UPDATE seals SET images='[]'。

---

## 具体改动

### 一、后端

#### 1.1 `backend/app/models/seal.py` — 新增模型 + source字段

在当前 Seal 类中新增：
- `source = Column(Text, default='')`

新增 SealImage ORM 模型，并在 Seal 上添加 `images_rel = relationship("SealImage", order_by="SealImage.sort_order")`

#### 1.2 `backend/app/api/seals.py` — Schema + 端点

**Pydantic schemas 变更**：
- `SealCreate` / `SealUpdate` 新增 `source: Optional[str]` 字段
- 新增 `SealImageOut(BaseModel)`: id, path, description, sort_order
- 所有 seal 输出增加 `images: List[SealImageOut]`（替代旧 `images: List[str]`）

**端点变更**：

| 方法 | 路径 | 变更 |
|:--|:--|:--|
| GET | `/seals` | 返回 `images` 改为 `[{id, path, description, sort_order}]` 格式；兼容：如果旧 `images` 还有 JSON 数据则一并迁移到 seal_images |
| GET | `/seals/{id}` | 同上 |
| POST | `/seals` | 接收 `source`，创建后如果旧 images JSON 有数据则迁移 |
| PUT | `/seals/{id}` | 接收 `source` 更新 |
| POST | `/seals/{id}/images` | 上传图片，参数新增 `description: str`（FormData），存入 seal_images 表而非 images JSON |
| PUT | `/seals/{id}/images/{image_id}` | **新增**：更新单张图片的 description 或 sort_order |
| DELETE | `/seals/{id}/images/{image_id}` | 改为按 `image_id` 删（旧版按 index） |

**兼容处理函数**（API 层）：
```python
def _migrate_old_images(db_conn, seal_row):
    """将 seals.images JSON 迁移到 seal_images 表，迁移后清空 JSON"""
    import json
    old = json.loads(seal_row.get('images', '[]'))
    for i, path in enumerate(old):
        db_conn.execute(
            "INSERT INTO seal_images (seal_id, path, sort_order) VALUES (?,?,?)",
            (seal_row['id'], path, i)
        )
    db_conn.execute("UPDATE seals SET images='[]' WHERE id=?", (seal_row['id'],))
```

#### 1.3 `backend/app/core/database.py` — 建表/加列

在 `run_migrations()` 或主启动流程中增加：
```python
conn.execute(text("CREATE TABLE IF NOT EXISTS seal_images (...)"))
conn.execute(text("ALTER TABLE seals ADD COLUMN source TEXT DEFAULT ''"))
```

---

### 二、前端 — 管理面板 `SealManager.vue`

**新增字段**：
- 弹窗表单顶部新增「来源出处」输入框（`<el-input type="textarea" :rows="2">`）

**图片管理区改造**（原有：简单上传列表）→ 改为每张图片独立卡片：
```
┌─────────────────────────────────┐
│ [缩略图 120×120]             [×] │
│ 版本说明：[早年使用___________]   │
│ 排序：[∧] [∨]                  │
├─────────────────────────────────┤
│ [缩略图 120×120]             [×] │
│ 版本说明：[晚年用印___________]   │
│ 排序：[∧] [∨]                  │
├─────────────────────────────────┤
│ [+ 添加印章图片]                 │
└─────────────────────────────────┘
```
每张图片：缩略图预览 + description 输入框 + 删除按钮。底部 "+" 按钮触发文件选择后自动上传。

**旧数据兼容**：列表加载时检测 `images` 为旧格式（字符串数组）的印章，打开编辑时自动触发迁移（调用 PUT 保存触发后端迁移）。

---

### 三、前端 — 公开展示页 `ArtistSeals.vue`  → 改为画廊模式

#### 3.1 卡片网格（不变，仅增强 hover 效果）

保持现有 `as-grid` 布局，但卡片改为：
- 显示第一张图片作为封面
- 右上角若有 ≥2 张图片则显示角标 `「3图」`
- hover 时轻微放大 + 阴影
- 点击打开 Lightbox

#### 3.2 Lightbox 画廊（新增核心功能）

点击卡片 → 全屏遮罩弹出：

```
                     [× 关闭]
┌────────────────────────────────────────────┐
│                                            │
│              [←]  [印章大图]  [→]          │
│                                            │
│     ┌─────────────────────────────┐        │
│     │                             │        │
│     │     印章图片（居中显示）      │        │
│     │     max-width: 90vw         │        │
│     │     max-height: 70vh        │        │
│     │                             │        │
│     └─────────────────────────────┘        │
│                                            │
│         早年使用（版本描述文字）              │
│                                            │
│   ○ ● ○        （缩略图导航点）             │
│                                            │
│  印章名称 · 类型   来源引用（灰色小字）       │
│  底部显示 seal.name / seal_type / source   │
└────────────────────────────────────────────┘
```

**交互**：
- 点击遮罩空白处或 × 关闭
- 键盘 ← → 翻页
- 底部圆点指示器可点击跳转
- 支持 `el-image` 的 `preview-src-list` 或自定义 `<img>` 预览

**实现方式**：新建一个 `SealLightbox.vue` 子组件，接收 `seal` prop，管理当前图片索引。使用 `<el-image>` 的 `preview-src-list` 模式实现简单图片预览（非 OpenSeadragon 深缩放）。

#### 3.3 来源引用展示

在每张印章卡片底部（名称下方），如果有 source 内容，显示灰色小字来源信息（截断到一行，hover 显示完整）。

---

### 四、API 模块 `frontend/src/api/index.js`

```javascript
export const sealsApi = {
  list(params),                  // 不变
  get(sealId),                   // 不变
  create(data),                  // data 新增 source
  update(sealId, data),          // data 新增 source
  delete(sealId),                // 不变
  uploadImage(id, file, desc),   // 参数变：新增 desc 字段 → FormData
  updateImage(sealId, imgId, data),  // 新增：PUT /seals/{id}/images/{img_id}
  deleteImage(sealId, imgId),    // 参数变：从 index 改为 imgId
  // ...其他不变
}
```

---

### 五、实施步骤

| # | 步骤 | 文件 |
|:--|:--|:--|
| 1 | 修改 ORM Seal 模型 + 新增 SealImage 模型 | `backend/app/models/seal.py` |
| 2 | 启动迁移：建 seal_images 表、加 source 列、迁移旧数据 | `backend/app/core/database.py` |
| 3 | 改造后端 API schemas + 所有端点 | `backend/app/api/seals.py` |
| 4 | 更新前端 sealsApi | `frontend/src/api/index.js` |
| 5 | SealManager 增加 source 字段 + 图片描述管理 | `frontend/src/views/SealManager.vue` |
| 6 | 新建 Lightbox 组件 | `frontend/src/components/seal/SealLightbox.vue` |
| 7 | ArtistSeals 改为画廊模式（卡片可点击 + Lightbox） | `frontend/src/views/artist/ArtistSeals.vue` |
| 8 | 构建 + 部署 | `npm run build` → `deploy.sh` |

---

### 六、验证清单

- [ ] 数据库 `seal_images` 表已创建、`seals.source` 列已存在
- [ ] 旧 `seals.images` JSON 数据在首次编辑保存时自动迁移到 seal_images
- [ ] SealManager：添加来源文本、上传多图片每张填描述、翻页排序
- [ ] `/artist/李鱓/seals`：显示所有印章卡片，含封面缩略图
- [ ] 点击印章卡片 → Lightbox 弹出，← → 翻页，下方显示描述
- [ ] 有 source 的印章卡片底部显示引用文字
- [ ] 部署后线上验证
