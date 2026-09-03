# ArtistList 全面重构计划

## 1. 现状总结

| 方面 | 当前状态 | 问题 |
|:--|:--|:--|
| 数据量 | `page_size=200` 硬编码 | 486 位画家只加载 200 位，500+ 时直接丢失数据 |
| 分页 | 前端 `computed` 做分组/过滤 | 无真分页，全量前端内存消耗大 |
| 排序 | 后端支持 `sort` 参数 | 前端无任何排序控件，固定 `created_at` |
| 搜索 | `@input` 无防抖 | 每次按键触发一次 API 请求 |
| API 层 | 原生 `fetch` 裸调用 | 和项目其他模块（axios + api 封装）不一致 |
| 缓存 | **零缓存** | 无 HTTP 缓存头、无 Redis、无 Pinia Store、无前端持久化 |
| 筛选 | 搜索框 + 朝代下拉 + 画派下拉 | 对 500+ 人规模偏少 |
| 布局 | 固定朝代分组卡片 | 无可切换布局、无时间轴浏览 |

## 2. 设计方案概览

```
┌──────────────────────────────────────────────────────┐
│  Hero 区                                              │
│  「艺术家百科」                                        │
├──────────────────────────────────────────────────────┤
│  视图切换: [卡片网格] [时间轴] [紧凑表格]               │
│  筛选栏: [搜索框] [朝代▼] [画派▼] [排序▼]              │
│  拼音导航: [A-D] [E-H] [J-L] [M-Q] [R-T] [W-Z]      │
├──────────────────────────────────────────────────────┤
│                                                      │
│  卡片网格视图（默认）                                  │
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐               │
│  │头像  │ │头像  │ │头像  │ │头像  │               │
│  │姓名  │ │姓名  │ │姓名  │ │姓名  │               │
│  │年代  │ │年代  │ │年代  │ │年代  │               │
│  └──────┘ └──────┘ └──────┘ └──────┘               │
│                                                      │
│  加载更多 / 分批展示                                   │
└──────────────────────────────────────────────────────┘
```

### 2.1 三种视图

| 视图 | 布局 | 适用场景 |
|:--|:--|:--|
| **卡片网格**（默认） | `auto-fill, minmax(240px, 1fr)` 网格，头像首字+姓名+年代+标签 | 日常浏览、视觉展示 |
| **时间轴** | 纵向时间线，按生卒年排列，左侧朝代标签 | 理解艺术史脉络 |
| **紧凑表格** | `el-table`，列：头像/姓名/字号/朝代/生卒/画派/作品数 | 快速检索、批量对比 |

视图切换持久化到 `localStorage`，刷新保持用户选择。

### 2.2 筛选系统（轻量增强）

| 控件 | 类型 | 说明 |
|:--|:--|:--|
| 搜索框 | `el-input` + 300ms 防抖 | 搜索姓名/字号/简介，后端 `keyword` 参数 |
| 朝代 | `el-select` 多选 | 从 `/artists/periods` 获取，后端传入逗号分隔 |
| 画派 | `el-select` 多选 | 从 `/artists/schools` 获取 |
| 排序 | `el-select` | 选项：创建时间/姓名/出生年份/作品数量 |
| 拼音导航 | 字母按钮组 | 前端按姓名拼音首字母跳转，配合当前页数据 |

### 2.3 分页策略

后端真分页，`page_size=40`：
- 卡片视图 → 无限滚动（滚动到底自动加载下一页）
- 表格视图 → 传统页码器
- 时间轴视图 → 全部加载（按生卒年排列的数据量不会太大）

### 2.4 缓存架构（三层）

```
第1层: 浏览器 HTTP 缓存
  后端返回 ETag / Cache-Control: max-age=300
  → 同一用户 5 分钟内不重复请求

第2层: 后端内存缓存（lru_cache + TTL）
  artists 列表数据（不分页全量或热门筛选组合）缓存 5 分钟
  periods/schools 数据缓存 30 分钟（基本不变）
  → 减轻 SQLite 压力

第3层: 前端 Pinia Store
  artistStore 缓存当前加载的艺术家数组
  跨组件复用（ArtistList ↔ ArtistOverview 切换时不重新请求）
  页面刷新后从 localStorage 恢复列表骨架数据
```

## 3. 详细实现计划

### 3.1 后端改动

#### 3.1.1 `backend/app/api/artists.py` — 增强 `list_artists`

**当前**（第97-150行）：单 dynasty + 单 school + 单 keyword

**改为**：
```python
@router.get("")
async def list_artists(
    dynasty: Optional[str] = None,        # 支持逗号分隔多选："唐,宋,元"
    school: Optional[str] = None,         # 支持逗号分隔多选
    keyword: Optional[str] = None,
    featured: Optional[bool] = None,
    verified_only: bool = True,
    page: int = 1,
    page_size: int = 40,
    sort: str = "created_at",             # 新增: name / birth_year / artwork_count
):
```

变动点：
1. `dynasty` 和 `school` 多选 → SQL `WHERE dynasty IN (?, ?, ...)` 或 `OR art_school LIKE`
2. 新增 `sort=name` / `sort=birth_year` / `sort=artwork_count` 排序逻辑
3. 新增 HTTP 缓存头：`Cache-Control: max-age=300` + `ETag`
4. 添加 `cached` 字段到返回 JSON 用于调试

#### 3.1.2 新增 `/artists/letter-index` 端点

```python
@router.get("/letter-index")
async def get_letter_index():
    """返回按拼音首字母分组的艺术家计数"""
    # 返回: {"A": 3, "B": 8, "C": 15, "D": 12, ...}
```

前端用于渲染拼音导航条，可按需加载或缓存到 `periods/schools` 同一请求中。

#### 3.1.3 新增 `/artists/stats-summary` 端点

```python
@router.get("/stats-summary")
async def get_stats_summary():
    """返回各朝代/画派/世纪计数（用于侧边栏统计标签）"""
```

#### 3.1.4 后端缓存装饰器（可选，Phase 2）

在 `backend/app/services/` 新增 `cache.py`：
```python
from functools import lru_cache, wraps
import time

def ttl_cache(ttl_seconds=300):
    """简单 TTL 内存缓存"""
    def decorator(fn):
        cache = {}
        @wraps(fn)
        def wrapper(*args, **kwargs):
            key = str(args) + str(sorted(kwargs.items()))
            now = time.time()
            if key in cache and now - cache[key]['ts'] < ttl_seconds:
                return cache[key]['data']
            data = fn(*args, **kwargs)
            cache[key] = {'data': data, 'ts': now}
            return data
        return wrapper
    return decorator
```

将 `list_artists` 的 SQL 查询结果用此装饰器包裹。

### 3.2 前端改动

#### 3.2.1 新建 `frontend/src/stores/artistStore.js`

```javascript
// Pinia Store — 艺术家数据缓存
export const useArtistStore = defineStore('artist', () => {
  const list = ref([])           // 当前加载的艺术家数组
  const total = ref(0)
  const periods = ref([])
  const schools = ref([])
  const lastFetchTime = ref(0)
  const CACHE_TTL = 5 * 60 * 1000  // 5 分钟

  function isStale() { return Date.now() - lastFetchTime.value > CACHE_TTL }
  // ...
})
```

#### 3.2.2 重构 `frontend/src/views/ArtistList.vue`

**改动计划：**

| 区域 | 当前 | 改为 |
|:--|:--|:--|
| 视图 | 固定卡片网格 | `el-radio-group` 三视图切换 |
| 筛选 | 3 个内联控件 | 搜索框 + 朝代多选 + 画派多选 + 排序 + 拼音导航 |
| 分页 | 一次性 200 条 | 无限滚动（卡片）+ 页码器（表格） |
| API | 原生 `fetch` | 使用 `artistsApi`（新建） |
| 卡片 | 圆头像+姓名+年代 | 增加作品数徽标、hover 预览简介 |
| 状态 | 本地 ref | Pinia `artistStore` |

**新页面结构：**

```vue
<template>
  <div class="artist-list-page">
    <!-- Hero -->
    <div class="al-hero">...</div>

    <!-- 视图切换 + 筛选栏 -->
    <div class="al-toolbar">
      <el-radio-group v-model="viewMode">卡片/表格/时间轴</el-radio-group>
      <div class="al-filters">
        <el-input v-model="keyword" placeholder="搜索..." @input="debouncedSearch" />
        <el-select v-model="dynastyFilters" multiple placeholder="朝代" />
        <el-select v-model="schoolFilters" multiple placeholder="画派" />
        <el-select v-model="sortBy" placeholder="排序" />
      </div>
      <!-- 拼音导航 -->
      <div class="al-pinyin-nav">
        <button v-for="letter in pinyinIndex" :key="letter" @click="jumpToLetter(letter)">
          {{ letter }}
        </button>
      </div>
    </div>

    <!-- 卡片视图 -->
    <div v-if="viewMode === 'card'" class="al-card-grid">
      <ArtistCard v-for="artist in artists" :key="artist.id" :artist="artist" />
      <div ref="loadMoreTrigger" />
    </div>

    <!-- 表格视图 -->
    <el-table v-else-if="viewMode === 'table'" :data="artists">...</el-table>

    <!-- 时间轴视图 -->
    <div v-else class="al-timeline">...</div>
  </div>
</template>
```

#### 3.2.3 新建 `frontend/src/components/artist/ArtistCard.vue`

抽取卡片为独立组件，方便复用：
- 头像（首字或真实图片，fallback 到首字）
- 姓名 + 字号
- 生卒年
- 朝代/画派标签
- 作品数徽标
- hover 显示 30 字简介

#### 3.2.4 新建 `frontend/src/components/artist/ArtistTimeline.vue`

时间轴组件：
- 使用 `el-timeline` 或自定义 CSS 纵向时间线
- 每张卡片含年代区间+姓名+朝代标签
- 支持按世纪缩放

#### 3.2.5 新建 `frontend/src/api/artists.js`（或扩展 `index.js`）

```javascript
export const artistsApi = {
  list(params) { return api.get('/artists', { params }) },
  getByName(name) { return api.get(`/artists/by-name/${encodeURIComponent(name)}`) },
  periods() { return api.get('/artists/periods') },
  schools() { return api.get('/artists/schools') },
  letterIndex() { return api.get('/artists/letter-index') },
  statsSummary() { return api.get('/artists/stats-summary') },
}
```

#### 3.2.6 拼音首字母导航

前端使用 `pinyin-pro` 库（或已有的拼音工具）：
```javascript
import { pinyin } from 'pinyin-pro'

function getFirstLetter(name) {
  const py = pinyin(name, { toneType: 'none', type: 'array' })
  return py[0]?.charAt(0).toUpperCase() || '#'
}
```

### 3.3 数据流

```
用户访问 /#/artists
  │
  ├─ artistStore 检查缓存
  │    ├─ 未过期 → 直接用缓存渲染
  │    └─ 已过期 / 首次访问
  │         └─ GET /artists?page=1&page_size=40&sort=name
  │              ├─ 后端查 SQLite
  │              ├─ 后端 TTL 内存缓存（5min）
  │              ├─ 返回 + Cache-Control: max-age=300
  │              └─ artistStore 存储结果
  │
  ├─ 并行加载:
  │    GET /artists/periods    → store (30min TTL)
  │    GET /artists/schools     → store (30min TTL)
  │    GET /artists/letter-index → store (30min TTL)
  │
  ├─ 滚动到底
  │    └─ GET /artists?page=2&page_size=40 ...
  │         → 追加到 artistStore.list
  │
  └─ 用户切换筛选
       └─ 清空 store，重新第1页请求
```

## 4. 实施步骤

### Step 1: 后端 — 增强 API（~2h）
- [ ] `list_artists` 支持多选 dynasty/school
- [ ] 新增 `sort` 选项: `name`, `birth_year`, `artwork_count`
- [ ] 新增 HTTP 缓存头
- [ ] 新增 `/artists/letter-index` 端点
- [ ] 后端 `functools.lru_cache` 或简单 TTL 缓存

### Step 2: 前端 — API 层 + Store（~1h）
- [ ] 新建 `api/artists.js` 封装
- [ ] 新建 `stores/artistStore.js`

### Step 3: 前端 — 组件开发（~4h）
- [ ] 新建 `ArtistCard.vue`
- [ ] 新建 `ArtistTimeline.vue`
- [ ] 新建 `PinyinNav.vue`

### Step 4: 前端 — 重构 ArtistList.vue（~3h）
- [ ] 三视图切换框架
- [ ] 筛选栏重构（多选 + 防抖 + 排序）
- [ ] 无限滚动 / 页码器
- [ ] 接入 Pinia store + 缓存逻辑
- [ ] 响应式适配

### Step 5: 测试 + 性能验证（~1h）
- [ ] 验证缓存命中率
- [ ] 验证 500 位画家的加载性能
- [ ] 验证筛选/排序/分页正常
- [ ] 验证视图切换状态持久化

## 5. 不包含（明确排除）

- ❌ AI 语义搜索（Phase 3）
- ❌ 全文检索引擎（Elasticsearch）
- ❌ Redis 数据缓存（保留未来可能，先用内存缓存）
- ❌ 服务端渲染（SSR）
- ❌ 艺术家对比功能
- ❌ 收藏/关注功能

## 6. 风险与回滚

- **风险**: 后端缓存可能导致数据不一致 → TTL 5分钟 + 操作时主动清除
- **回滚**: 新 API 向下兼容旧参数，前端可随时切回旧 `ArtistList.vue`

## 7. 验收标准

1. 486 位画家全部可访问，不丢数据
2. 首屏加载 < 1.5s
3. 三视图切换流畅，无闪烁
4. 筛选 + 排序 + 分页联动正常
5. 同一 session 内重复访问不重新请求
6. 拼音导航可快速定位
7. 移动端响应式正常
