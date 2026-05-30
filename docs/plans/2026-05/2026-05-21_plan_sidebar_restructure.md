# 侧边栏导航重构：作品库 → 树形菜单

## 一、目标

将左侧栏从扁平化菜单改为以**作品库为入口的树形结构**，每个具体作品库下挂载其关联的操作子菜单（艺术家信息、尺寸录入、印章管理、册页管理、条屏管理、标签管理），点击后自动以该库为上下文筛选数据。

## 二、新侧边栏结构

```
内容（原"内容"分组，不变）
├── 题跋校对
├── 标注图
└── 变更审核

作品库（展开式树形）
├── 全部作品库       → 跳转到库列表（现有 LibraryManage）
├── 郑燮
│   ├── 作品列表      → 默认进入该库的作品页
│   ├── 艺术家信息     → 跳转 /admin/artist/:name/edit
│   ├── 尺寸录入       → 嵌入面板，自动筛选该库作品
│   ├── 印章管理       → 嵌入面板，自动筛选该库
│   ├── 册页管理       → 嵌入面板，自动筛选该库
│   ├── 条屏管理       → 嵌入面板，自动筛选该库
│   └── 标签管理       → 嵌入面板，自动筛选该库
├── 李鱓（同郑燮结构）
├── ...

知识
├── 画家规则

工具
├── 作品查重

系统
├── 系统概览
├── 用户管理
├── 权限配置
├── 系统设置
```

**说明**：
- 「作品库」展开后默认折叠，点击展开显示"全部作品库"和各库名
- 点击库名展开该库的子菜单
- "内容"分组保留不变（题跋校对/标注图/变更审核保持全局）
- "元数据"分组**删除**，其 5 项操作移至各具体库的子菜单中
- "知识"分组保留画家规则，"艺术家"按钮不再在顶层

## 三、URL 方案

采用 query param 驱动：

| 操作 | URL |
|------|-----|
| 全部作品库 | `/admin?tab=libraries` |
| 郑燮→作品列表 | `/admin?tab=libraries&detail_id=5` |
| 郑燮→艺术家信息 | `/admin/artist/郑燮/edit`（独立路由跳转） |
| 郑燮→尺寸录入 | `/admin?tab=libraries&detail_id=5&panel=dimensions` |
| 郑燮→印章管理 | `/admin?tab=libraries&detail_id=5&panel=seal` |
| 郑燮→册页管理 | `/admin?tab=libraries&detail_id=5&panel=album` |
| 郑燮→条屏管理 | `/admin?tab=libraries&detail_id=5&panel=strip` |
| 郑燮→标签管理 | `/admin?tab=libraries&detail_id=5&panel=tag` |

## 四、修改的文件

### 4.1 `AdminLayout.vue` — 侧边栏重写（核心改动）

**改动**：
1. **删除** MENU_DEF 中的 "元数据" 分组（5 项不再全局平铺）
2. **重写** "作品库" 菜单项：从简单 link 改为**动态嵌套树**：
   - 第 1 层：外部 v-for 遍历`menuGroups`（内容/作品库/知识/工具/系统）
   - 作品库组特殊处理：`category='作品库'` 时渲染可展开的树结构
   - "全部作品库"作为第一个子项 → link=`/admin?tab=libraries`
   - 其余子项为各库名，点开渲染子菜单
3. **宽度增加**：从 120px → 160px 或 180px，容纳嵌套缩进
4. **isActive() 扩展**：支持 `detail_id` + `panel` 组合的激活判断
5. **嵌套菜单 CSS**：子菜单缩进 + 库名 hover/active 样式

**关键逻辑**：
```js
// 作品库树形渲染示意
if (group.category === '作品库') {
  // 1. "全部作品库" - 静态
  // 2. 已获取的 accessibleLibraries 列表
  //    每个库展开后显示子菜单项
}
```

### 4.2 `ContentVerify.vue` — 接收 panel 参数

**改动**：
1. 在 `libraries` tab 的渲染逻辑中，读取 `route.query.panel`
2. 如果 `panel` 有值，传递 `detail_id` + `panel` 给 LibraryManage
3. 已有权限检查不变

### 4.3 `LibraryManage.vue` — 嵌入元数据面板

**改动**：
1. 接收从 ContentVerify 传入的 `panel` 参数
2. 当 `detail_id` 和 `panel` 同时存在时，**不渲染 LibraryDetail**，改为渲染对应的元数据面板组件
3. 面板组件接收 `libraryId` prop 进行自动筛选
4. 面板列表：

| panel 值 | 组件 | 说明 |
|----------|------|------|
| `dimensions` | DimensionInput | 显示该库作品的尺寸录入 |
| `seal` | SealManager | 显示该库关联画家的印章管理 |
| `album` | AlbumManager | 册页管理 |
| `strip` | StripManager | 条屏管理 |
| `tag` | TagManager | 标签管理 |
| `artist-info` | → 跳转 ArtistEditor | 跳转到独立页 |

5. 每个面板顶部显示面包屑：「知识库 > 郑燮 > 尺寸录入」，有"返回作品列表"按钮

### 4.4 元数据组件 — 添加 library_id 筛选

**涉及的组件**（在 ContentVerify.vue 中直接 import 的）：

| 组件名 | 文件路径 |
|--------|----------|
| DimensionInput | 待确认 |
| SealManager | 待确认 |
| AlbumManager | 待确认 |
| StripManager | 待确认 |
| TagManager | 待确认 |

**改动**：
- 每个组件新增 `libraryId` prop（`Number`，默认为空）
- 组件内部 API 调用时，如果 `libraryId` 有值，追加 `?library_id=N` 参数
- 数据加载逻辑添加 `library_id` 过滤条件

### 4.5 API 后端调整（如需）

查看各元数据 API 是否已支持 `library_id` 筛选参数，如果没有则添加：

- `GET /seals?library_id=N`
- `GET /dimensions?library_id=N`
- `GET /albums?library_id=N`
- `GET /strips?library_id=N`
- `GET /tags?library_id=N`

### 4.6 `router/index.js` — 无需修改

侧边栏嵌套通过 query param 驱动，不新增路由 path。

## 五、实现步骤

1. **git push** 当前所有更改（用户要求在开始前做）
2. **AdminLayout.vue**：重写作品库菜单为树形结构
3. **LibraryManage.vue**：处理 `panel` 参数，嵌入元数据面板
4. **ContentVerify.vue**：传递 `panel` + `detail_id`
5. **元数据组件**：逐个添加 `libraryId` prop + 筛选逻辑
6. **API 后端**：检查并添加 `library_id` 筛选参数
7. **构建 + 测试**：npm run build，手动验证各面板

## 六、注意事项

- **宽屏适配**：sidebar 120px → 至少 160px（嵌套缩进需要）
- **权限保留**：各子菜单继承原有 perm 检查，editor 只能看到自己有权限的操作
- **空库处理**：库内无相关数据时显示空状态提示
- **深度链接**：URL 要可收藏/可分享，刷新后保持状态
- **backToList 兼容**：从作品库子面板点"返回"回到该库的作品列表

## 七、验证步骤

1. 侧边栏「作品库」→ 展开显示"全部作品库"和各库名
2. 点击库名 → 展开显示子菜单列表
3. 点击「作品列表」→ 显示该库作品网格
4. 点击「尺寸录入」→ 嵌入面板，只显示该库作品的数据
5. 点击「艺术家信息」→ 跳转 ArtistEditor 独立页
6. 刷新页面 → URL 保持，侧边栏激活项正确
7. 回到「全部作品库」→ 显示库列表正常
