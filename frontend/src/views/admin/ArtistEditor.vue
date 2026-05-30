<template>
  <div class="ae-root">
    <div class="ae-sidebar">
      <div class="ae-sidebar-top">
        <el-button text size="small" @click="goBack" class="ae-back-btn"><el-icon><ArrowLeft /></el-icon></el-button>
        <span class="ae-artist-name" :title="form.name || '新建'">{{ form.name || '新建' }}</span>
      </div>
      <nav class="ae-nav">
        <a v-for="s in sections" :key="s.id" class="ae-nav-item" :class="{ active: activeSection === s.id }" @click="scrollTo(s.id)">
          {{ s.label }}
        </a>
      </nav>
      <div class="ae-sidebar-actions">
        <el-button size="small" @click="handleAiFill" :loading="aiLoading">
          <el-icon><MagicStick /></el-icon>AI补充
        </el-button>
        <el-button size="small" type="primary" @click="handleSave" :loading="saving">保存</el-button>
      </div>
    </div>

    <div class="ae-main">
      <div v-if="loading" class="ae-loading">加载中...</div>
      <template v-else>
        <section v-for="s in sections" :key="s.id" :id="s.id" class="ae-section">
          <h2 class="ae-section-title">{{ s.label }}</h2>

          <!-- ===== 基本资料 ===== -->
          <div v-if="s.id === 'basic'" class="ae-grid ae-grid-2">
            <div class="ae-field">
              <label class="ae-label">姓名 <span class="ae-required">*</span></label>
              <el-input v-model="form.name" placeholder="如：李鱓" />
              <div v-if="editing && form.name !== originalName" class="ae-hint ae-hint-warn">修改姓名将同步所有相关作品</div>
            </div>
            <div class="ae-field">
              <label class="ae-label">字号</label>
              <el-input v-model="form.alias" placeholder="字复堂，号懊道人" />
            </div>
            <div class="ae-field">
              <label class="ae-label">朝代</label>
              <el-select v-model="form.dynasty" filterable allow-create clearable placeholder="选择或输入朝代" style="width:100%">
                <el-option v-for="p in periods" :key="p" :label="p" :value="p" />
              </el-select>
            </div>
            <div class="ae-field">
              <label class="ae-label">籍贯</label>
              <el-input v-model="form.hometown" placeholder="如：江苏兴化" />
            </div>
            <div class="ae-field">
              <label class="ae-label">出生年份</label>
              <el-input v-model.number="form.birth_year" placeholder="如：1686" type="number" />
            </div>
            <div class="ae-field">
              <label class="ae-label">卒年</label>
              <el-input v-model.number="form.death_year" placeholder="如：1762" type="number" />
            </div>
            <div class="ae-field">
              <label class="ae-label">国籍</label>
              <el-input v-model="form.nationality" placeholder="如：中国" />
            </div>
            <div class="ae-field">
              <label class="ae-label">职业</label>
              <el-input v-model="form.occupation" placeholder="如：画家、书法家" />
            </div>
            <div class="ae-field">
              <label class="ae-label">画派</label>
              <el-input v-model="form.art_school" placeholder="如：扬州八怪" />
            </div>
            <div class="ae-field">
              <label class="ae-label">专长</label>
              <el-input v-model="form.specialties" placeholder="如：写意花鸟、泼墨" />
            </div>
            <div class="ae-field">
              <label class="ae-label">推荐展示</label>
              <div class="ae-switch-wrap">
                <el-switch v-model="form.featured" :active-value="1" :inactive-value="0" />
                <span class="ae-switch-label">{{ form.featured ? '已推荐' : '未推荐' }}</span>
              </div>
            </div>
            <div class="ae-field">
              <label class="ae-label">启用状态</label>
              <div class="ae-switch-wrap">
                <el-switch v-model="form.enabled" :active-value="1" :inactive-value="0" />
                <span class="ae-switch-label">{{ form.enabled ? '已启用' : '已禁用' }}</span>
              </div>
            </div>
            <div class="ae-field">
              <label class="ae-label">认证画家</label>
              <div class="ae-switch-wrap">
                <el-switch v-model="form.verified" :active-value="1" :inactive-value="0" />
                <span class="ae-switch-label">{{ form.verified ? '已认证（公开可见）' : '未认证（仅后台可见）' }}</span>
              </div>
            </div>
          </div>

          <!-- ===== 概述与图像 ===== -->
          <div v-if="s.id === 'overview'">
            <div class="ae-field">
              <label class="ae-label">概述（百科摘要）</label>
              <el-input v-model="form.summary" type="textarea" :rows="4" placeholder="画家的百科概述，一段话概括其生平与艺术地位" />
            </div>
            <div class="ae-field">
              <label class="ae-label">背景简介</label>
              <el-input v-model="form.background" type="textarea" :rows="6" placeholder="画家背景简介，支持Markdown格式" />
            </div>
            <div class="ae-grid ae-grid-2">
              <div class="ae-field">
                <label class="ae-label">头像 <span class="ae-hint-dim">(建议 300×300px)</span></label>
                <div class="ae-upload-row">
                  <el-input v-model="form.avatar_url" placeholder="https://..." />
                  <el-upload :show-file-list="false" :before-upload="(f) => uploadFile(f)" accept="image/*" style="flex-shrink:0">
                    <el-button size="small">上传</el-button>
                  </el-upload>
                </div>
                <div style="margin-top:8px">
                  <img v-if="form.avatar_url" :src="form.avatar_url" style="width:80px;height:80px;border-radius:8px;object-fit:cover;display:block" />
                  <el-avatar v-else :size="80" shape="square" style="background:#c45a3c;font-size:32px;border-radius:8px">{{ form.name?.charAt(0) || '?' }}</el-avatar>
                </div>
              </div>
              <div class="ae-field">
                <label class="ae-label">本人照片</label>
                <div class="ae-upload-row">
                  <el-upload :show-file-list="false" :before-upload="(f) => uploadPhoto(f)" accept="image/*" style="flex-shrink:0" :disabled="uploadingPhoto">
                    <el-button size="small" :loading="uploadingPhoto">上传照片</el-button>
                  </el-upload>
                </div>
                <div v-if="form.photos.length > 0" class="ae-photo-grid">
                  <div v-for="(p, i) in form.photos" :key="i" class="ae-photo-item">
                    <img :src="photoThumb(p)" class="ae-photo-img" />
                    <el-button size="small" type="danger" circle :icon="Delete" @click="removePhoto(i)" class="ae-photo-del" />
                  </div>
                </div>
                <p v-else class="ae-hint-dim" style="margin-top:4px">暂未上传本人照片，将在前端概览页头像下方显示</p>
              </div>
            </div>
          </div>

          <!-- ===== 生平 ===== -->
          <div v-if="s.id === 'biography'">
            <div class="ae-field">
              <label class="ae-label">生平简介</label>
              <el-input v-model="form.biography" type="textarea" :rows="8" placeholder="详细生平介绍文本，支持长文" />
            </div>
          </div>

          <!-- ===== 艺术年谱 ===== -->
          <div v-if="s.id === 'chronology'">
            <div class="ae-field">
              <label class="ae-label">艺术年谱</label>
              <div class="ae-array">
                <p class="ae-array-hint">按年份整理画家的艺术创作历程（年份+事件+描述，用于翰墨行旅等模块）</p>
                <div v-for="(item, idx) in form.art_chronology" :key="idx" class="ae-array-card">
                  <div class="ae-array-card-header">
                    <span>#{{ idx + 1 }}</span>
                    <el-button type="danger" size="small" text @click="removeItem('art_chronology', idx)">删除</el-button>
                  </div>
                  <div class="ae-array-card-body">
                    <div class="ae-grid ae-grid-3">
                      <el-input v-model="item.year" placeholder="年份" size="small" />
                      <el-input v-model="item.event" placeholder="事件标题" size="small" />
                      <el-input v-model="item.location" placeholder="地点（可选）" size="small" />
                    </div>
                    <el-input v-model="item.description" placeholder="详细描述" size="small" type="textarea" :rows="2" style="margin-top:6px" />
                  </div>
                </div>
                <el-button size="small" @click="addItem('art_chronology', {year: '', event: '', location: '', description: ''})">
                  <el-icon><Plus /></el-icon>添加年谱条目
                </el-button>
                <p v-if="form.art_chronology.length === 0" class="ae-array-empty">暂未添加艺术年谱</p>
              </div>
            </div>
          </div>

          <!-- ===== 艺术研究 ===== -->
          <div v-if="s.id === 'research'">
            <div class="ae-field">
              <label class="ae-label">艺术特色</label>
              <el-input v-model="form.art_style" type="textarea" :rows="8" placeholder="画家的艺术风格、技法特点、用笔用墨特色等" />
            </div>
            <div class="ae-grid ae-grid-2">
              <div class="ae-field">
                <label class="ae-label">主要成就</label>
                <el-input v-model="form.main_achievements" type="textarea" :rows="4" placeholder="画家的主要艺术成就" />
              </div>
              <div class="ae-field">
                <label class="ae-label">后世影响</label>
                <el-input v-model="form.influence" type="textarea" :rows="4" placeholder="画家对后世的影响与贡献" />
              </div>
            </div>
            <div class="ae-field">
              <label class="ae-label">历史评价</label>
              <el-input v-model="form.historical_evaluation" type="textarea" :rows="4" placeholder="后人对画家的历史评价" />
            </div>
          </div>

          <!-- ===== 人物关系 ===== -->
          <div v-if="s.id === 'relations'">
            <div class="ae-field">
              <label class="ae-label">人物关系</label>
              <div class="ae-array">
                <p class="ae-array-hint">添加与画家相关的人物（可关联已有画家实现双链）</p>
                <div v-for="(rel, idx) in form.character_relations" :key="idx" class="ae-array-card">
                  <div class="ae-array-card-header">
                    <span>#{{ idx + 1 }}</span>
                    <el-button type="danger" size="small" text @click="removeItem('character_relations', idx)">删除</el-button>
                  </div>
                  <div class="ae-array-card-body">
                    <div class="ae-grid ae-grid-3">
                      <el-select v-model="rel.name" filterable allow-create clearable placeholder="选择或输入姓名" size="small" style="width:100%">
                        <el-option v-for="a in artistOptions" :key="a" :label="a" :value="a" />
                      </el-select>
                      <el-select v-model="rel.relationship" filterable allow-create clearable placeholder="关系" size="small">
                        <el-option label="好友" value="好友" />
                        <el-option label="老师" value="老师" />
                        <el-option label="学生" value="学生" />
                        <el-option label="同门" value="同门" />
                        <el-option label="父子" value="父子" />
                        <el-option label="合作" value="合作" />
                        <el-option label="仰慕" value="仰慕" />
                        <el-option label="受其影响" value="受其影响" />
                      </el-select>
                      <el-input v-model="rel.image_url" placeholder="头像URL（可选）" size="small" />
                    </div>
                    <el-input v-model="rel.description" placeholder="关系描述" size="small" type="textarea" :rows="2" style="margin-top:6px" />
                  </div>
                </div>
                <el-button size="small" @click="addItem('character_relations', {name: '', relationship: '', description: '', image_url: ''})">
                  <el-icon><Plus /></el-icon>添加关系
                </el-button>
                <p v-if="form.character_relations.length === 0" class="ae-array-empty">暂未添加人物关系</p>
              </div>
            </div>
            <div class="ae-field">
              <label class="ae-label">轶事典故</label>
              <div class="ae-array">
                <p class="ae-array-hint">添加与画家相关的轶事典故</p>
                <div v-for="(ane, idx) in form.anecdotes" :key="idx" class="ae-array-card">
                  <div class="ae-array-card-header">
                    <span>#{{ idx + 1 }}</span>
                    <el-button type="danger" size="small" text @click="removeItem('anecdotes', idx)">删除</el-button>
                  </div>
                  <div class="ae-array-card-body">
                    <el-input v-model="ane.title" placeholder="典故标题" size="small" style="margin-bottom:6px" />
                    <el-input v-model="ane.content" placeholder="典故内容" size="small" type="textarea" :rows="3" />
                  </div>
                </div>
                <el-button size="small" @click="addItem('anecdotes', {title: '', content: ''})">
                  <el-icon><Plus /></el-icon>添加典故
                </el-button>
                <p v-if="form.anecdotes.length === 0" class="ae-array-empty">暂未添加轶事典故</p>
              </div>
            </div>
          </div>

          <!-- ===== 文献与出版 ===== -->
          <div v-if="s.id === 'literature'">
            <div class="ae-field">
              <label class="ae-label">代表作品</label>
              <el-select v-model="form.masterpieces" multiple filterable allow-create default-first-option placeholder="输入作品名后回车添加" style="width:100%" />
            </div>
            <div class="ae-field">
              <label class="ae-label">代表作品文本</label>
              <el-input v-model="form.representative_works_text" placeholder="用于百科展示，如：《松藤图》《土墙蝶花图》" />
            </div>
            <div class="ae-field">
              <label class="ae-label">出版著作</label>
              <div class="ae-array">
                <p class="ae-array-hint">添加画家的出版著作（支持后续PDF/CAJ上传）</p>
                <div v-for="(pw, idx) in form.published_works" :key="idx" class="ae-array-card">
                  <div class="ae-array-card-header">
                    <span>#{{ idx + 1 }}</span>
                    <el-button type="danger" size="small" text @click="removeItem('published_works', idx)">删除</el-button>
                  </div>
                  <div class="ae-array-card-body">
                    <div class="ae-grid ae-grid-3">
                      <el-input v-model="pw.title" placeholder="书名" size="small" />
                      <el-input v-model="pw.publisher" placeholder="出版社" size="small" />
                      <el-input v-model="pw.year" placeholder="年份" size="small" />
                    </div>
                    <el-input v-model="pw.isbn" placeholder="ISBN/链接（可选）" size="small" style="margin-top:6px" />
                  </div>
                </div>
                <el-button size="small" @click="addItem('published_works', {title: '', publisher: '', year: '', isbn: ''})">
                  <el-icon><Plus /></el-icon>添加著作
                </el-button>
                <p v-if="form.published_works.length === 0" class="ae-array-empty">暂未添加出版著作</p>
              </div>
            </div>
            <div class="ae-field">
              <label class="ae-label">参考文献</label>
              <div class="ae-array">
                <div v-for="(ref, idx) in form.references" :key="idx" class="ae-array-card">
                  <div class="ae-array-card-header">
                    <span>#{{ idx + 1 }}</span>
                    <el-button type="danger" size="small" text @click="removeItem('references', idx)">删除</el-button>
                  </div>
                  <div class="ae-array-card-body">
                    <div class="ae-grid ae-grid-2">
                      <el-input v-model="ref.author" placeholder="作者" size="small" />
                      <el-input v-model="ref.title" placeholder="文献标题" size="small" />
                    </div>
                    <div class="ae-grid ae-grid-2" style="margin-top:6px">
                      <el-input v-model="ref.publisher" placeholder="出版社/期刊" size="small" />
                      <el-input v-model="ref.year" placeholder="年份" size="small" />
                    </div>
                  </div>
                </div>
                <el-button size="small" @click="addItem('references', {author: '', title: '', publisher: '', year: ''})">
                  <el-icon><Plus /></el-icon>添加文献
                </el-button>
                <p v-if="form.references.length === 0" class="ae-array-empty">暂未添加参考文献</p>
              </div>
            </div>
          </div>

          <!-- ===== 作品图集 ===== -->
          <div v-if="s.id === 'gallery'">
            <div class="ae-field">
              <label class="ae-label">作品图集</label>
              <div class="ae-array">
                <p class="ae-array-hint">从作品库精选代表作，在前端百科展示。可搜索现有作品并添加</p>
                <div class="ae-search-row" style="margin-bottom:12px">
                  <el-input v-model="gallerySearch" placeholder="搜索作品库标题..." size="small" style="flex:1" clearable @keyup.enter="searchArtworks" />
                  <el-button size="small" type="primary" @click="searchArtworks" :loading="searching">搜索</el-button>
                </div>
                <div v-if="searchResults.length > 0" class="ae-search-results">
                  <div v-for="aw in searchResults" :key="aw.id" class="ae-search-item" :class="{ added: isInGallery(aw.id) }" @click="toggleGallery(aw)">
                    <el-image v-if="aw.thumbnail_url" :src="aw.thumbnail_url" style="width:40px;height:40px;border-radius:4px;object-fit:cover;flex-shrink:0" />
                    <span style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:13px">{{ aw.title || '未命名' }}</span>
                    <span style="font-size:12px;color:#b0a890;flex-shrink:0">{{ aw.year || '' }}</span>
                    <el-tag v-if="isInGallery(aw.id)" size="small" type="success">已选</el-tag>
                  </div>
                </div>
                <p v-if="searchResults.length === 0 && gallerySearch" class="ae-array-empty">未找到匹配作品</p>
                <div v-if="form.gallery_images.length > 0" style="margin-top:12px">
                  <p style="font-size:12px;color:#8a8578;margin:0 0 8px">已选 {{ form.gallery_images.length }} 幅作品图集：</p>
                  <div class="ae-gallery-grid">
                    <div v-for="(gi, idx) in form.gallery_images" :key="idx" class="ae-gallery-item">
                      <el-image v-if="gi.url" :src="gi.url" style="width:100%;aspect-ratio:3/4;object-fit:cover;border-radius:6px" />
                      <div class="ae-gallery-item-info">
                        <span class="ae-gallery-item-title">{{ gi.title || gi.artwork_name || '未命名' }}</span>
                        <el-button type="danger" size="small" text @click="removeItem('gallery_images', idx)" style="margin-top:4px">移除</el-button>
                      </div>
                    </div>
                  </div>
                </div>
                <p v-if="form.gallery_images.length === 0 && !gallerySearch" class="ae-array-empty">暂未添加作品图集，请搜索并添加</p>
              </div>
            </div>
            <div class="ae-field">
              <label class="ae-label">标签</label>
              <el-select v-model="form.tags" multiple filterable allow-create default-first-option placeholder="输入后回车添加" style="width:100%" />
            </div>
          </div>
        </section>

        <div class="ae-bottom-bar">
          <el-button @click="goBack" size="default">取消</el-button>
        </div>
      </template>
    </div>
  </div>
  <AvatarCropper ref="cropperRef" @cropped="onAvatarCropped" />
</template>

<script setup>
import { ref, reactive, onMounted, nextTick, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ArrowLeft, Plus, MagicStick, Delete } from '@element-plus/icons-vue'
import api from '@/api'
import AvatarCropper from '@/components/AvatarCropper.vue'

const route = useRoute()
const router = useRouter()

const artistName = computed(() => route.params.name)
const editing = ref(false)
const artistId = ref(null)
const originalName = ref('')
const loading = ref(true)
const saving = ref(false)
const aiLoading = ref(false)
const activeSection = ref('basic')
const periods = ref([])
const artistOptions = ref([])
const gallerySearch = ref('')
const searching = ref(false)
const searchResults = ref([])

const form = reactive({
  name: '', alias: '', dynasty: '', hometown: '', birth_year: null, death_year: null,
  nationality: '', occupation: '', art_school: '', specialties: '',
  summary: '', background: '', avatar_url: '',
  biography: '', art_chronology: [],
  art_style: '', main_achievements: '', influence: '', historical_evaluation: '',
  character_relations: [], anecdotes: [],
  masterpieces: [], representative_works_text: '', tags: [],
  published_works: [], references: [], gallery_images: [], photos: [],
  featured: 0, enabled: 1, verified: 0,
})

const JSON_ARRAYS = ['art_chronology', 'character_relations', 'anecdotes', 'masterpieces', 'tags', 'published_works', 'references', 'gallery_images', 'photos']

const sections = [
  { id: 'basic', label: '基本' },
  { id: 'overview', label: '概述' },
  { id: 'biography', label: '生平' },
  { id: 'chronology', label: '年谱' },
  { id: 'research', label: '研究' },
  { id: 'relations', label: '关系' },
  { id: 'literature', label: '文献' },
  { id: 'gallery', label: '图集' },
]

function addItem(field, defaults) { form[field].push({...defaults}) }
function removeItem(field, idx) { form[field].splice(idx, 1) }
function isInGallery(id) { return form.gallery_images.some(gi => gi.artwork_id === id) }

function toggleGallery(aw) {
  const idx = form.gallery_images.findIndex(gi => gi.artwork_id === aw.id)
  if (idx >= 0) { form.gallery_images.splice(idx, 1) }
  else { form.gallery_images.push({ url: aw.thumbnail_url || aw.url || '', title: aw.title || '', artwork_id: aw.id, artwork_name: aw.title || '' }) }
}

function scrollTo(id) {
  activeSection.value = id
  const el = document.getElementById(id)
  if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

function goBack() { router.push('/admin?tab=artist-info') }

const cropperRef = ref(null)
const uploadingPhoto = ref(false)

async function uploadFile(file) {
  await nextTick()
  cropperRef.value?.open(file)
  return false
}

async function onAvatarCropped(blob) {
  const fd = new FormData()
  fd.append('file', blob, 'avatar.jpg')
  try {
    const data = await api.post('/artists/upload-image', fd)
    if (data.success && data.url) {
      form.avatar_url = data.url
      ElMessage.success('上传成功')
    } else {
      ElMessage.error(data.detail || '上传失败')
    }
  } catch (e) { ElMessage.error(e.response?.data?.detail || '上传失败') }
}

async function uploadPhoto(file) {
  uploadingPhoto.value = true
  const fd = new FormData()
  fd.append('file', file)
  try {
    const data = await api.post('/artists/upload-photo', fd)
    if (data.success && data.url) {
      form.photos.push({ url: data.url, thumb_url: data.thumb_url || data.url })
      ElMessage.success('照片已上传')
    } else {
      ElMessage.error(data.detail || '上传失败')
    }
  } catch (e) { ElMessage.error(e.response?.data?.detail || '上传失败') }
  finally { uploadingPhoto.value = false }
  return false
}

function removePhoto(idx) {
  form.photos.splice(idx, 1)
}

function photoThumb(p) {
  if (typeof p === 'string') return p
  return p.thumb_url || p.url || ''
}

function normalizePhoto(p) {
  if (typeof p === 'string') return { url: p, thumb_url: p }
  return p
}

async function searchArtworks() {
  if (!gallerySearch.value || !artistName.value) return
  searching.value = true
  try {
    const params = { keyword: gallerySearch.value, limit: 20 }
    const data = await api.get('/tiba/search', { params })
    searchResults.value = (data.data || []).map(w => ({
      id: w.id || w.db_id,
      title: w.title || w.work_name || '未命名',
      year: w.year || '',
      thumbnail_url: w.thumbnail_url || w.url || '',
      url: w.url || ''
    }))
  } catch (e) { }
  finally { searching.value = false }
}

async function fetchPeriods() {
  try { const d = await api.get('/artists/periods'); periods.value = d.periods || [] } catch (e) { }
}

async function fetchArtistOptions() {
  try { const d = await api.get('/content-analysis/artists'); artistOptions.value = d.artists || [] } catch (e) { }
}

async function loadArtist() {
  if (artistName.value && artistName.value !== 'new') {
    await fetchArtist()
  } else {
    editing.value = false
    loading.value = false
  }
}

// 侧边栏切换艺术家时自动重新加载
watch(artistName, () => {
  if (artistName.value && artistName.value !== 'new') {
    fetchArtist()
  }
})

async function fetchArtist() {
  loading.value = true
  try {
    const data = await api.get(`/artists/by-name/${encodeURIComponent(artistName.value)}`)
    if (data.success && data.artist) {
      const a = data.artist
      artistId.value = a.id
      originalName.value = a.name
      editing.value = true
      for (const key of Object.keys(form)) {
        if (JSON_ARRAYS.includes(key)) {
          try { form[key] = typeof a[key] === 'string' ? JSON.parse(a[key] || '[]') : (Array.isArray(a[key]) ? a[key] : []) } catch { form[key] = [] }
          if (key === 'photos') form[key] = form[key].map(normalizePhoto)
        } else if (key === 'birth_year' || key === 'death_year') {
          form[key] = a[key] || null
        } else if (key === 'featured' || key === 'enabled') {
          form[key] = a[key] || 0
        } else {
          form[key] = a[key] || ''
        }
      }
    }
  } catch (e) { ElMessage.error('加载画家数据失败') }
  finally { loading.value = false }
}

async function handleSave() {
  if (!form.name) { ElMessage.warning('请输入画家姓名'); return }
  saving.value = true
  try {
    const payload = {}
    for (const key of Object.keys(form)) {
      if (JSON_ARRAYS.includes(key)) { payload[key] = JSON.stringify(form[key]) }
      else { payload[key] = form[key] }
    }
    if (editing.value && artistId.value) {
      await api.put(`/artists/${artistId.value}`, payload)
      if (form.name !== originalName.value) {
        await api.post(`/artists/${artistId.value}/sync-name`, { old_name: originalName.value, new_name: form.name })
      }
      ElMessage.success('画家信息已更新')
    } else {
      const res = await api.post('/artists', payload)
      if (res.success) {
        ElMessage.success('画家已创建')
        router.push(`/admin/artist/${encodeURIComponent(form.name)}/edit`)
      }
    }
  } catch (e) { ElMessage.error(e?.response?.data?.detail || '保存失败') }
  finally { saving.value = false }
}

async function handleAiFill() {
  if (!artistId.value) return
  aiLoading.value = true
  try {
    const res = await api.post(`/artists/${artistId.value}/ai-fill`)
    ElMessage.success(res.message || 'AI补充完成，正在刷新...')
    await fetchArtist()
  } catch (e) { ElMessage.error(e?.response?.data?.detail || 'AI补充失败') }
  finally { aiLoading.value = false }
}

const observer = ref(null)
onMounted(async () => {
  await Promise.all([fetchPeriods(), fetchArtistOptions()])
  await loadArtist()
  observer.value = new IntersectionObserver((entries) => {
    for (const entry of entries) {
      if (entry.isIntersecting) { activeSection.value = entry.target.id }
    }
  }, { rootMargin: '-20% 0px -70% 0px' })
  document.querySelectorAll('.ae-section').forEach(el => observer.value?.observe(el))
})
</script>

<style scoped>
.ae-root { display: block; min-height: 100vh; background: #fafaf8; padding-left: 130px; }

.ae-sidebar { width: 130px; background: #fff; border-right: 1px solid #edeae1; padding: 12px 8px; position: fixed; left: 120px; top: 64px; bottom: 0; display: flex; flex-direction: column; z-index: 5; }
.ae-sidebar-top { display: flex; align-items: center; gap: 4px; margin-bottom: 8px; padding-bottom: 8px; border-bottom: 1px solid #edeae1; }
.ae-back-btn { padding: 2px; min-height: auto; }
.ae-artist-name { font-size: 12px; color: #3a3222; font-weight: 600; font-family: 'Noto Serif SC', serif; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: 1; min-width: 0; }
.ae-nav { display: flex; flex-direction: column; gap: 1px; }
.ae-nav-item { padding: 6px 8px; font-size: 12px; color: #8c7a5c; text-decoration: none; border-radius: 6px; cursor: pointer; transition: all 0.15s; text-align: center; }
.ae-nav-item:hover { background: #f5f3ed; color: #3a3222; }
.ae-nav-item.active { background: #fdf6f0; color: #c45a3c; font-weight: 500; }
.ae-sidebar-actions { margin-top: auto; padding-top: 10px; border-top: 1px solid #edeae1; display: flex; flex-direction: column; gap: 6px; }
.ae-sidebar-actions .el-button { display: inline-flex; align-items: center; justify-content: center; padding-left: 0; padding-right: 0; box-sizing: border-box; overflow: hidden; }

.ae-main { flex: 1; padding: 32px 40px 120px; max-width: 960px; margin-left: 0; }
.ae-loading { text-align: center; padding: 100px 0; color: #b0a890; }
.ae-section { margin-bottom: 52px; scroll-margin-top: 20px; }
.ae-section-title { font-family: 'Noto Serif SC', serif; font-size: 19px; color: #3a3222; margin: 0 0 22px; padding-left: 12px; border-left: 3px solid #c45a3c; }

.ae-grid { display: grid; gap: 16px; }
.ae-grid-2 { grid-template-columns: repeat(2, 1fr); }
.ae-grid-3 { grid-template-columns: repeat(3, 1fr); }
@media (max-width: 768px) { .ae-grid-2, .ae-grid-3 { grid-template-columns: 1fr; } .ae-sidebar { display: none; } .ae-root { padding-left: 0; } .ae-main { padding: 20px 16px 120px; } }

.ae-field { margin-bottom: 18px; }
.ae-label { display: block; font-size: 13px; color: #5c5346; font-weight: 500; margin-bottom: 6px; }
.ae-required { color: #c45a3c; }
.ae-hint { font-size: 12px; margin-top: 4px; color: #b0a890; }
.ae-hint-warn { color: #c45a3c; }
.ae-hint-dim { font-size: 11px; color: #b0a890; font-weight: 400; }

.ae-upload-row { display: flex; gap: 8px; align-items: center; }

.ae-switch-wrap { display: flex; align-items: center; gap: 10px; padding: 6px 0; }
.ae-switch-label { font-size: 13px; color: #5c5346; }

.ae-array { background: #fafaf8; border: 1px solid #edeae1; border-radius: 10px; padding: 16px; }
.ae-array-hint { font-size: 12px; color: #8a8578; margin: 0 0 12px; }
.ae-array-empty { font-size: 13px; color: #b0a890; padding: 12px 0; text-align: center; }
.ae-array-card { background: #fff; border: 1px solid #edeae1; border-radius: 8px; padding: 14px; margin-bottom: 10px; }
.ae-array-card-header { display: flex; justify-content: space-between; align-items: center; font-size: 12px; color: #8a8578; margin-bottom: 10px; }

.ae-search-row { display: flex; gap: 8px; }
.ae-search-results { margin-bottom: 12px; max-height: 240px; overflow-y: auto; }
.ae-search-item { display: flex; align-items: center; gap: 8px; padding: 8px; border: 1px solid #edeae1; border-radius: 6px; margin-bottom: 6px; cursor: pointer; transition: all 0.15s; }
.ae-search-item:hover { background: #fdf6f0; }
.ae-search-item.added { background: #f6f9f6; border-color: #a3c4a3; }

.ae-gallery-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(120px, 1fr)); gap: 10px; }
.ae-gallery-item { text-align: center; }
.ae-gallery-item-info { padding: 4px 0; }
.ae-gallery-item-title { font-size: 11px; color: #5c5346; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; display: block; max-width: 120px; }

.ae-photo-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(80px, 1fr)); gap: 8px; margin-top: 8px; }
.ae-photo-item { position: relative; border-radius: 6px; overflow: hidden; aspect-ratio: 1; }
.ae-photo-img { width: 100%; height: 100%; object-fit: cover; display: block; }
.ae-photo-del { position: absolute; top: 2px; right: 2px; width: 22px; height: 22px; }

.ae-bottom-bar { display: flex; justify-content: center; padding: 24px 0; border-top: 1px solid #edeae1; margin-top: 32px; }

:deep(.el-input__wrapper) { display: flex; align-items: center; }
.ae-field :deep(.el-input__inner) { line-height: normal; }
:deep(.el-button) { display: inline-flex; align-items: center; justify-content: center; line-height: 1; }
</style>
