<template>
  <div class="artist-sub-page">
    <div class="asp-header">
      <h2><router-link :to="{ name: 'ArtistOverview', params: { name: artistName } }" class="asp-back-link">{{ artistName }}</router-link> 的文献</h2>
    </div>
    <div class="asp-sub-nav">
      <router-link :to="{ name: 'ArtistOverview', params: { name: artistName } }" class="asp-nav-item">概览</router-link>
      <router-link :to="{ name: 'ArtistWorks', params: { name: artistName } }" class="asp-nav-item">作品</router-link>
      <router-link :to="{ name: 'ArtistSeals', params: { name: artistName } }" class="asp-nav-item">印章</router-link>
      <router-link :to="{ name: 'ArtistLiterature', params: { name: artistName } }" class="asp-nav-item active">文献</router-link>
      <router-link :to="{ name: 'ArtistAnalysis', params: { name: artistName } }" class="asp-nav-item">分析</router-link>
    </div>
    <div v-if="loading" class="asp-loading">搜索相关文献...</div>
    <div v-else-if="literature.length === 0" class="asp-empty">
      <p>暂无关联文献</p>
      <p class="asp-empty-hint">文献著录功能开发中，敬请期待</p>
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
.artist-sub-page { max-width: 1100px; margin: 0 auto; padding: 24px 20px; min-height: 100vh; background: #fafaf8; }
.asp-header h2 { font-family: 'Noto Serif SC', serif; font-size: 22px; color: #3a3222; margin: 0 0 16px; }
.asp-back-link { color: #3a3222; text-decoration: none; }
.asp-sub-nav { display: flex; gap: 0; border-bottom: 1px solid #edeae1; margin-bottom: 24px; }
.asp-nav-item { padding: 10px 20px; font-size: 14px; color: #8c7a5c; text-decoration: none; border-bottom: 2px solid transparent; }
.asp-nav-item:hover { color: #c45a3c; }
.asp-nav-item.active { color: #c45a3c; border-bottom-color: #c45a3c; font-weight: 500; }
.asp-loading, .asp-empty { text-align: center; padding: 60px 0; color: #b0a890; font-size: 15px; }
.asp-empty-hint { font-size: 13px; color: #ccc; margin-top: 8px; }
.al-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 16px; }
.al-card { display: flex; gap: 14px; background: #fff; border: 1px solid #edeae1; border-radius: 8px; padding: 16px; }
.al-card-icon { font-size: 28px; flex-shrink: 0; }
.al-card-info { min-width: 0; }
.al-card-title { font-size: 14px; font-weight: 500; color: #3a3222; margin-bottom: 4px; }
.al-card-author { font-size: 12px; color: #8a8578; }
.al-card-source { font-size: 12px; color: #b0a890; margin-top: 2px; }
</style>
