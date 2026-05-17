<template>
  <div class="libraries-page" :class="{ 'embedded': embedded }">
    <div class="page-header" v-if="!embedded">
      <h1 class="page-title">我的作品库</h1>
    </div>

    <div class="libraries-toolbar">
      <div class="toolbar-left">
        <el-button type="primary" @click="showCreateDialog = true" :disabled="!authStore.isLoggedIn">
          <el-icon><Plus /></el-icon> 新建作品库
        </el-button>
        <el-button plain @click="$router.push('/libraries/public')">
          <el-icon><View /></el-icon> 浏览公开库
        </el-button>
      </div>
      <div class="toolbar-right">
        <el-radio-group v-model="viewMode" size="small">
          <el-radio-button value="card">
            <el-icon><Grid /></el-icon>
          </el-radio-button>
          <el-radio-button value="list">
            <el-icon><List /></el-icon>
          </el-radio-button>
        </el-radio-group>
      </div>
    </div>

    <div v-if="!authStore.isLoggedIn" class="empty-wrap">
      <el-empty description="请先登录以管理您的作品库" :image-size="100">
        <el-button type="primary" @click="$router.push('/login')">去登录</el-button>
      </el-empty>
    </div>

    <div v-else-if="loading" class="loading-wrap">
      <el-skeleton :rows="4" animated />
    </div>

    <div v-else-if="libraries.length === 0" class="empty-wrap">
      <el-empty description="还没有作品库，快去创建一个吧" :image-size="80">
        <el-button type="primary" @click="showCreateDialog = true">新建作品库</el-button>
      </el-empty>
    </div>

    <!-- 卡片模式 -->
    <div v-else-if="viewMode === 'card'" class="library-grid">
      <div
        v-for="lib in libraries"
        :key="lib.id"
        class="library-card"
        @click="$router.push(`/libraries/${lib.id}`)"
      >
        <div class="card-cover">
          <el-icon :size="40"><Collection /></el-icon>
          <el-tag
            :type="lib.visibility === 'public' ? 'success' : 'info'"
            size="small"
            effect="dark"
            class="card-vis-tag"
          >
            {{ lib.visibility === 'public' ? '公开' : '私有' }}
          </el-tag>
        </div>
        <div class="card-body">
          <h3 class="card-name">{{ lib.name }}</h3>
          <p class="card-artist" v-if="lib.artist_name">{{ lib.artist_name }}</p>
          <p class="card-desc" v-if="lib.description">{{ lib.description }}</p>
          <div class="card-footer">
            <span class="card-count">{{ lib.artwork_count || 0 }} 件作品</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 列表模式 -->
    <div v-else class="library-list-wrap">
      <el-table :data="libraries" stripe size="small" style="width:100%" @row-click="row => $router.push(`/libraries/${row.id}`)">
        <el-table-column label="作品库" min-width="180">
          <template #default="{ row }">
            <div class="list-name">
              <el-icon><Collection /></el-icon>
              <span>{{ row.name }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="artist_name" label="画家" width="120" />
        <el-table-column prop="description" label="描述" min-width="200" show-overflow-tooltip>
          <template #default="{ row }">{{ row.description || '-' }}</template>
        </el-table-column>
        <el-table-column label="可见性" width="80">
          <template #default="{ row }">
            <el-tag :type="row.visibility === 'public' ? 'success' : 'info'" size="small" effect="plain">
              {{ row.visibility === 'public' ? '公开' : '私有' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="作品数" width="80" align="center">
          <template #default="{ row }">{{ row.artwork_count || 0 }}</template>
        </el-table-column>
      </el-table>
    </div>

    <el-dialog v-model="showCreateDialog" title="新建作品库" width="500px" destroy-on-close>
      <el-form :model="createForm" label-position="top">
        <el-form-item label="作品库名称" required>
          <el-input v-model="createForm.name" placeholder="如：李鱓花鸟册" maxlength="100" />
        </el-form-item>
        <el-form-item label="画家">
          <el-select v-model="createForm.artist_name" filterable allow-create default-first-option placeholder="搜索或输入新画家" style="width:100%" :loading="artistLoading" remote :remote-method="searchArtists">
            <el-option v-for="a in artistOptions" :key="a.name" :label="a.label" :value="a.name" />
          </el-select>
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="createForm.description" type="textarea" :rows="3" placeholder="简要描述这个作品库..." />
        </el-form-item>
        <el-form-item label="可见性">
          <el-radio-group v-model="createForm.visibility">
            <el-radio value="private">私有（仅自己可见）</el-radio>
            <el-radio value="public">公开（所有人可见）</el-radio>
          </el-radio-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" @click="handleCreate" :loading="creating">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Plus, View, Collection, Grid, List } from '@element-plus/icons-vue'
import { useAuthStore } from '../stores/authStore'
import { libraryApi } from '../api'

const props = defineProps({
  embedded: { type: Boolean, default: false }
})

const router = useRouter()
const authStore = useAuthStore()

const viewMode = ref('card')
const loading = ref(false)
const libraries = ref([])
const showCreateDialog = ref(false)
const creating = ref(false)
const artistOptions = ref([])
const artistLoading = ref(false)
const API_BASE = import.meta.env.VITE_API_BASE || '/api/v1'

const createForm = reactive({
  name: '',
  artist_name: '',
  description: '',
  visibility: 'private',
})

async function fetchArtists(keyword) {
  artistLoading.value = true
  try {
    const params = new URLSearchParams({ limit: 50 })
    if (keyword) params.set('keyword', keyword)
    const res = await fetch(`${API_BASE}/artists?${params}`)
    if (res.ok) {
      const data = await res.json()
      const list = data.artists || data.data || []
      artistOptions.value = list.map(a => ({
        name: a.name,
        label: a.alias ? `${a.name}（${a.alias}）` : a.name,
      }))
    }
  } catch (e) { console.error(e) }
  finally { artistLoading.value = false }
}

function searchArtists(q) {
  if (q) fetchArtists(q)
  else fetchArtists()
}

watch(showCreateDialog, (v) => { if (v) fetchArtists() })

async function loadLibraries() {
  if (!authStore.isLoggedIn) return
  loading.value = true
  try {
    const data = await libraryApi.getMine()
    libraries.value = Array.isArray(data) ? data : (data.items || [])
  } catch (e) {
    ElMessage.error('加载作品库失败')
  } finally {
    loading.value = false
  }
}

async function handleCreate() {
  if (!createForm.name.trim()) {
    ElMessage.warning('请输入作品库名称')
    return
  }
  creating.value = true
  try {
    await libraryApi.create(createForm)
    ElMessage.success('作品库创建成功')
    showCreateDialog.value = false
    createForm.name = ''
    createForm.artist_name = ''
    createForm.description = ''
    createForm.visibility = 'private'
    await loadLibraries()
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '创建失败')
  } finally {
    creating.value = false
  }
}

onMounted(loadLibraries)
</script>

<style scoped>
.libraries-page {
  max-width: var(--container-wide);
  margin: 0 auto;
  padding: var(--space-2xl) var(--space-xl);
}
.libraries-page.embedded {
  padding: 0;
}
.page-title {
  font-family: 'Noto Serif SC', serif;
  font-size: 24px;
  font-weight: 500;
  color: var(--near-black);
  margin-bottom: var(--space-xl);
}
.libraries-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--space-xl);
  flex-wrap: wrap;
  gap: var(--space-md);
}
.toolbar-left {
  display: flex;
  gap: var(--space-sm);
}
.loading-wrap {
  max-width: 600px;
  margin: var(--space-4xl) auto;
}
.empty-wrap {
  margin: var(--space-4xl) auto;
}

/* ── 卡片模式 ── */
.library-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: var(--space-lg);
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
  transform: translateY(-3px);
  box-shadow: 0 8px 28px rgba(0,0,0,0.07);
  border-color: var(--border-warm);
}
.card-cover {
  height: 120px;
  background: linear-gradient(135deg, var(--ivory), var(--parchment));
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--ring-warm);
  position: relative;
}
.card-vis-tag {
  position: absolute;
  top: 10px;
  right: 10px;
}
.card-body {
  padding: var(--space-md) var(--space-lg);
}
.card-name {
  font-family: 'Noto Serif SC', serif;
  font-size: 16px;
  font-weight: 500;
  color: var(--near-black);
  margin-bottom: 2px;
}
.card-artist {
  font-size: 12px;
  color: var(--stone-gray);
  margin-bottom: 4px;
}
.card-desc {
  font-size: 12px;
  color: var(--olive-gray);
  margin-bottom: var(--space-sm);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  line-height: 1.5;
}
.card-footer {
  display: flex;
  align-items: center;
  gap: var(--space-md);
  padding-top: var(--space-sm);
  border-top: 1px solid var(--border-cream);
}
.card-count {
  font-size: 12px;
  color: var(--stone-gray);
}

/* ── 列表模式 ── */
.library-list-wrap {
  border: 1px solid var(--border-cream);
  border-radius: var(--radius-lg);
  overflow: hidden;
}
.list-name {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 500;
  color: var(--near-black);
}
</style>
