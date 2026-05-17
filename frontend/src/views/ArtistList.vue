<template>
  <div class="artist-list-page">
    <div class="al-hero">
      <h1 class="al-title">艺术家百科</h1>
      <p class="al-subtitle">探索历代书画家的艺术世界</p>
    </div>

    <div class="al-toolbar">
      <div class="al-view-switch">
        <el-radio-group v-model="viewMode" size="small" @change="onViewModeChange">
          <el-radio-button value="card"><el-icon><Grid /></el-icon> 卡片</el-radio-button>
          <el-radio-button value="timeline">时间轴</el-radio-button>
          <el-radio-button value="table">表格</el-radio-button>
        </el-radio-group>
      </div>

      <div class="al-filters">
        <el-input v-model="keyword" placeholder="搜索画家/字号..." clearable class="al-search"
          @input="debouncedSearch" @clear="onFilterChange">
          <template #prefix><el-icon><Search /></el-icon></template>
        </el-input>
        <el-select v-model="dynastyFilters" placeholder="朝代" clearable multiple collapse-tags
          collapse-tags-tooltip class="al-filter-select" @change="onFilterChange">
          <el-option v-for="p in store.periods" :key="p" :label="p" :value="p" />
        </el-select>
        <el-select v-model="schoolFilters" placeholder="画派" clearable multiple collapse-tags
          collapse-tags-tooltip class="al-filter-select" @change="onFilterChange">
          <el-option v-for="s in store.schools" :key="s.id" :label="s.name" :value="s.name" />
        </el-select>
        <el-select v-model="sortBy" placeholder="排序" class="al-sort" @change="onFilterChange">
          <el-option label="默认" value="created_at" />
          <el-option label="姓名 A-Z" value="name" />
          <el-option label="出生年份" value="birth_year" />
        </el-select>
      </div>

      <PinyinNav :names="store.letterNames" :active-letter="activeLetter" @select="onLetterSelect" />
    </div>

    <section v-if="featuredArtists.length > 0" class="al-featured">
      <h2 class="al-section-title">推荐画家</h2>
      <div class="al-featured-scroll">
        <div v-for="artist in featuredArtists" :key="artist.id" class="al-featured-card"
          @click="goToArtist(artist.name)">
          <div class="al-featured-avatar">
            <img v-if="artist.avatar_url" :src="artist.avatar_url" class="al-featured-avatar-img" referrerpolicy="no-referrer" />
            <span v-else>{{ artist.name.charAt(0) }}</span>
          </div>
          <div class="al-featured-name">{{ artist.name }}</div>
          <div class="al-featured-meta">{{ artist.dynasty }} · {{ artist.artwork_count || 0 }}件</div>
        </div>
      </div>
    </section>

    <div v-if="loading && store.list.length === 0" class="al-loading">加载中...</div>

    <template v-else>
      <div v-if="viewMode === 'card'" class="al-card-grid">
        <ArtistCard v-for="artist in store.list" :key="artist.id" :artist="artist"
          @click="goToArtist(artist.name)" />
      </div>

      <div v-else-if="viewMode === 'timeline'">
        <ArtistTimeline :artists="store.list" @select="goToArtist" />
      </div>

      <el-table v-else :data="store.list" stripe style="width:100%" @row-click="onRowClick"
        class="al-table" empty-text="没有符合条件的艺术家">
        <el-table-column label="" width="56">
          <template #default="{ row }">
            <div class="at-avatar">
              <img v-if="row.avatar_url" :src="row.avatar_url" class="at-avatar-img" referrerpolicy="no-referrer" />
              <span v-else>{{ row.name.charAt(0) }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="姓名" prop="name" sortable="custom" width="100" />
        <el-table-column label="字号" prop="alias" min-width="120" />
        <el-table-column label="朝代" prop="dynasty" width="80" />
        <el-table-column label="生卒年" width="120">
          <template #default="{ row }">
            {{ row.birth_year || '?' }} – {{ row.death_year || '?' }}
          </template>
        </el-table-column>
        <el-table-column label="画派" prop="art_school" min-width="100" />
        <el-table-column label="作品" prop="artwork_count" width="70" />
      </el-table>

      <div v-if="viewMode === 'table' && store.total > 40" class="al-pagination">
        <el-pagination background layout="prev, pager, next" :total="store.total"
          :page-size="40" :current-page="currentPage" @current-change="onPageChange" />
      </div>

      <div v-if="viewMode !== 'table' && store.hasMore && !loadingMore" class="al-load-more">
        <el-button text @click="loadMore" :loading="loadingMore">加载更多</el-button>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { Grid, Search } from '@element-plus/icons-vue'
import { pinyin } from 'pinyin-pro'
import { useArtistStore } from '../stores/artistStore'
import { artistsApi } from '../api/artists'
import ArtistCard from '../components/artist/ArtistCard.vue'
import ArtistTimeline from '../components/artist/ArtistTimeline.vue'
import PinyinNav from '../components/artist/PinyinNav.vue'

const router = useRouter()
const store = useArtistStore()

const viewMode = ref(localStorage.getItem('artistViewMode') || 'card')
const keyword = ref('')
const dynastyFilters = ref([])
const schoolFilters = ref([])
const sortBy = ref('created_at')
const activeLetter = ref('')
const currentPage = ref(1)
const loading = ref(false)
const loadingMore = ref(false)
const featuredArtists = ref([])
let debounceTimer = null

async function fetchFeatured() {
  try {
    const data = await artistsApi.list({ featured: 1, page_size: 20 })
    featuredArtists.value = data.artists || []
  } catch (e) { console.error(e) }
}

function onViewModeChange() {
  localStorage.setItem('artistViewMode', viewMode.value)
}

const pinyinLetterNames = ref([])

function buildFilters() {
  const filters = {
    dynasty: dynastyFilters.value.join(','),
    school: schoolFilters.value.join(','),
    keyword: keyword.value,
    sort: sortBy.value,
  }
  if (pinyinLetterNames.value.length > 0) {
    filters.names = pinyinLetterNames.value.join(',')
  }
  return filters
}

async function doLoad(page = 1) {
  loading.value = true
  try {
    await store.fetchPage(page, buildFilters())
    currentPage.value = page
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

async function loadMore() {
  loadingMore.value = true
  try {
    await store.fetchPage(currentPage.value + 1, buildFilters())
    currentPage.value++
  } catch (e) {
    console.error(e)
  } finally {
    loadingMore.value = false
  }
}

function onFilterChange() {
  store.clear()
  currentPage.value = 1
  pinyinLetterNames.value = []
  activeLetter.value = ''
  doLoad(1)
}

function onPageChange(page) {
  currentPage.value = page
  doLoad(page)
}

function debouncedSearch() {
  clearTimeout(debounceTimer)
  debounceTimer = setTimeout(() => {
    onFilterChange()
  }, 300)
}

function onLetterSelect(letter) {
  activeLetter.value = letter
  const matching = []
  for (const name of store.letterNames) {
    if (!name) continue
    const py = pinyin(name, { toneType: 'none', type: 'array' })
    const first = (py[0]?.charAt(0) || '').toUpperCase()
    if (first === letter || (letter === '#' && !/[A-Z]/.test(first))) {
      matching.push(name)
    }
  }
  pinyinLetterNames.value = matching
  store.clear()
  currentPage.value = 1
  doLoad(1)
}

function onRowClick(row) {
  goToArtist(row.name)
}

function goToArtist(name) {
  router.push(`/artist/${encodeURIComponent(name)}`)
}

let scrollObserver = null

function setupInfiniteScroll() {
  document.querySelectorAll('.al-scroll-sentinel').forEach(el => el.remove())
  if (viewMode.value !== 'card') return
  const sentinel = document.createElement('div')
  sentinel.className = 'al-scroll-sentinel'
  const grid = document.querySelector('.al-card-grid')
  if (grid) grid.after(sentinel)
  if (scrollObserver) scrollObserver.disconnect()
  scrollObserver = new IntersectionObserver((entries) => {
    if (entries[0].isIntersecting && store.hasMore && !loadingMore.value) {
      loadMore()
    }
  }, { rootMargin: '200px' })
  if (sentinel) scrollObserver.observe(sentinel)
}

watch(viewMode, () => {
  if (scrollObserver) scrollObserver.disconnect()
  setTimeout(setupInfiniteScroll, 100)
})

watch(() => store.list.length, () => {
  if (viewMode.value === 'card') {
    setTimeout(setupInfiniteScroll, 100)
  }
})

onMounted(async () => {
  await store.loadMeta()
  await Promise.all([doLoad(1), fetchFeatured()])
  setTimeout(setupInfiniteScroll, 200)
})

onUnmounted(() => {
  if (scrollObserver) scrollObserver.disconnect()
})
</script>

<style scoped>
.artist-list-page {
  max-width: 1200px;
  margin: 0 auto;
  padding: 40px 24px 80px;
  min-height: 100vh;
  background: #fafaf8;
}

.al-hero {
  text-align: center;
  margin-bottom: 32px;
}

.al-title {
  font-family: 'Noto Serif SC', 'KaiTi', 'STKaiti', serif;
  font-size: 2.25rem;
  font-weight: 500;
  color: #3a3222;
  letter-spacing: 0.15em;
  margin: 0 0 12px;
}

.al-subtitle {
  font-size: 1rem;
  color: #8a8578;
  letter-spacing: 0.2em;
  margin: 0;
}

.al-toolbar {
  margin-bottom: 32px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.al-view-switch {
  display: flex;
  justify-content: flex-end;
}

.al-filters {
  display: flex;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
}

.al-search {
  width: 240px;
}

.al-filter-select {
  width: 140px;
}

.al-sort {
  width: 130px;
}

.al-card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 14px;
}

.al-table {
  border-radius: 10px;
  overflow: hidden;
}

.at-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  overflow: hidden;
  background: linear-gradient(135deg, #c45a3c, #dbbca8);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-family: 'Noto Serif SC', 'KaiTi', 'STKaiti', serif;
  font-size: 0.85rem;
}
.at-avatar-img {
  width: 100%; height: 100%; object-fit: cover; display: block;
}

.al-loading {
  text-align: center;
  padding: 80px 0;
  color: #8a8578;
  font-size: 0.9rem;
}

.al-pagination {
  display: flex;
  justify-content: center;
  margin-top: 24px;
}

.al-load-more {
  text-align: center;
  padding: 32px 0;
}

.al-scroll-sentinel {
  height: 1px;
}

.al-featured {
  margin-bottom: 32px;
}

.al-section-title {
  font-family: 'Noto Serif SC', 'KaiTi', 'STKaiti', serif;
  font-size: 1.1rem;
  font-weight: 500;
  color: #3a3222;
  letter-spacing: 0.1em;
  margin: 0 0 14px;
  padding-left: 12px;
  border-left: 3px solid #c45a3c;
}

.al-featured-scroll {
  display: flex;
  gap: 12px;
  overflow-x: auto;
  padding: 4px 2px 12px;
  -webkit-overflow-scrolling: touch;
}

.al-featured-scroll::-webkit-scrollbar {
  height: 5px;
}

.al-featured-scroll::-webkit-scrollbar-thumb {
  background: #d6d2c8;
  border-radius: 3px;
}

.al-featured-card {
  flex-shrink: 0;
  width: 150px;
  background: #fff;
  border-radius: 10px;
  padding: 20px 14px;
  text-align: center;
  cursor: pointer;
  transition: all 0.25s ease;
  border: 1px solid #edeae1;
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.03);
}

.al-featured-card:hover {
  transform: translateY(-3px);
  box-shadow: 0 6px 22px rgba(0, 0, 0, 0.07);
  border-color: #dbbca8;
}

.al-featured-avatar {
  width: 50px;
  height: 50px;
  margin: 0 auto 10px;
  border-radius: 50%;
  overflow: hidden;
  background: linear-gradient(135deg, #c45a3c, #dbbca8);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: 'Noto Serif SC', 'KaiTi', 'STKaiti', serif;
  font-size: 1.1rem;
  font-weight: 500;
}
.al-featured-avatar-img {
  width: 100%; height: 100%; object-fit: cover; display: block;
}

.al-featured-name {
  font-family: 'Noto Serif SC', 'KaiTi', 'STKaiti', serif;
  font-size: 0.9rem;
  font-weight: 500;
  color: #3a3222;
  margin-bottom: 4px;
}

.al-featured-meta {
  font-size: 0.7rem;
  color: #8a8578;
}

@media (max-width: 768px) {
  .artist-list-page {
    padding: 24px 16px 60px;
  }

  .al-title {
    font-size: 1.75rem;
  }

  .al-filters {
    flex-direction: column;
    align-items: stretch;
  }

  .al-search,
  .al-filter-select,
  .al-sort {
    width: 100%;
  }

  .al-card-grid {
    grid-template-columns: 1fr;
  }
}
</style>
