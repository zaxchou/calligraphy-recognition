<template>
  <div class="libraries-page">
    <div class="page-header">
      <h1 class="page-title">我的作品库</h1>
      <div class="page-actions">
        <el-button type="primary" @click="showCreateDialog = true" :disabled="!authStore.isLoggedIn">
          <el-icon><Plus /></el-icon> 新建作品库
        </el-button>
        <el-button text @click="$router.push('/libraries/public')">
          <el-icon><View /></el-icon> 浏览公开库
        </el-button>
      </div>
    </div>

    <!-- 未登录提示 -->
    <el-empty v-if="!authStore.isLoggedIn" description="请先登录以管理您的作品库" :image-size="120">
      <el-button type="primary" @click="$router.push('/login')">去登录</el-button>
    </el-empty>

    <!-- 加载中 -->
    <div v-else-if="loading" class="loading-wrap">
      <el-skeleton :rows="3" animated />
    </div>

    <!-- 空状态 -->
    <el-empty v-else-if="libraries.length === 0" description="还没有作品库，快去创建一个吧" :image-size="100">
      <el-button type="primary" @click="showCreateDialog = true">新建作品库</el-button>
    </el-empty>

    <!-- 作品库列表 -->
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
            <el-tag :type="lib.visibility === 'public' ? 'success' : 'info'" size="small">
              {{ lib.visibility === 'public' ? '公开' : '私有' }}
            </el-tag>
            <span class="meta-count">{{ lib.artwork_count || 0 }} 件作品</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 新建作品库对话框 -->
    <el-dialog v-model="showCreateDialog" title="新建作品库" width="500px" destroy-on-close>
      <el-form :model="createForm" label-position="top">
        <el-form-item label="作品库名称" required>
          <el-input v-model="createForm.name" placeholder="如：李鱓花鸟册" maxlength="100" />
        </el-form-item>
        <el-form-item label="画家">
          <el-input v-model="createForm.artist_name" placeholder="如：李鱓" maxlength="100" />
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
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Plus, View, Collection } from '@element-plus/icons-vue'
import { useAuthStore } from '../stores/authStore'
import { libraryApi } from '../api'

const router = useRouter()
const authStore = useAuthStore()

const loading = ref(false)
const libraries = ref([])
const showCreateDialog = ref(false)
const creating = ref(false)

const createForm = reactive({
  name: '',
  artist_name: '',
  description: '',
  visibility: 'private',
})

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
  padding: var(--space-3xl) var(--space-2xl);
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--space-2xl);
  flex-wrap: wrap;
  gap: var(--space-md);
}

.page-title {
  font-family: 'Noto Serif SC', serif;
  font-size: 28px;
  font-weight: 500;
  color: var(--near-black);
}

.page-actions {
  display: flex;
  gap: var(--space-md);
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
  height: 160px;
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
  gap: var(--space-md);
}

.meta-count {
  font-size: 12px;
  color: var(--stone-gray);
}
</style>
