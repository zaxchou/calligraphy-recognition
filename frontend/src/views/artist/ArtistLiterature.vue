<template>
  <div class="av-page">
    <header class="av-header">
      <div class="av-header-inner">
        <h1 class="av-name">
          <router-link :to="{ name: 'ArtistOverview', params: { name: artistName } }" class="av-name-link">{{ artistName }}</router-link>
          <span class="av-name-suffix">· 文献</span>
        </h1>
      </div>
    </header>

    <nav class="av-sub-nav">
      <router-link :to="{ name: 'ArtistOverview', params: { name: artistName } }" class="av-nav-link">概览</router-link>
      <router-link :to="{ name: 'ArtistWorks', params: { name: artistName } }" class="av-nav-link">作品</router-link>
      <router-link :to="{ name: 'ArtistSeals', params: { name: artistName } }" class="av-nav-link">印章</router-link>
      <router-link :to="{ name: 'ArtistLiterature', params: { name: artistName } }" class="av-nav-link active">文献</router-link>
      <router-link :to="{ name: 'ArtistAnalysis', params: { name: artistName } }" class="av-nav-link">分析</router-link>
    </nav>

    <div v-if="loading" class="av-loading">搜索相关文献...</div>
    <div v-else-if="literature.length === 0" class="av-empty">
      <p>暂无关联文献</p>
      <p class="av-empty-hint">文献著录功能开发中，敬请期待</p>
    </div>
    <div v-else class="al-grid">
      <div v-for="doc in literature" :key="doc.id" class="al-card">
        <div class="al-card-icon">&#128214;</div>
        <div class="al-card-info">
          <div class="al-card-title">{{ doc.title }}</div>
          <div v-if="doc.author" class="al-card-author">{{ doc.author }}</div>
          <div v-if="doc.source" class="al-card-source">{{ doc.source }}</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const API_BASE = import.meta.env.VITE_API_BASE || '/api/v1'
const artistName = route.params.name
const literature = ref([])
const loading = ref(true)

async function fetchLiterature() {
  try {
    const res = await fetch(`${API_BASE}/libraries?artist=${encodeURIComponent(artistName)}&limit=50`)
    if (res.ok) {
      const data = await res.json()
      literature.value = data.libraries || data.records || data.results || data.data || []
    }
  } catch (e) { console.error(e) }
  finally { loading.value = false }
}

onMounted(fetchLiterature)
</script>

<style scoped>
.av-page { max-width: var(--container-wide); margin: 0 auto; padding: 0 24px 120px; min-height: 100vh; background: #faf8f5; }
.av-loading, .av-empty { text-align: center; padding: 80px 0; color: #8a8578; font-size: 15px; }
.av-empty-hint { font-size: 13px; color: #c0b8a8; margin-top: 8px; }

.av-header { padding: 32px 0 12px; }
.av-header-inner { display: flex; align-items: baseline; }
.av-name { font-family: 'Noto Serif SC', serif; font-size: 24px; font-weight: 700; color: #2c2416; margin: 0; }
.av-name-link { color: #2c2416; text-decoration: none; }
.av-name-link:hover { color: #c45a3c; }
.av-name-suffix { font-weight: 400; color: #8a8578; font-size: 20px; }

.av-sub-nav { display: flex; gap: 4px; padding: 16px 0; margin-bottom: 24px; border-bottom: 1px solid #e8e3da; overflow-x: auto; }
.av-nav-link { padding: 8px 18px; font-size: 13px; color: #8c7a5c; text-decoration: none; border-radius: 6px; transition: all 0.15s; white-space: nowrap; }
.av-nav-link:hover { background: #f5f0e8; color: #3a3222; }
.av-nav-link.active { background: #fdf6f0; color: #c45a3c; font-weight: 600; }

.al-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 14px; }
.al-card { display: flex; gap: 14px; background: #fff; border: 1px solid #e8e3da; border-radius: 10px; padding: 18px; transition: all 0.2s; }
.al-card:hover { border-color: #d0b898; box-shadow: 0 2px 12px rgba(0,0,0,0.05); }
.al-card-icon { font-size: 28px; flex-shrink: 0; }
.al-card-info { min-width: 0; }
.al-card-title { font-size: 14px; font-weight: 600; color: #2c2416; margin-bottom: 6px; font-family: 'Noto Serif SC', serif; }
.al-card-author { font-size: 12px; color: #8a8578; }
.al-card-source { font-size: 12px; color: #b0a890; margin-top: 2px; }

@media (max-width: 768px) { .av-page { padding: 0 16px 80px; } }
</style>
