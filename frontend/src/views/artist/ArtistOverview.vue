<template>
  <div class="bk-page">
    <div v-if="loading" class="bk-loading">加载中...</div>

    <div v-else-if="notFound" class="bk-not-found">
      <div class="bk-not-found-icon">?</div>
      <h2>未找到该画家</h2>
      <p>请确认名称是否正确，或返回<router-link to="/artists">艺术家列表</router-link>浏览</p>
    </div>

    <template v-else-if="artist">
      <div class="bk-hero" :style="heroStyle">
        <div class="bk-hero-overlay" />
        <div class="bk-hero-content">
          <div class="bk-hero-left">
            <div v-if="artist.avatar_url" class="bk-hero-avatar-wrap">
              <img :src="artist.avatar_url" :alt="artist.name" class="bk-hero-avatar" />
            </div>
            <div v-else class="bk-hero-avatar bk-hero-avatar-text">{{ artist.name?.charAt(0) || '?' }}</div>
            <div class="bk-hero-text">
              <h1 class="bk-hero-name">{{ artist.name }}</h1>
              <p v-if="artist.alias" class="bk-hero-alias">{{ artist.alias }}</p>
              <div class="bk-hero-tags">
                <span v-if="artist.dynasty" class="bk-hero-tag">{{ artist.dynasty }}</span>
                <span v-if="artist.art_school" class="bk-hero-tag bk-hero-tag-school">{{ artist.art_school }}</span>
                <span v-if="artist.birth_year || artist.death_year" class="bk-hero-tag">{{ formatYears(artist.birth_year, artist.death_year) }}</span>
              </div>
            </div>
          </div>
          <div v-if="authStore.isEditor" class="bk-hero-actions">
            <el-button size="small" plain class="bk-btn-ghost" @click="handleEdit">编辑</el-button>
            <el-button size="small" plain class="bk-btn-ghost" @click="handleMyChanges">我的修改</el-button>
          </div>
        </div>
      </div>

      <nav class="bk-sub-nav">
        <router-link
          v-for="tab in subNavTabs"
          :key="tab.name"
          :to="{ name: tab.name, params: { name: artistName } }"
          class="bk-nav-item"
          :class="{ active: route.name === tab.name }"
        >
          {{ tab.label }}
        </router-link>
        <a v-if="artist.baidu_url" :href="artist.baidu_url" target="_blank" class="bk-nav-item bk-nav-external">去百科 &rarr;</a>
      </nav>

      <div class="bk-body">
        <aside class="bk-sidebar">
          <section class="bk-card">
            <h2 class="bk-card-title">基本信息</h2>
            <table class="bk-info-table">
              <tr v-if="artist.name">
                <td class="bk-info-label">本名</td>
                <td class="bk-info-value">{{ artist.name }}</td>
              </tr>
              <tr v-if="artist.alias">
                <td class="bk-info-label">别号</td>
                <td class="bk-info-value">{{ artist.alias }}</td>
              </tr>
              <tr v-if="artist.alias && artist.alias.includes(',')">
                <td class="bk-info-label">字/号</td>
                <td class="bk-info-value">{{ artist.alias }}</td>
              </tr>
              <tr v-if="artist.dynasty">
                <td class="bk-info-label">朝代</td>
                <td class="bk-info-value">{{ artist.dynasty }}</td>
              </tr>
              <tr v-if="artist.hometown">
                <td class="bk-info-label">出生地</td>
                <td class="bk-info-value">{{ artist.hometown }}</td>
              </tr>
              <tr v-if="artist.nationality">
                <td class="bk-info-label">国籍</td>
                <td class="bk-info-value">{{ artist.nationality }}</td>
              </tr>
              <tr v-if="artist.birth_year || artist.death_year">
                <td class="bk-info-label">出生日期</td>
                <td class="bk-info-value">{{ artist.birth_year || '不详' }}</td>
              </tr>
              <tr v-if="artist.birth_year || artist.death_year">
                <td class="bk-info-label">逝世日期</td>
                <td class="bk-info-value">{{ artist.death_year || '不详' }}</td>
              </tr>
              <tr v-if="artist.occupation">
                <td class="bk-info-label">职业</td>
                <td class="bk-info-value">{{ artist.occupation }}</td>
              </tr>
              <tr v-if="artist.art_school">
                <td class="bk-info-label">画派</td>
                <td class="bk-info-value">{{ artist.art_school }}</td>
              </tr>
              <tr v-if="artist.main_achievements">
                <td class="bk-info-label">主要成就</td>
                <td class="bk-info-value">{{ artist.main_achievements }}</td>
              </tr>
              <tr v-if="artist.representative_works_text">
                <td class="bk-info-label">代表作品</td>
                <td class="bk-info-value">{{ artist.representative_works_text }}</td>
              </tr>
            </table>
          </section>

          <section class="bk-card">
            <h2 class="bk-card-title">数据概览</h2>
            <div class="bk-stats-grid">
              <div class="bk-stat-item">
                <span class="bk-stat-number">{{ stats.total ?? '-' }}</span>
                <span class="bk-stat-label">作品</span>
              </div>
              <div class="bk-stat-item">
                <span class="bk-stat-number">{{ stats.analyzed ?? '-' }}</span>
                <span class="bk-stat-label">已分析</span>
              </div>
              <div class="bk-stat-item">
                <span class="bk-stat-number">{{ stats.seal_count ?? '-' }}</span>
                <span class="bk-stat-label">印章</span>
              </div>
            </div>
          </section>

          <section v-if="tags.length > 0" class="bk-card">
            <h2 class="bk-card-title">标签</h2>
            <div class="bk-tags-wrap">
              <span v-for="(tag, idx) in tags" :key="idx" class="bk-tag-item">{{ tag }}</span>
            </div>
          </section>
        </aside>

        <main class="bk-main">
          <section v-if="artist.summary || artist.biography" class="bk-card">
            <h2 class="bk-card-title">概述</h2>
            <p class="bk-text">{{ artist.summary || artist.biography }}</p>
          </section>

          <section v-if="artist.biography" class="bk-card">
            <h2 class="bk-card-title">人物生平</h2>
            <p class="bk-text">{{ artist.biography }}</p>
            <div v-if="timelineEvents.length > 0" class="bk-timeline">
              <div v-for="(evt, idx) in timelineEvents" :key="idx" class="bk-timeline-item">
                <div class="bk-timeline-dot" />
                <div class="bk-timeline-content">
                  <span v-if="evt.year" class="bk-timeline-year">{{ evt.year }}</span>
                  <span class="bk-timeline-desc">{{ evt.event || evt.description || '' }}</span>
                </div>
              </div>
            </div>
          </section>

          <section v-if="artChronology.length > 0" class="bk-card">
            <h2 class="bk-card-title">艺术年谱</h2>
            <div class="bk-chronology">
              <div v-for="(item, idx) in artChronology" :key="idx" class="bk-chrono-item">
                <div class="bk-chrono-year">{{ item.year }}</div>
                <div class="bk-chrono-body">
                  <div class="bk-chrono-event">{{ item.event }}</div>
                  <p v-if="item.description" class="bk-chrono-desc">{{ item.description }}</p>
                </div>
              </div>
            </div>
          </section>

          <section v-if="artist.art_style" class="bk-card">
            <h2 class="bk-card-title">艺术特色</h2>
            <p class="bk-text" v-html="renderMarkdown(artist.art_style)" />
          </section>

          <section v-if="artist.main_achievements" class="bk-card">
            <h2 class="bk-card-title">主要成就</h2>
            <p class="bk-text">{{ artist.main_achievements }}</p>
          </section>

          <section v-if="artist.influence" class="bk-card">
            <h2 class="bk-card-title">后世影响</h2>
            <p class="bk-text">{{ artist.influence }}</p>
          </section>

          <section v-if="artist.historical_evaluation" class="bk-card">
            <h2 class="bk-card-title">历史评价</h2>
            <p class="bk-text">{{ artist.historical_evaluation }}</p>
          </section>

          <section v-if="characterRelations.length > 0" class="bk-card">
            <h2 class="bk-card-title">人物关系</h2>
            <div class="bk-relations-row">
              <div v-for="(rel, idx) in characterRelations" :key="idx" class="bk-relation-card" @click="goToRelationArtist(rel)">
                <el-avatar v-if="rel.image_url" :src="rel.image_url" :size="48" shape="circle" />
                <el-avatar v-else :size="48" shape="circle" style="background:#c45a3c;color:#fff;font-size:18px">{{ (rel.name || '?').charAt(0) }}</el-avatar>
                <div class="bk-relation-name">{{ rel.name }}</div>
                <el-tag size="small" type="warning">{{ rel.relationship }}</el-tag>
                <p v-if="rel.description" class="bk-relation-desc">{{ rel.description }}</p>
              </div>
            </div>
          </section>

          <section v-if="anecdotes.length > 0" class="bk-card">
            <h2 class="bk-card-title">轶事典故</h2>
            <div v-for="(item, idx) in anecdotes" :key="idx" class="bk-anecdote-item">
              <div class="bk-anecdote-header" @click="toggleAnecdote(idx)">
                <span class="bk-anecdote-title">{{ item.title || `轶事 ${idx + 1}` }}</span>
                <span class="bk-anecdote-toggle">{{ expandedAnecdote === idx ? '−' : '+' }}</span>
              </div>
              <div v-show="expandedAnecdote === idx" class="bk-anecdote-body">
                <p class="bk-text">{{ item.content || item.description || '' }}</p>
              </div>
            </div>
          </section>

          <section v-if="masterpieces.length > 0" class="bk-card">
            <h2 class="bk-card-title">代表作品</h2>
            <div class="bk-masterpiece-grid">
              <div v-for="item in masterpieces" :key="item.id || item.title" class="bk-masterpiece-item" @click="goToWork(item.id)">
                <div class="bk-masterpiece-thumb">
                  <img v-if="item.thumbnail_url || item.image_url" :src="item.thumbnail_url || item.image_url" :alt="item.title || '作品'" />
                  <span v-else class="bk-thumb-placeholder">{{ (item.title || '?').charAt(0) }}</span>
                </div>
                <p class="bk-masterpiece-title">{{ item.title || item.work_name || '无题' }}</p>
                <p v-if="item.year" class="bk-masterpiece-year">{{ item.year }}</p>
              </div>
            </div>
          </section>

          <section v-if="publishedWorks.length > 0" class="bk-card">
            <h2 class="bk-card-title">出版著作</h2>
            <div class="bk-published-grid">
              <div v-for="(pw, idx) in publishedWorks" :key="idx" class="bk-published-item">
                <div class="bk-published-title">{{ pw.title }}</div>
                <div class="bk-published-meta">{{ [pw.publisher, pw.year].filter(Boolean).join(' · ') }}</div>
                <a v-if="pw.isbn" :href="pw.isbn.startsWith('http') ? pw.isbn : undefined" target="_blank" class="bk-published-isbn">{{ pw.isbn }}</a>
              </div>
            </div>
          </section>

          <section v-if="galleryImages.length > 0" class="bk-card">
            <h2 class="bk-card-title">作品图集</h2>
            <div class="bk-gallery-grid">
              <div v-for="(gi, idx) in galleryImages" :key="idx" class="bk-gallery-item" @click="gi.artwork_id && goToWork(gi.artwork_id)">
                <div class="bk-gallery-thumb">
                  <img v-if="gi.url" :src="gi.url" :alt="gi.title || gi.artwork_name" loading="lazy" />
                  <span v-else class="bk-thumb-placeholder">{{ (gi.title || '?').charAt(0) }}</span>
                </div>
                <p class="bk-gallery-title">{{ gi.title || gi.artwork_name || '未命名' }}</p>
              </div>
            </div>
          </section>

          <section v-if="references.length > 0" class="bk-card">
            <h2 class="bk-card-title">参考文献</h2>
            <ol class="bk-ref-list">
              <li v-for="(ref, idx) in references" :key="idx" class="bk-ref-item">{{ typeof ref === 'string' ? ref : ref.text || ref.title || '' }}</li>
            </ol>
          </section>
        </main>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../../stores/authStore'
import { ElMessage } from 'element-plus'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const API_BASE = import.meta.env.VITE_API_BASE || '/api/v1'

const artistName = computed(() => route.params.name)
const loading = ref(true)
const notFound = ref(false)
const artist = ref(null)
const stats = ref({})
const masterpieces = ref([])
const expandedAnecdote = ref(-1)

const subNavTabs = [
  { label: '概览', name: 'ArtistOverview' },
  { label: '作品', name: 'ArtistWorks' },
  { label: '印章', name: 'ArtistSeals' },
  { label: '文献', name: 'ArtistLiterature' },
  { label: '分析', name: 'ArtistAnalysis' },
]

const heroStyle = computed(() => {
  if (artist.value?.banner_url) {
    return {
      backgroundImage: `url(${artist.value.banner_url})`,
      backgroundSize: 'cover',
      backgroundPosition: 'center',
    }
  }
  return {
    background: 'linear-gradient(135deg, #3a3222 0%, #6b5b4a 40%, #8a7a6a 100%)',
  }
})

const timelineEvents = computed(() => {
  if (!artist.value?.bio_events) return []
  return parseJsonField(artist.value.bio_events)
})

const artChronology = computed(() => {
  if (!artist.value?.art_chronology) return []
  return parseJsonField(artist.value.art_chronology)
})

const characterRelations = computed(() => {
  if (!artist.value?.character_relations) return []
  return parseJsonField(artist.value.character_relations)
})

const anecdotes = computed(() => {
  if (!artist.value?.anecdotes) return []
  return parseJsonField(artist.value.anecdotes)
})

const publishedWorks = computed(() => {
  if (!artist.value?.published_works) return []
  return parseJsonField(artist.value.published_works)
})

const galleryImages = computed(() => {
  if (!artist.value?.gallery_images) return []
  return parseJsonField(artist.value.gallery_images)
})

const tags = computed(() => {
  if (!artist.value?.tags) return []
  return parseJsonField(artist.value.tags)
})

const references = computed(() => {
  if (!artist.value?.references) return []
  return parseJsonField(artist.value.references)
})

function parseJsonField(field) {
  try {
    const parsed = typeof field === 'string' ? JSON.parse(field) : field
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

function formatYears(birth, death) {
  if (!birth && !death) return ''
  const b = birth || '?'
  const d = death || '?'
  return `${b} — ${d}`
}

function renderMarkdown(text) {
  if (!text) return ''
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/^### (.+)$/gm, '<h3 class="bk-md-h3">$1</h3>')
    .replace(/^## (.+)$/gm, '<h2 class="bk-md-h2">$1</h2>')
    .replace(/\n/g, '<br>')
}

function toggleAnecdote(idx) {
  expandedAnecdote.value = expandedAnecdote.value === idx ? -1 : idx
}

function goToWork(id) {
  if (id) window.open(`/#/tubi/${id}`, '_blank')
}

function goToRelationArtist(rel) {
  if (rel.name) router.push({ name: 'ArtistOverview', params: { name: rel.name } })
}

function handleEdit() {
  router.push('/admin?tab=artist-info')
}

function handleMyChanges() {
  router.push('/admin?tab=change-requests')
}

async function fetchArtist() {
  const name = artistName.value
  if (!name) {
    notFound.value = true
    loading.value = false
    return
  }
  try {
    const res = await fetch(`${API_BASE}/artists/by-name/${encodeURIComponent(name)}`)
    if (!res.ok) {
      if (res.status === 404) notFound.value = true
      return
    }
    const data = await res.json()
    artist.value = data.artist || null
    if (!artist.value) notFound.value = true
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
  const name = artistName.value
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
.bk-page {
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 24px 80px;
  min-height: 100vh;
  background: #f5f2ed;
}
.bk-loading {
  text-align: center;
  padding: 80px 0;
  color: #8a8578;
  font-size: 0.95rem;
}
.bk-not-found {
  text-align: center;
  padding: 80px 24px;
}
.bk-not-found-icon {
  width: 80px; height: 80px;
  margin: 0 auto 20px;
  border-radius: 50%;
  background: #f0e8e0;
  color: #8a8578;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 2.25rem;
  font-family: 'Noto Serif SC', 'KaiTi', 'STKaiti', serif;
}
.bk-not-found h2 {
  font-family: 'Noto Serif SC', 'KaiTi', 'STKaiti', serif;
  font-size: 1.4rem;
  color: #3a3222;
  margin: 0 0 12px;
  font-weight: 500;
}
.bk-not-found p { color: #8a8578; font-size: 0.9rem; margin: 0; }
.bk-not-found a { color: #c45a3c; text-decoration: none; }
.bk-not-found a:hover { text-decoration: underline; }

.bk-hero {
  position: relative;
  height: 280px;
  border-radius: 0 0 16px 16px;
  overflow: hidden;
  display: flex;
  align-items: flex-end;
}
.bk-hero-overlay {
  position: absolute;
  inset: 0;
  background: linear-gradient(to top, rgba(0,0,0,0.75) 0%, rgba(0,0,0,0.3) 50%, rgba(0,0,0,0.1) 100%);
}
.bk-hero-content {
  position: relative;
  z-index: 1;
  width: 100%;
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  padding: 32px;
  gap: 16px;
}
.bk-hero-left {
  display: flex;
  align-items: flex-end;
  gap: 20px;
}
.bk-hero-avatar-wrap {
  width: 80px; height: 80px;
  flex-shrink: 0;
  border-radius: 50%;
  overflow: hidden;
  border: 3px solid rgba(255,255,255,0.8);
  box-shadow: 0 2px 12px rgba(0,0,0,0.2);
}
.bk-hero-avatar {
  width: 100%; height: 100%;
  object-fit: cover;
}
.bk-hero-avatar-text {
  background: linear-gradient(135deg, #c45a3c, #dbbca8);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: 'Noto Serif SC', 'KaiTi', 'STKaiti', serif;
  font-size: 2rem;
  font-weight: 500;
}
.bk-hero-text { flex: 1; }
.bk-hero-name {
  font-family: 'Noto Serif SC', 'KaiTi', 'STKaiti', serif;
  font-size: 2.4rem;
  font-weight: 500;
  color: #fff;
  margin: 0 0 6px;
  letter-spacing: 0.1em;
  line-height: 1.2;
  text-shadow: 0 1px 4px rgba(0,0,0,0.3);
}
.bk-hero-alias {
  font-size: 0.95rem;
  color: rgba(255,255,255,0.8);
  margin: 0 0 10px;
  line-height: 1.4;
  text-shadow: 0 1px 3px rgba(0,0,0,0.2);
}
.bk-hero-tags { display: flex; gap: 8px; flex-wrap: wrap; }
.bk-hero-tag {
  display: inline-block;
  font-size: 0.75rem;
  padding: 3px 14px;
  border-radius: 999px;
  background: rgba(255,255,255,0.2);
  color: #fff;
  letter-spacing: 0.04em;
  line-height: 1.5;
  backdrop-filter: blur(4px);
}
.bk-hero-tag-school { background: rgba(255,255,255,0.15); }
.bk-hero-actions {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
  flex-wrap: wrap;
  justify-content: flex-end;
}
.bk-btn-ghost {
  font-size: 0.8rem;
  color: rgba(255,255,255,0.85) !important;
  border-color: rgba(255,255,255,0.4) !important;
  background: transparent !important;
}
.bk-btn-ghost:hover {
  color: #fff !important;
  border-color: rgba(255,255,255,0.7) !important;
  background: rgba(255,255,255,0.1) !important;
}

.bk-sub-nav {
  display: flex;
  align-items: center;
  gap: 0;
  margin-bottom: 32px;
  border-bottom: 1px solid #e0d8ce;
  background: #fff;
  border-radius: 0 0 12px 12px;
  padding: 0 16px;
}
.bk-nav-item {
  display: block;
  padding: 14px 22px;
  font-size: 0.9rem;
  color: #7a6f5e;
  text-decoration: none;
  letter-spacing: 0.06em;
  transition: color 0.2s;
  position: relative;
  white-space: nowrap;
}
.bk-nav-item::after {
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
.bk-nav-item:hover { color: #3a3222; }
.bk-nav-item.active { color: #3a3222; font-weight: 500; }
.bk-nav-item.active::after { width: 60%; }
.bk-nav-external {
  margin-left: auto;
  color: #c45a3c;
  font-size: 0.85rem;
}
.bk-nav-external:hover { color: #a84838; }

.bk-body {
  display: flex;
  gap: 28px;
  align-items: flex-start;
}
.bk-sidebar {
  width: 300px;
  flex-shrink: 0;
  position: sticky;
  top: 24px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}
.bk-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.bk-card {
  background: #fff;
  border-radius: 12px;
  padding: 24px;
  border: 1px solid #edeae1;
  box-shadow: 0 1px 6px rgba(0,0,0,0.04);
}
.bk-card-title {
  font-family: 'Noto Serif SC', 'KaiTi', 'STKaiti', serif;
  font-size: 1.05rem;
  font-weight: 500;
  color: #3a3222;
  margin: 0 0 18px;
  padding-left: 12px;
  border-left: 3px solid #c45a3c;
  letter-spacing: 0.08em;
}

.bk-info-table {
  width: 100%;
  border-collapse: collapse;
}
.bk-info-table tr {
  border-bottom: 1px solid #f0ece4;
}
.bk-info-table tr:last-child {
  border-bottom: none;
}
.bk-info-table td {
  padding: 8px 0;
  vertical-align: top;
  line-height: 1.5;
}
.bk-info-label {
  width: 72px;
  font-size: 0.78rem;
  color: #a09b8e;
  letter-spacing: 0.04em;
  white-space: nowrap;
  padding-right: 8px;
}
.bk-info-value {
  font-size: 0.9rem;
  color: #3a3222;
}

.bk-stats-grid {
  display: flex;
  gap: 0;
  justify-content: space-around;
}
.bk-stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  min-width: 70px;
}
.bk-stat-number {
  font-family: 'Noto Serif SC', 'KaiTi', 'STKaiti', serif;
  font-size: 1.6rem;
  font-weight: 500;
  color: #c45a3c;
}
.bk-stat-label {
  font-size: 0.75rem;
  color: #8a8578;
  letter-spacing: 0.06em;
}

.bk-tags-wrap {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.bk-tag-item {
  display: inline-block;
  font-size: 0.75rem;
  padding: 4px 14px;
  border-radius: 999px;
  background: #f0ece4;
  color: #6b5b4a;
  letter-spacing: 0.04em;
}

.bk-text {
  font-size: 0.95rem;
  color: #3a3222;
  line-height: 1.8;
  margin: 0;
}

.bk-timeline {
  position: relative;
  padding-left: 24px;
  margin-top: 20px;
}
.bk-timeline::before {
  content: '';
  position: absolute;
  left: 6px;
  top: 4px;
  bottom: 4px;
  width: 2px;
  background: #edeae1;
}
.bk-timeline-item {
  position: relative;
  padding-bottom: 18px;
}
.bk-timeline-item:last-child { padding-bottom: 0; }
.bk-timeline-dot {
  position: absolute;
  left: -18px;
  top: 6px;
  width: 10px; height: 10px;
  border-radius: 50%;
  background: #c45a3c;
  border: 2px solid #fff;
  box-shadow: 0 0 0 2px #dbbca8;
}
.bk-timeline-content {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.bk-timeline-year {
  font-family: 'Noto Serif SC', 'KaiTi', 'STKaiti', serif;
  font-size: 0.85rem;
  font-weight: 500;
  color: #c45a3c;
}
.bk-timeline-desc {
  font-size: 0.9rem;
  color: #3a3222;
  line-height: 1.5;
}

.bk-chronology {
  position: relative;
}
.bk-chrono-item {
  display: flex;
  gap: 16px;
  padding-bottom: 20px;
  position: relative;
}
.bk-chrono-item:last-child { padding-bottom: 0; }
.bk-chrono-item::before {
  content: '';
  position: absolute;
  left: 60px;
  top: 24px;
  bottom: 0;
  width: 1px;
  background: #edeae1;
}
.bk-chrono-item:last-child::before { display: none; }
.bk-chrono-year {
  width: 60px;
  flex-shrink: 0;
  font-family: 'Noto Serif SC', 'KaiTi', 'STKaiti', serif;
  font-size: 0.95rem;
  font-weight: 500;
  color: #c45a3c;
  padding-top: 2px;
  position: relative;
}
.bk-chrono-year::after {
  content: '';
  position: absolute;
  right: -8px;
  top: 8px;
  width: 8px; height: 8px;
  border-radius: 50%;
  background: #c45a3c;
  border: 2px solid #fff;
  box-shadow: 0 0 0 2px #dbbca8;
}
.bk-chrono-body {
  flex: 1;
  padding-left: 16px;
}
.bk-chrono-event {
  font-size: 0.95rem;
  font-weight: 500;
  color: #3a3222;
  margin-bottom: 4px;
}
.bk-chrono-desc {
  font-size: 0.88rem;
  color: #6b5b4a;
  line-height: 1.6;
  margin: 0;
}

.bk-md-h2 {
  font-family: 'Noto Serif SC', 'KaiTi', 'STKaiti', serif;
  font-size: 1rem;
  font-weight: 500;
  color: #3a3222;
  margin: 16px 0 8px;
}
.bk-md-h3 {
  font-family: 'Noto Serif SC', 'KaiTi', 'STKaiti', serif;
  font-size: 0.95rem;
  font-weight: 500;
  color: #3a3222;
  margin: 12px 0 6px;
}

.bk-relations-row {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}
.bk-relation-card {
  flex: 1;
  min-width: 160px;
  max-width: 260px;
  padding: 14px 16px;
  border-radius: 8px;
  border: 1px solid #edeae1;
  background: #faf8f5;
}
.bk-relation-name {
  font-size: 0.95rem;
  font-weight: 500;
  color: #3a3222;
}
.bk-relation-role {
  font-size: 0.8rem;
  color: #c45a3c;
  margin: 2px 0 6px;
}
.bk-relation-desc {
  font-size: 0.85rem;
  color: #6b5b4a;
  line-height: 1.5;
  margin: 0;
}

.bk-anecdote-item {
  border-bottom: 1px solid #f0ece4;
}
.bk-anecdote-item:last-child {
  border-bottom: none;
}
.bk-anecdote-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 0;
  cursor: pointer;
  user-select: none;
}
.bk-anecdote-header:hover {
  color: #c45a3c;
}
.bk-anecdote-title {
  font-size: 0.95rem;
  font-weight: 500;
  color: inherit;
}
.bk-anecdote-toggle {
  font-size: 1.2rem;
  color: #c45a3c;
  width: 24px;
  text-align: center;
  flex-shrink: 0;
}
.bk-anecdote-body {
  padding-bottom: 16px;
}

.bk-masterpiece-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 16px;
}
.bk-masterpiece-item {
  cursor: pointer;
  transition: transform 0.2s;
  text-align: center;
}
.bk-masterpiece-item:hover {
  transform: translateY(-3px);
}
.bk-masterpiece-thumb {
  width: 100%;
  aspect-ratio: 4 / 3;
  border-radius: 8px;
  overflow: hidden;
  background: #f0ece4;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 8px;
}
.bk-masterpiece-thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.bk-thumb-placeholder {
  font-family: 'Noto Serif SC', serif;
  font-size: 1.5rem;
  color: #a09b8e;
}
.bk-masterpiece-title {
  font-size: 0.85rem;
  color: #3a3222;
  margin: 0 0 2px;
  line-height: 1.3;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.bk-masterpiece-year {
  font-size: 0.75rem;
  color: #a09b8e;
  margin: 0;
}

.bk-ref-list {
  margin: 0;
  padding-left: 20px;
}
.bk-ref-item {
  font-size: 0.88rem;
  color: #3a3222;
  line-height: 1.7;
  margin-bottom: 4px;
}

.bk-published-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 12px; }
.bk-published-item { padding: 14px; background: #fafaf8; border: 1px solid #edeae1; border-radius: 8px; }
.bk-published-title { font-size: 14px; font-weight: 600; color: #3a3222; margin-bottom: 4px; font-family: 'Noto Serif SC', serif; }
.bk-published-meta { font-size: 12px; color: #8a8578; }
.bk-published-isbn { font-size: 11px; color: #c45a3c; display: block; margin-top: 4px; }

.bk-gallery-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 14px; }
.bk-gallery-item { cursor: pointer; transition: transform 0.2s; }
.bk-gallery-item:hover { transform: translateY(-2px); }
.bk-gallery-thumb { width: 100%; aspect-ratio: 3/4; border-radius: 8px; overflow: hidden; background: #f5f3ed; display: flex; align-items: center; justify-content: center; }
.bk-gallery-thumb img { width: 100%; height: 100%; object-fit: cover; }
.bk-gallery-title { font-size: 12px; color: #3a3222; margin: 6px 0 0; text-align: center; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

@media (max-width: 900px) {
  .bk-body {
    flex-direction: column;
  }
  .bk-sidebar {
    width: 100%;
    position: static;
    order: 0;
  }
  .bk-main {
    order: 1;
  }
  .bk-hero {
    height: 220px;
  }
  .bk-hero-content {
    padding: 20px;
  }
  .bk-hero-name {
    font-size: 1.6rem;
  }
  .bk-hero-avatar-wrap {
    width: 56px; height: 56px;
  }
  .bk-hero-avatar-text {
    width: 56px; height: 56px;
    font-size: 1.4rem;
  }
  .bk-sub-nav {
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
    padding: 0 8px;
  }
  .bk-nav-item {
    padding: 12px 14px;
    font-size: 0.82rem;
  }
  .bk-card {
    padding: 18px;
  }
  .bk-relations-row {
    flex-direction: column;
  }
  .bk-relation-card {
    max-width: none;
  }
  .bk-masterpiece-grid {
    grid-template-columns: repeat(auto-fill, minmax(110px, 1fr));
    gap: 12px;
  }
}
</style>