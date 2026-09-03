<template>
  <div class="public-libraries-page">
    <div class="page-header">
      <div>
        <el-breadcrumb separator="/">
          <el-breadcrumb-item :to="{ path: '/libraries' }">{{ $t('gallery.title') }}</el-breadcrumb-item>
          <el-breadcrumb-item>{{ $t('publiclibraries.t1') }}</el-breadcrumb-item>
        </el-breadcrumb>
        <h1 class="page-title">{{ $t('publiclibraries.t1') }}</h1>
        <p class="page-subtitle">{{ $t('publiclibraries.t2') }}</p>
      </div>
    </div>

    <div v-if="loading" class="loading-wrap">
      <el-skeleton :rows="3" animated />
    </div>

    <el-empty v-else-if="libraries.length === 0" :description="$t('publiclibraries.a1')">
      <el-button type="primary" @click="$router.push('/libraries')">{{ $t('publiclibraries.t3') }}</el-button>
    </el-empty>

    <div v-else class="library-grid">
      <div
        v-for="lib in libraries"
        :key="lib.id"
        class="library-card"
        @click="$router.push(`/libraries/${lib.id}`)"
      >
        <div class="card-cover">
          <el-icon :size="48"><Collection /></el-icon>
        </div>
        <div class="card-body">
          <h3 class="card-name">{{ lib.name }}</h3>
          <p class="card-artist" v-if="lib.artist_name">{{ lib.artist_name }}</p>
          <p class="card-desc" v-if="lib.description">{{ lib.description }}</p>
          <div class="card-meta">
            <span class="meta-count">{{ lib.artwork_count || 0 }} 件作品</span>
          </div>
        </div>
      </div>
    </div>

    <div class="pagination-wrap" v-if="total > pageSize">
      <el-pagination
        v-model:current-page="currentPage"
        :page-size="pageSize"
        :total="total"
        layout="prev, pager, next"
        @current-change="loadLibraries"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { Collection } from '@element-plus/icons-vue'
import { libraryApi } from '../api'

const loading = ref(false)
const libraries = ref([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(20)

async function loadLibraries() {
  loading.value = true
  try {
    const data = await libraryApi.getPublic(currentPage.value, pageSize.value)
    libraries.value = data.items || []
    total.value = data.total || 0
  } catch (e) {
    console.error('加载公开库失败', e)
  } finally {
    loading.value = false
  }
}

onMounted(loadLibraries)
</script>

<style scoped>
.public-libraries-page {
  max-width: var(--container-wide);
  margin: 0 auto;
  padding: var(--space-3xl) var(--space-2xl);
}

.page-header {
  margin-bottom: var(--space-2xl);
}

.page-title {
  font-family: 'Noto Serif SC', serif;
  font-size: 28px;
  font-weight: 500;
  color: var(--near-black);
  margin-top: var(--space-sm);
}

.page-subtitle {
  font-size: 14px;
  color: var(--stone-gray);
  margin-top: var(--space-sm);
}

.loading-wrap {
  max-width: 600px;
  margin: var(--space-4xl) auto;
}

.library-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: var(--space-xl);
}

.library-card {
  background: var(--pure-white);
  border: 1px solid var(--border-cream);
  border-radius: var(--radius-lg);
  overflow: hidden;
  cursor: pointer;
  transition: all var(--transition-normal);
}

.library-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 30px rgba(0, 0, 0, 0.08);
  border-color: var(--border-warm);
}

.card-cover {
  height: 140px;
  background: linear-gradient(135deg, var(--ivory), var(--parchment));
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--ring-warm);
}

.card-body {
  padding: var(--space-lg);
}

.card-name {
  font-family: 'Noto Serif SC', serif;
  font-size: 18px;
  font-weight: 500;
  color: var(--near-black);
  margin-bottom: 4px;
}

.card-artist {
  font-size: 13px;
  color: var(--stone-gray);
  margin-bottom: 4px;
}

.card-desc {
  font-size: 13px;
  color: var(--olive-gray);
  margin-bottom: var(--space-md);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.card-meta {
  display: flex;
  align-items: center;
}

.meta-count {
  font-size: 12px;
  color: var(--stone-gray);
}

.pagination-wrap {
  margin-top: var(--space-2xl);
  display: flex;
  justify-content: center;
}
</style>
