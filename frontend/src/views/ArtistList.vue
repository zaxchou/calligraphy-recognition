<template>
  <div class="artist-list-page">
    <div class="al-hero">
      <h1 class="al-title">艺术家百科</h1>
      <p class="al-subtitle">探索历代书画家的艺术世界</p>
    </div>

    <div class="al-toolbar">
      <el-input v-model="keyword" placeholder="搜索画家/字号..." clearable class="al-search"
        @input="debouncedSearch" @clear="onFilterChange">
        <template #prefix><el-icon><Search /></el-icon></template>
      </el-input>
    </div>

    <div v-if="loading" class="al-loading">加载中...</div>

    <ArtistTimeline v-else :artists="store.list" @select="goToArtist" />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Search } from '@element-plus/icons-vue'
import { useArtistStore } from '../stores/artistStore'
import ArtistTimeline from '../components/artist/ArtistTimeline.vue'

const router = useRouter()
const store = useArtistStore()

const keyword = ref('')
const loading = ref(true)
let debounceTimer = null

function buildFilters() {
  return {
    keyword: keyword.value,
    sort: 'birth_year',
  }
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
  doLoad()
}

function debouncedSearch() {
  clearTimeout(debounceTimer)
  debounceTimer = setTimeout(onFilterChange, 300)
}

function goToArtist(name) {
  router.push(`/artist/${encodeURIComponent(name)}`)
}

onMounted(() => doLoad())
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
  justify-content: center;
}

.al-search {
  width: 360px;
  max-width: 100%;
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

  .al-search {
    width: 100%;
  }
}
</style>
