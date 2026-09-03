# OpenSeadragon 集成方案

## 1. 调研结论

### OpenSeadragon 是否合适 → ✅ 非常合适

| 维度 | 结论 |
|:--|:--|
| 核心能力 | 纯 JS 高性能切片式图像查看，支持几十 MB～几百 MB 超大图 |
| 移动端 | 内置触控手势（双指缩放、单指拖拽），自适应容器宽度 |
| 适合书法的关键 | 放大局部看墨迹、笔触、题跋细节——这正是 OpenSeadragon 的核心场景 |
| 未来 App | 采用标准 DZI/IIIF 格式，Cordova/React Native 中也能用同一套后端协议 |
| 生态 | 活跃维护（6.0.2, 2026/5 最新 commit），丰富插件（标注、测量、滤镜等） |
| 许可证 | BSD-3-Clause，商业友好 |
| 替代方案比较 | **Leaflet**（地图型，不适合高精细单图）、**Fabric.js**（矢量编辑为主，大图性能差）、**自定义 canvas 缩放**（实现成本高，功能远不如 OSD） |

### 当前实现的核心不足

当前 [TubiImageZoomDialog.vue](file:///z:/BaiduSync/BaiduSyncdisk/calligraphy-recognition/frontend/src/components/tubi/TubiImageZoomDialog.vue) 直接加载原图 `url → <img>` 然后用 CSS transform 缩放：
- 几十 MB 的原图直接加载 → 浏览器 OOM/白屏
- 最大 10x 缩放、0.25 步进 → 细节不够
- 无平滑动画过渡
- 移动端手势依托 Element Plus Dialog，体验差
- 无导航小图（mini-map）方便定位

---

## 2. 需要做的工作

### 2.1 后端：上传时自动生成 DZI 瓦片

- 安装 **libvips / pyvips**（Python 绑定）：命令行生成 DZI
- 上传 API 扩展：收到原图后异步调用 `vips dzsave input.jpg output_dir`，生成 `{filename}_files/`（瓦片目录）+ `{filename}.dzi`（描述文件）
- DZI 存放在 `backend/data/dzi/{filename}/` 下
- API `/api/v1/tubi/{id}` 返回中增加 `dzi_url` 字段指向 `.dzi` 文件
- FastAPI mount 新的一级 `/dzi` 静态路由服务瓦片目录

### 2.2 前端：新开 DeepZoomDialog 组件

- 新建 `TubiDeepZoomDialog.vue` 替代 `TubiImageZoomDialog.vue`
- 用 `npm install openseadragon` 安装依赖
- 组件使用 Vue 3 Composition API + TypeScript（可选）
- 集成内置工具栏：缩放滑块、全屏、旋转、翻页
- 开启 Viewport Navigator（缩略导航图）
- 关闭时调用 `viewer.destroy()` 防止内存泄漏
- 适配移动端触控（OSD 默认支持）

### 2.3 向后兼容

- 新上传的图片 → DZI 切片加载
- 历史图片（无 DZI） → 降级到当前简易缩放模式
- 前端判断：`image.dzi_url ? 使用 DeepZoomDialog : 使用原有 ZoomDialog`

### 2.4 后续可扩展（暂不纳入本轮）

- Annotorious 插件：在图上叠加标注（题跋位置、印章位置等）
- Scalebar 插件：按像素显示标尺
- 照片相册集成：多图 Sequence Mode 切换到原作、题跋、印章大图看细节
- App 场景：后端提供标准 IIIF API，App 直接用开源 OSD 绑定

---

## 3. 实施步骤

| 步骤 | 文件/目录 | 变更 |
|:--|:--|:--|
| 后端安装 pyvips | `backend/requirements.txt` | +`pyvips` |
| 后台上传生成 DZI | `backend/app/api/tubi.py` | 上传后调用 `dzsave`，存 `dzi_url` 到 DB |
| 新增 /dzi 静态路由 | `backend/app/main.py` | `app.mount("/dzi", ...)` |
| API 返回 dzi_url | `backend/app/api/tubi.py` GET `/{id}` | 添加 `dzi_url` 字段 |
| 前端安装 OSD | `frontend/package.json` | +`openseadragon` |
| 新建 DeepZoomDialog | `frontend/src/components/tubi/TubiDeepZoomDialog.vue` | 220 行新组件，OSD 核心集成 |
| 替换调用 | `frontend/src/views/TubiDetail.vue` | 条件渲染：有 DZI 走新组件，否则走旧组件 |
| 后端迁移：历史图片 | 脚本生成 DZI | 一次性脚本为已有图补 DZI |

---

## 4. 验证

- [ ] 上传一张几十 MB 的测试图，打开查看确认 60fps 流畅缩放
- [ ] 移动端浏览器上双指缩放、拖拽正常
- [ ] 无 DZI 的历史图片降级正常
- [ ] 内存：反复打开/关闭多个图片后无泄漏
