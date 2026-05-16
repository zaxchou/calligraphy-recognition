<template>
  <div class="artist-sub-page">
    <div class="asp-header">
      <h2><router-link :to="{ name: 'ArtistOverview', params: { name: artistName } }" class="asp-back-link">{{ artistName }}</router-link> 的数据分析</h2>
    </div>
    <div class="asp-sub-nav">
      <router-link :to="{ name: 'ArtistOverview', params: { name: artistName } }" class="asp-nav-item">概览</router-link>
      <router-link :to="{ name: 'ArtistWorks', params: { name: artistName } }" class="asp-nav-item">作品</router-link>
      <router-link :to="{ name: 'ArtistSeals', params: { name: artistName } }" class="asp-nav-item">印章</router-link>
      <router-link :to="{ name: 'ArtistLiterature', params: { name: artistName } }" class="asp-nav-item">文献</router-link>
      <router-link :to="{ name: 'ArtistAnalysis', params: { name: artistName } }" class="asp-nav-item active">分析</router-link>
    </div>
    <div v-if="loading" class="asp-loading">加载中...</div>
    <template v-else-if="hasData">
      <div class="aa-section">
        <h3 class="aa-section-title">主题分布</h3>
        <div class="aa-chart-wrap">
          <div v-for="item in themeData" :key="item.theme_name || item.theme" class="aa-bar-item">
            <span class="aa-bar-label">{{ item.theme_name || item.theme }}</span>
            <div class="aa-bar-track"><div class="aa-bar-fill" :style="{ width: item.percent + '%' }"></div></div>
            <span class="aa-bar-val">{{ item.count }}幅</span>
          </div>
          <div v-if="themeData.length === 0" class="aa-no-data">暂无主题数据</div>
        </div>
      </div>
      <div class="aa-section">
        <h3 class="aa-section-title">情感倾向</h3>
        <div class="aa-chart-wrap">
          <div class="aa-sentiment-bar">
            <div class="aa-sentiment-negative" :style="{ width: sentimentData.negative + '%' }">{{ sentimentData.negative > 10 ? '负面 ' + sentimentData.negative + '%' : '' }}</div>
            <div class="aa-sentiment-neutral" :style="{ width: sentimentData.neutral + '%' }">{{ sentimentData.neutral > 10 ? '中性 ' + sentimentData.neutral + '%' : '' }}</div>
            <div class="aa-sentiment-positive" :style="{ width: sentimentData.positive + '%' }">{{ sentimentData.positive > 10 ? '正面 ' + sentimentData.positive + '%' : '' }}</div>
          </div>
        </div>
      </div>
    </template>
    <div v-else class="asp-empty">暂无分析数据，请先在题跋校对中进行作品分析</div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const API_BASE = import.meta.env.VITE_API_BASE || '/api/v1'
const artistName = route.params.name
const loading = ref(true)
const themeData = ref([])
const sentimentData = ref({ negative: 0, neutral: 0, positive: 0 })
const hasData = ref(false)

async function fetchAnalysis() {
  try {
    const res = await fetch(`${API_BASE}/content-analysis/stats?artist=${encodeURIComponent(artistName)}`)
    if (!res.ok) return
    const data = await res.json()
    if (data.theme_distribution && data.theme_distribution.length > 0) {
      const total = data.theme_distribution.reduce((s, i) => s + (i.count || 0), 0) || 1
      themeData.value = data.theme_distribution.map(i => ({ ...i, percent: Math.round(((i.count || 0) / total) * 100) }))
    }
    if (data.sentiment_distribution && data.sentiment_distribution.length > 0) {
      const st = data.sentiment_distribution.reduce((a, i) => a + (i.count || 0), 0) || 1
      const neg = data.sentiment_distribution.find(i => (i.polarity || '').toLowerCase() === 'negative')
      const neu = data.sentiment_distribution.find(i => (i.polarity || '').toLowerCase() === 'neutral')
      const pos = data.sentiment_distribution.find(i => (i.polarity || '').toLowerCase() === 'positive')
      sentimentData.value = {
        negative: Math.round(((neg?.count || 0) / st) * 100),
        neutral: Math.round(((neu?.count || 0) / st) * 100),
        positive: Math.round(((pos?.count || 0) / st) * 100),
      }
    }
    hasData.value = data.total_count > 0 || themeData.value.length > 0
  } catch (e) { console.error(e) }
  finally { loading.value = false }
}

onMounted(fetchAnalysis)
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
.aa-section { background: #fff; border: 1px solid #edeae1; border-radius: 8px; padding: 20px 24px; margin-bottom: 20px; }
.aa-section-title { font-size: 16px; color: #3a3222; font-weight: 600; margin: 0 0 16px; font-family: 'Noto Serif SC', serif; }
.aa-bar-item { display: flex; align-items: center; gap: 12px; margin-bottom: 10px; }
.aa-bar-label { width: 100px; font-size: 13px; color: #5c5346; text-align: right; flex-shrink: 0; }
.aa-bar-track { flex: 1; height: 20px; background: #f5f3ed; border-radius: 10px; overflow: hidden; }
.aa-bar-fill { height: 100%; background: #c45a3c; border-radius: 10px; transition: width 0.5s; }
.aa-bar-val { width: 50px; font-size: 12px; color: #b0a890; }
.aa-no-data { color: #b0a890; text-align: center; padding: 20px; }
.aa-sentiment-bar { display: flex; height: 32px; border-radius: 16px; overflow: hidden; font-size: 12px; color: #fff; text-align: center; line-height: 32px; }
.aa-sentiment-negative { background: #d96c6c; }
.aa-sentiment-neutral { background: #b8a47e; }
.aa-sentiment-positive { background: #5a7d5a; }
</style>
