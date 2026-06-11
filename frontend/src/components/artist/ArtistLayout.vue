<template>
  <div class="av-page-wrap">
    <div class="av-page">
      <template v-if="artistData">
        <header class="av-header" :class="{ 'av-header-compact': compact }">
          <div class="av-header-inner">
            <div class="av-header-avatar-section">
              <div class="av-avatar-wrap" :class="{ 'av-avatar-compact': compact }">
                <img v-if="artistData.avatar_url && !avatarError" :src="artistData.avatar_url" class="av-avatar-img" :class="{ 'av-avatar-img-compact': compact }" alt="" @error="avatarError = true" />
                <span v-else class="av-avatar-text" :class="{ 'av-avatar-text-compact': compact }">{{ artistData.name?.charAt(0) || '?' }}</span>
              </div>
              <div v-if="!compact && artistPhotos.length > 0" class="av-photo-strip">
                <button v-if="photoScroll > 0" class="av-photo-arrow av-photo-arrow-left" @click.stop="photoScroll = Math.max(0, photoScroll - 1)">&#8249;</button>
                <div class="av-photo-track">
                  <img v-for="(p, i) in artistPhotos" :key="i" :src="photoThumbUrl(p)" class="av-photo-thumb" :class="{ 'av-photo-active': photoZoomIdx === i }" :style="{ transform: `translateX(${-photoScroll * 36}px)` }" @click.stop="openPhotoZoom(i)" />
                </div>
                <button v-if="photoScroll < artistPhotos.length - 4" class="av-photo-arrow av-photo-arrow-right" @click.stop="photoScroll = Math.min(artistPhotos.length - 4, photoScroll + 1)">&#8250;</button>
              </div>
            </div>

            <div class="av-header-center">
              <h1 class="av-name" :class="{ 'av-name-compact': compact }">{{ artistData.name }}</h1>
              <p v-if="artistData.alias" class="av-alias" :class="{ 'av-alias-compact': compact }">{{ artistData.alias }}</p>
              <div class="av-meta" :class="{ 'av-meta-compact': compact }">
                <span v-if="artistData.dynasty" class="av-meta-item">{{ artistData.dynasty }}</span>
                <span class="av-meta-item">{{ formatYears(artistData.birth_year, artistData.death_year) || '生卒年不详' }}</span>
                <span v-if="artistData.art_school" class="av-meta-item av-meta-school">{{ artistData.art_school }}</span>
                <span v-if="artistData.hometown" class="av-meta-item">{{ artistData.hometown }}</span>
                <span v-if="artistData.occupation" class="av-meta-item">{{ artistData.occupation }}</span>
              </div>
              <p v-if="!compact && artistData.summary" class="av-summary">{{ artistData.summary }}</p>
            </div>

            <div class="av-header-actions">
              <el-button size="small" plain @click="$router.push({ name: 'ArtistList' })">返回列表</el-button>
            </div>
          </div>
        </header>

        <ArtistSubNav :artist-name="artistName" :current-route="currentRoute" :artist="artistData" />

        <slot />
      </template>

      <slot v-else name="empty" />
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
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { ArrowUp } from '@element-plus/icons-vue'
import ArtistSubNav from './ArtistSubNav.vue'

const props = defineProps({
  artistName: { type: String, required: true },
  currentRoute: { type: String, required: true },
  artist: { type: Object, default: null },
  compact: { type: Boolean, default: false },
})

const API_BASE = import.meta.env.VITE_API_BASE || '/api/v1'
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

async function fetchArtist() {
  if (props.artist) {
    artistData.value = props.artist
    return
  }
  try {
    const res = await fetch(`${API_BASE}/artists/by-name/${encodeURIComponent(props.artistName)}`)
    if (res.ok) {
      const result = await res.json()
      artistData.value = result.artist
    }
  } catch (_) {}
}

onMounted(async () => {
  await fetchArtist()
  backTopHandler = () => { showBackTop.value = window.scrollY > 600 }
  window.addEventListener('scroll', backTopHandler, { passive: true })
})

onUnmounted(() => {
  if (backTopHandler) window.removeEventListener('scroll', backTopHandler)
})
</script>

<style scoped>
/* ── Layout ── */
.av-page-wrap { min-height: 100vh; background: #faf8f5; }
.av-page {
  max-width: var(--container-wide);
  margin: 0 auto;
  padding: 0 24px 120px;
}

/* ── Header (unified) ── */
.av-header {
  position: relative;
  margin-bottom: 0;
  border-radius: 12px;
  overflow: hidden;
  background: linear-gradient(135deg, #3a3222 0%, #6b5b4a 35%, #8a7a6a 70%);
  transition: border-radius 0.35s ease, box-shadow 0.35s ease;
}
.av-header .av-name { color: #fff; text-shadow: 0 1px 4px rgba(0,0,0,0.25); font-size: 20px; font-weight: 700; margin: 0; line-height: 1.2; }
.av-header .av-alias { color: rgba(255,255,255,0.7); margin: 0; font-size: 13px; font-family: 'Noto Serif SC', serif; }
.av-header .av-meta-item { background: rgba(255,255,255,0.12); color: rgba(255,255,255,0.9); display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; line-height: 1.5; }
.av-header .av-meta-school { background: rgba(196,90,60,0.45); color: #fff; }
.av-header-inner {
  position: relative; z-index: 1;
  display: flex; gap: 18px; align-items: center;
  padding: 0 28px;
  transition: padding 0.35s ease;
}
.av-header-left { flex-shrink: 0; }
.av-header-center { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 5px; }
.av-header-center .av-meta { display: flex; flex-wrap: wrap; gap: 5px; }
.av-summary {
  font-size: 13px; color: rgba(255,255,255,0.75); line-height: 1.7;
  margin: 2px 0 0; max-width: 560px;
}

/* Large-specific overrides */
.av-header:not(.av-header-compact) {
  padding: 28px 0;
}
.av-header:not(.av-header-compact) .av-name {
  font-size: 32px;
  text-shadow: 0 2px 6px rgba(0,0,0,0.3);
}
.av-header:not(.av-header-compact) .av-alias {
  font-size: 15px; color: rgba(255,255,255,0.75);
}
.av-header:not(.av-header-compact) .av-meta-item {
  padding: 3px 10px; font-size: 12px;
}
.av-header:not(.av-header-compact) .av-header-inner {
  align-items: flex-start;
  padding: 0 32px;
}
.av-header:not(.av-header-compact) .av-header-center {
  gap: 8px;
}

/* Compact-specific overrides */
.av-header-compact {
  padding: 14px 0;
  border-radius: 8px;
  box-shadow: 0 2px 10px rgba(0,0,0,0.08);
}
.av-header-compact .av-header-inner {
  gap: 14px;
}

/* ── Avatar ── */
.av-header-avatar-section { flex-shrink: 0; display: flex; flex-direction: column; align-items: center; gap: 8px; }
.av-avatar-wrap { width: 150px; height: 150px; transition: width 0.35s ease, height 0.35s ease; }
.av-avatar-compact { width: 56px; height: 56px; }
.av-avatar-img {
  width: 150px; height: 150px; border-radius: 12px; object-fit: cover; display: block;
  box-shadow: 0 4px 20px rgba(0,0,0,0.25);
  transition: width 0.35s ease, height 0.35s ease, border-radius 0.35s ease, box-shadow 0.35s ease;
}
.av-avatar-img-compact { width: 56px; height: 56px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.18); }
.av-avatar-text {
  display: flex; align-items: center; justify-content: center;
  width: 150px; height: 150px; border-radius: 12px;
  background: linear-gradient(135deg, #c45a3c, #dbbca8);
  color: #fff; font-family: 'Noto Serif SC', serif;
  font-size: 56px; font-weight: 500;
  box-shadow: 0 4px 20px rgba(0,0,0,0.25);
  transition: width 0.35s ease, height 0.35s ease, border-radius 0.35s ease, font-size 0.35s ease, box-shadow 0.35s ease;
}
.av-avatar-text-compact { width: 56px; height: 56px; border-radius: 8px; font-size: 24px; box-shadow: 0 2px 8px rgba(0,0,0,0.18); }

.av-photo-strip { display: flex; align-items: center; gap: 0; width: 150px; position: relative; }
.av-photo-track { flex: 1; overflow: hidden; display: flex; gap: 4px; width: 140px; min-width: 0; }
.av-photo-thumb { width: 32px; height: 32px; flex-shrink: 0; border-radius: 4px; object-fit: cover; cursor: pointer; border: 2px solid rgba(255,255,255,0.3); transition: border-color .15s, transform .3s; }
.av-photo-thumb:hover, .av-photo-active { border-color: rgba(255,255,255,0.9); }
.av-photo-arrow { width: 18px; height: 32px; flex-shrink: 0; border: none; background: rgba(255,255,255,0.1); color: rgba(255,255,255,0.6); font-size: 16px; cursor: pointer; display: flex; align-items: center; justify-content: center; border-radius: 3px; transition: background .15s; }
.av-photo-arrow:hover { background: rgba(255,255,255,0.25); color: #fff; }
.av-zoom-nav { margin-top: 16px; display: flex; align-items: center; justify-content: center; gap: 12px; color: #5c5040; }

/* ── Header Info (compact hidden, shared) ── */
.av-header-center .av-name,
.av-header-center .av-alias,
.av-header-center .av-meta,
.av-header-center .av-summary {
  transition: font-size 0.35s ease, max-height 0.35s ease, opacity 0.35s ease, margin 0.35s ease;
}
.av-name-compact,
.av-alias-compact,
.av-meta-compact { display: none; }

/* ── Header Actions ── */
.av-header-actions {
  flex-shrink: 0; display: flex; flex-direction: column;
  align-items: flex-end; gap: 10px; padding-top: 4px;
}
.av-header-compact .av-header-actions {
  padding-top: 0;
}

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

/* ── Header collapse transition ── */
.header-collapse-enter-active,
.header-collapse-leave-active {
  transition: all 0.3s ease;
  overflow: hidden;
}
.header-collapse-enter-from,
.header-collapse-leave-to {
  opacity: 0;
  max-height: 0;
  padding-top: 0;
  padding-bottom: 0;
}

@media (max-width: 768px) {
  .av-page { padding: 0 16px 80px; }
  .av-header { padding: 24px 0 20px; }
  .av-header-compact { padding: 12px 0; }
  .av-header-inner { flex-direction: column; gap: 16px; padding: 0 20px; }
  .av-header-compact .av-header-inner { flex-direction: row; gap: 12px; padding: 0 16px; }
  .av-header-actions { flex-direction: row; align-items: center; }
  .av-name { font-size: 26px; }
  .av-back-top { right: 16px; bottom: 24px; }
}
</style>
