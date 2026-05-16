<template>
  <div class="artist-sub-page">
    <div class="asp-header">
      <h2><router-link :to="{ name: 'ArtistOverview', params: { name: artistName } }" class="asp-back-link">{{ artistName }}</router-link> 的印章</h2>
    </div>
    <div class="asp-sub-nav">
      <router-link :to="{ name: 'ArtistOverview', params: { name: artistName } }" class="asp-nav-item">概览</router-link>
      <router-link :to="{ name: 'ArtistWorks', params: { name: artistName } }" class="asp-nav-item">作品</router-link>
      <router-link :to="{ name: 'ArtistSeals', params: { name: artistName } }" class="asp-nav-item active">印章</router-link>
      <router-link :to="{ name: 'ArtistLiterature', params: { name: artistName } }" class="asp-nav-item">文献</router-link>
      <router-link :to="{ name: 'ArtistAnalysis', params: { name: artistName } }" class="asp-nav-item">分析</router-link>
    </div>
    <div v-if="loading" class="asp-loading">加载中...</div>
    <div v-else-if="seals.length === 0" class="asp-empty">暂无印章数据</div>
    <div v-else class="as-grid">
      <div v-for="s in seals" :key="s.id" class="as-card">
        <div v-if="s.images && s.images.length > 0" class="as-image-wrap">
          <img v-for="(img, i) in s.images.slice(0, 3)" :key="i" :src="img" class="as-image" :alt="s.name" />
        </div>
        <div v-else class="as-image-placeholder">印</div>
        <div class="as-info">
          <div class="as-name">{{ s.name }}</div>
          <div class="as-type">{{ s.seal_type || '印章' }}</div>
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
const seals = ref([])
const loading = ref(true)

async function fetchSeals() {
  try {
    const res = await fetch(`${API_BASE}/seals?artist=${encodeURIComponent(artistName)}&limit=100`)
    const data = await res.json()
    seals.value = data.seals || data.records || data.results || data.data || []
  } catch (e) { console.error(e) }
  finally { loading.value = false }
}

onMounted(fetchSeals)
</script>

<style scoped>
.artist-sub-page { max-width: 1100px; margin: 0 auto; padding: 24px 20px; min-height: 100vh; background: #fafaf8; }
.asp-header h2 { font-family: 'Noto Serif SC', serif; font-size: 22px; color: #3a3222; margin: 0 0 16px; }
.asp-back-link { color: #3a3222; text-decoration: none; }
.asp-back-link:hover { color: #c45a3c; }
.asp-sub-nav { display: flex; gap: 0; border-bottom: 1px solid #edeae1; margin-bottom: 24px; }
.asp-nav-item { padding: 10px 20px; font-size: 14px; color: #8c7a5c; text-decoration: none; border-bottom: 2px solid transparent; transition: all 0.2s; }
.asp-nav-item:hover { color: #c45a3c; }
.asp-nav-item.active { color: #c45a3c; border-bottom-color: #c45a3c; font-weight: 500; }
.asp-loading, .asp-empty { text-align: center; padding: 60px 0; color: #b0a890; font-size: 15px; }
.as-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 16px; }
.as-card { background: #fff; border: 1px solid #edeae1; border-radius: 8px; padding: 16px; text-align: center; }
.as-image-wrap { display: flex; gap: 4px; justify-content: center; margin-bottom: 12px; }
.as-image { width: 60px; height: 60px; object-fit: contain; border: 1px solid #edeae1; border-radius: 4px; }
.as-image-placeholder { width: 80px; height: 80px; margin: 0 auto 12px; background: #f5f3ed; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 28px; color: #c45a3c; font-family: 'Noto Serif SC', serif; }
.as-name { font-size: 15px; color: #3a3222; font-weight: 500; }
.as-type { font-size: 12px; color: #b0a890; margin-top: 4px; }
</style>
