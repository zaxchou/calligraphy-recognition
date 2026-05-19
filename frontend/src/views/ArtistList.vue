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

    <ArtistTimeline v-else :artists="store.list" @select="goToArtist" />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Search } from '@element-plus/icons-vue'
import { pinyin } from 'pinyin-pro'
import { useArtistStore } from '../stores/artistStore'
import ArtistTimeline from '../components/artist/ArtistTimeline.vue'
import PinyinNav from '../components/artist/PinyinNav.vue'

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

function onFilterChange() {
  store.clear()
  pinyinLetterNames.value = []
  activeLetter.value = ''
  doLoad()
}

function debouncedSearch() {
  clearTimeout(debounceTimer)
  debounceTimer = setTimeout(onFilterChange, 300)
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

function goToArtist(name) {
  router.push(`/artist/${encodeURIComponent(name)}`)
}

onMounted(async () => {
  await store.loadMeta()
  doLoad()
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
