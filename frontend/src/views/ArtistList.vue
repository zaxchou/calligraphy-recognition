<template>
  <div class="artist-list-page">
    <div class="al-hero">
      <h1 class="al-title">艺术家百科</h1>
      <p class="al-subtitle">探索历代书画家的艺术世界</p>
    </div>

    <div class="al-filter-bar">
      <el-input v-model="searchQuery" placeholder="搜索画家..." clearable @input="onSearch" class="al-search" />
      <el-select v-model="dynastyFilter" placeholder="朝代" clearable @change="fetchArtists" class="al-filter-select">
        <el-option v-for="p in periods" :key="p" :label="p" :value="p" />
      </el-select>
      <el-select v-model="schoolFilter" placeholder="画派" clearable @change="fetchArtists" class="al-filter-select">
        <el-option v-for="s in schools" :key="s.id" :label="s.name" :value="s.name" />
      </el-select>
    </div>

    <section v-if="featuredArtists.length > 0" class="al-section">
      <h2 class="al-section-title">推荐画家</h2>
      <div class="al-featured-scroll">
        <div v-for="artist in featuredArtists" :key="artist.id" class="al-featured-card" @click="goToArtist(artist.name)">
          <div class="al-card-avatar">{{ artist.name.charAt(0) }}</div>
          <div class="al-card-name">{{ artist.name }}</div>
          <div class="al-card-alias">{{ artist.alias || '' }}</div>
          <div class="al-card-meta">{{ artist.dynasty }} · {{ artist.artwork_count || 0 }}件作品</div>
        </div>
      </div>
    </section>

    <div v-for="group in dynastyGroups" :key="group.dynasty" class="al-section">
      <h2 class="al-section-title">{{ group.dynasty }}</h2>
      <div class="al-grid">
        <div v-for="artist in group.artists" :key="artist.id" class="al-card" @click="goToArtist(artist.name)">
          <div class="al-card-avatar">{{ artist.name.charAt(0) }}</div>
          <div class="al-card-info">
            <div class="al-card-name">{{ artist.name }}</div>
            <div class="al-card-alias">{{ artist.alias || '' }}</div>
            <div class="al-card-years">{{ artist.birth_year || '?' }}{{ artist.death_year ? '-' + artist.death_year : '' }}</div>
            <div class="al-card-tags">
              <span v-if="artist.dynasty" class="al-tag">{{ artist.dynasty }}</span>
              <span v-if="artist.art_school" class="al-tag al-tag-school">{{ artist.art_school }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div v-if="loading" class="al-loading">加载中...</div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()
const API_BASE = import.meta.env.VITE_API_BASE || '/api/v1'

const featuredArtists = ref([])
const allArtists = ref([])
const periods = ref([])
const schools = ref([])
const searchQuery = ref('')
const dynastyFilter = ref('')
const schoolFilter = ref('')
const loading = ref(true)

const dynastyGroups = computed(() => {
  const filtered = allArtists.value.filter(a => {
    if (dynastyFilter.value && a.dynasty !== dynastyFilter.value) return false
    if (schoolFilter.value && a.art_school !== schoolFilter.value) return false
    return true
  })
  const groups = {}
  for (const a of filtered) {
    const d = a.dynasty || '未知'
    if (!groups[d]) groups[d] = { dynasty: d, artists: [] }
    groups[d].artists.push(a)
  }
  return Object.values(groups)
})

async function fetchFeatured() {
  try {
    const res = await fetch(`${API_BASE}/artists?featured=1&page_size=20`)
    const data = await res.json()
    featuredArtists.value = data.artists || []
  } catch (e) { console.error(e) }
}

async function fetchArtists() {
  try {
    const params = new URLSearchParams({ page_size: 200, sort: 'created_at' })
    if (dynastyFilter.value) params.set('dynasty', dynastyFilter.value)
    if (schoolFilter.value) params.set('school', schoolFilter.value)
    if (searchQuery.value) params.set('keyword', searchQuery.value)
    const res = await fetch(`${API_BASE}/artists?${params}`)
    const data = await res.json()
    allArtists.value = data.artists || []
  } catch (e) { console.error(e) }
}

async function fetchPeriods() {
  try {
    const res = await fetch(`${API_BASE}/artists/periods`)
    const data = await res.json()
    periods.value = data.periods || []
  } catch (e) { console.error(e) }
}

async function fetchSchools() {
  try {
    const res = await fetch(`${API_BASE}/artists/schools`)
    const data = await res.json()
    schools.value = data.schools || []
  } catch (e) { console.error(e) }
}

function onSearch() {
  fetchArtists()
}

function goToArtist(name) {
  router.push(`/artist/${encodeURIComponent(name)}`)
}

onMounted(async () => {
  loading.value = true
  await Promise.all([fetchFeatured(), fetchArtists(), fetchPeriods(), fetchSchools()])
  loading.value = false
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
  margin-bottom: 40px;
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

.al-filter-bar {
  display: flex;
  gap: 12px;
  margin-bottom: 48px;
  align-items: center;
  flex-wrap: wrap;
}

.al-search {
  width: 260px;
}

.al-filter-select {
  width: 160px;
}

.al-section {
  margin-bottom: 48px;
}

.al-section-title {
  font-family: 'Noto Serif SC', 'KaiTi', 'STKaiti', serif;
  font-size: 1.25rem;
  font-weight: 500;
  color: #3a3222;
  letter-spacing: 0.1em;
  margin: 0 0 20px;
  padding-left: 12px;
  border-left: 3px solid #c45a3c;
}

.al-featured-scroll {
  display: flex;
  gap: 16px;
  overflow-x: auto;
  padding: 8px 4px 16px;
  scroll-snap-type: x mandatory;
  -webkit-overflow-scrolling: touch;
}

.al-featured-scroll::-webkit-scrollbar {
  height: 6px;
}

.al-featured-scroll::-webkit-scrollbar-track {
  background: transparent;
}

.al-featured-scroll::-webkit-scrollbar-thumb {
  background: #d6d2c8;
  border-radius: 3px;
}

.al-featured-card {
  flex-shrink: 0;
  width: 180px;
  background: #fff;
  border-radius: 12px;
  padding: 24px 16px;
  text-align: center;
  cursor: pointer;
  transition: all 0.3s ease;
  border: 1px solid #edeae1;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.04);
  scroll-snap-align: start;
}

.al-featured-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 8px 28px rgba(0, 0, 0, 0.08);
  border-color: #dbbca8;
}

.al-featured-card .al-card-avatar {
  width: 64px;
  height: 64px;
  font-size: 1.5rem;
  margin: 0 auto 12px;
}

.al-featured-card .al-card-name {
  font-size: 1rem;
  margin-bottom: 4px;
}

.al-featured-card .al-card-alias {
  font-size: 0.75rem;
  margin-bottom: 8px;
}

.al-featured-card .al-card-meta {
  font-size: 0.75rem;
  color: #8a8578;
}

.al-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
}

.al-card {
  display: flex;
  gap: 16px;
  background: #fff;
  border-radius: 12px;
  padding: 20px;
  cursor: pointer;
  transition: all 0.3s ease;
  border: 1px solid #edeae1;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.04);
}

.al-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 28px rgba(0, 0, 0, 0.08);
  border-color: #dbbca8;
}

.al-card-avatar {
  width: 56px;
  height: 56px;
  flex-shrink: 0;
  border-radius: 50%;
  background: linear-gradient(135deg, #c45a3c, #dbbca8);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: 'Noto Serif SC', 'KaiTi', 'STKaiti', serif;
  font-size: 1.25rem;
  font-weight: 500;
}

.al-card-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.al-card-name {
  font-family: 'Noto Serif SC', 'KaiTi', 'STKaiti', serif;
  font-size: 1.05rem;
  font-weight: 500;
  color: #3a3222;
  line-height: 1.3;
}

.al-card-alias {
  font-size: 0.8rem;
  color: #8a8578;
  line-height: 1.3;
}

.al-card-years {
  font-size: 0.8rem;
  color: #a09b8e;
}

.al-card-tags {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  margin-top: 4px;
}

.al-tag {
  display: inline-block;
  font-size: 0.7rem;
  padding: 2px 10px;
  border-radius: 999px;
  background: #f5f0ea;
  color: #8a6f4c;
  letter-spacing: 0.04em;
  line-height: 1.5;
}

.al-tag-school {
  background: #f0ede8;
  color: #6b6b60;
}

.al-loading {
  text-align: center;
  padding: 60px 0;
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

  .al-filter-bar {
    flex-direction: column;
    align-items: stretch;
  }

  .al-search,
  .al-filter-select {
    width: 100%;
  }

  .al-grid {
    grid-template-columns: 1fr;
  }

  .al-featured-card {
    width: 150px;
    padding: 20px 12px;
  }

  .al-featured-card .al-card-avatar {
    width: 52px;
    height: 52px;
    font-size: 1.25rem;
  }
}
</style>
