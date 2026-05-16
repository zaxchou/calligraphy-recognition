<template>
  <div class="artist-sub-page">
    <div class="asp-hero">
      <h2 class="asp-hero-title">
        <router-link :to="{ name: 'ArtistOverview', params: { name: artistName } }" class="asp-back-link">{{ artistName }}</router-link>
      </h2>
    </div>
    <nav class="asp-sub-nav">
      <router-link :to="{ name: 'ArtistOverview', params: { name: artistName } }" class="asp-nav-item">概览</router-link>
      <router-link :to="{ name: 'ArtistWorks', params: { name: artistName } }" class="asp-nav-item">作品</router-link>
      <router-link :to="{ name: 'ArtistSeals', params: { name: artistName } }" class="asp-nav-item">印章</router-link>
      <router-link :to="{ name: 'ArtistLiterature', params: { name: artistName } }" class="asp-nav-item">文献</router-link>
      <router-link :to="{ name: 'ArtistAnalysis', params: { name: artistName } }" class="asp-nav-item active">分析</router-link>
    </nav>

    <!-- 工具栏 -->
    <div class="aa-toolbar">
      <el-select v-model="selectedArtist" size="small" placeholder="切换画家" @change="onArtistChange" style="width:140px">
        <el-option v-for="name in artistList" :key="name" :value="name" :label="name" />
      </el-select>
      <el-button size="small" plain @click="goToFullAnalysis">
        查看完整分析 <el-icon style="margin-left:4px"><TopRight /></el-icon>
      </el-button>
    </div>

    <div v-if="loading" class="asp-loading">加载中...</div>
    <template v-else-if="hasData">
      <!-- 统计摘要条 -->
      <div class="aa-summary-bar">
        <div class="aa-summary-item"><span class="aa-summary-num">{{ stats.total_count }}</span>幅分析作品</div>
        <div class="aa-summary-item"><span class="aa-summary-num">{{ stats.theme_distribution?.length || 0 }}</span>种主题</div>
        <div class="aa-summary-item"><span class="aa-summary-num">{{ stats.sentiment_distribution?.length || 0 }}</span>种情感</div>
      </div>

      <!-- 主题分布 -->
      <section class="aa-card">
        <h3 class="aa-card-title">主题分布</h3>
        <div v-if="themeData.length > 0" class="aa-chart">
          <div v-for="item in themeData" :key="item.theme_name || item.theme" class="aa-bar-row">
            <span class="aa-bar-label">{{ item.theme_name || item.theme }}</span>
            <div class="aa-bar-track">
              <div class="aa-bar-fill" :style="{ width: item.percent + '%' }"></div>
            </div>
            <span class="aa-bar-val">{{ item.count }}幅 {{ item.percent }}%</span>
          </div>
        </div>
        <div v-else class="aa-no-data">暂无主题分布数据</div>
      </section>

      <!-- 情感倾向 -->
      <section class="aa-card">
        <h3 class="aa-card-title">情感倾向</h3>
        <div v-if="sentimentData.length > 0" class="aa-sentiment-bar">
          <div
            v-for="item in sentimentData"
            :key="item.polarity"
            class="aa-sentiment-seg"
            :class="'aa-sentiment-' + item.polarity"
            :style="{ width: item.percent + '%', minWidth: item.percent > 5 ? '60px' : '0' }"
          >
            {{ item.percent > 8 ? item.label + ' ' + item.percent + '%' : '' }}
          </div>
        </div>
        <div v-else class="aa-no-data">暂无情感倾向数据</div>
      </section>

      <!-- 分期统计 -->
      <section v-if="periodData.length > 0" class="aa-card">
        <h3 class="aa-card-title">分期统计</h3>
        <div class="aa-period-grid">
          <div v-for="p in periodData" :key="p.period" class="aa-period-item">
            <div class="aa-period-name">{{ p.period }}</div>
            <div class="aa-period-count">{{ p.count }}幅</div>
          </div>
        </div>
      </section>
    </template>
    <div v-else class="asp-empty">暂无分析数据，请先<a :href="'/#/content-analysis?artist=' + encodeURIComponent(artistName)" class="aa-link">进行题跋大数据分析</a></div>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { TopRight } from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()
const API_BASE = import.meta.env.VITE_API_BASE || '/api/v1'

const artistName = route.params.name
const selectedArtist = ref(artistName)
const artistList = ref([])
const loading = ref(true)
const hasData = ref(false)
const stats = ref({})
const themeData = ref([])
const sentimentData = ref([])
const periodData = ref([])

function onArtistChange() {
  const val = selectedArtist.value
  if (val) router.replace({ name: 'ArtistAnalysis', params: { name: val } })
}

function goToFullAnalysis() {
  window.open(`/#/content-analysis?artist=${encodeURIComponent(selectedArtist.value)}`, '_blank')
}

async function fetchArtistList() {
  try {
    const res = await fetch(`${API_BASE}/content-analysis/artists`)
    if (res.ok) {
      const data = await res.json()
      artistList.value = data.artists || []
    }
  } catch (e) { console.error(e) }
}

async function loadStats() {
  loading.value = true
  try {
    const res = await fetch(`${API_BASE}/content-analysis/stats?artist=${encodeURIComponent(selectedArtist.value)}`)
    if (!res.ok) return
    const data = await res.json()
    stats.value = data

    if (data.theme_distribution && data.theme_distribution.length > 0) {
      const total = data.theme_distribution.reduce((s, i) => s + (i.count || 0), 0) || 1
      themeData.value = data.theme_distribution.map(i => ({
        ...i,
        percent: Math.round(((i.count || 0) / total) * 100)
      }))
    } else { themeData.value = [] }

    if (data.sentiment_distribution && data.sentiment_distribution.length > 0) {
      const st = data.sentiment_distribution.reduce((a, i) => a + (i.count || 0), 0) || 1
      const polarityMap = { negative: '负面', neutral: '中性', positive: '正面' }
      sentimentData.value = data.sentiment_distribution.map(i => ({
        ...i,
        label: polarityMap[i.polarity?.toLowerCase()] || i.polarity,
        percent: Math.round(((i.count || 0) / st) * 100)
      }))
    } else { sentimentData.value = [] }

    if (data.period_distribution && data.period_distribution.length > 0) {
      periodData.value = data.period_distribution
    } else { periodData.value = [] }

    hasData.value = (data.total_count || 0) > 0
  } catch (e) { console.error(e) }
  finally { loading.value = false }
}

watch(() => route.params.name, (newName) => {
  if (newName) { selectedArtist.value = newName; loadStats() }
})

onMounted(async () => {
  await fetchArtistList()
  loadStats()
})
</script>

<style scoped>
.artist-sub-page { max-width: 1100px; margin: 0 auto; padding: 24px 20px 80px; min-height: 100vh; background: #fafaf8; }
.asp-hero { margin-bottom: 8px; }
.asp-hero-title { font-family: 'Noto Serif SC', serif; font-size: 22px; color: #3a3222; margin: 0; }
.asp-back-link { color: #3a3222; text-decoration: none; }
.asp-back-link:hover { color: #c45a3c; }
.asp-sub-nav { display: flex; gap: 0; border-bottom: 1px solid #edeae1; margin-bottom: 24px; }
.asp-nav-item { padding: 10px 20px; font-size: 14px; color: #8c7a5c; text-decoration: none; border-bottom: 2px solid transparent; transition: all 0.2s; }
.asp-nav-item:hover { color: #c45a3c; }
.asp-nav-item.active { color: #c45a3c; border-bottom-color: #c45a3c; font-weight: 500; }
.asp-loading, .asp-empty { text-align: center; padding: 60px 0; color: #b0a890; font-size: 15px; }
.asp-empty a { color: #c45a3c; }
.aa-link { color: #c45a3c; text-decoration: none; }
.aa-toolbar { display: flex; gap: 12px; align-items: center; margin-bottom: 24px; flex-wrap: wrap; }
.aa-summary-bar { display: flex; gap: 24px; justify-content: center; margin-bottom: 24px; padding: 16px 20px; background: #fff; border: 1px solid #edeae1; border-radius: 10px; }
.aa-summary-item { text-align: center; font-size: 13px; color: #8a8578; }
.aa-summary-num { font-family: 'Noto Serif SC', serif; display: block; font-size: 22px; color: #c45a3c; font-weight: 500; margin-bottom: 2px; }
.aa-card { background: #fff; border: 1px solid #edeae1; border-radius: 10px; padding: 24px 28px; margin-bottom: 20px; }
.aa-card-title { font-family: 'Noto Serif SC', serif; font-size: 16px; font-weight: 500; color: #3a3222; margin: 0 0 20px; padding-left: 12px; border-left: 3px solid #c45a3c; }
.aa-bar-row { display: flex; align-items: center; gap: 12px; margin-bottom: 10px; }
.aa-bar-label { width: 100px; font-size: 13px; color: #5c5346; text-align: right; flex-shrink: 0; }
.aa-bar-track { flex: 1; height: 22px; background: #f5f3ed; border-radius: 11px; overflow: hidden; }
.aa-bar-fill { height: 100%; background: linear-gradient(90deg, #dbbca8, #c45a3c); border-radius: 11px; transition: width 0.5s; }
.aa-bar-val { width: 80px; font-size: 12px; color: #8a8578; flex-shrink: 0; }
.aa-no-data { color: #b0a890; text-align: center; padding: 20px; font-size: 13px; }
.aa-sentiment-bar { display: flex; height: 36px; border-radius: 18px; overflow: hidden; font-size: 12px; color: #fff; text-align: center; line-height: 36px; }
.aa-sentiment-negative { background: #d96c6c; }
.aa-sentiment-neutral { background: #b8a47e; }
.aa-sentiment-positive { background: #5a7d5a; }
.aa-period-grid { display: flex; gap: 12px; flex-wrap: wrap; }
.aa-period-item { flex: 1; min-width: 100px; background: #fafaf8; border: 1px solid #edeae1; border-radius: 8px; padding: 14px; text-align: center; }
.aa-period-name { font-size: 13px; color: #3a3222; font-weight: 500; margin-bottom: 4px; }
.aa-period-count { font-size: 18px; color: #c45a3c; font-family: 'Noto Serif SC', serif; }
@media (max-width: 768px) {
  .aa-toolbar { flex-direction: column; align-items: stretch; }
  .aa-summary-bar { gap: 12px; flex-wrap: wrap; }
  .aa-bar-label { width: 70px; font-size: 12px; }
  .aa-period-grid { flex-direction: column; }
}
</style>
