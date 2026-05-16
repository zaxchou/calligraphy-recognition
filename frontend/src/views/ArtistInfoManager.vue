<template>
  <div class="artist-info-manager">
    <div class="toolbar">
      <div class="toolbar-left">
        <el-input v-model="searchQuery" placeholder="搜索画家姓名..." clearable size="small" style="width:200px" />
        <el-select v-model="dynastyFilter" placeholder="筛选朝代" clearable size="small" style="width:130px">
          <el-option v-for="p in periods" :key="p" :label="p" :value="p" />
        </el-select>
      </div>
      <el-button type="primary" plain size="small" @click="openCreate"><el-icon><Plus /></el-icon>新增画家</el-button>
    </div>

    <div v-loading="loading" class="artist-list">
      <div v-for="artist in filteredArtists" :key="artist.id" class="artist-card">
        <div class="artist-row">
          <div class="artist-main">
            <el-avatar v-if="artist.avatar_url" :src="artist.avatar_url" :size="36" shape="square" />
            <el-avatar v-else :size="36" shape="square" style="background:#c45a3c">{{ artist.name?.charAt(0) || '?' }}</el-avatar>
            <span class="artist-name">{{ artist.name }}</span>
            <el-tag v-if="artist.dynasty" size="small">{{ artist.dynasty }}</el-tag>
            <el-tag v-if="artist.alias" size="small" type="info">{{ artist.alias }}</el-tag>
            <template v-if="artist.birth_year || artist.death_year">
              <el-tag size="small" type="info">{{ artist.birth_year || '?' }}-{{ artist.death_year || '?' }}</el-tag>
            </template>
            <el-tag v-if="!artist.enabled" size="small" type="danger">已禁用</el-tag>
            <el-tag v-if="artist.featured" size="small" type="warning">推荐</el-tag>
          </div>
          <div class="artist-actions">
            <el-button size="small" @click="openEdit(artist)">编辑</el-button>
            <el-button size="small" type="primary" plain @click="handleAiFill(artist)" :loading="aiFillLoading[artist.id]">
              <el-icon><MagicStick /></el-icon>AI查询
            </el-button>
            <el-button size="small" :type="artist.enabled ? 'warning' : 'success'" plain @click="toggleEnabled(artist)">
              {{ artist.enabled ? '禁用' : '启用' }}
            </el-button>
            <el-button size="small" type="danger" plain @click="handleDelete(artist)">删除</el-button>
          </div>
        </div>
      </div>
      <div v-if="!loading && artists.length === 0" class="empty-state"><el-empty description="暂无画家数据" /></div>
    </div>

    <el-dialog v-model="showEditDialog" :title="editingArtist ? '编辑画家：' + editingArtist.name : '新增画家'" width="800px" class="claude-dialog" destroy-on-close top="3vh">
      <el-tabs v-model="activeTab" type="border-card">
        <el-tab-pane label="基本信息" name="basic">
          <el-form :model="editForm" label-position="top" class="modern-form artist-edit-form">
            <div class="form-row">
              <el-form-item label="姓名" required class="form-item-half">
                <el-input v-model="editForm.name" placeholder="如：李鱓" />
                <div v-if="editingArtist && editForm.name !== editingArtist.name" class="rename-warning">修改姓名将同步更新所有相关画作的作者信息</div>
              </el-form-item>
              <el-form-item label="字号" class="form-item-half">
                <el-input v-model="editForm.alias" placeholder="字复堂，号懊道人" />
              </el-form-item>
            </div>
            <div class="form-row">
              <el-form-item label="朝代" class="form-item-half">
                <el-select v-model="editForm.dynasty" filterable allow-create clearable placeholder="选择或输入朝代" style="width:100%">
                  <el-option v-for="p in periods" :key="p" :label="p" :value="p" />
                </el-select>
              </el-form-item>
              <el-form-item label="籍贯" class="form-item-half">
                <el-input v-model="editForm.hometown" placeholder="如：江苏兴化" />
              </el-form-item>
            </div>
            <div class="form-row">
              <el-form-item label="出生年份" class="form-item-half">
                <el-input v-model.number="editForm.birth_year" placeholder="如：1686" type="number" />
              </el-form-item>
              <el-form-item label="卒年" class="form-item-half">
                <el-input v-model.number="editForm.death_year" placeholder="如：1762" type="number" />
              </el-form-item>
            </div>
            <div class="form-row">
              <el-form-item label="画派" class="form-item-half">
                <el-input v-model="editForm.art_school" placeholder="如：扬州八怪" />
              </el-form-item>
              <el-form-item label="专长" class="form-item-half">
                <el-input v-model="editForm.specialties" placeholder="如：写意花鸟" />
              </el-form-item>
            </div>
            <el-form-item label="背景简介">
              <el-input v-model="editForm.background" type="textarea" :rows="2" placeholder="画家背景简介，支持Markdown格式" />
            </el-form-item>
            <el-form-item label="概述">
              <el-input v-model="editForm.summary" type="textarea" :rows="3" placeholder="画家概述（用于百科展示）" />
            </el-form-item>
          </el-form>
        </el-tab-pane>

        <el-tab-pane label="生平与年谱" name="bio">
          <el-form :model="editForm" label-position="top" class="modern-form artist-edit-form">
            <el-form-item label="生平简介">
              <el-input v-model="editForm.biography" type="textarea" :rows="6" placeholder="详细生平介绍文本" />
            </el-form-item>
            <el-form-item label="头像">
              <div class="avatar-url-row">
                <el-input v-model="editForm.avatar_url" placeholder="https://..." style="flex:1" />
                <el-avatar v-if="editForm.avatar_url" :src="editForm.avatar_url" :size="48" shape="square" />
                <el-avatar v-else :size="48" shape="square" style="background:#c45a3c">{{ editForm.name?.charAt(0) || '?' }}</el-avatar>
              </div>
            </el-form-item>
            <el-form-item label="生平时间线">
              <div class="array-editor">
                <p class="array-editor-hint">按时间顺序添加重要生平事件</p>
                <div v-for="(evt, idx) in editForm.bio_events" :key="idx" class="array-item">
                  <div class="array-item-header">
                    <span class="array-item-index">#{{ idx + 1 }}</span>
                    <el-button type="danger" size="small" text @click="removeBioEvent(idx)">删除</el-button>
                  </div>
                  <div class="array-item-fields">
                    <el-input v-model="evt.year" placeholder="年份" size="small" style="width:100px" type="number" />
                    <el-input v-model="evt.type" placeholder="类型(如：入仕)" size="small" style="width:120px" />
                    <el-input v-model="evt.title" placeholder="标题" size="small" style="flex:1" />
                  </div>
                  <el-input v-model="evt.description" placeholder="详细描述" size="small" style="margin-top:6px" />
                </div>
                <el-button type="primary" size="small" plain @click="addBioEvent" style="margin-top:8px">
                  <el-icon><Plus /></el-icon>添加事件
                </el-button>
                <p v-if="editForm.bio_events.length === 0" class="array-editor-empty">暂未添加时间线事件</p>
              </div>
            </el-form-item>
            <el-form-item label="艺术年谱">
              <div class="array-editor">
                <p class="array-editor-hint">按时间顺序添加艺术创作年谱</p>
                <div v-for="(item, idx) in editForm.art_chronology" :key="idx" class="array-item">
                  <div class="array-item-header">
                    <span class="array-item-index">#{{ idx + 1 }}</span>
                    <el-button type="danger" size="small" text @click="removeChronologyEvent(idx)">删除</el-button>
                  </div>
                  <div class="array-item-fields">
                    <el-input v-model="item.year" placeholder="年份" size="small" style="width:100px" />
                    <el-input v-model="item.event" placeholder="事件标题" size="small" style="flex:1" />
                  </div>
                  <el-input v-model="item.description" placeholder="详细描述" size="small" style="margin-top:6px" />
                </div>
                <el-button type="primary" size="small" plain @click="addChronologyEvent" style="margin-top:8px">
                  <el-icon><Plus /></el-icon>添加年谱条目
                </el-button>
                <p v-if="editForm.art_chronology.length === 0" class="array-editor-empty">暂未添加艺术年谱</p>
              </div>
            </el-form-item>
          </el-form>
        </el-tab-pane>

        <el-tab-pane label="艺术研究" name="research">
          <el-form :model="editForm" label-position="top" class="modern-form artist-edit-form">
            <el-form-item label="艺术特色">
              <el-input v-model="editForm.art_style" type="textarea" :rows="6" placeholder="画家的艺术风格、技法特点等" />
            </el-form-item>
            <el-form-item label="主要成就">
              <el-input v-model="editForm.main_achievements" type="textarea" :rows="4" placeholder="画家的主要艺术成就" />
            </el-form-item>
            <el-form-item label="后世影响">
              <el-input v-model="editForm.influence" type="textarea" :rows="4" placeholder="画家对后世的影响与贡献" />
            </el-form-item>
            <el-form-item label="历史评价">
              <el-input v-model="editForm.historical_evaluation" type="textarea" :rows="4" placeholder="后人对画家的历史评价" />
            </el-form-item>
            <el-form-item label="百度百科链接">
              <el-input v-model="editForm.baidu_url" placeholder="https://baike.baidu.com/..." />
            </el-form-item>
          </el-form>
        </el-tab-pane>

        <el-tab-pane label="人物关系" name="relations">
          <el-form :model="editForm" label-position="top" class="modern-form artist-edit-form">
            <el-form-item label="人物关系">
              <div class="array-editor">
                <p class="array-editor-hint">添加与画家相关的人物关系</p>
                <div v-for="(rel, idx) in editForm.character_relations" :key="idx" class="array-item">
                  <div class="array-item-header">
                    <span class="array-item-index">#{{ idx + 1 }}</span>
                    <el-button type="danger" size="small" text @click="removeRelation(idx)">删除</el-button>
                  </div>
                  <div class="array-item-fields">
                    <el-input v-model="rel.name" placeholder="姓名" size="small" style="flex:1" />
                    <el-input v-model="rel.relationship" placeholder="关系(如：好友)" size="small" style="width:120px" />
                  </div>
                  <div style="display:flex;gap:6px;margin-top:6px">
                    <el-input v-model="rel.description" placeholder="关系描述" size="small" style="flex:1" />
                    <el-input v-model="rel.image_url" placeholder="人物头像URL" size="small" style="flex:1" />
                  </div>
                </div>
                <el-button type="primary" size="small" plain @click="addRelation" style="margin-top:8px">
                  <el-icon><Plus /></el-icon>添加关系
                </el-button>
                <p v-if="editForm.character_relations.length === 0" class="array-editor-empty">暂未添加人物关系</p>
              </div>
            </el-form-item>
            <el-form-item label="轶事典故">
              <div class="array-editor">
                <p class="array-editor-hint">添加与画家相关的轶事典故</p>
                <div v-for="(ane, idx) in editForm.anecdotes" :key="idx" class="array-item">
                  <div class="array-item-header">
                    <span class="array-item-index">#{{ idx + 1 }}</span>
                    <el-button type="danger" size="small" text @click="removeAnecdote(idx)">删除</el-button>
                  </div>
                  <el-input v-model="ane.title" placeholder="典故标题" size="small" style="margin-bottom:6px" />
                  <el-input v-model="ane.content" placeholder="典故内容" size="small" type="textarea" :rows="2" />
                </div>
                <el-button type="primary" size="small" plain @click="addAnecdote" style="margin-top:8px">
                  <el-icon><Plus /></el-icon>添加典故
                </el-button>
                <p v-if="editForm.anecdotes.length === 0" class="array-editor-empty">暂未添加轶事典故</p>
              </div>
            </el-form-item>
          </el-form>
        </el-tab-pane>

        <el-tab-pane label="高级信息" name="advanced">
          <el-form :model="editForm" label-position="top" class="modern-form artist-edit-form">
            <div class="form-row">
              <el-form-item label="代表作品" class="form-item-half">
                <el-select v-model="editForm.masterpieces" multiple filterable allow-create default-first-option placeholder="输入代表作名称后回车添加" style="width:100%" />
              </el-form-item>
              <el-form-item label="代表作品文本" class="form-item-half">
                <el-input v-model="editForm.representative_works_text" placeholder="用于百科展示的代表作品文本" />
              </el-form-item>
            </div>
            <el-form-item label="标签">
              <el-select v-model="editForm.tags" multiple filterable allow-create default-first-option placeholder="输入标签后回车添加" style="width:100%" />
            </el-form-item>
            <el-form-item label="出版著作">
              <div class="array-editor">
                <p class="array-editor-hint">添加画家的出版著作</p>
                <div v-for="(pw, idx) in editForm.published_works" :key="idx" class="array-item">
                  <div class="array-item-header">
                    <span class="array-item-index">#{{ idx + 1 }}</span>
                    <el-button type="danger" size="small" text @click="removePublishedWork(idx)">删除</el-button>
                  </div>
                  <div class="array-item-fields">
                    <el-input v-model="pw.title" placeholder="书名" size="small" style="flex:1" />
                    <el-input v-model="pw.publisher" placeholder="出版社" size="small" style="flex:1" />
                    <el-input v-model="pw.year" placeholder="年份" size="small" style="width:100px" />
                  </div>
                </div>
                <el-button type="primary" size="small" plain @click="addPublishedWork" style="margin-top:8px">
                  <el-icon><Plus /></el-icon>添加著作
                </el-button>
                <p v-if="editForm.published_works.length === 0" class="array-editor-empty">暂未添加出版著作</p>
              </div>
            </el-form-item>
            <el-form-item label="参考文献">
              <div class="array-editor">
                <p class="array-editor-hint">添加参考文献</p>
                <div v-for="(ref, idx) in editForm.references" :key="idx" class="array-item">
                  <div class="array-item-header">
                    <span class="array-item-index">#{{ idx + 1 }}</span>
                    <el-button type="danger" size="small" text @click="removeReference(idx)">删除</el-button>
                  </div>
                  <div class="array-item-fields">
                    <el-input v-model="ref.author" placeholder="作者" size="small" style="width:120px" />
                    <el-input v-model="ref.title" placeholder="文献标题" size="small" style="flex:1" />
                  </div>
                  <div class="array-item-fields" style="margin-top:6px">
                    <el-input v-model="ref.publisher" placeholder="出版社/期刊" size="small" style="flex:1" />
                    <el-input v-model="ref.year" placeholder="年份" size="small" style="width:100px" />
                  </div>
                </div>
                <el-button type="primary" size="small" plain @click="addReference" style="margin-top:8px">
                  <el-icon><Plus /></el-icon>添加文献
                </el-button>
                <p v-if="editForm.references.length === 0" class="array-editor-empty">暂未添加参考文献</p>
              </div>
            </el-form-item>
            <el-form-item label="作品图集">
              <div class="array-editor">
                <p class="array-editor-hint">添加作品展示图片</p>
                <div v-for="(img, idx) in editForm.gallery_images" :key="idx" class="array-item">
                  <div class="array-item-header">
                    <span class="array-item-index">#{{ idx + 1 }}</span>
                    <el-button type="danger" size="small" text @click="removeGalleryImage(idx)">删除</el-button>
                  </div>
                  <div class="array-item-fields">
                    <el-input v-model="img.url" placeholder="图片URL" size="small" style="flex:1" />
                    <el-input v-model="img.title" placeholder="图片标题" size="small" style="flex:1" />
                  </div>
                </div>
                <el-button type="primary" size="small" plain @click="addGalleryImage" style="margin-top:8px">
                  <el-icon><Plus /></el-icon>添加图片
                </el-button>
                <p v-if="editForm.gallery_images.length === 0" class="array-editor-empty">暂未添加作品图集</p>
              </div>
            </el-form-item>
            <div class="form-row">
              <el-form-item label="封面题图" class="form-item-half">
                <el-input v-model="editForm.banner_url" placeholder="封面题图URL" />
              </el-form-item>
              <el-form-item label="国籍" class="form-item-half">
                <el-input v-model="editForm.nationality" placeholder="如：中国" />
              </el-form-item>
            </div>
            <div class="form-row">
              <el-form-item label="职业" class="form-item-half">
                <el-input v-model="editForm.occupation" placeholder="如：画家、书法家" />
              </el-form-item>
              <el-form-item label="推荐展示" class="form-item-half">
                <el-switch v-model="editForm.featured" :active-value="1" :inactive-value="0" active-text="推荐首页展示" inactive-text="不推荐" />
              </el-form-item>
            </div>
            <el-form-item label="启用状态">
              <el-switch v-model="editForm.enabled" :active-value="1" :inactive-value="0" active-text="已启用" inactive-text="已禁用" />
            </el-form-item>
          </el-form>
        </el-tab-pane>
      </el-tabs>

      <template #footer>
        <el-button @click="showEditDialog = false">取消</el-button>
        <el-button type="primary" @click="handleSave" :loading="saving">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, MagicStick } from '@element-plus/icons-vue'
import api from '@/api'

const API_BASE = import.meta.env.VITE_API_BASE || '/api/v1'

const props = defineProps({
  artist: { type: Object, default: null },
  libraryId: { type: [Number, String], default: null }
})

const artists = ref([])
const loading = ref(false)
const searchQuery = ref('')
const dynastyFilter = ref('')
const periods = ref([])

const saving = ref(false)
const aiFillLoading = reactive({})
const showEditDialog = ref(false)
const editingArtist = ref(null)
const activeTab = ref('basic')

const defaultForm = {
  name: '', alias: '', dynasty: '', hometown: '', avatar_url: '',
  birth_year: null, death_year: null, biography: '', background: '',
  specialties: '', bio_events: [], art_school: '', masterpieces: [],
  tags: [], baidu_url: '', featured: 0, enabled: 1,
  summary: '', nationality: '', occupation: '',
  main_achievements: '', representative_works_text: '',
  art_style: '', influence: '', historical_evaluation: '',
  character_relations: [], anecdotes: [], art_chronology: [],
  published_works: [], gallery_images: [], references: [],
  banner_url: ''
}

const editForm = ref({ ...defaultForm })

const filteredArtists = computed(() => {
  let list = artists.value.slice()
  const q = searchQuery.value.trim().toLowerCase()
  if (q) list = list.filter(a => a.name.toLowerCase().includes(q))
  if (dynastyFilter.value) list = list.filter(a => a.dynasty === dynastyFilter.value)
  list.sort((a, b) => {
    if (a.enabled && !b.enabled) return -1
    if (!a.enabled && b.enabled) return 1
    return a.id - b.id
  })
  return list
})

function parseJsonArray(val) {
  if (!val) return []
  if (Array.isArray(val)) return val
  try { const p = JSON.parse(val); return Array.isArray(p) ? p : [] }
  catch { return [] }
}

async function loadArtists() {
  loading.value = true
  try {
    const data = await api.get('/artists', { params: { page_size: 200 } })
    const raw = data.artists || data || []
    artists.value = raw.map(a => ({
      ...a,
      bio_events: parseJsonArray(a.bio_events),
      masterpieces: parseJsonArray(a.masterpieces),
      tags: parseJsonArray(a.tags),
      art_chronology: parseJsonArray(a.art_chronology),
      character_relations: parseJsonArray(a.character_relations),
      anecdotes: parseJsonArray(a.anecdotes),
      published_works: parseJsonArray(a.published_works),
      references: parseJsonArray(a.references),
      gallery_images: parseJsonArray(a.gallery_images)
    }))
  } catch (e) {
    ElMessage.error('加载画家列表失败: ' + e.message)
  } finally { loading.value = false }
}

async function loadPeriods() {
  try {
    const res = await fetch(`${API_BASE}/artists/periods`)
    const data = await res.json()
    periods.value = data.periods || data || []
  } catch (e) { console.warn('加载朝代列表失败', e) }
}

function resetForm() {
  editForm.value = {
    name: '', alias: '', dynasty: '', hometown: '', avatar_url: '',
    birth_year: null, death_year: null, biography: '', background: '',
    specialties: '', bio_events: [], art_school: '', masterpieces: [],
    tags: [], baidu_url: '', featured: 0, enabled: 1,
    summary: '', nationality: '', occupation: '',
    main_achievements: '', representative_works_text: '',
    art_style: '', influence: '', historical_evaluation: '',
    character_relations: [], anecdotes: [], art_chronology: [],
    published_works: [], gallery_images: [], references: [],
    banner_url: ''
  }
}

function openCreate() {
  editingArtist.value = null
  activeTab.value = 'basic'
  resetForm()
  showEditDialog.value = true
}

function openEdit(artist) {
  editingArtist.value = artist
  activeTab.value = 'basic'
  editForm.value = {
    name: artist.name || '',
    alias: artist.alias || '',
    dynasty: artist.dynasty || '',
    hometown: artist.hometown || '',
    avatar_url: artist.avatar_url || '',
    birth_year: artist.birth_year ?? null,
    death_year: artist.death_year ?? null,
    biography: artist.biography || '',
    background: artist.background || '',
    specialties: artist.specialties || '',
    bio_events: Array.isArray(artist.bio_events) ? artist.bio_events.map(e => ({ ...e })) : [],
    art_school: artist.art_school || '',
    masterpieces: Array.isArray(artist.masterpieces) ? [...artist.masterpieces] : [],
    tags: Array.isArray(artist.tags) ? [...artist.tags] : [],
    baidu_url: artist.baidu_url || '',
    featured: artist.featured ?? 0,
    enabled: artist.enabled ?? 1,
    summary: artist.summary || '',
    nationality: artist.nationality || '',
    occupation: artist.occupation || '',
    main_achievements: artist.main_achievements || '',
    representative_works_text: artist.representative_works_text || '',
    art_style: artist.art_style || '',
    influence: artist.influence || '',
    historical_evaluation: artist.historical_evaluation || '',
    character_relations: Array.isArray(artist.character_relations) ? artist.character_relations.map(r => ({ ...r })) : [],
    anecdotes: Array.isArray(artist.anecdotes) ? artist.anecdotes.map(a => ({ ...a })) : [],
    art_chronology: Array.isArray(artist.art_chronology) ? artist.art_chronology.map(c => ({ ...c })) : [],
    published_works: Array.isArray(artist.published_works) ? artist.published_works.map(p => ({ ...p })) : [],
    gallery_images: Array.isArray(artist.gallery_images) ? artist.gallery_images.map(g => ({ ...g })) : [],
    references: Array.isArray(artist.references) ? artist.references.map(r => ({ ...r })) : [],
    banner_url: artist.banner_url || ''
  }
  showEditDialog.value = true
}

function addBioEvent() {
  editForm.value.bio_events.push({ year: '', type: '', title: '', description: '' })
}

function removeBioEvent(idx) {
  editForm.value.bio_events.splice(idx, 1)
}

function addChronologyEvent() {
  editForm.value.art_chronology.push({ year: '', event: '', description: '' })
}

function removeChronologyEvent(idx) {
  editForm.value.art_chronology.splice(idx, 1)
}

function addRelation() {
  editForm.value.character_relations.push({ name: '', relationship: '', description: '', image_url: '' })
}

function removeRelation(idx) {
  editForm.value.character_relations.splice(idx, 1)
}

function addAnecdote() {
  editForm.value.anecdotes.push({ title: '', content: '' })
}

function removeAnecdote(idx) {
  editForm.value.anecdotes.splice(idx, 1)
}

function addPublishedWork() {
  editForm.value.published_works.push({ title: '', publisher: '', year: '' })
}

function removePublishedWork(idx) {
  editForm.value.published_works.splice(idx, 1)
}

function addReference() {
  editForm.value.references.push({ author: '', title: '', publisher: '', year: '' })
}

function removeReference(idx) {
  editForm.value.references.splice(idx, 1)
}

function addGalleryImage() {
  editForm.value.gallery_images.push({ url: '', title: '' })
}

function removeGalleryImage(idx) {
  editForm.value.gallery_images.splice(idx, 1)
}

async function handleSave() {
  if (!editForm.value.name?.trim()) {
    ElMessage.warning('请输入画家姓名')
    return
  }

  if (editingArtist.value && editForm.value.name !== editingArtist.value.name) {
    try {
      await ElMessageBox.confirm(
        `修改姓名将从「${editingArtist.value.name}」改为「${editForm.value.name}」，所有相关画作的作者信息也会同步更新。确认修改？`,
        '确认修改姓名',
        { confirmButtonText: '确认修改', cancelButtonText: '取消', type: 'warning' }
      )
    } catch { return }
  }

  saving.value = true
  try {
    const payload = {
      name: editForm.value.name.trim(),
      alias: editForm.value.alias,
      dynasty: editForm.value.dynasty,
      hometown: editForm.value.hometown,
      avatar_url: editForm.value.avatar_url,
      birth_year: editForm.value.birth_year || null,
      death_year: editForm.value.death_year || null,
      biography: editForm.value.biography,
      background: editForm.value.background,
      specialties: editForm.value.specialties,
      bio_events: JSON.stringify(editForm.value.bio_events),
      art_school: editForm.value.art_school,
      masterpieces: JSON.stringify(editForm.value.masterpieces),
      tags: JSON.stringify(editForm.value.tags),
      baidu_url: editForm.value.baidu_url,
      featured: editForm.value.featured,
      enabled: editForm.value.enabled,
      summary: editForm.value.summary,
      nationality: editForm.value.nationality,
      occupation: editForm.value.occupation,
      main_achievements: editForm.value.main_achievements,
      representative_works_text: editForm.value.representative_works_text,
      art_style: editForm.value.art_style,
      influence: editForm.value.influence,
      historical_evaluation: editForm.value.historical_evaluation,
      character_relations: JSON.stringify(editForm.value.character_relations),
      anecdotes: JSON.stringify(editForm.value.anecdotes),
      art_chronology: JSON.stringify(editForm.value.art_chronology),
      published_works: JSON.stringify(editForm.value.published_works),
      gallery_images: JSON.stringify(editForm.value.gallery_images),
      references: JSON.stringify(editForm.value.references),
      banner_url: editForm.value.banner_url
    }

    if (editingArtist.value) {
      const data = await api.put(`/artists/${editingArtist.value.id}`, payload)
      if (data.success) {
        if (editForm.value.name !== editingArtist.value.name) {
          try { await api.post(`/artists/${editingArtist.value.id}/sync-name`, { old_name: editingArtist.value.name, new_name: editForm.value.name }) }
          catch (e) { console.error('同步画家姓名失败', e) }
        }
        ElMessage.success('画家信息已更新')
        showEditDialog.value = false
        await loadArtists()
      } else {
        ElMessage.error(data.detail || data.message || '保存失败')
      }
    } else {
      const data = await api.post('/artists', payload)
      if (data.success) {
        ElMessage.success('画家创建成功')
        showEditDialog.value = false
        await loadArtists()
      } else {
        ElMessage.error(data.detail || data.message || '保存失败')
      }
    }
  } catch (e) {
    ElMessage.error('保存失败: ' + e.message)
  } finally { saving.value = false }
}

async function handleDelete(artist) {
  try {
    await ElMessageBox.confirm(`确定删除画家「${artist.name}」？`, '确认删除', { type: 'warning' })
    const data = await api.delete(`/artists/${artist.id}`)
    if (data.success) {
      ElMessage.success('画家已删除')
      await loadArtists()
    } else { ElMessage.error(data.detail || '删除失败') }
  } catch (e) { if (e !== 'cancel') ElMessage.error('删除失败: ' + e.message) }
}

async function toggleEnabled(artist) {
  try {
    const data = await api.put(`/artists/${artist.id}`, { enabled: artist.enabled ? 0 : 1 })
    if (data.success) {
      ElMessage.success(artist.enabled ? '画家已禁用' : '画家已启用')
      await loadArtists()
    }
  } catch (e) { ElMessage.error('操作失败: ' + e.message) }
}

async function handleAiFill(artist) {
  aiFillLoading[artist.id] = true
  try {
    const data = await api.post(`/artists/${artist.id}/ai-fill`)
    if (data.success) {
      ElMessage.success(data.message || 'AI查询完成')
      await loadArtists()
    } else { ElMessage.error(data.detail || data.message || 'AI查询失败') }
  } catch (e) { ElMessage.error('AI查询失败: ' + e.message) }
  finally { aiFillLoading[artist.id] = false }
}

onMounted(() => { loadArtists(); loadPeriods() })
</script>

<style scoped>
.artist-info-manager { padding: 0; }
.toolbar { margin-bottom: 16px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px; }
.toolbar-left { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.artist-list { display: flex; flex-direction: column; gap: 8px; min-height: 200px; }
.artist-card { background: white; border-radius: 10px; padding: 14px 18px; box-shadow: 0 1px 8px rgba(0,0,0,0.05); }
.artist-row { display: flex; justify-content: space-between; align-items: center; gap: 12px; flex-wrap: wrap; }
.artist-main { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.artist-name { font-size: 15px; font-weight: 600; color: #333; }
.artist-actions { display: flex; gap: 6px; flex-shrink: 0; flex-wrap: wrap; }
.artist-actions :deep(.el-button) { display: inline-flex; align-items: center; justify-content: center; }
.artist-actions :deep(.el-button__content) { display: inline-flex; align-items: center; gap: 4px; }
.empty-state { padding: 40px 0; }
.form-row { display: flex; gap: 16px; flex-wrap: wrap; }
.form-item-half { flex: 1; min-width: 160px; }
.rename-warning { font-size: 12px; color: #e6a23c; margin-top: 4px; }
.avatar-url-row { display: flex; gap: 8px; align-items: center; width: 100%; }
.array-editor { width: 100%; display: flex; flex-direction: column; gap: 4px; }
.array-editor-hint { font-size: 12px; color: #909399; margin: 0 0 8px 0; }
.array-editor-empty { font-size: 12px; color: #c0c4cc; text-align: center; padding: 20px; margin: 0; }
.array-item { border: 1px solid #e4e7ed; border-radius: 6px; padding: 10px 12px; background: #fafafa; }
.array-item-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; }
.array-item-index { font-size: 11px; color: #909399; font-weight: 600; }
.array-item-fields { display: flex; gap: 6px; flex-wrap: wrap; }
</style>
