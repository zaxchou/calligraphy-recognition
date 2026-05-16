<template>
  <div class="ao-page">
    <div v-if="loading" class="ao-loading">加载中...</div>

    <div v-else-if="notFound" class="ao-not-found">
      <div class="ao-not-found-icon">?</div>
      <h2>未找到该画家</h2>
      <p>请确认名称是否正确，或返回<a href="#/artists">艺术家列表</a>浏览</p>
    </div>

    <template v-else-if="artist">
      <div class="ao-header">
        <div class="ao-avatar">{{ artist.name?.charAt(0) || '?' }}</div>
        <div class="ao-header-info">
          <h1 class="ao-name">{{ artist.name }}</h1>
          <p v-if="artist.alias" class="ao-alias">{{ artist.alias }}</p>
          <div class="ao-header-tags">
            <span v-if="artist.dynasty" class="ao-tag">{{ artist.dynasty }}</span>
            <span v-if="artist.art_school" class="ao-tag ao-tag-school">{{ artist.art_school }}</span>
          </div>
        </div>
        <div v-if="authStore.isEditor" class="ao-header-actions">
          <el-button size="small" plain class="ao-btn-edit">编辑</el-button>
          <el-button size="small" plain class="ao-btn-edit">AI 补充</el-button>
          <el-button size="small" plain class="ao-btn-edit">我的修改</el-button>
        </div>
      </div>

      <nav class="ao-sub-nav">
        <router-link
          v-for="tab in subNavTabs"
          :key="tab.path"
          :to="tab.path"
          class="ao-nav-item"
          :class="{ active: isActiveTab(tab.path) }"
        >
          {{ tab.label }}
        </router-link>
      </nav>

      <div class="ao-body">
        <section class="ao-card ao-info-card">
          <h2 class="ao-card-title">基本信息</h2>
          <div class="ao-info-grid">
            <div v-if="artist.alias" class="ao-info-item">
              <span class="ao-info-label">别号</span>
              <span class="ao-info-value">{{ artist.alias }}</span>
            </div>
            <div v-if="artist.hometown" class="ao-info-item">
              <span class="ao-info-label">籍贯</span>
              <span class="ao-info-value">{{ artist.hometown }}</span>
            </div>
            <div v-if="artist.birth_year || artist.death_year" class="ao-info-item">
              <span class="ao-info-label">生卒</span>
              <span class="ao-info-value">{{ formatYears(artist.birth_year, artist.death_year) }}</span>
            </div>
            <div v-if="artist.dynasty" class="ao-info-item">
              <span class="ao-info-label">朝代</span>
              <span class="ao-info-value">{{ artist.dynasty }}</span>
            </div>
            <div v-if="artist.art_school" class="ao-info-item">
              <span class="ao-info-label">画派</span>
              <span class="ao-info-value">{{ artist.art_school }}</span>
            </div>
          </div>
        </section>

        <section class="ao-card ao-bio-card">
          <h2 class="ao-card-title">生平</h2>
          <p v-if="artist.biography" class="ao-bio-text">{{ artist.biography }}</p>
          <p v-else class="ao-bio-empty">暂无生平信息</p>
        </section>

        <section v-if="timelineEvents.length > 0" class="ao-card ao-timeline-card">
          <h2 class="ao-card-title">生平年表</h2>
          <div class="ao-timeline">
            <div v-for="(event, idx) in timelineEvents" :key="idx" class="ao-timeline-item">
              <div class="ao-timeline-dot" />
              <div class="ao-timeline-content">
                <span v-if="event.year" class="ao-timeline-year">{{ event.year }}</span>
                <span class="ao-timeline-desc">{{ event.event || event.description || '' }}</span>
              </div>
            </div>
          </div>
        </section>

        <section class="ao-card ao-stats-card">
          <h2 class="ao-card-title">数据概览</h2>
          <div class="ao-stats-row">
            <div class="ao-stat-item">
              <span class="ao-stat-number">{{ stats.total ?? '-' }}</span>
              <span class="ao-stat-label">作品总数</span>
            </div>
            <div class="ao-stat-item">
              <span class="ao-stat-number">{{ stats.analyzed ?? '-' }}</span>
              <span class="ao-stat-label">已分析</span>
            </div>
            <div class="ao-stat-item">
              <span class="ao-stat-number">{{ stats.verified ?? '-' }}</span>
              <span class="ao-stat-label">已核验</span>
            </div>
            <div class="ao-stat-item">
              <span class="ao-stat-number">{{ stats.seal_count ?? '-' }}</span>
              <span class="ao-stat-label">印章</span>
            </div>
          </div>
        </section>

        <section v-if="masterpieces.length > 0" class="ao-card ao-masterpieces-card">
          <h2 class="ao-card-title">代表作品</h2>
          <div class="ao-masterpieces-scroll">
            <div v-for="item in masterpieces" :key="item.id" class="ao-masterpiece-item">
              <div class="ao-masterpiece-thumb">
                <img v-if="item.image_url" :src="item.image_url" :alt="item.title || '作品'" />
                <span v-else class="ao-thumb-placeholder">📄</span>
              </div>
              <div class="ao-masterpiece-info">
                <p class="ao-masterpiece-title">{{ item.title || '无题' }}</p>
                <p v-if="item.year" class="ao-masterpiece-year">{{ item.year }}</p>
              </div>
            </div>
          </div>
        </section>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '../../stores/authStore'

const route = useRoute()
const authStore = useAuthStore()
const API_BASE = import.meta.env.VITE_API_BASE || '/api/v1'
const artistEncoded = computed(() => encodeURIComponent(route.params.name))

const loading = ref(true)
const notFound = ref(false)
const artist = ref(null)
const stats = ref({})
const masterpieces = ref([])

const subNavTabs = [
  { label: '概览', path: '' },
  { label: '作品', path: 'works' },
  { label: '印章', path: 'seals' },
  { label: '文献', path: 'literature' },
  { label: '分析', path: 'analysis' },
]

function isActiveTab(tabPath) {
  const current = route.path.replace(/\/+$/, '')
  const base = current.substring(0, current.lastIndexOf('/'))
  if (!tabPath) return current === base || current.endsWith('/artist/' + artistEncoded.value)
  return current.endsWith('/' + tabPath)
}

const timelineEvents = computed(() => {
  if (!artist.value?.bio_events) return []
  try {
    const parsed = typeof artist.value.bio_events === 'string'
      ? JSON.parse(artist.value.bio_events)
      : artist.value.bio_events
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
})

function formatYears(birth, death) {
  if (!birth && !death) return ''
  const b = birth || '?'
  const d = death || '?'
  return `${b} — ${d}`
}

async function fetchArtist() {
  const name = route.params.name
  if (!name) {
    notFound.value = true
    loading.value = false
    return
  }
  try {
    const res = await fetch(`${API_BASE}/artists/by-name/${encodeURIComponent(name)}`)
    if (!res.ok) {
      if (res.status === 404) {
        notFound.value = true
      }
      return
    }
    const data = await res.json()
    artist.value = data.artist || null
    if (!artist.value) {
      notFound.value = true
    }
  } catch (e) {
    console.error('获取画家信息失败:', e)
    notFound.value = true
  }
}

async function fetchStats() {
  if (!artist.value?.id) return
  try {
    const res = await fetch(`${API_BASE}/artists/${artist.value.id}/stats`)
    if (res.ok) {
      const data = await res.json()
      stats.value = data.stats || {}
    }
  } catch (e) {
    console.error('获取统计数据失败:', e)
  }
}

async function fetchMasterpieces() {
  const name = route.params.name
  if (!name) return
  try {
    const res = await fetch(`${API_BASE}/content-analysis/records?artist=${encodeURIComponent(name)}&limit=10`)
    if (res.ok) {
      const data = await res.json()
      const records = data.records || data.results || data.data || []
      masterpieces.value = records.slice(0, 6)
    }
  } catch (e) {
    console.error('获取作品列表失败:', e)
  }
}

onMounted(async () => {
  loading.value = true
  await fetchArtist()
  if (artist.value) {
    await Promise.all([fetchStats(), fetchMasterpieces()])
  }
  loading.value = false
})
</script>

<style scoped>
.ao-page {
  max-width: 1000px;
  margin: 0 auto;
  padding: 40px 24px 80px;
  min-height: 100vh;
  background: #fafaf8;
}

.ao-loading {
  text-align: center;
  padding: 80px 0;
  color: #8a8578;
  font-size: 0.95rem;
}

.ao-not-found {
  text-align: center;
  padding: 80px 24px;
}

.ao-not-found-icon {
  width: 80px;
  height: 80px;
  margin: 0 auto 20px;
  border-radius: 50%;
  background: #f5f0ea;
  color: #8a8578;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 2.25rem;
  font-family: 'Noto Serif SC', 'KaiTi', 'STKaiti', serif;
}

.ao-not-found h2 {
  font-family: 'Noto Serif SC', 'KaiTi', 'STKaiti', serif;
  font-size: 1.4rem;
  color: #3a3222;
  margin: 0 0 12px;
  font-weight: 500;
}

.ao-not-found p {
  color: #8a8578;
  font-size: 0.9rem;
  margin: 0;
}

.ao-not-found a {
  color: #c45a3c;
  text-decoration: none;
}

.ao-not-found a:hover {
  text-decoration: underline;
}

.ao-header {
  display: flex;
  align-items: flex-start;
  gap: 24px;
  margin-bottom: 28px;
}

.ao-avatar {
  width: 80px;
  height: 80px;
  flex-shrink: 0;
  border-radius: 50%;
  background: linear-gradient(135deg, #c45a3c, #dbbca8);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: 'Noto Serif SC', 'KaiTi', 'STKaiti', serif;
  font-size: 2rem;
  font-weight: 500;
}

.ao-header-info {
  flex: 1;
  min-width: 0;
}

.ao-name {
  font-family: 'Noto Serif SC', 'KaiTi', 'STKaiti', serif;
  font-size: 2rem;
  font-weight: 500;
  color: #3a3222;
  margin: 0 0 6px;
  letter-spacing: 0.08em;
  line-height: 1.2;
}

.ao-alias {
  font-size: 0.9rem;
  color: #8a8578;
  margin: 0 0 10px;
  line-height: 1.4;
}

.ao-header-tags {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.ao-tag {
  display: inline-block;
  font-size: 0.75rem;
  padding: 3px 12px;
  border-radius: 999px;
  background: #f5f0ea;
  color: #8a6f4c;
  letter-spacing: 0.04em;
  line-height: 1.5;
}

.ao-tag-school {
  background: #f0ede8;
  color: #6b6b60;
}

.ao-header-actions {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.ao-btn-edit {
  font-size: 0.8rem;
  color: #8a6f4c;
  border-color: #d6d2c8;
}

.ao-btn-edit:hover {
  color: #c45a3c;
  border-color: #c45a3c;
  background: #fdf6f0;
}

.ao-sub-nav {
  display: flex;
  justify-content: center;
  gap: 0;
  margin-bottom: 36px;
  border-bottom: 1px solid #edeae1;
  position: relative;
}

.ao-nav-item {
  display: block;
  padding: 12px 24px;
  font-size: 0.9rem;
  color: #8a8578;
  text-decoration: none;
  letter-spacing: 0.06em;
  transition: color 0.2s;
  position: relative;
  white-space: nowrap;
}

.ao-nav-item::after {
  content: '';
  position: absolute;
  bottom: 0;
  left: 50%;
  transform: translateX(-50%);
  width: 0;
  height: 2px;
  background: #c45a3c;
  transition: width 0.25s ease;
}

.ao-nav-item:hover {
  color: #3a3222;
}

.ao-nav-item.active {
  color: #3a3222;
  font-weight: 500;
}

.ao-nav-item.active::after {
  width: 60%;
}

.ao-body {
  display: flex;
  flex-direction: column;
  gap: 28px;
}

.ao-card {
  background: #fff;
  border-radius: 12px;
  padding: 28px;
  border: 1px solid #edeae1;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.04);
}

.ao-card-title {
  font-family: 'Noto Serif SC', 'KaiTi', 'STKaiti', serif;
  font-size: 1.1rem;
  font-weight: 500;
  color: #3a3222;
  margin: 0 0 20px;
  padding-left: 12px;
  border-left: 3px solid #c45a3c;
  letter-spacing: 0.06em;
}

.ao-info-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 16px;
}

.ao-info-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.ao-info-label {
  font-size: 0.75rem;
  color: #a09b8e;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

.ao-info-value {
  font-size: 0.95rem;
  color: #3a3222;
  line-height: 1.4;
}

.ao-bio-text {
  font-size: 0.95rem;
  color: #3a3222;
  line-height: 1.8;
  margin: 0;
  text-indent: 2em;
}

.ao-bio-empty {
  color: #a09b8e;
  font-size: 0.9rem;
  margin: 0;
}

.ao-timeline {
  position: relative;
  padding-left: 24px;
}

.ao-timeline::before {
  content: '';
  position: absolute;
  left: 6px;
  top: 4px;
  bottom: 4px;
  width: 2px;
  background: #edeae1;
}

.ao-timeline-item {
  position: relative;
  padding-bottom: 20px;
}

.ao-timeline-item:last-child {
  padding-bottom: 0;
}

.ao-timeline-dot {
  position: absolute;
  left: -18px;
  top: 6px;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: #c45a3c;
  border: 2px solid #fafaf8;
  box-shadow: 0 0 0 2px #dbbca8;
}

.ao-timeline-content {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.ao-timeline-year {
  font-family: 'Noto Serif SC', 'KaiTi', 'STKaiti', serif;
  font-size: 0.85rem;
  font-weight: 500;
  color: #c45a3c;
}

.ao-timeline-desc {
  font-size: 0.9rem;
  color: #3a3222;
  line-height: 1.5;
}

.ao-stats-row {
  display: flex;
  gap: 24px;
  justify-content: center;
}

.ao-stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  min-width: 100px;
}

.ao-stat-number {
  font-family: 'Noto Serif SC', 'KaiTi', 'STKaiti', serif;
  font-size: 1.75rem;
  font-weight: 500;
  color: #c45a3c;
}

.ao-stat-label {
  font-size: 0.8rem;
  color: #8a8578;
  letter-spacing: 0.06em;
}

.ao-masterpieces-scroll {
  display: flex;
  gap: 16px;
  overflow-x: auto;
  padding: 4px 4px 12px;
  scroll-snap-type: x mandatory;
  -webkit-overflow-scrolling: touch;
}

.ao-masterpieces-scroll::-webkit-scrollbar {
  height: 6px;
}

.ao-masterpieces-scroll::-webkit-scrollbar-track {
  background: transparent;
}

.ao-masterpieces-scroll::-webkit-scrollbar-thumb {
  background: #d6d2c8;
  border-radius: 3px;
}

.ao-masterpiece-item {
  flex-shrink: 0;
  width: 160px;
  scroll-snap-align: start;
}

.ao-masterpiece-thumb {
  width: 160px;
  height: 120px;
  border-radius: 8px;
  overflow: hidden;
  background: #f5f0ea;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 8px;
}

.ao-masterpiece-thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.ao-thumb-placeholder {
  font-size: 1.5rem;
  opacity: 0.5;
}

.ao-masterpiece-info {
  text-align: center;
}

.ao-masterpiece-title {
  font-size: 0.85rem;
  color: #3a3222;
  margin: 0 0 2px;
  line-height: 1.3;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ao-masterpiece-year {
  font-size: 0.75rem;
  color: #a09b8e;
  margin: 0;
}

@media (max-width: 768px) {
  .ao-page {
    padding: 24px 16px 60px;
  }

  .ao-header {
    flex-direction: column;
    align-items: center;
    text-align: center;
    gap: 16px;
  }

  .ao-header-actions {
    justify-content: center;
  }

  .ao-name {
    font-size: 1.5rem;
  }

  .ao-sub-nav {
    gap: 0;
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
  }

  .ao-nav-item {
    padding: 10px 14px;
    font-size: 0.82rem;
  }

  .ao-card {
    padding: 20px;
  }

  .ao-info-grid {
    grid-template-columns: 1fr 1fr;
    gap: 12px;
  }

  .ao-stats-row {
    gap: 12px;
  }

  .ao-stat-item {
    min-width: 80px;
  }

  .ao-stat-number {
    font-size: 1.4rem;
  }

  .ao-masterpiece-item {
    width: 130px;
  }

  .ao-masterpiece-thumb {
    width: 130px;
    height: 100px;
  }
}
</style>
