<template>
  <el-dialog
    v-model="visible"
    title="编辑画作信息"
    width="600px"
    :close-on-click-modal="true"
    class="modern-form-dialog"
  >
    <div class="form-section">
      <h4 class="form-section-title">基本信息</h4>
      <!-- 重新上传图片按钮 -->
      <div style="margin-bottom: 16px;">
        <el-button type="primary" plain size="small" @click="triggerReplaceImage">
          重新上传图片（替换原图）
        </el-button>
        <span style="margin-left: 12px; color: var(--tupi-text-secondary, #666); font-size: 13px;">
          替换后保留元数据和面积数据，缩略图自动刷新
        </span>
      </div>
      <input type="file" ref="replaceImageInput" accept="image/*" style="display: none;" @change="handleReplaceImage" />
      <el-form :model="form" label-position="top" class="modern-form">
        <div class="form-row">
          <el-form-item label="画作标题" class="form-item-half">
            <el-input v-model="form.title" placeholder="请输入画作标题" />
          </el-form-item>
          <el-form-item label="作者姓名" class="form-item-half">
            <el-select v-model="form.artistChoice" placeholder="请选择作者" style="width: 100%" @change="onArtistChange">
              <el-option label="李鱓" value="李鱓" />
              <el-option label="郑燮" value="郑燮" />
              <el-option label="其他" value="other" />
            </el-select>
          </el-form-item>
        </div>
        <div v-if="form.artistChoice === 'other'" class="form-row">
          <el-form-item label="作者姓名（其他）">
            <el-input v-model="form.artistCustom" placeholder="请输入作者姓名" />
          </el-form-item>
        </div>
        <div class="form-row">
          <el-form-item label="创作年代" class="form-item-half">
            <el-input v-model.number="form.year" placeholder="如：1725" @change="onYearChange" />
          </el-form-item>
          <el-form-item label="作者年龄" class="form-item-half">
            <el-input v-model.number="form.age" placeholder="如：39" @change="onAgeChange">
              <template #append>岁</template>
            </el-input>
          </el-form-item>
        </div>
      </el-form>
    </div>

    <div class="form-section">
      <h4 class="form-section-title">题跋占比数据 (%)</h4>
      <el-form :model="form" label-position="top" class="modern-form">
        <el-form-item label="题跋区域">
          <el-input-number 
            v-model="form.inscriptionPercent" 
            :min="0" 
            :max="100" 
            :precision="1"
            placeholder="0.0"
            style="width: 100%"
          />
        </el-form-item>
      </el-form>
    </div>

    <div class="form-section">
      <h4 class="form-section-title">分析说明</h4>
      <el-form :model="form" label-position="top" class="modern-form">
        <el-form-item label="AI分析说明">
          <el-input 
            v-model="form.analysisNote" 
            type="textarea" 
            :rows="4" 
            placeholder="请输入AI分析说明内容"
            class="modern-textarea"
          />
        </el-form-item>
        <el-form-item label="款识题跋">
          <el-input 
            v-model="form.inscriptionContent" 
            type="textarea" 
            :rows="3" 
            placeholder="请输入款识题跋内容"
            class="modern-textarea"
          />
        </el-form-item>
        <el-form-item label="印章内容">
          <div class="seal-tag-editor">
            <!-- 已选印章标签 -->
            <div class="seal-tags-area">
              <el-tag
                v-for="(seal, idx) in sealTags"
                :key="idx"
                closable
                :type="seal.isNew ? 'success' : undefined"
                class="seal-tag"
                @close="removeSealTag(idx)"
                @mouseenter="showSealPreview(seal.name)"
                @mouseleave="hideSealPreview"
              >
                {{ seal.name }}
                <template v-if="sealTypeMap[seal.name]">
                  <span class="seal-tag-type">({{ sealTypeMap[seal.name] }})</span>
                </template>
              </el-tag>
              <el-button v-if="sealTags.length > 0" type="danger" text size="small" @click="clearAllSeals" class="clear-seals-btn">
                清空
              </el-button>
              <!-- hover 图片预览 -->
              <div v-if="previewSeal && sealImageMap[previewSeal]" class="seal-preview-popup">
                <img :src="sealImageMap[previewSeal]" class="seal-preview-img" />
              </div>
            </div>
            <!-- 手动输入 -->
            <div class="seal-input-row">
              <el-input
                v-model="sealInput"
                placeholder="输入印章名回车添加"
                size="small"
                style="width: 200px;"
                @keyup.enter="addSealInput"
              />
            </div>
            <!-- 印章库按类型分组列出 -->
            <div v-if="sealLibrary.length > 0" class="seal-library">
              <div class="seal-library-title">印章库（点击添加）</div>
              <div v-for="group in groupedSeals" :key="group.type" class="seal-group">
                <div class="seal-group-header">{{ group.type }}</div>
                <div class="seal-library-grid">
                  <div
                    v-for="s in group.seals"
                    :key="s.name"
                    class="seal-library-item"
                    :class="{ 'is-selected': sealTags.some(t => t.name === s.name) }"
                    @click="addSealFromLibrary(s.name)"
                    @mouseenter="showSealPreview(s.name)"
                    @mouseleave="hideSealPreview"
                  >
                    <div v-if="sealImageMap[s.name]" class="seal-lib-thumb">
                      <img :src="sealImageMap[s.name]" />
                    </div>
                    <div v-else class="seal-lib-icon">
                      <el-icon :size="14"><Stamp /></el-icon>
                    </div>
                    <span class="seal-lib-name">{{ s.name }}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </el-form-item>
        <el-form-item label="备注信息">
          <el-input 
            v-model="form.notes" 
            type="textarea" 
            :rows="3" 
            placeholder="请输入备注信息"
            class="modern-textarea"
          />
        </el-form-item>
      </el-form>
    </div>

    <template #footer>
      <div class="dialog-footer modern-footer">
        <el-button @click="visible = false" class="btn-cancel">取消</el-button>
        <el-button v-if="authStore.isAdmin || (authStore.isEditor && form.owner_id === authStore.userId)" type="danger" @click="handleDelete" class="btn-delete">删除</el-button>
        <el-button type="primary" @click="handleSave" class="btn-submit">保存</el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, reactive, computed, watch } from 'vue'
import { ElMessage, ElMessageBox, ElLoading } from 'element-plus'
import { ArrowDown, Stamp } from '@element-plus/icons-vue'
import { tubiApi, sealsApi } from '../../api'
import { ARTISTS } from '../../tubi/constants'
import { calculateAge, calculateYear, getDisplayAge } from '../../tubi/utils'
import { useAuthStore } from '../../stores/authStore'

const API_BASE = import.meta.env.VITE_API_BASE || '/api/v1'

const authStore = useAuthStore()

const emit = defineEmits(['saved', 'deleted', 'replaced'])

const visible = ref(false)
const replaceImageInput = ref(null)

const form = reactive({
  id: '',
  owner_id: '',
  title: '',
  artistChoice: '',
  artistCustom: '',
  year: '',
  age: '',
  notes: '',
  analysisNote: '',
  inscriptionContent: '',
  sealContent: '',
  inscriptionPercent: 0,
  paintingPercent: 0,
  blankPercent: 0
})

// 印章标签模式
const sealTags = ref([])
const sealInput = ref('')
const sealLibrary = ref([])
const sealImageMap = ref({})
const sealTypeMap = ref({})
const previewSeal = ref(null)

const availableSeals = computed(() => {
  return sealLibrary.value.filter(s => !sealTags.value.some(t => t.name === s.name))
})

// 按类型分组的印章库（名章在前，闲章/收藏印在后）
const groupedSeals = computed(() => {
  const groups = []
  const typeOrder = ['名章', '闲章', '收藏印']
  const grouped = {}
  for (const s of sealLibrary.value) {
    const type = s.seal_type || '名章'
    if (!grouped[type]) grouped[type] = []
    grouped[type].push(s)
  }
  // 按预定义顺序输出
  for (const t of typeOrder) {
    if (grouped[t] && grouped[t].length > 0) {
      groups.push({ type: t, seals: grouped[t] })
    }
  }
  // 其他未在预定义中的类型
  for (const t of Object.keys(grouped)) {
    if (!typeOrder.includes(t)) {
      groups.push({ type: t, seals: grouped[t] })
    }
  }
  return groups
})

function parseSealContent(content) {
  if (!content) return []
  // 去掉"作者印："前缀
  const cleaned = content.replace(/^作者印[：:]\s*/, '')
  return cleaned.split(/[、，,]/).map(n => n.trim()).filter(n => n).map(n => ({ name: n, isNew: false }))
}

function sealTagsToString() {
  const names = sealTags.value.map(t => t.name).filter(n => n)
  return names.length > 0 ? names.join('、') : ''
}

function removeSealTag(idx) {
  sealTags.value.splice(idx, 1)
  form.sealContent = sealTagsToString()
}

function addSealInput() {
  const name = sealInput.value.trim()
  if (!name) return
  if (sealTags.value.some(t => t.name === name)) {
    ElMessage.warning('该印章已添加')
    return
  }
  sealTags.value.push({ name, isNew: true })
  form.sealContent = sealTagsToString()
  sealInput.value = ''
}

function addSealFromLibrary(name) {
  if (sealTags.value.some(t => t.name === name)) return
  sealTags.value.push({ name, isNew: false })
  form.sealContent = sealTagsToString()
}

function clearAllSeals() {
  sealTags.value = []
  form.sealContent = ''
}

function showSealPreview(name) {
  previewSeal.value = name
}

function hideSealPreview() {
  previewSeal.value = null
}

async function loadSealLibrary() {
  try {
    const params = { limit: 200 }
    if (artist.value) params.artist = artist.value
    const res = await sealsApi.list(params)
    if (res.success) {
      sealLibrary.value = res.seals || []
      // 构建图片映射和类型映射
      const imgMap = {}
      const typeMap = {}
      for (const s of sealLibrary.value) {
        if (s.images && s.images.length > 0) {
          const img = s.images[0]
          imgMap[s.name] = img.startsWith('http') ? img : `${API_BASE.replace('/api/v1', '')}${img}`
        }
        if (s.seal_type) {
          typeMap[s.name] = s.seal_type
        }
      }
      sealImageMap.value = imgMap
      sealTypeMap.value = typeMap
    }
  } catch (e) {
    console.error('加载印章库失败', e)
  }
}

const artist = computed(() => {
  if (form.artistChoice === 'other') {
    return (form.artistCustom || '').trim()
  }
  return form.artistChoice
})

function open(item) {
  form.id = item.id
  form.owner_id = item.owner_id
  form.title = item.title || ''
  const existingArtist = item.artist || ''
  if (existingArtist === '李鱓' || existingArtist === '郑燮') {
    form.artistChoice = existingArtist
    form.artistCustom = ''
  } else {
    form.artistChoice = 'other'
    form.artistCustom = existingArtist
  }
  form.year = item.year || ''
  form.age = getDisplayAge(item) ?? ''
  form.notes = item.notes || ''
  form.analysisNote = item.analysisNote || item.analysis_note || ''
  form.inscriptionContent = item.inscriptionContent || item.inscription_content || ''
  form.sealContent = item.sealContent || item.seal_content || ''
  form.inscriptionPercent = item.inscriptionPercent || item.inscription_percent || 0
  form.paintingPercent = item.paintingPercent || item.painting_percent || 0
  form.blankPercent = item.blankPercent || item.blank_percent || 0

  // 解析印章标签
  sealTags.value = parseSealContent(form.sealContent)
  sealInput.value = ''

  // 加载印章库
  loadSealLibrary()

  visible.value = true
}

function onArtistChange(artistChoice) {
  if (artistChoice === 'other') return
  const artistInfo = ARTISTS[artistChoice]
  if (artistInfo) {
    form.year = artistInfo.defaultYear
    form.age = calculateAge(artistInfo.defaultYear, artistChoice)
  }
  // 作者切换时重新加载印章库
  loadSealLibrary()
}

function onYearChange(year) {
  if (year && !isNaN(parseInt(year)) && ARTISTS[artist.value]) {
    form.age = calculateAge(year, artist.value)
  }
}

function onAgeChange(age) {
  if (age && !isNaN(parseInt(age)) && ARTISTS[artist.value]) {
    form.year = calculateYear(age, artist.value)
  }
}

async function handleSave() {
  try {
    const finalArtist = artist.value
    if (form.artistChoice === 'other' && !finalArtist) {
      ElMessage.warning('请输入作者姓名')
      return
    }
    const response = await tubiApi.updateImageInfo(form.id, {
      title: form.title,
      artist: finalArtist,
      year: form.year ? parseInt(form.year) : null,
      age: form.age ? parseInt(form.age) : null,
      notes: form.notes,
      analysis_note: form.analysisNote,
      inscription_content: form.inscriptionContent,
      seal_content: sealTagsToString(),
      inscription_percent: parseFloat(form.inscriptionPercent) || 0,
      painting_percent: parseFloat(form.paintingPercent) || 0,
      blank_percent: parseFloat(form.blankPercent) || 0
    })

    if (response.success) {
      ElMessage.success('保存成功')
      visible.value = false
      emit('saved', {
        id: form.id,
        updates: {
          title: form.title,
          artist: finalArtist,
          year: form.year,
          age: form.age,
          notes: form.notes,
          analysisNote: form.analysisNote,
          inscriptionContent: form.inscriptionContent,
          sealContent: sealTagsToString(),
          inscriptionPercent: parseFloat(form.inscriptionPercent) || 0,
          paintingPercent: parseFloat(form.paintingPercent) || 0,
          blankPercent: parseFloat(form.blankPercent) || 0
        }
      })
    } else {
      ElMessage.error(response.message || '保存失败')
    }
  } catch (error) {
    console.error('保存失败:', error)
    ElMessage.error('保存失败')
  }
}

async function handleDelete() {
  try {
    await ElMessageBox.confirm(
      `确定要删除「${form.title || '未命名'}」吗？`,
      '确认删除',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )

    const response = await tubiApi.deleteImage(form.id)
    if (response.success) {
      ElMessage.success('删除成功')
      visible.value = false
      emit('deleted', form.id)
    } else {
      ElMessage.error(response.message || '删除失败')
    }
  } catch (error) {
    if (error !== 'cancel') {
      console.error('删除失败:', error)
      ElMessage.error('删除失败')
    }
  }
}

function triggerReplaceImage() {
  if (!replaceImageInput.value) return
  replaceImageInput.value.click()
}

async function handleReplaceImage(event) {
  const file = event.target.files?.[0]
  if (!file) return

  const loading = ElLoading.service({
    lock: true,
    text: '正在替换图片...',
    background: 'rgba(0, 0, 0, 0.7)',
  })

  try {
    const result = await tubiApi.replaceImage(form.id, file)
    if (result.success) {
      ElMessage.success('图片替换成功！缩略图已刷新')
      emit('replaced', {
        id: form.id,
        url: result.data.url,
        thumbnail_url: result.data.thumbnail_url
      })
    } else {
      ElMessage.error(result.detail || '图片替换失败')
    }
  } catch (error) {
    console.error('图片替换失败:', error)
    ElMessage.error('图片替换失败')
  } finally {
    loading.close()
    if (replaceImageInput.value) {
      replaceImageInput.value.value = ''
    }
  }
}

defineExpose({ open })
</script>

<style scoped>
/* 现代表单样式 — 从 TubiAnalysis.css 复制 */
.modern-form-dialog :deep(.el-dialog__header) {
  background: var(--near-black);
  padding: 16px 20px;
  margin: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
}

.modern-form-dialog :deep(.el-dialog__title) {
  color: var(--parchment);
  font-size: 16px;
  font-weight: 500;
  font-family: 'Noto Serif SC', 'KaiTi', serif;
  letter-spacing: 0.08em;
  line-height: 1;
}

.modern-form-dialog :deep(.el-dialog__headerbtn) {
  position: absolute;
  right: 16px;
  top: 50%;
  transform: translateY(-50%);
  width: 28px;
  height: 28px;
  border-radius: var(--radius-sm, 6px);
  transition: background var(--transition-fast, 0.15s);
}

.modern-form-dialog :deep(.el-dialog__headerbtn:hover) {
  background: rgba(255, 255, 255, 0.1);
}

.modern-form-dialog :deep(.el-dialog__headerbtn .el-dialog__close) {
  color: rgba(245, 244, 237, 0.6);
  font-size: 14px;
  transition: color var(--transition-fast, 0.15s);
}

.modern-form-dialog :deep(.el-dialog__headerbtn:hover .el-dialog__close) {
  color: var(--parchment);
}

.modern-form-dialog :deep(.el-dialog__body) {
  padding: 0;
  background: var(--ivory, #faf9f5);
}

.form-section {
  background: white;
  margin: 16px;
  padding: 20px;
  border-radius: 12px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.06);
}

.form-section-title {
  font-size: 16px;
  font-weight: 500;
  font-family: 'Noto Serif SC', 'KaiTi', serif;
  color: var(--near-black);
  margin: 0 0 20px 0;
  padding-bottom: 12px;
  border-bottom: 2px solid var(--border-cream, #e8e5de);
  position: relative;
}

.form-section-title::after {
  content: '';
  position: absolute;
  bottom: -2px;
  left: 0;
  width: 60px;
  height: 2px;
  background: var(--cinnabar);
}

.modern-form :deep(.el-form-item__label) {
  font-size: 14px;
  font-weight: 500;
  color: #555;
  padding-bottom: 8px;
  line-height: 1.4;
}

.modern-form :deep(.el-input__wrapper) {
  border-radius: 8px;
  transition: all 0.3s ease;
}

.modern-form :deep(.el-textarea__inner) {
  border-radius: 8px;
  border: 1px solid #e0e0e0;
  padding: 12px;
  font-size: 14px;
  resize: none;
  transition: all 0.3s ease;
}

.modern-form :deep(.el-textarea__inner:hover) {
  border-color: #667eea;
}

.modern-form :deep(.el-textarea__inner:focus) {
  border-color: #667eea;
  box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
}

.form-row {
  display: flex;
  gap: 20px;
}

.form-item-half {
  flex: 1;
  margin-bottom: 16px;
}

.form-item-half :deep(.el-form-item__content) {
  width: 100%;
}

.modern-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding: 16px 24px;
  background: white;
  border-top: 1px solid #e8e8e8;
  margin: 0;
}

.btn-cancel {
  padding: 10px 24px;
  border-radius: 8px;
  border: 1px solid #d0d0d0;
  background: white;
  color: #666;
  font-weight: 500;
}

.btn-cancel:hover {
  border-color: #667eea;
  color: #667eea;
  background: #f5f3ff;
}

.btn-submit {
  padding: 10px 32px;
  border-radius: 8px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border: none;
  color: white;
  font-weight: 500;
}

.btn-submit:hover {
  background: linear-gradient(135deg, #5a6fd6 0%, #6a4190 100%);
}

.btn-delete {
  padding: 10px 24px;
  border-radius: 8px;
}

/* 印章标签编辑器 */
.seal-tag-editor {
  width: 100%;
}

.seal-tags-area {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 8px;
  min-height: 32px;
  padding: 8px;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  background: #fafaf8;
  position: relative;
}

.seal-tag {
  cursor: default;
}

.seal-tag-type {
  font-size: 10px;
  color: #999;
  margin-left: 2px;
}

.clear-seals-btn {
  margin-left: auto;
}

.seal-preview-popup {
  position: absolute;
  top: -110px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 100;
  background: white;
  border-radius: 8px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.15);
  padding: 6px;
}

.seal-preview-img {
  width: 96px;
  height: 96px;
  object-fit: contain;
}

.seal-input-row {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-bottom: 8px;
}

.seal-input-row :deep(.el-button) {
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.seal-input-row :deep(.el-button__content) {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

/* 印章库网格 */
.seal-library {
  border: 1px solid #ebe8e0;
  border-radius: 8px;
  padding: 10px;
  background: #fdfcf9;
}

.seal-library-title {
  font-size: 12px;
  color: #999;
  margin-bottom: 8px;
}

.seal-group {
  margin-bottom: 6px;
}

.seal-group:last-child {
  margin-bottom: 0;
}

.seal-group-header {
  font-size: 11px;
  font-weight: 600;
  color: #c96442;
  padding: 2px 0 4px 0;
  border-bottom: 1px dashed #ebe8e0;
  margin-bottom: 4px;
}

.seal-library-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.seal-library-item {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 8px;
  border-radius: 6px;
  border: 1px solid #e0ddd5;
  cursor: pointer;
  font-size: 12px;
  transition: all 0.15s;
  background: white;
}

.seal-library-item:hover {
  border-color: #c96442;
  background: #fef8f5;
}

.seal-library-item.is-selected {
  background: #f0ebe5;
  border-color: #c0b8a8;
  opacity: 0.6;
  cursor: default;
}

.seal-lib-thumb {
  width: 20px;
  height: 20px;
  border-radius: 3px;
  overflow: hidden;
}

.seal-lib-thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.seal-lib-icon {
  color: #c0b8a8;
}

.seal-lib-name {
  color: #333;
}

.seal-lib-type {
  font-size: 10px;
  color: #aaa;
}
</style>
