<template>
  <div class="av-page-wrap">
    <div class="av-page" :class="{ 'av-page-fullscreen': isFullscreen }">
      <template v-if="artistData">
        <!-- 全屏模式（分析/行旅）：导航已在 App.vue 隐藏，直接显示内容 -->
        <template v-if="isFullscreen">
          <router-view />
        </template>

        <!-- 普通模式 -->
        <template v-else>
          <header class="av-header" :class="{ 'av-header-compact': !isOverview }">
            <div class="av-header-inner">
              <div class="av-header-avatar-section">
                <div class="av-avatar-wrap" :class="{ 'av-avatar-compact': !isOverview }">
                  <img v-if="artistData.avatar_url && !avatarError" :src="artistData.avatar_url" class="av-avatar-img" :class="{ 'av-avatar-img-compact': !isOverview }" alt="" @error="avatarError = true" />
                  <span v-else class="av-avatar-text" :class="{ 'av-avatar-text-compact': !isOverview }">{{ artistData.name?.charAt(0) || '?' }}</span>
                </div>
                <div v-if="isOverview && artistPhotos.length > 0" class="av-photo-strip">
                  <button v-if="photoScroll > 0" class="av-photo-arrow av-photo-arrow-left" @click.stop="photoScroll = Math.max(0, photoScroll - 1)">&#8249;</button>
                  <div class="av-photo-track">
                    <img v-for="(p, i) in artistPhotos" :key="i" :src="photoThumbUrl(p)" class="av-photo-thumb" :class="{ 'av-photo-active': photoZoomIdx === i }" :style="{ transform: `translateX(${-photoScroll * 36}px)` }" @click.stop="openPhotoZoom(i)" />
                  </div>
                  <button v-if="photoScroll < artistPhotos.length - 4" class="av-photo-arrow av-photo-arrow-right" @click.stop="photoScroll = Math.min(artistPhotos.length - 4, photoScroll + 1)">&#8250;</button>
                </div>
              </div>

              <div class="av-header-center">
                <h1 class="av-name" :class="{ 'av-name-compact': !isOverview }">{{ artistData.name }}</h1>
                <p v-if="artistData.alias" class="av-alias" :class="{ 'av-alias-compact': !isOverview }">{{ artistData.alias }}</p>
                <div class="av-meta" :class="{ 'av-meta-compact': !isOverview }">
                  <span v-if="artistData.dynasty" class="av-meta-item">{{ artistData.dynasty }}</span>
                  <span class="av-meta-item">{{ formatYears(artistData.birth_year, artistData.death_year) || '生卒年不详' }}</span>
                  <span v-if="artistData.art_school" class="av-meta-item av-meta-school">{{ artistData.art_school }}</span>
                  <span v-if="artistData.hometown" class="av-meta-item">{{ artistData.hometown }}</span>
                  <span v-if="artistData.occupation" class="av-meta-item">{{ artistData.occupation }}</span>
                </div>
                <p v-if="isOverview && artistData.summary" class="av-summary">{{ artistData.summary }}</p>
              </div>

              <div class="av-header-actions">
                <el-button size="small" plain @click="$router.push({ name: 'ArtistList' })">返回列表</el-button>
              </div>
            </div>
          </header>

          <ArtistSubNav :artist-name="route.params.name" :current-route="route.name" :artist="artistData" />

          <transition name="page-slide" mode="out-in">
            <router-view v-slot="{ Component }">
              <component :is="Component" :key="$route.path" />
            </router-view>
          </transition>
        </template>
      </template>
    </div>

    <button class="av-back-top" :class="{ visible: showBackTop }" @click="scrollToTop" title="回到顶部">
      <el-icon><ArrowUp /></el-icon>
    </button>

    <el-dialog v-model="photoZoomVisible" title="本人照片" width="720px" align-center @closed="photoZoomIdx = -1">
      <div style="text-align:center">
        <img v-if="photoZoomIdx >= 0 && artistPhotos[photoZoomIdx]" :src="photoFullUrl(artistPhotos[photoZoomIdx])" style="max-width:100%;max-height:70vh;object-fit:contain;border-radius:8px" />
        <div v-if="artistPhotos.length > 1" class="av-zoom-nav">
          <el-button size="small" :disabled="photoZoomIdx <= 0" @click="photoZoomIdx--">上一张</el-button>
          <span>{{ photoZoomIdx + 1 }} / {{ artistPhotos.length }}</span>
          <el-button size="small" :disabled="photoZoomIdx >= artistPhotos.length - 1" @click="photoZoomIdx++">下一张</el-button>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { ArrowUp } from '@element-plus/icons-vue'
import ArtistSubNav from './ArtistSubNav.vue'

const route = useRoute()
const API_BASE = import.meta.env.VITE_API_BASE || '/api/v1'

const isOverview = computed(() => route.name === 'ArtistOverview')
const isFullscreen = computed(() => route.name === 'ArtistAnalysis' || route.name === 'ArtistAnalysisLegacy' || route.name === 'ArtistMap' || route.name === 'ArtistLiteratureReader')

const artistData = ref(null)
const showBackTop = ref(false)
const avatarError = ref(false)
const photoZoomVisible = ref(false)
const photoZoomIdx = ref(-1)
const photoScroll = ref(0)

function openPhotoZoom(idx) {
  photoZoomIdx.value = idx
  photoZoomVisible.value = true
}

function photoThumbUrl(p) {
  if (typeof p === 'string') return p
  return p.thumb_url || p.url || ''
}

function photoFullUrl(p) {
  if (typeof p === 'string') return p
  return p.url || ''
}

function formatYears(birth, death) {
  if (!birth && !death) return ''
  const b = birth || '?'
  const d = death || '?'
  return `${b} — ${d}`
}

function scrollToTop() {
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

const artistPhotos = computed(() => {
  if (!artistData.value?.photos) return []
  try {
    const parsed = typeof artistData.value.photos === 'string' ? JSON.parse(artistData.value.photos) : artistData.value.photos
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
})

let backTopHandler = null

onMounted(async () => {
  const name = route.params.name
  try {
    const res = await fetch(`${API_BASE}/artists/by-name/${encodeURIComponent(name)}`)
    if (res.ok) {
      const result = await res.json()
      artistData.value = result.artist
    }
  } catch (_) {}
  backTopHandler = () => { showBackTop.value = window.scrollY > 600 }
  window.addEventListener('scroll', backTopHandler, { passive: true })
})

onUnmounted(() => {
  if (backTopHandler) window.removeEventListener('scroll', backTopHandler)
})
</script>

<style scoped>
.av-page-wrap { min-height: 100vh; background: #faf8f5; }
.av-page {
  max-width: var(--container-wide);
  margin: 0 auto;
  padding: 0 24px 120px;
}

.av-page-fullscreen { padding: 0; max-width: 100%; }
.af-back-bar { position: sticky; top: 0; z-index: 50; padding: 10px 20px; background: rgba(250,249,245,0.92); backdrop-filter: blur(8px); border-bottom: 1px solid var(--border-cream); }

/* ── Header (C: 学术典雅) ── */
.av-header {
  position: relative;
  margin-bottom: 0;
  border-radius: 4px;
  overflow: hidden;
  background: #fff;
  border-bottom: 2px solid #c45a3c;
  transition: padding 0.35s ease, border-radius 0.35s ease, box-shadow 0.35s ease;
}
.av-header::after {
  content: ''; position: absolute; bottom: -2px; left: 32px; width: 80px; height: 2px; background: #c45a3c;
}
.av-header .av-name { color: #2c2416; margin: 0; line-height: 1.2; }
.av-header .av-alias { color: #8a8578; margin: 0; font-family: 'Noto Serif SC', serif; }
.av-header .av-meta-item { padding: 3px 12px; font-size: 11px; color: #6b6050; border: 1px solid #e0dcd4; border-radius: 3px; background: #fff; display: inline-block; line-height: 1.5; }
.av-header .av-meta-school { border-color: #c45a3c; color: #c45a3c; background: #fdf6f0; }
.av-header-inner {
  position: relative; z-index: 1;
  display: flex; gap: 24px; align-items: flex-start;
  padding: 0 32px;
  transition: padding 0.35s ease;
}
.av-header-center { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 6px; }
.av-header-center .av-meta { display: flex; flex-wrap: wrap; gap: 6px; }
.av-summary {
  font-size: 13px; color: #6b6050; line-height: 1.7;
  margin: 4px 0 0; max-width: 560px;
}

/* Large mode */
.av-header:not(.av-header-compact) {
  padding: 28px 0;
}
.av-header:not(.av-header-compact) .av-name {
  font-size: 30px; font-weight: 700; letter-spacing: 0.04em;
}
.av-header:not(.av-header-compact) .av-alias {
  font-size: 15px;
}
.av-header:not(.av-header-compact) .av-header-inner {
  padding: 0 32px;
}

/* Compact mode */
.av-header-compact {
  padding: 14px 0;
  border-radius: 4px;
  border-bottom-width: 2px;
}
.av-header-compact .av-header-inner {
  align-items: center;
  gap: 14px;
}
.av-header-compact .av-name {
  font-size: 20px; font-weight: 700; letter-spacing: 0.02em;
}
.av-header-compact .av-alias {
  font-size: 13px;
}
.av-header-compact .av-meta-item {
  padding: 1px 8px; font-size: 10px;
}
.av-header-compact::after {
  left: 20px; width: 60px;
}

/* ── Avatar ── */
.av-header-avatar-section { flex-shrink: 0; display: flex; flex-direction: column; align-items: center; gap: 8px; transition: gap 0.35s ease; }
.av-avatar-wrap { width: 90px; height: 90px; transition: width 0.35s ease, height 0.35s ease; }
.av-avatar-compact { width: 48px; height: 48px; }
.av-avatar-img {
  width: 90px; height: 90px; border-radius: 4px; object-fit: cover; display: block;
  box-shadow: 0 2px 10px rgba(0,0,0,0.08);
  transition: width 0.35s ease, height 0.35s ease, border-radius 0.35s ease, box-shadow 0.35s ease;
}
.av-avatar-img-compact { width: 48px; height: 48px; border-radius: 3px; box-shadow: 0 1px 6px rgba(0,0,0,0.06); }
.av-avatar-text {
  display: flex; align-items: center; justify-content: center;
  width: 90px; height: 90px; border-radius: 4px;
  background: linear-gradient(135deg, #3a3222, #6b5b4a);
  color: #d4c4a8; font-family: 'Noto Serif SC', serif;
  font-size: 36px; font-weight: 500;
  border: 1px solid #e0dcd4;
  transition: width 0.35s ease, height 0.35s ease, border-radius 0.35s ease, font-size 0.35s ease;
}
.av-avatar-text-compact { width: 48px; height: 48px; border-radius: 3px; font-size: 22px; }

.av-photo-strip { display: flex; align-items: center; gap: 0; width: 90px; position: relative; }
.av-photo-track { flex: 1; overflow: hidden; display: flex; gap: 4px; width: 84px; min-width: 0; }
.av-photo-thumb { width: 26px; height: 26px; flex-shrink: 0; border-radius: 3px; object-fit: cover; cursor: pointer; border: 2px solid rgba(255,255,255,0.3); transition: border-color .15s, transform .3s; }
.av-photo-thumb:hover, .av-photo-active { border-color: rgba(255,255,255,0.9); }
.av-photo-arrow { width: 16px; height: 26px; flex-shrink: 0; border: none; background: rgba(255,255,255,0.1); color: rgba(255,255,255,0.6); font-size: 14px; cursor: pointer; display: flex; align-items: center; justify-content: center; border-radius: 2px; transition: background .15s; }
.av-photo-arrow:hover { background: rgba(255,255,255,0.25); color: #fff; }
.av-zoom-nav { margin-top: 16px; display: flex; align-items: center; justify-content: center; gap: 12px; color: #5c5040; }

/* ── Header Actions ── */
.av-header-actions {
  flex-shrink: 0; display: flex; flex-direction: column;
  align-items: flex-end; gap: 10px; padding-top: 2px;
}
.av-header-compact .av-header-actions { padding-top: 0; }

/* ── Back to Top ── */
.av-back-top {
  position: fixed; right: 32px; bottom: 40px; z-index: 100;
  width: 40px; height: 40px; border-radius: 50%;
  background: #3a3222; color: #fff; border: none;
  display: flex; align-items: center; justify-content: center;
  cursor: pointer; font-size: 18px; opacity: 0; pointer-events: none;
  transition: opacity 0.3s; box-shadow: 0 2px 12px rgba(0,0,0,0.15);
}
.av-back-top.visible { opacity: 0.85; pointer-events: auto; }
.av-back-top:hover { opacity: 1; background: #c45a3c; }

/* ── Content transition ── */
.page-slide-enter-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}
.page-slide-leave-active {
  transition: opacity 0.15s ease, transform 0.15s ease;
}
.page-slide-enter-from {
  opacity: 0;
  transform: translateY(6px);
}
.page-slide-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}

@media (max-width: 768px) {
  .av-page { padding: 0 16px 80px; }
  .av-header { padding: 24px 0 20px; }
  .av-header-compact { padding: 12px 0; }
  .av-header-inner { flex-direction: column; gap: 16px; padding: 0 20px; }
  .av-header-compact .av-header-inner { flex-direction: row; gap: 12px; padding: 0 16px; }
  .av-header-actions { flex-direction: row; align-items: center; }
  .av-back-top { right: 16px; bottom: 24px; }
}
</style>
