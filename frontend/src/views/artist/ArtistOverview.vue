<template>
  <div class="av-page">
    <div v-if="loading" class="av-loading">加载中...</div>

    <div v-else-if="notFound" class="av-not-found">
      <div class="av-not-found-icon">?</div>
      <h2>未找到该画家</h2>
      <p>请确认名称是否正确，或返回<router-link to="/artists">艺术家列表</router-link>浏览</p>
    </div>

    <template v-else-if="artist">
      <header class="av-header">
        <div class="av-header-inner">
          <div class="av-header-avatar">
            <el-avatar v-if="artist.avatar_url" :src="artist.avatar_url" :size="160" shape="square" class="av-avatar-img" />
            <span v-else class="av-avatar-text">{{ artist.name?.charAt(0) || '?' }}</span>
          </div>
          <div class="av-header-info">
            <h1 class="av-name">{{ artist.name }}</h1>
            <p v-if="artist.alias" class="av-alias">{{ artist.alias }}</p>
            <div class="av-meta">
              <span v-if="artist.dynasty" class="av-meta-item">{{ artist.dynasty }}</span>
              <span v-if="artist.birth_year || artist.death_year" class="av-meta-item">{{ formatYears(artist.birth_year, artist.death_year) }}</span>
              <span v-if="artist.art_school" class="av-meta-item av-meta-school">{{ artist.art_school }}</span>
              <span v-if="artist.hometown" class="av-meta-item">{{ artist.hometown }}</span>
              <span v-if="artist.occupation" class="av-meta-item">{{ artist.occupation }}</span>
            </div>
            <p v-if="artist.summary" class="av-summary">{{ artist.summary }}</p>
          </div>
          <div class="av-header-actions">
            <a v-if="artist.baidu_url" :href="artist.baidu_url" target="_blank" class="av-baike-link"><el-button size="small" plain>百度百科 &#8599;</el-button></a>
            <el-button size="small" plain @click="openSuggestEdit">我的修改</el-button>
          </div>
        </div>
      </header>

      <nav class="av-sub-nav">
        <router-link
          v-for="tab in subNavTabs"
          :key="tab.name"
          :to="{ name: tab.name, params: { name: artistName } }"
          class="av-nav-link"
          :class="{ active: route.name === tab.name }"
        >
          {{ tab.label }}
        </router-link>
      </nav>

      <div class="av-body">
        <main class="av-main">
          <section v-if="artist.biography" id="bio-life" class="av-section">
            <h2 class="av-section-title">人物生平</h2>
            <p class="av-text">{{ artist.biography }}</p>
          </section>

          <section v-if="artChronology.length > 0" id="bio-chrono" class="av-section">
            <h2 class="av-section-title">艺术年谱</h2>
            <div class="av-chrono-list">
              <div v-for="(item, idx) in artChronology" :key="idx" class="av-chrono-item">
                <div class="av-chrono-year">{{ item.year }}</div>
                <div class="av-chrono-body">
                  <div class="av-chrono-event">{{ item.event }}</div>
                  <p v-if="item.description" class="av-chrono-desc">{{ item.description }}</p>
                  <span v-if="item.location" class="av-chrono-loc">📍 {{ item.location }}</span>
                </div>
              </div>
            </div>
          </section>

          <section v-if="artist.art_style" id="bio-style" class="av-section">
            <h2 class="av-section-title">艺术特色</h2>
            <p class="av-text" v-html="renderMarkdown(artist.art_style)" />
          </section>

          <section v-if="artist.main_achievements" id="bio-achieve" class="av-section">
            <h2 class="av-section-title">主要成就</h2>
            <p class="av-text">{{ artist.main_achievements }}</p>
          </section>

          <section v-if="artist.influence" id="bio-influence" class="av-section">
            <h2 class="av-section-title">后世影响</h2>
            <p class="av-text">{{ artist.influence }}</p>
          </section>

          <section v-if="artist.historical_evaluation" id="bio-evaluation" class="av-section">
            <h2 class="av-section-title">历史评价</h2>
            <p class="av-text">{{ artist.historical_evaluation }}</p>
          </section>

          <section v-if="characterRelations.length > 0" id="bio-relations" class="av-section">
            <h2 class="av-section-title">人物关系</h2>
            <div class="av-relations-grid">
              <div v-for="(rel, idx) in characterRelations" :key="idx" class="av-relation-card" @click="goToRelationArtist(rel)">
                <el-avatar v-if="rel.image_url" :src="rel.image_url" :size="52" shape="circle" />
                <el-avatar v-else :size="52" shape="circle" class="av-avatar-placeholder">{{ (rel.name || '?').charAt(0) }}</el-avatar>
                <div class="av-relation-name">{{ rel.name }}</div>
                <span class="av-relation-tag">{{ rel.relationship }}</span>
                <p v-if="rel.description" class="av-relation-desc">{{ rel.description }}</p>
              </div>
            </div>
          </section>

          <section v-if="anecdotes.length > 0" id="bio-anecdotes" class="av-section">
            <h2 class="av-section-title">轶事典故</h2>
            <div v-for="(item, idx) in anecdotes" :key="idx" class="av-anecdote">
              <div class="av-anecdote-toggle" @click="expandedAnecdote = expandedAnecdote === idx ? -1 : idx">
                <span class="av-anecdote-title">{{ item.title || `轶事 ${idx + 1}` }}</span>
                <span class="av-anecdote-arrow" :class="{ open: expandedAnecdote === idx }">▾</span>
              </div>
              <div v-show="expandedAnecdote === idx" class="av-anecdote-body">
                <p class="av-text">{{ item.content || item.description || '' }}</p>
              </div>
            </div>
          </section>

          <section v-if="publishedWorks.length > 0" id="bio-published" class="av-section">
            <h2 class="av-section-title">出版著作</h2>
            <div class="av-published-grid">
              <div v-for="(pw, idx) in publishedWorks" :key="idx" class="av-published-item">
                <div class="av-published-title">{{ pw.title }}</div>
                <div class="av-published-meta">{{ [pw.publisher, pw.year].filter(Boolean).join(' · ') }}</div>
                <a v-if="pw.isbn" :href="pw.isbn.startsWith('http') ? pw.isbn : undefined" target="_blank" class="av-published-isbn">{{ pw.isbn }}</a>
              </div>
            </div>
          </section>

          <section v-if="galleryImages.length > 0" id="bio-gallery" class="av-section">
            <h2 class="av-section-title">作品图集</h2>
            <div class="av-gallery-grid">
              <div v-for="(gi, idx) in galleryImages" :key="idx" class="av-gallery-item" @click="gi.artwork_id && goToWork(gi.artwork_id)">
                <div class="av-gallery-thumb">
                  <img v-if="gi.url" :src="gi.url" :alt="gi.title || gi.artwork_name" loading="lazy" />
                  <span v-else class="av-thumb-placeholder">{{ (gi.title || '?').charAt(0) }}</span>
                </div>
                <p class="av-gallery-title">{{ gi.title || gi.artwork_name || '未命名' }}</p>
              </div>
            </div>
          </section>

          <section v-if="references.length > 0" id="bio-refs" class="av-section">
            <h2 class="av-section-title">参考文献</h2>
            <ol class="av-ref-list">
              <li v-for="(ref, idx) in references" :key="idx" class="av-ref-item">{{ typeof ref === 'string' ? ref : ref.text || ref.title || '' }}</li>
            </ol>
          </section>
        </main>

        <aside v-if="tocItems.length > 0" class="av-toc">
          <nav class="av-toc-nav">
            <div class="av-toc-title">目录</div>
            <a
              v-for="item in tocItems"
              :key="item.id"
              class="av-toc-link"
              :class="{ active: activeToc === item.id }"
              @click.prevent="scrollToSection(item.id)"
            >{{ item.label }}</a>
          </nav>
        </aside>
      </div>
    </template>
  </div>

  <el-dialog v-model="showSuggestDialog" title="我的修改" width="520px" align-center :close-on-click-modal="false" @open="onSuggestDialogOpen">
    <el-form label-width="80px" label-position="left">
      <el-form-item label="修改字段">
        <el-select v-model="suggestForm.field_name" placeholder="选择要修改的字段" style="width:100%">
          <el-option v-for="f in suggestFields" :key="f.value" :label="f.label" :value="f.value" />
        </el-select>
      </el-form-item>
      <el-form-item label="当前内容">
        <div class="av-suggest-old">{{ suggestForm.old_value || '(空)' }}</div>
      </el-form-item>
      <el-form-item label="修改为">
        <el-input v-model="suggestForm.new_value" type="textarea" :rows="5" placeholder="请输入新内容" />
      </el-form-item>
      <el-form-item label="修改说明">
        <el-input v-model="suggestForm.change_summary" placeholder="简要说明为什么做此修改" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="showSuggestDialog = false">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="handleSubmitChange">提交</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../../stores/authStore'
import { ElMessage } from 'element-plus'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const API_BASE = import.meta.env.VITE_API_BASE || '/api/v1'

const artistName = computed(() => route.params.name)
const loading = ref(true)
const notFound = ref(false)
const artist = ref(null)
const stats = ref({})
const expandedAnecdote = ref(-1)
const activeToc = ref('')

const suggestFields = [
  { value: 'summary', label: '概述' },
  { value: 'biography', label: '生平简介' },
  { value: 'art_style', label: '艺术特色' },
  { value: 'art_chronology', label: '艺术年谱' },
  { value: 'main_achievements', label: '主要成就' },
  { value: 'influence', label: '后世影响' },
  { value: 'historical_evaluation', label: '历史评价' },
  { value: 'occupation', label: '职业' },
  { value: 'nationality', label: '国籍' },
  { value: 'representative_works_text', label: '代表作品' },
  { value: 'specialties', label: '专长' },
  { value: 'character_relations', label: '人物关系' },
  { value: 'anecdotes', label: '轶事典故' },
  { value: 'published_works', label: '出版著作' },
  { value: 'references', label: '参考文献' },
]

const showSuggestDialog = ref(false)
const suggestForm = reactive({
  field_name: 'summary',
  old_value: '',
  new_value: '',
  change_summary: '',
})
const submitting = ref(false)

const subNavTabs = [
  { label: '概览', name: 'ArtistOverview' },
  { label: '作品', name: 'ArtistWorks' },
  { label: '印章', name: 'ArtistSeals' },
  { label: '文献', name: 'ArtistLiterature' },
  { label: '分析', name: 'ArtistAnalysis' },
]

const tocItems = computed(() => {
  const items = []
  const add = (id, label, condition) => {
    if (condition) items.push({ id, label })
  }
  add('bio-life', '人物生平', artist.value?.biography)
  add('bio-chrono', '艺术年谱', artChronology.value.length > 0)
  add('bio-style', '艺术特色', artist.value?.art_style)
  add('bio-achieve', '主要成就', artist.value?.main_achievements)
  add('bio-influence', '后世影响', artist.value?.influence)
  add('bio-evaluation', '历史评价', artist.value?.historical_evaluation)
  add('bio-relations', '人物关系', characterRelations.value.length > 0)
  add('bio-anecdotes', '轶事典故', anecdotes.value.length > 0)
  add('bio-published', '出版著作', publishedWorks.value.length > 0)
  add('bio-gallery', '作品图集', galleryImages.value.length > 0)
  add('bio-refs', '参考文献', references.value.length > 0)
  return items
})

const artChronology = computed(() => {
  if (!artist.value?.art_chronology) return []
  return parseJsonField(artist.value.art_chronology)
})

const characterRelations = computed(() => {
  if (!artist.value?.character_relations) return []
  return parseJsonField(artist.value.character_relations)
})

const anecdotes = computed(() => {
  if (!artist.value?.anecdotes) return []
  return parseJsonField(artist.value.anecdotes)
})

const publishedWorks = computed(() => {
  if (!artist.value?.published_works) return []
  return parseJsonField(artist.value.published_works)
})

const galleryImages = computed(() => {
  if (!artist.value?.gallery_images) return []
  return parseJsonField(artist.value.gallery_images)
})

const tags = computed(() => {
  if (!artist.value?.tags) return []
  return parseJsonField(artist.value.tags)
})

const references = computed(() => {
  if (!artist.value?.references) return []
  return parseJsonField(artist.value.references)
})

function parseJsonField(field) {
  try {
    const parsed = typeof field === 'string' ? JSON.parse(field) : field
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

function formatYears(birth, death) {
  if (!birth && !death) return ''
  const b = birth || '?'
  const d = death || '?'
  return `${b} — ${d}`
}

function renderMarkdown(text) {
  if (!text) return ''
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/^### (.+)$/gm, '<h3 class="av-md-h3">$1</h3>')
    .replace(/^## (.+)$/gm, '<h2 class="av-md-h2">$1</h2>')
    .replace(/\n/g, '<br>')
}

function scrollToSection(id) {
  activeToc.value = id
  const el = document.getElementById(id)
  if (el) {
    el.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }
}

function goToWork(id) {
  if (id) window.open(`/#/tubi/${id}`, '_blank')
}

function goToRelationArtist(rel) {
  if (rel.name) router.push({ name: 'ArtistOverview', params: { name: rel.name } })
}

function openSuggestEdit() {
  suggestForm.field_name = 'summary'
  suggestForm.old_value = getArtistField('summary')
  suggestForm.new_value = suggestForm.old_value
  suggestForm.change_summary = ''
  showSuggestDialog.value = true
}

function getArtistField(fieldName) {
  if (!artist.value) return ''
  const val = artist.value[fieldName]
  if (val === null || val === undefined) return ''
  if (typeof val === 'object') return JSON.stringify(val, null, 2)
  return String(val)
}

function onSuggestDialogOpen() {
  suggestForm.old_value = getArtistField(suggestForm.field_name)
  suggestForm.new_value = suggestForm.old_value
}

watch(() => suggestForm.field_name, () => {
  if (showSuggestDialog.value) {
    suggestForm.old_value = getArtistField(suggestForm.field_name)
    suggestForm.new_value = suggestForm.old_value
  }
})

async function handleSubmitChange() {
  if (!suggestForm.new_value) {
    ElMessage.warning('请输入新值')
    return
  }
  if (!suggestForm.change_summary.trim()) {
    ElMessage.warning('请填写修改说明')
    return
  }
  submitting.value = true
  try {
    const params = new URLSearchParams({
      field_name: suggestForm.field_name,
      old_value: suggestForm.old_value,
      new_value: suggestForm.new_value,
      change_summary: suggestForm.change_summary,
    })
    const res = await fetch(`${API_BASE}/artists/${artist.value.id}/change-requests?${params}`, {
      method: 'POST',
      headers: authStore.token ? { Authorization: `Bearer ${authStore.token}` } : {},
    })
    if (res.ok) {
      const data = await res.json()
      if (data.direct_update) {
        ElMessage.success('已直接更新（编辑权限）')
      } else {
        ElMessage.success('修改建议已提交，等待审核')
      }
      showSuggestDialog.value = false
    } else {
      const err = await res.json().catch(() => ({}))
      ElMessage.error(err.detail || '提交失败')
    }
  } catch (e) {
    ElMessage.error('提交失败')
  } finally {
    submitting.value = false
  }
}

async function fetchArtist() {
  const name = artistName.value
  if (!name) {
    notFound.value = true
    loading.value = false
    return
  }
  try {
    const res = await fetch(`${API_BASE}/artists/by-name/${encodeURIComponent(name)}`)
    if (!res.ok) {
      if (res.status === 404) notFound.value = true
      return
    }
    const data = await res.json()
    artist.value = data.artist || null
    if (!artist.value) notFound.value = true
  } catch (e) {
    console.error('获取画家信息失败:', e)
    notFound.value = true
  }
}

async function fetchStats() {
  if (!artist.value?.id) return
  try {
    const res = await fetch(`${API_BASE}/artists/${artist.value.id}/stats`)
    if (res.ok) {
      const data = await res.json()
      stats.value = data.stats || {}
    }
  } catch (e) {
    console.error('获取统计数据失败:', e)
  }
}

let tocObserver = null
function setupTocObserver() {
  const sectionIds = tocItems.value.map(i => i.id)
  if (sectionIds.length === 0) return
  tocObserver = new IntersectionObserver((entries) => {
    for (const entry of entries) {
      if (entry.isIntersecting) {
        activeToc.value = entry.target.id
        break
      }
    }
  }, { rootMargin: '-10% 0px -80% 0px' })
  sectionIds.forEach(id => {
    const el = document.getElementById(id)
    if (el) tocObserver.observe(el)
  })
}

onMounted(async () => {
  loading.value = true
  await fetchArtist()
  if (artist.value) {
    document.title = `${artist.value.name} - 画家百科`
    await fetchStats()
  }
  loading.value = false
  setTimeout(setupTocObserver, 200)
})

watch(tocItems, (items) => {
  if (tocObserver) tocObserver.disconnect()
  if (items.length > 0) {
    setTimeout(setupTocObserver, 100)
  }
}, { deep: true })
</script>

<style scoped>
.av-page {
  max-width: var(--container-wide);
  margin: 0 auto;
  padding: 0 24px 120px;
  min-height: 100vh;
  background: #faf8f5;
}
.av-loading { text-align: center; padding: 120px 0; color: #8a8578; }
.av-not-found { text-align: center; padding: 120px 24px; }
.av-not-found-icon { width: 80px; height: 80px; margin: 0 auto 20px; border-radius: 50%; background: #f0e8e0; color: #8a8578; display: flex; align-items: center; justify-content: center; font-size: 2.25rem; font-family: 'Noto Serif SC', serif; }
.av-not-found h2 { font-family: 'Noto Serif SC', serif; font-size: 1.4rem; color: #3a3222; margin: 0 0 12px; font-weight: 500; }
.av-not-found p { color: #8a8578; font-size: 0.9rem; margin: 0; }
.av-not-found a { color: #c45a3c; text-decoration: none; }

/* ── Header ── */
.av-header {
  position: relative;
  padding: 64px 0 48px;
  margin-bottom: 0;
  border-radius: 12px;
  overflow: hidden;
  background: linear-gradient(135deg, #3a3222 0%, #6b5b4a 35%, #8a7a6a 70%);
}
.av-header .av-name { color: #fff; text-shadow: 0 2px 6px rgba(0,0,0,0.3); }
.av-header .av-alias { color: rgba(255,255,255,0.75); }
.av-header .av-summary { color: rgba(255,255,255,0.8); }
.av-header .av-meta-item { background: rgba(255,255,255,0.12); color: rgba(255,255,255,0.9); }
.av-header .av-meta-school { background: rgba(196,90,60,0.45); color: #fff; }
.av-header-inner {
  position: relative; z-index: 1;
  display: flex; gap: 32px; align-items: flex-start;
  padding: 0 48px;
}
.av-header-avatar { flex-shrink: 0; margin-top: 0; }
.av-avatar-img { border: 3px solid rgba(255,255,255,0.3); box-shadow: 0 6px 30px rgba(0,0,0,0.25); border-radius: 10px; }
.av-avatar-text {
  display: flex; align-items: center; justify-content: center;
  width: 160px; height: 160px; border-radius: 10px;
  background: linear-gradient(135deg, #c45a3c, #dbbca8);
  color: #fff; font-family: 'Noto Serif SC', serif;
  font-size: 64px; font-weight: 500;
  border: 3px solid rgba(255,255,255,0.3);
  box-shadow: 0 6px 30px rgba(0,0,0,0.25);
}
.av-header-info { flex: 1; min-width: 0; }
.av-name {
  font-family: 'Noto Serif SC', serif;
  font-size: 32px; font-weight: 700; color: #2c2416;
  margin: 0 0 4px; line-height: 1.2; letter-spacing: 0.02em;
}
.av-alias {
  font-size: 15px; color: #6b6050; margin: 0 0 10px;
  font-family: 'Noto Serif SC', serif;
}
.av-meta { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 10px; }
.av-meta-item {
  display: inline-block; padding: 3px 10px;
  background: #f0ebe0; color: #5c5040;
  border-radius: 4px; font-size: 12px; line-height: 1.5;
}
.av-meta-school { background: #fdf6f0; color: #c45a3c; font-weight: 500; }
.av-summary {
  font-size: 14px; color: #5c5040; line-height: 1.8;
  margin: 0; max-width: 680px;
}
.av-header-actions {
  flex-shrink: 0; display: flex; flex-direction: column;
  align-items: flex-end; gap: 10px; padding-top: 4px;
}
.av-baike-link { text-decoration: none; }

.av-suggest-old {
  max-height: 160px; overflow-y: auto; font-size: 13px;
  color: #8a8578; line-height: 1.6; padding: 10px 12px;
  background: #f5f3ed; border-radius: 6px; white-space: pre-wrap;
  word-break: break-all;
}

/* ── Sub Nav ── */
.av-sub-nav {
  display: flex; gap: 4px; padding: 16px 0; margin-bottom: 32px;
  border-bottom: 1px solid #e8e3da; overflow-x: auto;
}
.av-nav-link {
  padding: 8px 18px; font-size: 13px; color: #8c7a5c;
  text-decoration: none; border-radius: 6px;
  transition: all 0.15s; white-space: nowrap;
}
.av-nav-link:hover { background: #f5f0e8; color: #3a3222; }
.av-nav-link.active { background: #fdf6f0; color: #c45a3c; font-weight: 600; }

/* ── Body ── */
.av-body { display: flex; gap: 48px; align-items: flex-start; }
.av-main { flex: 1; min-width: 0; max-width: 780px; }

/* ── Sections ── */
.av-section { margin-bottom: 44px; scroll-margin-top: 24px; }
.av-section-title {
  font-family: 'Noto Serif SC', serif;
  font-size: 22px; font-weight: 700; color: #2c2416;
  margin: 0 0 16px; padding-bottom: 10px;
  border-bottom: 2px solid #c45a3c; display: inline-block;
}
.av-text {
  font-size: 15px; color: #3a3222; line-height: 1.9; margin: 0;
  text-align: justify;
}

/* ── Chronology ── */
.av-chrono-list { border-left: 2px solid #e0d8c8; padding-left: 24px; margin-left: 8px; }
.av-chrono-item { margin-bottom: 20px; position: relative; }
.av-chrono-item::before {
  content: ''; position: absolute; left: -30px; top: 6px;
  width: 10px; height: 10px; border-radius: 50%;
  background: #c45a3c; border: 2px solid #faf8f5;
}
.av-chrono-year {
  font-size: 12px; color: #c45a3c; font-weight: 600;
  margin-bottom: 4px; font-family: 'Noto Serif SC', serif;
}
.av-chrono-event { font-size: 15px; color: #2c2416; font-weight: 600; margin-bottom: 4px; }
.av-chrono-desc { font-size: 13px; color: #5c5040; line-height: 1.7; margin: 0; }
.av-chrono-loc { font-size: 11px; color: #a09080; display: block; margin-top: 4px; }

/* ── Relations ── */
.av-relations-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 14px; }
.av-relation-card {
  padding: 18px 16px; background: #fff; border: 1px solid #e8e3da;
  border-radius: 10px; text-align: center; cursor: pointer;
  transition: all 0.2s; display: flex; flex-direction: column; align-items: center; gap: 6px;
}
.av-relation-card:hover { border-color: #d0b898; box-shadow: 0 2px 12px rgba(0,0,0,0.06); transform: translateY(-1px); }
.av-avatar-placeholder { background: #c45a3c; color: #fff; font-family: 'Noto Serif SC', serif; font-size: 18px; }
.av-relation-name { font-size: 14px; font-weight: 600; color: #2c2416; }
.av-relation-tag {
  font-size: 11px; padding: 2px 8px; background: #fdf6f0;
  color: #c45a3c; border-radius: 3px; font-weight: 500;
}
.av-relation-desc { font-size: 12px; color: #8a8578; line-height: 1.5; margin: 0; }

/* ── Anecdotes ── */
.av-anecdote { border: 1px solid #e8e3da; border-radius: 8px; margin-bottom: 10px; overflow: hidden; }
.av-anecdote-toggle {
  display: flex; justify-content: space-between; align-items: center;
  padding: 14px 18px; cursor: pointer; transition: background 0.15s;
}
.av-anecdote-toggle:hover { background: #faf8f5; }
.av-anecdote-title { font-size: 15px; color: #2c2416; font-weight: 600; }
.av-anecdote-arrow { font-size: 12px; color: #8a8578; transition: transform 0.2s; }
.av-anecdote-arrow.open { transform: rotate(180deg); }
.av-anecdote-body { padding: 0 18px 18px; }

/* ── Published ── */
.av-published-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 12px; }
.av-published-item { padding: 16px; background: #fff; border: 1px solid #e8e3da; border-radius: 8px; }
.av-published-title { font-size: 14px; font-weight: 600; color: #2c2416; margin-bottom: 4px; font-family: 'Noto Serif SC', serif; }
.av-published-meta { font-size: 12px; color: #8a8578; }
.av-published-isbn { font-size: 11px; color: #c45a3c; display: block; margin-top: 4px; }

/* ── Gallery ── */
.av-gallery-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 16px; }
.av-gallery-item { cursor: pointer; transition: transform 0.2s; }
.av-gallery-item:hover { transform: translateY(-2px); }
.av-gallery-thumb {
  width: 100%; aspect-ratio: 3/4; border-radius: 8px; overflow: hidden;
  background: #f5f0e8; display: flex; align-items: center; justify-content: center;
}
.av-gallery-thumb img { width: 100%; height: 100%; object-fit: cover; }
.av-thumb-placeholder { font-family: 'Noto Serif SC', serif; font-size: 24px; color: #c0b8a8; }
.av-gallery-title { font-size: 12px; color: #2c2416; margin: 8px 0 0; text-align: center; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

/* ── References ── */
.av-ref-list { margin: 0; padding-left: 20px; }
.av-ref-item { font-size: 13px; color: #3a3222; line-height: 1.7; margin-bottom: 6px; }

/* ── TOC ── */
.av-toc { width: 200px; flex-shrink: 0; position: sticky; top: 80px; }
.av-toc-nav { border-left: 2px solid #e8e3da; padding-left: 16px; }
.av-toc-title { font-size: 12px; color: #a09080; text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 12px; font-weight: 600; }
.av-toc-link {
  display: block; padding: 4px 0; font-size: 13px; color: #8a8578;
  text-decoration: none; border-radius: 4px; cursor: pointer;
  transition: all 0.15s; border-left: 2px solid transparent;
  margin-left: -18px; padding-left: 16px;
}
.av-toc-link:hover { color: #3a3222; }
.av-toc-link.active { color: #c45a3c; font-weight: 600; border-left-color: #c45a3c; }

@media (max-width: 1024px) { .av-toc { display: none; } }
@media (max-width: 768px) {
  .av-page { padding: 0 16px 80px; }
  .av-header { padding: 32px 0 28px; }
  .av-header-inner { flex-direction: column; gap: 16px; padding: 0 20px; }
  .av-header-actions { flex-direction: row; align-items: center; }
  .av-name { font-size: 26px; }
  .av-body { flex-direction: column; gap: 32px; }
  .av-relations-grid { grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); }
  .av-gallery-grid { grid-template-columns: repeat(auto-fill, minmax(120px, 1fr)); }
}
</style>
