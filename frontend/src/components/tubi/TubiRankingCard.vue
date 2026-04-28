<template>
  <div class="ranking-module">
    <div class="module-header">
      <h3 class="module-title">题跋比排行榜</h3>
      <el-button type="primary" size="small" @click="handleMore">
        更多
      </el-button>
    </div>
    <el-card shadow="never" class="ranking-card">

      <!-- 骨架屏（8条统一结构，与真实数据完全对齐） -->
      <div class="skeleton-wrap" v-if="loading">
        <div class="skeleton-body">
          <div v-for="i in 8" :key="i" class="skeleton-row" :class="{ 'skeleton-top': i <= 3 }">
            <div class="skeleton-medal skeleton-pulse" :class="{ 'skeleton-medal-lg': i <= 3 }"></div>
            <div class="skeleton-thumb skeleton-pulse" :class="{ 'skeleton-thumb-lg': i <= 3 }"></div>
            <div class="skeleton-info">
              <div class="skeleton-line skeleton-pulse" :style="{ width: i <= 3 ? '80px' : '70px', height: i <= 3 ? '14px' : '13px', marginBottom: i <= 3 ? '6px' : '5px' }"></div>
              <div class="skeleton-line skeleton-pulse" :style="{ width: i <= 3 ? '60px' : '50px', height: i <= 3 ? '12px' : '11px' }"></div>
            </div>
            <div class="skeleton-ratio skeleton-pulse" :class="{ 'skeleton-ratio-lg': i <= 3 }"></div>
          </div>
        </div>
      </div>

      <!-- 排行榜内容（8条统一列表） -->
      <div class="ranking-body" v-if="!loading && rankings.length > 0">
        <!-- 第1-3名 -->
        <div
          v-for="(item, index) in topThreeRankings"
          :key="item.id"
          class="ranking-row top-row"
          :class="[`rank-${index + 1}`, { 'first': index === 0, 'second': index === 1, 'third': index === 2 }]"
          @click="handleItemClick(item)"
        >
          <div class="ranking-row-medal" :class="{ 'gold': index === 0, 'silver': index === 1, 'bronze': index === 2 }">{{ index + 1 }}</div>
          <div class="ranking-row-thumb">
            <img v-if="item.thumbnailUrl || item.url" :src="item.thumbnailUrl || item.url" class="ranking-row-img" @error="handleImageError">
            <div v-else class="ranking-row-placeholder">
              <el-icon size="16"><Picture /></el-icon>
            </div>
          </div>
          <div class="ranking-row-info">
            <div class="ranking-row-name">{{ item.title || '未命名' }}</div>
            <div class="ranking-row-author">{{ item.artist || '李鱓' }}{{ getDisplayAge(item) !== null ? ` ${getDisplayAge(item)}岁` : '' }}</div>
          </div>
          <div class="ranking-row-ratio">{{ item.tubiRatio.toFixed(2) }}%</div>
        </div>

        <!-- 第4-8名 -->
        <div
          v-for="(item, index) in remainingRankings"
          :key="item.id"
          class="ranking-row"
          :class="`rank-${index + 4}`"
          @click="handleItemClick(item)"
        >
          <div class="ranking-row-medal">{{ index + 4 }}</div>
          <div class="ranking-row-thumb">
            <img v-if="item.thumbnailUrl || item.url" :src="item.thumbnailUrl || item.url" class="ranking-row-img" @error="handleImageError">
            <div v-else class="ranking-row-placeholder">
              <el-icon size="14"><Picture /></el-icon>
            </div>
          </div>
          <div class="ranking-row-info">
            <div class="ranking-row-name">{{ item.title || '未命名' }}</div>
            <div class="ranking-row-author">{{ item.artist || '李鱓' }}{{ getDisplayAge(item) !== null ? ` ${getDisplayAge(item)}岁` : '' }}</div>
          </div>
          <div class="ranking-row-ratio">{{ item.tubiRatio.toFixed(2) }}%</div>
        </div>
      </div>

      <!-- 无数据提示 -->
      <div v-if="!loading && rankings.length === 0" class="no-data">
        <el-icon size="48"><Picture /></el-icon>
        <p>暂无数据，请先上传画作</p>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { ArrowLeft, Picture } from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'

const router = useRouter()

// Props
const props = defineProps({
  historyList: {
    type: Array,
    required: true
  },
  getDisplayAge: {
    type: Function,
    required: true
  },
  loading: {
    type: Boolean,
    default: false
  }
})

// Emits
const emit = defineEmits(['item-click', 'more'])

// 题跋比排行榜数据
const rankings = computed(() => {
  // 按题跋占比排序
  return props.historyList
    .filter(item => {
      // 确保有题跋占比数据且大于0
      return item.inscriptionPercent !== undefined && 
             item.inscriptionPercent > 0
    })
    .map(item => {
      // 题跋占比即排序值
      const tubiRatio = item.inscriptionPercent
      return {
        ...item,
        tubiRatio: tubiRatio
      }
    })
    .sort((a, b) => b.tubiRatio - a.tubiRatio) // 按题跋比降序排序
    .slice(0, 8) // 最多显示8条
})

// 前三名排行榜数据
const topThreeRankings = computed(() => {
  return rankings.value.slice(0, 3)
})

// 第4-8名排行榜数据
const remainingRankings = computed(() => {
  return rankings.value.slice(3, 8)
})

// 处理图片加载错误
function handleImageError(e) {
  e.target.src = ''
  e.target.style.display = 'none'
  const placeholder = e.target.nextElementSibling
  if (placeholder) {
    placeholder.style.display = 'flex'
  }
}

// 处理排行榜项点击
function handleItemClick(item) {
  emit('item-click', item)
}

// 处理更多按钮点击
function handleMore() {
  emit('more')
}
</script>

<style scoped>
.ranking-module {
  flex: 3;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.module-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  height: 32px;
  flex-wrap: nowrap;
  white-space: nowrap;
}

.module-title {
  font-family: 'Noto Serif SC', 'KaiTi', serif;
  font-size: 18px;
  color: #1a1a1a;
  font-weight: 600;
  margin: 0;
  letter-spacing: 0.02em;
}

.ranking-card {
  border-radius: var(--radius-lg);
  border: 1px solid var(--border-cream);
  flex: 1;
  display: flex;
  flex-direction: column;
}

.ranking-card :deep(.el-card__body) {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: 18px 16px;
}

.ranking-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 3px;
}

/* 前三名样式 */
/* ─── 骨架屏 ─── */
.skeleton-wrap {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: 2px 0;
}

.skeleton-body {
  display: flex;
  flex-direction: column;
  gap: 3px;
  flex: 1;
}

.skeleton-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 10px;
}

.skeleton-medal {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  flex-shrink: 0;
}

.skeleton-thumb {
  width: 36px;
  height: 36px;
  border-radius: 4px;
  flex-shrink: 0;
}

.skeleton-info {
  flex: 1;
}

.skeleton-line {
  border-radius: 4px;
}

.skeleton-ratio {
  width: 40px;
  height: 18px;
  border-radius: 4px;
  flex-shrink: 0;
}

/* 前3名骨架屏稍大，与真实数据 top-row 对齐 */
.skeleton-top .skeleton-thumb-lg {
  width: 44px;
  height: 44px;
}

.skeleton-top .skeleton-ratio-lg {
  width: 44px;
  height: 20px;
}

@keyframes skeletonPulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

.skeleton-pulse {
  animation: skeletonPulse 1.5s ease-in-out infinite;
  background: var(--border-cream);
}

/* ─── 统一排行榜行（7条）─── */
.ranking-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.ranking-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 10px;
  border-radius: var(--radius-md);
  border: 1px solid transparent;
  cursor: pointer;
  transition: all var(--transition-fast);
}

.ranking-row:hover {
  background: var(--parchment);
}

/* 前三名特殊边框 */
.ranking-row.first {
  background: var(--ivory);
  border-color: var(--gold-light);
}

.ranking-row.first:hover {
  background: #f5f0e4;
  border-color: #c9b896;
}

.ranking-row.second {
  background: var(--ivory);
  border-color: var(--ring-warm);
}

.ranking-row.second:hover {
  background: #f5f0e4;
  border-color: #b8a898;
}

.ranking-row.third {
  background: var(--ivory);
  border-color: var(--gold);
}

.ranking-row.third:hover {
  background: #f5f0e4;
  border-color: #c9a86c;
}

.ranking-row-medal {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: var(--ring-warm);
  color: var(--charcoal-warm);
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
  font-size: 11px;
  flex-shrink: 0;
}

.ranking-row-medal.gold {
  background: var(--tubi-medal-gold);
  color: var(--pure-white);
}

.ranking-row-medal.silver {
  background: var(--tubi-medal-silver);
  color: var(--pure-white);
}

.ranking-row-medal.bronze {
  background: var(--tubi-medal-bronze);
  color: var(--pure-white);
}

.ranking-row-thumb {
  width: 36px;
  height: 36px;
  border-radius: var(--radius-sm);
  overflow: hidden;
  background: var(--parchment);
  border: 1px solid var(--border-warm);
  flex-shrink: 0;
}

.ranking-row-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.ranking-row-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--cinnabar);
  background: var(--parchment);
}

.ranking-row-info {
  flex: 1;
  min-width: 0;
}

.ranking-row-name {
  font-size: 12px;
  font-weight: 600;
  color: var(--near-black);
  margin-bottom: 1px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  font-family: 'Noto Serif SC', 'KaiTi', serif;
}

.ranking-row-author {
  font-size: 10px;
  color: var(--olive-gray);
}

.ranking-row-ratio {
  font-size: 13px;
  font-weight: 500;
  color: var(--stone-gray);
  flex-shrink: 0;
  transition: color var(--transition-fast);
}

/* ─── 前三名百分比突出（Claude风格层次）─── */
.rank-1 .ranking-row-ratio {
  color: #1a1a1a;
  font-weight: 700;
  font-size: 15px;
}

.rank-2 .ranking-row-ratio {
  color: #3d3d3d;
  font-weight: 600;
  font-size: 14px;
}

.rank-3 .ranking-row-ratio {
  color: #5c5c5c;
  font-weight: 600;
  font-size: 14px;
}

/* 第4-8名保持柔和灰调 */

/* 无数据提示 */
.no-data {
  text-align: center;
  padding: 32px 16px;
  color: var(--stone-gray);
}

.no-data el-icon {
  margin-bottom: 8px;
  color: var(--cinnabar);
}

.no-data p {
  font-size: 13px;
  margin: 0;
}

/* ─── 排名边框渐变色（从浅到几乎不可见） ─── */
.ranking-row.rank-1 {
  border-color: #d8d0c4;
}

.ranking-row.rank-2 {
  border-color: #ddd6cc;
}

.ranking-row.rank-3 {
  border-color: #e2dcd4;
}

.ranking-row.rank-4 {
  border-color: #e7e2dc;
}

.ranking-row.rank-5 {
  border-color: #ece9e4;
}

.ranking-row.rank-6 {
  border-color: #f0eee8;
}

.ranking-row.rank-7 {
  border-color: #f3f1ec;
}

.ranking-row.rank-8 {
  border-color: #f5f4f0;
}
</style>
