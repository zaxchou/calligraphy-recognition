<template>
  <div class="artist-sub-page">
    <div class="asp-header">
      <h2><router-link :to="artistUrl" class="asp-back-link">{{ artistName }}</router-link> 的作品</h2>
    </div>
    <div class="asp-sub-nav">
      <router-link :to="artistUrl" class="asp-nav-item">概览</router-link>
      <router-link :to="artistUrl + '/works'" class="asp-nav-item active">作品</router-link>
      <router-link :to="artistUrl + '/seals'" class="asp-nav-item">印章</router-link>
      <router-link :to="artistUrl + '/literature'" class="asp-nav-item">文献</router-link>
      <router-link :to="artistUrl + '/analysis'" class="asp-nav-item">分析</router-link>
    </div>
    <div v-if="loading" class="asp-loading">加载中...</div>
    <div v-else-if="works.length === 0" class="asp-empty">暂无作品数据</div>
    <div v-else class="aw-grid">
      <div v-for="w in works" :key="w.id" class="aw-card" @click="goToWork(w.id)">
        <div class="aw-thumb">
          <img v-if="w.thumbnail_url" :src="w.thumbnail_url" :alt="w.title" />
          <span v-else class="aw-placeholder">{{ w.title?.charAt(0) || '?' }}</span>
        </div>
        <div class="aw-info">
          <div class="aw-title">{{ w.title || '未命名' }}</div>
          <div class="aw-year">{{ w.year || '年份不详' }}</div>
        </div>
      </div>
    </div>
    <div v-if="total > pageSize" class="asp-pagination">
      <el-pagination background layout="prev, pager, next" :total="total" :page-size="pageSize" v-model:current-page="page" @current-change="fetchWorks" />
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()
const API_BASE = import.meta.env.VITE_API_BASE || '/api/v1'
const artistName = route.params.name
const artistUrl = computed(() => '/artist/' + encodeURIComponent(artistName))
const works = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const loading = ref(true)

function encodeURIComponent(s) { return encodeURIComponent(s) }

async function fetchWorks() {
  loading.value = true
  try {
    const res = await fetch(`${API_BASE}/content-analysis/records?artist=${encodeURIComponent(artistName)}&limit=${pageSize}&offset=${(page.value - 1) * pageSize}`)
    const data = await res.json()
    works.value = data.records || []
    total.value = data.total || 0
  } catch (e) { console.error(e) }
  finally { loading.value = false }
}

function goToWork(id) {
  window.open(`/#/tubi/${id}`, '_blank')
}

onMounted(fetchWorks)
</script>

<style scoped>
.artist-sub-page { max-width: 1100px; margin: 0 auto; padding: 24px 20px; }
.asp-header h2 { font-family: 'Noto Serif SC', serif; font-size: 22px; color: #3a3222; margin: 0 0 16px; }
.asp-back-link { color: #3a3222; text-decoration: none; }
.asp-back-link:hover { color: #c45a3c; }
.asp-sub-nav { display: flex; gap: 0; border-bottom: 1px solid #edeae1; margin-bottom: 24px; }
.asp-nav-item { padding: 10px 20px; font-size: 14px; color: #8c7a5c; text-decoration: none; border-bottom: 2px solid transparent; transition: all 0.2s; }
.asp-nav-item:hover { color: #c45a3c; }
.asp-nav-item.active { color: #c45a3c; border-bottom-color: #c45a3c; font-weight: 500; }
.asp-loading, .asp-empty { text-align: center; padding: 60px 0; color: #b0a890; font-size: 15px; }
.aw-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 16px; }
.aw-card { background: #fff; border: 1px solid #edeae1; border-radius: 8px; overflow: hidden; cursor: pointer; transition: all 0.2s; }
.aw-card:hover { transform: translateY(-2px); box-shadow: 0 4px 16px rgba(0,0,0,0.06); border-color: #d4cfc0; }
.aw-thumb { width: 100%; aspect-ratio: 3/4; background: #f5f3ed; display: flex; align-items: center; justify-content: center; overflow: hidden; }
.aw-thumb img { width: 100%; height: 100%; object-fit: cover; }
.aw-placeholder { font-size: 32px; color: #d0ccc0; font-family: 'Noto Serif SC', serif; }
.aw-info { padding: 10px 12px; }
.aw-title { font-size: 14px; color: #3a3222; font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.aw-year { font-size: 12px; color: #b0a890; margin-top: 2px; }
.asp-pagination { margin-top: 24px; display: flex; justify-content: center; }
</style>
