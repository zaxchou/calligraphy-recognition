<template>
  <div class="as-page">
    <div class="as-toolbar">
      <div class="as-search">
        <el-icon class="as-search-icon"><Search /></el-icon>
        <input v-model="searchText" placeholder="搜索印章名称..." class="as-search-input" />
        <span v-if="searchText" class="as-search-clear" @click="searchText = ''">✕</span>
      </div>
      <span class="as-count">{{ filteredSeals.length }} / {{ seals.length }} 方</span>
    </div>

    <div v-if="loading" class="av-loading">加载中...</div>
    <div v-else-if="seals.length === 0" class="av-empty">暂无印章数据</div>
    <div v-else-if="filteredSeals.length === 0" class="av-empty">无匹配印章</div>
    <div v-else class="as-grid">
      <div v-for="s in filteredSeals" :key="s.id" class="as-card" @click="openLightbox(s)">
        <div v-if="s.images && s.images.length > 0" class="as-image-wrap">
          <div v-if="s.images.length > 1" class="as-badge">{{ s.images.length }}图</div>
          <img :src="getImageUrl(s.images[0].thumb_url || s.images[0].path || s.images[0])" class="as-image" :alt="s.name" />
        </div>
        <div v-else class="as-image-placeholder">印</div>
        <div class="as-info">
          <div class="as-name">{{ s.name }}</div>
          <div class="as-type">{{ s.seal_type || '印章' }}</div>
          <div v-if="s.source" class="as-source" :title="s.source">{{ s.source }}</div>
        </div>
      </div>
    </div>

    <SealLightbox :visible="lightboxVisible" :seal="selectedSeal" @close="lightboxVisible = false" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { Search } from '@element-plus/icons-vue'
import SealLightbox from '@/components/seal/SealLightbox.vue'

const route = useRoute()
const API_BASE = import.meta.env.VITE_API_BASE || '/api/v1'
const STATIC_ORIGIN = window.location.origin

const artistName = route.params.name
const loading = ref(true)
const seals = ref([])
const searchText = ref('')

const filteredSeals = computed(() => {
  const q = searchText.value.trim().toLowerCase()
  if (!q) return seals.value
  return seals.value.filter(s => s.name.toLowerCase().includes(q))
})

const lightboxVisible = ref(false)
const selectedSeal = ref({})

function getImageUrl(path) {
  if (!path) return ''
  const p = typeof path === 'string' ? path : (path.path || '')
  if (!p) return ''
  if (p.startsWith('http')) return p
  return `${STATIC_ORIGIN}${p}`
}

function openLightbox(seal) {
  selectedSeal.value = seal
  lightboxVisible.value = true
}

async function fetchSeals() {
  try {
    const res = await fetch(`${API_BASE}/seals?artist=${encodeURIComponent(artistName)}`)
    if (res.ok) {
      const data = await res.json()
      seals.value = data.seals || data.items || []
    }
  } catch (e) {
    console.error('获取印章失败:', e)
  } finally {
    loading.value = false
  }
}

onMounted(() => fetchSeals())
</script>

<style scoped>
.av-loading, .av-empty { text-align: center; padding: 80px 0; color: #8a8578; font-size: 15px; }

.as-toolbar { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; gap: 12px; }
.as-search { position: relative; flex: 1; max-width: 320px; }
.as-search-icon { position: absolute; left: 12px; top: 50%; transform: translateY(-50%); color: #b0a898; font-size: 14px; }
.as-search-input { width: 100%; padding: 10px 36px 10px 36px; border: 1px solid #e0dcd0; border-radius: 8px; background: #fff; font-size: 13px; color: #3a3222; outline: none; transition: border-color 0.2s; font-family: inherit; }
.as-search-input:focus { border-color: #c45a3c; }
.as-search-input::placeholder { color: #c0b8a8; }
.as-search-clear { position: absolute; right: 12px; top: 50%; transform: translateY(-50%); color: #c0b8a8; cursor: pointer; font-size: 12px; line-height: 1; }
.as-search-clear:hover { color: #8a8578; }
.as-count { font-size: 13px; color: #8a8578; white-space: nowrap; }

.as-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 14px; }
.as-card { background: #fff; border: 1px solid #e8e3da; border-radius: 8px; overflow: hidden; transition: all 0.2s; cursor: pointer; }
.as-card:hover { transform: translateY(-2px); box-shadow: 0 4px 16px rgba(0,0,0,0.06); }
.as-image-wrap { width: 100%; aspect-ratio: 1; background: #f5f0e8; display: flex; align-items: center; justify-content: center; overflow: hidden; position: relative; }
.as-image { width: 100%; height: 100%; object-fit: contain; padding: 0; box-sizing: border-box; }
.as-image-placeholder { width: 100%; aspect-ratio: 1; background: #f5f0e8; display: flex; align-items: center; justify-content: center; font-family: 'Noto Serif SC', serif; font-size: 36px; color: #c45a3c; }
.as-badge { position: absolute; top: 4px; right: 4px; background: rgba(196, 90, 60, 0.88); color: #fff; font-size: 10px; padding: 1px 5px; border-radius: 3px; z-index: 1; }
.as-info { padding: 4px 0 0; text-align: center; }
.as-name { font-size: 12px; font-weight: 600; color: #2c2416; margin-bottom: 0; font-family: 'Noto Serif SC', serif; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.as-type { font-size: 11px; color: #8a8578; }
.as-source { font-size: 10px; color: #b0a88e; margin-top: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

@media (max-width: 768px) {
  .as-grid { grid-template-columns: repeat(auto-fill, minmax(120px, 1fr)); gap: 10px; }
}
</style>
