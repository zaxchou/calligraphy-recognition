<template>
  <div class="am-libs">
    <!-- 返回按钮（在二级详情页时显示） -->
    <div v-if="detailId" class="am-back-bar">
      <el-button size="small" text @click="detailId = null"><el-icon><ArrowLeft /></el-icon>返回作品库列表</el-button>
    </div>

    <!-- 一级：作品库列表管理 -->
    <div v-if="!detailId" class="am-lib-list">
      <div class="am-toolbar">
        <el-button type="primary" size="small" @click="showCreate = true">新建作品库</el-button>
      </div>

      <div v-if="loading" class="am-empty"><el-skeleton :rows="3" animated /></div>
      <div v-else-if="libs.length === 0" class="am-empty"><el-empty description="暂无作品库" :image-size="60" /></div>
      <div v-else class="am-lib-grid">
        <div v-for="lib in libs" :key="lib.id" class="am-lib-card" @click="detailId = lib.id">
          <div class="am-card-top">
            <div class="am-card-cover">
              <el-icon :size="32" color="#c8a45c"><Folder /></el-icon>
            </div>
            <div class="am-card-body">
              <div class="am-card-name">{{ lib.name }}</div>
              <div class="am-card-artist" v-if="lib.artist_name">{{ lib.artist_name }}</div>
              <div class="am-card-meta">
                <el-tag size="small" :type="lib.visibility === 'public' ? 'success' : 'info'">
                  {{ lib.visibility === 'public' ? '公开' : '私有' }}
                </el-tag>
                <span v-if="lib.artwork_count != null" class="am-card-count">{{ lib.artwork_count }} 件</span>
              </div>
            </div>
          </div>
          <div class="am-card-actions">
            <el-button size="small" text @click.stop="openEdit(lib)">编辑</el-button>
            <el-button size="small" text type="danger" @click.stop="handleDelete(lib)">删除</el-button>
          </div>
        </div>
      </div>
    </div>

    <!-- 二级：作品库详情（复用公共页面） -->
    <div v-else class="am-lib-detail">
      <LibraryDetail :library-id="detailId" :embedded="true" />
    </div>

    <!-- 新建/编辑对话框 -->
    <el-dialog v-model="showCreate" :title="editingLib ? '编辑作品库' : '新建作品库'" width="440px" destroy-on-close @closed="editingLib = null">
      <el-form :model="createForm" label-position="top" size="small">
        <el-form-item label="名称" required>
          <el-input v-model="createForm.name" placeholder="如：李鱓花鸟册" maxlength="100" />
        </el-form-item>
        <el-form-item label="画家">
          <el-select v-model="createForm.artist_name" filterable allow-create default-first-option
            placeholder="搜索或输入" style="width:100%" :loading="artistLoading" remote :remote-method="searchArtists">
            <el-option v-for="a in artistOptions" :key="a.name" :label="a.label" :value="a.name" />
          </el-select>
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="createForm.description" type="textarea" :rows="3" placeholder="简要描述..." />
        </el-form-item>
        <el-form-item label="可见性">
          <el-radio-group v-model="createForm.visibility">
            <el-radio value="private">私有</el-radio>
            <el-radio value="public">公开</el-radio>
          </el-radio-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button size="small" @click="showCreate = false">取消</el-button>
        <el-button size="small" type="primary" @click="handleCreate" :loading="creating">
          {{ editingLib ? '保存' : '创建' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowLeft, Folder } from '@element-plus/icons-vue'
import { libraryApi } from '../../api/index.js'
import LibraryDetail from '../LibraryDetail.vue'

const detailId = ref(null)
const loading = ref(false)
const libs = ref([])
const showCreate = ref(false)
const creating = ref(false)
const editingLib = ref(null)

const createForm = reactive({
  name: '', artist_name: '', description: '', visibility: 'private',
})

const artistOptions = ref([])
const artistLoading = ref(false)
const API_BASE = import.meta.env.VITE_API_BASE || '/api/v1'

async function fetchArtists(keyword) {
  artistLoading.value = true
  try {
    const res = await fetch(`${API_BASE}/artists?keyword=${encodeURIComponent(keyword || '')}&limit=50`)
    if (res.ok) {
      const data = await res.json()
      artistOptions.value = (data.artists || []).map(a => ({
        name: a.name, label: a.alias ? `${a.name}（${a.alias}）` : a.name,
      }))
    }
  } catch (e) { console.error(e) }
  finally { artistLoading.value = false }
}
function searchArtists(q) { fetchArtists(q) }
watch(showCreate, (v) => { if (v) fetchArtists() })

async function loadLibs() {
  loading.value = true
  try {
    const data = await libraryApi.getMine()
    libs.value = Array.isArray(data) ? data : (data.items || [])
  } catch (e) {
    ElMessage.error('加载作品库失败')
  } finally { loading.value = false }
}

async function handleCreate() {
  if (!createForm.name.trim()) { ElMessage.warning('请输入名称'); return }
  creating.value = true
  try {
    if (editingLib.value) {
      await libraryApi.update(editingLib.value.id, createForm)
      ElMessage.success('已保存')
    } else {
      await libraryApi.create(createForm)
      ElMessage.success('已创建')
    }
    showCreate.value = false
    createForm.name = ''
    createForm.artist_name = ''
    createForm.description = ''
    createForm.visibility = 'private'
    editingLib.value = null
    await loadLibs()
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || (editingLib.value ? '保存失败' : '创建失败'))
  } finally { creating.value = false }
}

function openEdit(lib) {
  editingLib.value = lib
  createForm.name = lib.name || ''
  createForm.artist_name = lib.artist_name || ''
  createForm.description = lib.description || ''
  createForm.visibility = lib.visibility || 'private'
  showCreate.value = true
  fetchArtists()
}

async function handleDelete(lib) {
  try {
    await ElMessageBox.confirm(`确定删除「${lib.name}」？`, '确认', { type: 'warning' })
    await libraryApi.delete(lib.id, true)
    ElMessage.success('已删除')
    await loadLibs()
  } catch (e) { if (e !== 'cancel') ElMessage.error('删除失败') }
}

onMounted(loadLibs)
</script>

<style scoped>
.am-libs { padding: 0; }
.am-back-bar { margin-bottom: 12px; }
.am-lib-list { display: flex; flex-direction: column; gap: 12px; }
.am-toolbar { display: flex; gap: 8px; }
.am-empty { margin: 40px auto; }
.am-lib-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 12px; }
.am-lib-card {
  background: #fff; border: 1px solid #edeae1; border-radius: 8px; overflow: hidden;
  cursor: pointer; transition: box-shadow .15s; display: flex; flex-direction: column;
}
.am-lib-card:hover { box-shadow: 0 4px 16px rgba(0,0,0,0.06); }
.am-card-top { flex: 1; padding: 14px; }
.am-card-cover {
  height: 60px; background: #faf9f5; border-radius: 6px;
  display: flex; align-items: center; justify-content: center; margin-bottom: 10px;
}
.am-card-name { font-size: 14px; font-weight: 600; color: #3a3222; margin-bottom: 4px; }
.am-card-artist { font-size: 11px; color: #b0a890; margin-bottom: 6px; }
.am-card-meta { display: flex; align-items: center; gap: 8px; }
.am-card-count { font-size: 11px; color: #8c7a5c; }
.am-card-actions { padding: 8px 14px; border-top: 1px solid #f0ebe0; display: flex; justify-content: flex-end; }
.am-lib-detail { padding: 0; }
</style>
