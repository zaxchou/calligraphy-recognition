<template>
  <div class="artist-list-page">
    <div class="al-hero">
      <h1 class="al-title">艺术家百科</h1>
      <p class="al-subtitle">探索历代书画家的艺术世界</p>
    </div>

    <div class="al-toolbar">
      <div class="al-toolbar-top">
        <el-input v-model="keyword" placeholder="搜索画家、字号..." clearable class="al-search"
          @input="debouncedSearch" @clear="onFilterChange">
          <template #prefix><el-icon><Search /></el-icon></template>
        </el-input>
        <el-select v-model="dynastyFilters" placeholder="朝代" clearable multiple collapse-tags
          collapse-tags-tooltip class="al-filter" @change="onFilterChange">
          <el-option v-for="p in store.periods" :key="p" :label="p" :value="p" />
        </el-select>
        <el-select v-model="schoolFilters" placeholder="画派" clearable multiple collapse-tags
          collapse-tags-tooltip class="al-filter" @change="onFilterChange">
          <el-option v-for="s in store.schools" :key="s.id" :label="s.name" :value="s.name" />
        </el-select>
        <el-select v-model="sortBy" placeholder="排序" class="al-sort" @change="onFilterChange">
          <el-option label="出生年份" value="birth_year" />
          <el-option label="姓名 A-Z" value="name" />
        </el-select>
      </div>

      <PinyinNav :names="store.letterNames" :active-letter="activeLetter" @select="onLetterSelect" />
    </div>

    <div v-if="loading" class="al-loading">加载中...</div>

    <template v-else>
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

      <ArtistTimeline :artists="store.list" :auto-expand="isFilterActive" @select="goToArtist" />
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Search } from '@element-plus/icons-vue'
import { pinyin } from 'pinyin-pro'
import { useArtistStore } from '../stores/artistStore'
import ArtistTimeline from '../components/artist/ArtistTimeline.vue'
import PinyinNav from '../components/artist/PinyinNav.vue'
import { artistsApi } from '../api/artists'

const router = useRouter()
const store = useArtistStore()

const keyword = ref('')
const dynastyFilters = ref([])
const schoolFilters = ref([])
const sortBy = ref('birth_year')
const activeLetter = ref('')
const loading = ref(true)
let debounceTimer = null

const pinyinLetterNames = ref([])
const pinyinSearchNames = ref([])
const featuredArtists = ref([])

async function fetchFeatured() {
  try {
    const data = await artistsApi.list({ featured: 1, page_size: 20 })
    featuredArtists.value = data.artists || []
  } catch (e) { console.error(e) }
}

function buildFilters() {
  const filters = {
    dynasty: dynastyFilters.value.join(','),
    school: schoolFilters.value.join(','),
    keyword: keyword.value,
    sort: sortBy.value,
  }
  if (pinyinLetterNames.value.length > 0 || pinyinSearchNames.value.length > 0) {
    const names = new Set([
      ...pinyinLetterNames.value,
      ...pinyinSearchNames.value,
    ])
    filters.names = [...names].join(',')
  }
  return filters
}

async function doLoad() {
  loading.value = true
  try {
    await store.fetchAll(buildFilters())
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

function debouncedSearch() {
  clearTimeout(debounceTimer)
  debounceTimer = setTimeout(() => {
    handlePinyinSearch()
  }, 300)
}

function handlePinyinSearch() {
  pinyinSearchNames.value = []
  const kw = keyword.value.trim().toLowerCase()
  if (kw && /^[a-z]+$/.test(kw)) {
    const matching = []
    for (const name of store.letterNames) {
      if (!name) continue
      const py = pinyin(name, { toneType: 'none', type: 'array' })
      const initials = py.map(p => (p[0] || '').toLowerCase()).join('')
      if (initials.includes(kw) || name.toLowerCase().includes(kw)) {
        matching.push(name)
      }
    }
    if (matching.length > 0) {
      pinyinSearchNames.value = matching
    }
  }
  onFilterChange()
}

function onFilterChange() {
  store.clear()
  pinyinLetterNames.value = []
  pinyinSearchNames.value = []
  activeLetter.value = ''
  doLoad()
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
  doLoad()
}

const isFilterActive = computed(() => {
  return !!keyword.value
    || dynastyFilters.value.length > 0
    || schoolFilters.value.length > 0
    || !!activeLetter.value
})

function goToArtist(name) {
  router.push(`/artist/${encodeURIComponent(name)}`)
}

onMounted(async () => {
  await store.loadMeta()
  await Promise.all([doLoad(), fetchFeatured()])
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
  gap: 10px;
}

.al-toolbar-top {
  display: flex;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
  justify-content: center;
}

.al-search {
  width: 260px;
  max-width: 100%;
}

.al-filter {
  width: 130px;
}

.al-sort {
  width: 120px;
}

.al-loading {
  text-align: center;
  padding: 80px 0;
  color: #8a8578;
  font-size: 0.9rem;
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

  .al-toolbar-top {
    flex-direction: column;
    align-items: stretch;
  }

  .al-search,
  .al-filter,
  .al-sort {
    width: 100%;
  }
}
</style>
