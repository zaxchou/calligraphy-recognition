<template>
  <!-- 初始加载骨架屏（有缓存时直接跳过） -->
  <div v-if="initialLoading && !currentImage" class="skeleton-container">

    <!-- 详情内容骨架 -->
    <div class="skeleton-content">
      <!-- 左侧骨架 -->
      <div class="skeleton-left">
        <div class="skeleton-card">
          <div class="skeleton-image"></div>
          <div class="skeleton-thumbnails">
            <div class="skeleton-thumb"></div>
            <div class="skeleton-thumb"></div>
            <div class="skeleton-thumb"></div>
          </div>
        </div>
        <div class="skeleton-card">
          <div class="skeleton-line skeleton-bold"></div>
          <div class="skeleton-line"></div>
          <div class="skeleton-line short"></div>
        </div>
      </div>

      <!-- 右侧骨架 -->
      <div class="skeleton-right">
        <div class="skeleton-card large">
          <div class="skeleton-line skeleton-title"></div>
          <div class="skeleton-grid">
            <div class="skeleton-grid-item"></div>
            <div class="skeleton-grid-item"></div>
          </div>
        </div>
        <div class="skeleton-card large">
          <div class="skeleton-line skeleton-title"></div>
          <div class="skeleton-block"></div>
        </div>
      </div>
    </div>
  </div>

  <!-- 详情内容 -->
  <div v-else-if="currentImage" class="tubi-analysis tubi-page">
    <TibaDetail
      :current-image="currentImage"
      :analysis="{
        status: analyzeStatus, progress: analyzeProgress,
        step: analyzingStep, areaStats, note: analysisNote,
        positionAnalysis,
      }"
      :prev-image="prevImage"
      :next-image="nextImage"
      :album-navigation="albumNavigation"
      :history-list="fullItemList"
      :get-detail-all-tags="getDetailAllTags"
      @back="backToHome"
      @edit-current="editCurrentImage"
      @auto-analyze="autoAnalyze"
      @navigate="navigateToImage"
      @navigate-album="navigateToAlbumItem"
      @open-annotator="openAnnotator"
      @filter-by-tag="filterByTag"
    />

    <TibaEditDialog ref="editDialogRef" @saved="onEditSaved" @deleted="onEditDeleted" @replaced="onEditReplaced" />
  </div>
</template>

<style src="../tiba/TibaAnalysis.css" scoped></style>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { tibaApi } from '../api'
import { useAuthStore } from '../stores/authStore'
import { useTibaDetail } from '../composables/useTibaDetail'
import TibaDetail from './TibaDetail.vue'
import TibaEditDialog from '../components/tiba/TibaEditDialog.vue'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()

// 本地缓存配置（与 composable 中保持一致）
const detailCache = {
  get(id) {
    try {
      const cache = JSON.parse(localStorage.getItem('tiba_detail_cache') || '{}')
      const item = cache[id]
      if (item && Date.now() - item.timestamp < 30 * 60 * 1000) {
        return item.data
      }
      return null
    } catch {}
    return null
  },
  set(id, data) {
    try {
      const cache = JSON.parse(localStorage.getItem('tiba_detail_cache') || '{}')
      const keys = Object.keys(cache)
      if (keys.length >= 10) {
        const sorted = keys.sort((a, b) => (cache[a].timestamp || 0) - (cache[b].timestamp || 0))
        sorted.slice(0, keys.length - 9).forEach(k => delete cache[k])
      }
      cache[id] = { data, timestamp: Date.now() }
      localStorage.setItem('tiba_detail_cache', JSON.stringify(cache))
    } catch {}
  }
}

const detail = useTibaDetail(router, route)

const {
  currentImage, analyzeStatus, analyzeProgress, analyzingStep,
  areaStats, analysisNote, positionAnalysis,
  prevImage, nextImage, fullItemList,
  loadFullItemList, selectImage, loadHistoryItem,
  navigateToImage, autoAnalyze, getDetailAllTags, filterByTag,
} = detail

const initialLoading = ref(true)
const editDialogRef = ref(null)

const albumNavigation = computed(() => {
  const img = currentImage.value
  if (!img?.album_name) return { is_in_album: false, items: [] }

  // 获取当前在同名册页中的索引
  const albumItems = fullItemList.value.filter(item => item.album_name === img.album_name)
  const currentIdx = albumItems.findIndex(item => item.id === img.id)

  return {
    is_in_album: true,
    album_name: img.album_name,
    current_index: currentIdx >= 0 ? currentIdx : 0,
    total_count: albumItems.length,
    items: albumItems.map(item => ({
      id: item.id,
      thumbnail_url: item.thumbnailUrl || item.url,
      is_current: item.id === img.id,
      page_role: item.page_role,
    })),
  }
})

function navigateToAlbumItem(item) {
  if (item.id !== currentImage.value?.id) loadHistoryItem(item)
}

function backToHome() {
  const artist = currentImage.value?.artist
  const query = artist && artist !== '李鱓' ? { artist } : {}
  router.push({ name: 'TibaAnalysis', query })
}

function openAnnotator() {
  if (!currentImage.value?.id) return
  router.push(`/annotate/${currentImage.value.id}`)
}

function editCurrentImage() {
  if (currentImage.value) editDialogRef.value?.open(currentImage.value)
  else ElMessage.warning('请先选择一幅画作')
}

function onEditSaved({ id, updates }) {
  if (currentImage.value?.id === id) {
    Object.assign(currentImage.value, {
      title: updates.title, artist: updates.artist, year: updates.year,
      age: updates.age, analysisNote: updates.analysisNote,
      inscriptionContent: updates.inscriptionContent, sealContent: updates.sealContent,
      inscriptionPercent: updates.inscriptionPercent,
      paintingPercent: updates.paintingPercent, blankPercent: updates.blankPercent,
    })
  }
}

function onEditDeleted(id) {
  if (currentImage.value?.id === id) {
    currentImage.value = null
    router.push({ name: 'TibaAnalysis' })
  }
}

function onEditReplaced({ id, url, thumbnail_url }) {
  if (currentImage.value?.id === id) {
    currentImage.value.url = url
    currentImage.value.thumbnailUrl = thumbnail_url
    currentImage.value.annotatedImageUrl = null
  }
}

onMounted(async () => {
  const imageId = route.params.id
  if (!imageId) {
    router.replace({ name: 'TibaAnalysis' })
    return
  }

  // 优先尝试从本地缓存加载（瞬间完成）
  const cached = detailCache.get(imageId)
  if (cached) {
    console.log('从本地缓存加载:', imageId)
    // 从缓存加载也需要调用 selectImage 来初始化所有状态
    await selectImage(cached)
    initialLoading.value = false
  }

  try {
    // 无论是否有缓存，都重新获取最新数据
    const response = await tibaApi.getAnalysisResult(imageId)
    if (!response.success) throw new Error(response.detail || '请求失败')

    const data = response.data
    const analysisNoteText = data.analysis_note || ''
    const historyImage = {
      id: data.id, image_id: data.image_id, owner_id: data.owner_id, library_id: data.library_id,
      name: data.name || '', url: data.url,
      thumbnailUrl: data.thumbnail_url || data.url, width: data.width, height: data.height,
      title: data.title, artist: data.artist, year: data.year,
      inscriptionPercent: data.inscription_percent, paintingPercent: data.painting_percent,
      blankPercent: data.blank_percent,
      regions: data.regions, positionAnalysis: data.position_analysis,
      annotatedImageUrl: data.annotated_image_url, isManualAnnotated: data.is_manual_annotated,
      analysisNote: analysisNoteText,
      inscriptionContent: data.inscription_content || '',
      sealContent: data.seal_content || '', inscriptionModern: data.inscription_modern || '',
      inscriptionEn: data.inscription_en || '', contentAnalysis: data.content_analysis || null,
      dzi_url: data.dzi_url,
      artwork_width_cm: data.artwork_width_cm, artwork_height_cm: data.artwork_height_cm,
      tags: data.tags, album_name: data.album_name, album_index: data.album_index,
      page_role: data.page_role, period_phase: data.period_phase,
      material_tags: data.material_tags, computed_tags: data.computed_tags,
      prev_image_id: data.prev_image_id, next_image_id: data.next_image_id,
    }

    // 缓存到本地
    detailCache.set(imageId, historyImage)

    // 平滑更新到 currentImage（如果有缓存，这是增量更新）
    if (cached) {
      Object.assign(currentImage.value, historyImage)
    } else {
      currentImage.value = historyImage
    }

    // 非阻塞加载全量列表
    loadFullItemList().catch(() => {})

    if (!cached) {
      ElMessage.success('已加载指定作品')
    }
  } catch (error) {
    console.error('加载指定作品失败:', error)
    if (!cached) {
      ElMessage.error('加载指定作品失败')
      router.replace({ name: 'TibaAnalysis' })
    }
  } finally {
    initialLoading.value = false
  }
})
</script>

<style src="../tiba/TibaAnalysis.css" scoped></style>

<style scoped>
/* ── 骨架屏样式 ── */
.skeleton-container {
  padding: 20px;
  max-width: 1400px;
  margin: 0 auto;
}

.skeleton-content {
  display: grid;
  grid-template-columns: 30% 1fr;
  gap: 20px;
}

.skeleton-left, .skeleton-right {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.skeleton-card {
  background: #fff;
  border-radius: 12px;
  padding: 16px;
  border: 1px solid #e8e4da;
}

.skeleton-card.large {
  min-height: 200px;
}

.skeleton-image {
  width: 100%;
  height: 300px;
  background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%);
  background-size: 200% 100%;
  animation: skeleton-shine 1.5s infinite;
  border-radius: 8px;
  margin-bottom: 16px;
}

.skeleton-thumbnails {
  display: flex;
  gap: 8px;
  justify-content: center;
}

.skeleton-thumb {
  width: 60px;
  height: 60px;
  background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%);
  background-size: 200% 100%;
  animation: skeleton-shine 1.5s infinite;
  border-radius: 4px;
}

.skeleton-line {
  height: 16px;
  background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%);
  background-size: 200% 100%;
  animation: skeleton-shine 1.5s infinite;
  border-radius: 4px;
  margin-bottom: 10px;
  width: 60%;
}

.skeleton-line.skeleton-bold {
  height: 20px;
  width: 40%;
  margin-bottom: 12px;
}

.skeleton-line.short {
  width: 30%;
}

.skeleton-line.skeleton-title {
  width: 50%;
  height: 18px;
  margin-bottom: 20px;
}

.skeleton-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.skeleton-grid-item {
  height: 100px;
  background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%);
  background-size: 200% 100%;
  animation: skeleton-shine 1.5s infinite;
  border-radius: 8px;
}

.skeleton-block {
  height: 150px;
  background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%);
  background-size: 200% 100%;
  animation: skeleton-shine 1.5s infinite;
  border-radius: 8px;
}

.skeleton-button {
  width: 36px;
  height: 36px;
  background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%);
  background-size: 200% 100%;
  animation: skeleton-shine 1.5s infinite;
  border-radius: 50%;
}

.skeleton-text {
  flex: 1;
  height: 16px;
  background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%);
  background-size: 200% 100%;
  animation: skeleton-shine 1.5s infinite;
  border-radius: 4px;
}

.skeleton-text.skeleton-title {
  max-width: 200px;
}

@keyframes skeleton-shine {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

/* 加载完成后的过渡 */
.skeleton-container {
  animation: skeleton-fade-out 0.3s ease-out;
}

@keyframes skeleton-fade-out {
  0% { opacity: 1; }
  100% { opacity: 0; }
}

.tdp-loading-overlay {
  position: fixed; inset: 0; background: #f5f4ed; z-index: 99999;
  display: flex; align-items: center; justify-content: center;
}
.tdp-loading-inner { text-align: center; color: #3d3d3d; }
.tdp-spinner {
  width: 40px; height: 40px;
  border: 3px solid #e8e4d8; border-top-color: #c45a3c;
  border-radius: 50%; animation: spin 0.8s linear infinite;
  margin: 0 auto 16px;
}
@keyframes spin { to { transform: rotate(360deg); } }
.tdp-loading-inner p { margin: 0; font-size: 15px; color: #8c8c8c; }
</style>
