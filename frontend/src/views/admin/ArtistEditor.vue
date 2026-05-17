<template>
  <div class="ae-root">
    <div class="ae-sidebar">
      <div class="ae-back">
        <el-button size="small" text @click="goBack"><el-icon><ArrowLeft /></el-icon>返回列表</el-button>
      </div>
      <div class="ae-sidebar-title">编辑画家</div>
      <div class="ae-sidebar-name">{{ form.name || '未命名' }}</div>
      <nav class="ae-nav">
        <a v-for="s in sections" :key="s.id" class="ae-nav-item" :class="{ active: activeSection === s.id }" @click="scrollTo(s.id)">
          {{ s.label }}
        </a>
      </nav>
      <div class="ae-actions">
        <el-button type="primary" @click="handleSave" :loading="saving" class="ae-btn-save">保存修改</el-button>
        <el-button @click="handleAiFill" :loading="aiLoading" class="ae-btn-ai">
          <el-icon><MagicStick /></el-icon>AI补充
        </el-button>
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
                <label class="ae-label">封面题图 <span class="ae-hint-dim">(建议 1200×400px)</span></label>
                <div class="ae-upload-row">
                  <el-input v-model="form.banner_url" placeholder="https://..." />
                  <el-upload :show-file-list="false" :before-upload="(f) => uploadFile(f, 'banner')" accept="image/*" style="flex-shrink:0">
                    <el-button size="small">上传</el-button>
                  </el-upload>
                </div>
                <div v-if="form.banner_url" class="ae-preview-banner"><img :src="form.banner_url" @error="e => e.target.style.display='none'" /></div>
              </div>
              <div class="ae-field">
                <label class="ae-label">头像 <span class="ae-hint-dim">(建议 200×200px)</span></label>
                <div class="ae-upload-row">
                  <el-input v-model="form.avatar_url" placeholder="https://..." />
                  <el-upload :show-file-list="false" :before-upload="(f) => uploadFile(f, 'avatar')" accept="image/*" style="flex-shrink:0">
                    <el-button size="small">上传</el-button>
                  </el-upload>
                </div>
                <div class="ae-preview-avatar" style="margin-top:8px">
                  <el-avatar v-if="form.avatar_url" :src="form.avatar_url" :size="64" shape="square" />
                  <el-avatar v-else :size="64" shape="square" style="background:#c45a3c;font-size:24px">{{ form.name?.charAt(0) || '?' }}</el-avatar>
                </div>
              </div>
            </div>
            <div class="ae-field">
              <label class="ae-label">百度百科链接</label>
              <el-input v-model="form.baidu_url" placeholder="https://baike.baidu.com/item/..." />
            </div>
          </div>

          <!-- ===== 生平 ===== -->
          <div v-if="s.id === 'biography'">
            <div class="ae-field">
              <label class="ae-label">生平简介</label>
              <el-input v-model="form.biography" type="textarea" :rows="8" placeholder="详细生平介绍文本，支持长文" />
            </div>
            <div class="ae-field">
              <label class="ae-label">生平时间线</label>
              <div class="ae-array">
                <p class="ae-array-hint">按年份添加画家的生平关键事件</p>
                <div v-for="(evt, idx) in form.bio_events" :key="idx" class="ae-array-card">
                  <div class="ae-array-card-header">
                    <span>#{{ idx + 1 }}</span>
                    <el-button type="danger" size="small" text @click="removeItem('bio_events', idx)">删除</el-button>
                  </div>
                  <div class="ae-array-card-body">
                    <div class="ae-grid ae-grid-3">
                      <el-input v-model="evt.year" placeholder="年份" size="small" type="number" />
                      <el-input v-model="evt.type" placeholder="类型（入仕/罢官/创作）" size="small" />
                      <el-input v-model="evt.title" placeholder="标题" size="small" />
                    </div>
                    <el-input v-model="evt.description" placeholder="详细描述" size="small" type="textarea" :rows="2" style="margin-top:6px" />
                  </div>
                </div>
                <el-button size="small" @click="addItem('bio_events', {year: '', type: '', title: '', description: ''})">
                  <el-icon><Plus /></el-icon>添加事件
                </el-button>
                <p v-if="form.bio_events.length === 0" class="ae-array-empty">暂未添加时间线事件</p>
              </div>
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
          <el-button @click="goBack">取消</el-button>
          <el-button type="primary" @click="handleSave" :loading="saving" class="ae-btn-save-main">保存修改</el-button>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ArrowLeft, Plus, MagicStick } from '@element-plus/icons-vue'
import api from '@/api'

const route = useRoute()
const router = useRouter()
const API_BASE = import.meta.env.VITE_API_BASE || '/api/v1'

const artistName = route.params.name
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
  summary: '', background: '', banner_url: '', avatar_url: '', baidu_url: '',
  biography: '', bio_events: [], art_chronology: [],
  art_style: '', main_achievements: '', influence: '', historical_evaluation: '',
  character_relations: [], anecdotes: [],
  masterpieces: [], representative_works_text: '', tags: [],
  published_works: [], references: [], gallery_images: [],
  featured: 0, enabled: 1,
})

const JSON_ARRAYS = ['bio_events', 'art_chronology', 'character_relations', 'anecdotes', 'masterpieces', 'tags', 'published_works', 'references', 'gallery_images']

const sections = [
  { id: 'basic', label: '基本资料' },
  { id: 'overview', label: '概述与图像' },
  { id: 'biography', label: '生平' },
  { id: 'chronology', label: '艺术年谱' },
  { id: 'research', label: '艺术研究' },
  { id: 'relations', label: '人物关系' },
  { id: 'literature', label: '文献与出版' },
  { id: 'gallery', label: '作品图集' },
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

async function uploadFile(file, type) {
  const fd = new FormData()
  fd.append('file', file)
  try {
    const res = await fetch(`${API_BASE}/tubi/upload`, { method: 'POST', body: fd })
    if (res.ok) {
      const data = await res.json()
      if (data.success && data.url) {
        if (type === 'avatar') form.avatar_url = data.url
        else form.banner_url = data.url
        ElMessage.success('上传成功')
      }
    } else {
      ElMessage.error('上传失败')
    }
  } catch (e) { ElMessage.error('上传失败') }
  return false
}

async function searchArtworks() {
  if (!gallerySearch.value || !artistName) return
  searching.value = true
  try {
    const params = new URLSearchParams({ keyword: gallerySearch.value, limit: 20 })
    if (editing.value) params.set('artist', originalName.value)
    const res = await fetch(`${API_BASE}/tubi/results?${params}`)
    if (res.ok) {
      const data = await res.json()
      searchResults.value = (data.data || []).map(w => ({
        id: w.id || w.db_id,
        title: w.title || w.work_name || '未命名',
        year: w.year || '',
        thumbnail_url: w.thumbnail_url || w.url || '',
        url: w.url || ''
      }))
    }
  } catch (e) { }
  finally { searching.value = false }
}

async function fetchPeriods() {
  try { const r = await fetch(`${API_BASE}/artists/periods`); if (r.ok) { const d = await r.json(); periods.value = d.periods || [] } } catch (e) { }
}

async function fetchArtistOptions() {
  try { const r = await fetch(`${API_BASE}/content-analysis/artists`); if (r.ok) { const d = await r.json(); artistOptions.value = d.artists || [] } } catch (e) { }
}

async function fetchArtist() {
  loading.value = true
  try {
    const res = await fetch(`${API_BASE}/artists/by-name/${encodeURIComponent(artistName)}`)
    if (res.ok) {
      const data = await res.json()
      if (data.success && data.artist) {
        const a = data.artist
        artistId.value = a.id
        originalName.value = a.name
        editing.value = true
        for (const key of Object.keys(form)) {
          if (JSON_ARRAYS.includes(key)) {
            try { form[key] = typeof a[key] === 'string' ? JSON.parse(a[key] || '[]') : (Array.isArray(a[key]) ? a[key] : []) } catch { form[key] = [] }
          } else if (key === 'birth_year' || key === 'death_year') {
            form[key] = a[key] || null
          } else if (key === 'featured' || key === 'enabled') {
            form[key] = a[key] || 0
          } else {
            form[key] = a[key] || ''
          }
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
  if (artistName && artistName !== 'new') {
    await fetchArtist()
  } else {
    editing.value = false
    loading.value = false
  }
  observer.value = new IntersectionObserver((entries) => {
    for (const entry of entries) {
      if (entry.isIntersecting) { activeSection.value = entry.target.id }
    }
  }, { rootMargin: '-20% 0px -70% 0px' })
  document.querySelectorAll('.ae-section').forEach(el => observer.value?.observe(el))
})
</script>

<style scoped>
.ae-root { display: flex; min-height: 100vh; background: #fafaf8; }

.ae-sidebar { width: 220px; flex-shrink: 0; background: #fff; border-right: 1px solid #edeae1; padding: 20px 14px; display: flex; flex-direction: column; position: sticky; top: 0; height: 100vh; overflow-y: auto; }
.ae-back { margin-bottom: 10px; }
.ae-sidebar-title { font-size: 11px; color: #8a8578; text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 2px; }
.ae-sidebar-name { font-size: 15px; color: #3a3222; font-weight: 600; font-family: 'Noto Serif SC', serif; margin-bottom: 18px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.ae-nav { display: flex; flex-direction: column; gap: 1px; flex: 1; }
.ae-nav-item { padding: 9px 12px; font-size: 13px; color: #8c7a5c; text-decoration: none; border-radius: 6px; cursor: pointer; transition: all 0.15s; }
.ae-nav-item:hover { background: #f5f3ed; color: #3a3222; }
.ae-nav-item.active { background: #fdf6f0; color: #c45a3c; font-weight: 500; }
.ae-actions { margin-top: 14px; padding-top: 14px; border-top: 1px solid #edeae1; display: flex; flex-direction: column; gap: 8px; }
.ae-btn-save { width: 100%; justify-content: center; font-weight: 500; }
.ae-btn-ai { width: 100%; justify-content: center; }

.ae-main { flex: 1; padding: 32px 40px 120px; max-width: 960px; }
.ae-loading { text-align: center; padding: 100px 0; color: #b0a890; }
.ae-section { margin-bottom: 52px; scroll-margin-top: 20px; }
.ae-section-title { font-family: 'Noto Serif SC', serif; font-size: 19px; color: #3a3222; margin: 0 0 22px; padding-left: 12px; border-left: 3px solid #c45a3c; }

.ae-grid { display: grid; gap: 16px; }
.ae-grid-2 { grid-template-columns: repeat(2, 1fr); }
.ae-grid-3 { grid-template-columns: repeat(3, 1fr); }
@media (max-width: 768px) { .ae-grid-2, .ae-grid-3 { grid-template-columns: 1fr; } .ae-sidebar { display: none; } .ae-main { padding: 20px 16px 120px; } }

.ae-field { margin-bottom: 18px; }
.ae-label { display: block; font-size: 13px; color: #5c5346; font-weight: 500; margin-bottom: 6px; }
.ae-required { color: #c45a3c; }
.ae-hint { font-size: 12px; margin-top: 4px; color: #b0a890; }
.ae-hint-warn { color: #c45a3c; }
.ae-hint-dim { font-size: 11px; color: #b0a890; font-weight: 400; }

.ae-upload-row { display: flex; gap: 8px; align-items: center; }
.ae-preview-banner { margin-top: 8px; width: 100%; max-height: 140px; border-radius: 8px; overflow: hidden; background: #f5f3ed; }
.ae-preview-banner img { width: 100%; height: 100%; object-fit: cover; }

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

.ae-bottom-bar { display: flex; justify-content: flex-end; gap: 12px; padding: 24px 0; border-top: 1px solid #edeae1; margin-top: 32px; }
.ae-btn-save-main { font-weight: 500; min-width: 120px; }
</style>
