<template>
  <div class="dimension-input-page">
    <!-- 页面头部 -->
    <div class="page-header">
      <div class="header-title-group">
        <h1 class="page-title">{{ selectedArtist === 'all' ? '全部作品' : selectedArtist + '作品' }}尺寸录入</h1>
        <p class="page-subtitle">{{ $t('dimensioninput.t1') }}</p>
        <div class="header-ornament">
          <span class="ornament-line"></span>
          <span class="ornament-dot">◇</span>
          <span class="ornament-line"></span>
        </div>
      </div>
      <div class="header-actions">
        <el-select v-model="selectedArtist" size="default" @change="onArtistChange" style="width: 150px;" class="claude-select">
          <el-option :label="$t('dimensioninput.a1')" value="all" />
          <el-option v-for="artist in artistList" :key="artist" :label="artist" :value="artist" />
        </el-select>
        <div class="progress-badge">
          <span class="progress-num">{{ filled }}</span>
          <span class="progress-sep">/</span>
          <span class="progress-total">{{ total }}</span>
          <span class="progress-label">{{ $t('dimensioninput.t2') }}</span>
        </div>
      </div>
    </div>

    <!-- 加载状态 -->
    <div v-if="loading" class="loading-state">
      <el-icon class="is-loading"><Loading /></el-icon>
      <span>{{ $t('albummanager.t3') }}</span>
    </div>

    <div v-else>
      <!-- 年份筛选 + 状态筛选 + 统计 -->
      <div class="filter-bar">
        <div class="year-filter">
          <button
            v-for="y in ['全部', ...years]"
            :key="y"
            :class="['year-btn', { active: selectedYear === y }]"
            @click="selectedYear = y"
          >{{ y === '全部' ? '全部' : typeof y === 'number' ? y + '年' : y }}</button>
        </div>
        <div class="status-filter">
          <button
            v-for="s in ['未录入', '已录入', '全部']"
            :key="s"
            :class="['status-btn', { active: selectedStatus === s }]"
            @click="selectedStatus = s"
          >{{ s }}</button>
        </div>
        <div class="filter-stats">
          <span class="stat-chip filled">已录 {{ filled }} 条</span>
          <span class="stat-chip empty">待录 {{ total - filled }} 条</span>
        </div>
      </div>

      <!-- 册页批量录入提示 -->
      <div class="album-tip" v-if="albumNames.length > 0">
        <span class="album-tip-icon">✦</span>
        {{ $t('dimensioninput.t3') }}<strong>{{ albumNames.length }}</strong> 部册页，
        可在册页卡片内批量录入整组尺寸
      </div>

      <!-- 按年份展示 -->
      <div v-for="year in displayYears" :key="year" class="year-section">
        <div class="year-section-header">
          <span class="year-label">{{ typeof year === 'number' ? year + '年' : year }}</span>
          <span class="year-period">{{ getPeriodLabel(year) }}</span>
          <span class="year-count">{{ getYearFilteredCount(year) }}条</span>
        </div>

        <!-- 册页卡片（album_name 非空的记录） -->
        <template v-for="albumName in getAlbumNamesForYear(year)" :key="'album-' + albumName">
          <div class="album-card">
            <div class="album-card-header" @click="toggleAlbum(albumName)">
              <span class="album-toggle-icon">{{ expandedAlbums.has(albumName) ? '▼' : '▶' }}</span>
              <span class="album-name">
                【{{ albumName }}】
                {{ getAlbumRecords(albumName).length }}开
              </span>
              <span class="album-status" :class="albumStatusClass(albumName)">
                {{ albumFilledCount(albumName) }}/{{ getAlbumRecords(albumName).length }} 已录
              </span>
              <span v-if="albumAllFilled(albumName)" class="album-badge-filled">✓</span>
            </div>

            <div v-if="expandedAlbums.has(albumName)" class="album-card-body">
              <!-- 册页整组批量输入 -->
              <div class="album-batch-input">
                <span class="batch-label">{{ $t('dimensioninput.t4') }}</span>
            <input
              class="dim-input"
              :class="{ filled: albumWidthFilled(albumName) }"
              v-model="albumHeights[albumName]"
              :placeholder="$t('dimensioninput.a2')"
              type="number"
              step="0.1"
              min="0"
              @keydown.enter.prevent="saveAlbumDimension(albumName)"
              @keyup.enter.prevent="saveAlbumDimension(albumName)"
              @blur="saveAlbumDimension(albumName)"
            />
            <span class="dim-sep">×</span>
            <input
              class="dim-input"
              :class="{ filled: albumHeightFilled(albumName) }"
              v-model="albumWidths[albumName]"
              :placeholder="$t('dimensioninput.a3')"
              type="number"
              step="0.1"
              min="0"
              @keydown.enter.prevent="saveAlbumDimension(albumName)"
              @keyup.enter.prevent="saveAlbumDimension(albumName)"
              @blur="saveAlbumDimension(albumName)"
            />
                <span class="dim-unit">cm</span>
                <span class="batch-hint">{{ $t('dimensioninput.t5') }}</span>
              </div>

              <!-- 册页内各开列表 -->
              <div class="album-items">
                <div
                  v-for="item in getAlbumRecords(albumName)"
                  :key="item.id"
                  class="record-row album-record"
                  :class="{ saved: item.artwork_width_cm && item.artwork_height_cm }"
                >
                  <img
                    v-if="item.thumbnail_url"
                    :src="item.thumbnail_url"
                    class="record-thumb"
                    @error="e => e.target.style.display='none'"
                  />
                  <div v-else class="record-thumb-placeholder">{{ $t('albummanager.t12') }}</div>
                  <div class="record-info">
                    <span class="record-title">{{ item.title || '无名' }}</span>
                    <span class="record-meta">
                      第{{ item.album_index }}开
                      <span v-if="item.char_count" class="char-count">{{ item.char_count }}字</span>
                    </span>
                  </div>
                  <div class="record-dims">
                    <span class="dim-display">
                      {{ item.artwork_height_cm ? item.artwork_height_cm + '×' + item.artwork_width_cm + 'cm' : '—' }}
                    </span>
                  </div>
                  <button
                    class="sync-to-album-btn"
                    :title="$t('dimensioninput.a4')"
                    @click="syncOneToAlbum(item)"
                  >{{ $t('dimensioninput.t6') }}</button>
                </div>
              </div>
            </div>
          </div>
        </template>

        <!-- 非册页记录列表 -->
        <div
          v-for="item in getStandaloneRecordsForYear(year)"
          :key="item.id"
          class="record-row"
          :class="{ saved: item.artwork_width_cm && item.artwork_height_cm }"
        >
          <img
            v-if="item.thumbnail_url"
            :src="item.thumbnail_url"
            class="record-thumb"
            @error="e => e.target.style.display='none'"
          />
          <div v-else class="record-thumb-placeholder">{{ $t('albummanager.t12') }}</div>
          <div class="record-info">
            <span class="record-title">{{ item.title || '无名' }}</span>
            <span class="record-meta">
              <span v-if="item.char_count" class="char-count">{{ item.char_count }}字</span>
            </span>
          </div>
          <div class="dim-inputs">
            <input
              class="dim-input"
              :class="{ filled: item.artwork_width_cm }"
              v-model.number="heightValues[item.id]"
              :placeholder="$t('dimensioninput.a5')"
              type="number"
              step="0.1"
              min="0"
              @keydown.enter="saveSingle(item.id)"
              @blur="saveSingle(item.id)"
            />
            <span class="dim-sep">×</span>
            <input
              class="dim-input"
              :class="{ filled: item.artwork_height_cm }"
              v-model.number="widthValues[item.id]"
              :placeholder="$t('dimensioninput.a6')"
              type="number"
              step="0.1"
              min="0"
              @keydown.enter="saveSingle(item.id)"
              @blur="saveSingle(item.id)"
            />
            <span class="dim-unit">cm</span>
          </div>
          <div class="record-status">
            <span v-if="item.artwork_width_cm && item.artwork_height_cm" class="status-filled">✓</span>
            <span v-else class="status-empty">—</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Loading } from '@element-plus/icons-vue'
import api from '../api'
import { translate as t } from '@/locales'

const props = defineProps({
  artist: { type: String, default: 'all' },
  libraryId: { type: Number, default: null }
})

const loading = ref(false)
const allItems = ref([])
const years = ref([])
const total = ref(0)
const filled = ref(0)

// 作者筛选（从 props 同步）
const artistList = ref([])
const selectedArtist = ref(props.artist)
function onArtistChange() {
  loadData()
}
async function fetchArtistList() {
  try {
    const data = await api.get('/content-analysis/artists')
    artistList.value = data.artists || []
    if (artistList.value.length > 0 && !artistList.value.includes(selectedArtist.value)) {
      selectedArtist.value = artistList.value[0]
    }
  } catch (e) {
    console.error('获取作者列表失败', e)
  }
}

// 监听父组件传入的 author 变化
watch(() => props.artist, (newArtist) => {
  if (newArtist && newArtist !== selectedArtist.value) {
    selectedArtist.value = newArtist
    loadData()
  }
})

// 筛选状态
const selectedYear = ref('全部')
const selectedStatus = ref('未录入') // 未录入 / 已录入 / 全部

// 编辑状态
const widthValues = ref({})
const heightValues = ref({})
const albumWidths = ref({})
const albumHeights = ref({})
const expandedAlbums = ref(new Set())
const savingIds = ref(new Set())

// 判断记录是否符合状态筛选
function matchesStatusFilter(item) {
  if (selectedStatus.value === '全部') return true
  const hasDimensions = item.artwork_width_cm && item.artwork_height_cm
  return selectedStatus.value === '已录入' ? hasDimensions : !hasDimensions
}

// 计算属性
const displayYears = computed(() => {
  if (selectedYear.value === '全部') {
    // 只显示有符合筛选条件记录的年份
    return years.value.filter(year => getYearRecords(year).length > 0)
  }
  return [selectedYear.value]
})

const albumNames = computed(() => {
  const names = new Set()
  allItems.value.forEach(item => {
    if (item.album_name) names.add(item.album_name)
  })
  return [...names]
})

const periodMap = computed(() => {
  const map = {}
  allItems.value.forEach(item => {
    if (item.year && item.period && !map[item.year]) {
      map[item.year] = item.period
    }
  })
  return map
})

// 数据获取
async function loadData() {
  loading.value = true
  try {
    const artistParam = selectedArtist.value === 'all' ? '' : selectedArtist.value
    const params = new URLSearchParams()
    if (artistParam) params.set('artist', artistParam)
    if (props.libraryId) params.set('library_id', String(props.libraryId))
    const queryStr = params.toString() ? `?${params.toString()}` : ''
    const data = await api.get(`/tiba/dimensions${queryStr}`)
    if (data.success) {
      allItems.value = data.data.items
      years.value = data.data.years
      total.value = data.data.total
      filled.value = data.data.filled

      // 初始化编辑值（swap后：widthValues存height数据，heightValues存width数据）
      allItems.value.forEach(item => {
        heightValues.value[item.id] = item.artwork_height_cm || ''
        widthValues.value[item.id] = item.artwork_width_cm || ''
        if (item.album_name) {
          if (!(item.album_name in albumWidths.value)) {
            albumHeights.value[item.album_name] = item.artwork_height_cm || ''
            albumWidths.value[item.album_name] = item.artwork_width_cm || ''
          }
        }
      })

      // 自动展开第一个有未录尺寸的册页
      const firstIncompleteAlbum = albumNames.value.find(name => !albumAllFilled(name))
      if (firstIncompleteAlbum) {
        expandedAlbums.value.add(firstIncompleteAlbum)
      }
    }
  } catch (e) {
    ElMessage.error('加载数据失败: ' + e.message)
  } finally {
    loading.value = false
  }
}

// 按年份和状态筛选记录
function getYearRecords(year) {
  if (year === '年代不详') {
    return allItems.value.filter(item => (item.year === null || item.year === undefined) && matchesStatusFilter(item))
  }
  return allItems.value.filter(item => item.year === year && matchesStatusFilter(item))
}

function getAlbumNamesForYear(year) {
  const yearRecords = getYearRecords(year)
  const names = new Set()
  yearRecords.forEach(item => {
    if (item.album_name) names.add(item.album_name)
  })
  return [...names].sort()
}

function getAlbumRecords(albumName) {
  return allItems.value
    .filter(item => item.album_name === albumName && matchesStatusFilter(item))
    .sort((a, b) => (a.album_index || 0) - (b.album_index || 0))
}

function getStandaloneRecordsForYear(year) {
  return getYearRecords(year).filter(item => !item.album_name)
}

// 获取筛选后年份记录数
function getYearFilteredCount(year) {
  return getYearRecords(year).length
}

// 册页状态
function albumFilledCount(albumName) {
  return getAlbumRecords(albumName).filter(
    item => item.artwork_width_cm && item.artwork_height_cm
  ).length
}

function albumAllFilled(albumName) {
  const records = getAlbumRecords(albumName)
  return records.length > 0 && records.every(
    item => item.artwork_width_cm && item.artwork_height_cm
  )
}

function albumWidthFilled(albumName) {
  const v = albumWidths.value[albumName]
  return v !== '' && v !== null && v !== undefined
}

function albumHeightFilled(albumName) {
  const v = albumHeights.value[albumName]
  return v !== '' && v !== null && v !== undefined
}

function albumStatusClass(albumName) {
  const count = albumFilledCount(albumName)
  const total = getAlbumRecords(albumName).length
  if (count === total) return 'status-all'
  if (count > 0) return 'status-partial'
  return 'status-none'
}

function getPeriodLabel(year) {
  const p = periodMap.value[year]
  if (p) return '· ' + p
  return ''
}

// 折叠/展开册页
function toggleAlbum(name) {
  if (expandedAlbums.value.has(name)) {
    expandedAlbums.value.delete(name)
  } else {
    expandedAlbums.value.add(name)
  }
}

// 保存单条尺寸
async function saveSingle(id) {
  const item = allItems.value.find(i => i.id === id)
  if (!item) return

  // 用户输入：第一个框是高，第二个框是宽
  // API字段：artwork_height_cm=高, artwork_width_cm=宽
  const height = heightValues.value[id] !== '' ? parseFloat(heightValues.value[id]) : null
  const width = widthValues.value[id] !== '' ? parseFloat(widthValues.value[id]) : null

  // 判断是否真正变了
  const widthChanged = width !== (item.artwork_width_cm ?? null)
  const heightChanged = height !== (item.artwork_height_cm ?? null)
  if (!widthChanged && !heightChanged) return

  try {
    const data = await api.put(`/tiba/dimensions/${id}`, {
      artwork_height_cm: height,
      artwork_width_cm: width,
    })
    if (data.success) {
      // 后端返回的已swap过（height↔width），本地变量名是反的所以直接用
      item.artwork_width_cm = data.data.artwork_width_cm
      item.artwork_height_cm = data.data.artwork_height_cm
      // 更新册页批量输入框（如果属于册页）
      if (item.album_name) {
        albumHeights.value[item.album_name] = height ?? ''
        albumWidths.value[item.album_name] = width ?? ''
      }
      // 更新计数
      const wasFilled = item.artwork_width_cm && item.artwork_height_cm
      const nowFilled = width && height
      if (!wasFilled && nowFilled) filled.value++
      // 更新本地值（精度对齐）
      heightValues.value[id] = height ?? ''
      widthValues.value[id] = width ?? ''
    }
  } catch (e) {
    ElMessage.error('保存失败: ' + e.message)
  }
}

// 保存册页整组尺寸
async function saveAlbumDimension(albumName) {
  const h = albumHeights.value[albumName]
  const w = albumWidths.value[albumName]
  console.log('[saveAlbum]', albumName, 'h=', h, 'w=', w)
  if (!h && !w) return
  if (!h || !w) { ElMessage.warning(t('dimensioninput.s1')); return }
  const height = parseFloat(h)
  const width = parseFloat(w)
  if (isNaN(height) || isNaN(width)) { ElMessage.warning(t('dimensioninput.s2')); return }

  try {
    console.log('[saveAlbum] sending...', { album_name: albumName, height, width })
    const data = await api.put('/tiba/dimensions/album/batch', {
      album_name: albumName,
      artwork_height_cm: height,
      artwork_width_cm: width,
    })
    if (data.success) {
      // 更新本地所有该册页记录
      const records = getAlbumRecords(albumName)
      let newFilled = 0
      records.forEach(item => {
        const wasFilled = !!(item.artwork_width_cm && item.artwork_height_cm)
        item.artwork_height_cm = height
        item.artwork_width_cm = width
        heightValues.value[item.id] = height
        widthValues.value[item.id] = width
        if (!wasFilled) newFilled++
      })
      filled.value += newFilled
      ElMessage.success(data.message)
    }
  } catch (e) {
    console.error('[saveAlbum] error:', e)
    ElMessage.error('批量保存失败: ' + e.message)
  }
}

// 将某一开的尺寸同步到整组册页
async function syncOneToAlbum(item) {
  if (!item.artwork_width_cm || !item.artwork_height_cm) {
    ElMessage.warning(t('dimensioninput.s3'))
    return
  }
  if (!item.album_name) return

  try {
    await ElMessageBox.confirm(
      `将「${item.title || '无名'}」的尺寸 ${item.artwork_height_cm}×${item.artwork_width_cm}cm 同步到整组「${item.album_name}」(${getAlbumRecords(item.album_name).length}开)？`,
      '同步确认',
      { confirmButtonText: '同步', cancelButtonText: '取消', type: 'info' }
    )
  } catch {
    return
  }

  const height = item.artwork_height_cm
  const width = item.artwork_width_cm

  try {
    const data = await api.put('/tiba/dimensions/album/batch', {
      album_name: item.album_name,
      artwork_height_cm: height,
      artwork_width_cm: width,
    })
    if (data.success) {
      const records = getAlbumRecords(item.album_name)
      let newFilled = 0
      records.forEach(r => {
        const wasFilled = !!(r.artwork_width_cm && r.artwork_height_cm)
        r.artwork_height_cm = height
        r.artwork_width_cm = width
        heightValues.value[r.id] = height
        widthValues.value[r.id] = width
        if (!wasFilled) newFilled++
      })
      filled.value += newFilled
      albumHeights.value[item.album_name] = height
      albumWidths.value[item.album_name] = width
      ElMessage.success(`已同步 ${records.length} 开尺寸`)
    }
  } catch (e) {
    ElMessage.error('同步失败: ' + e.message)
  }
}

onMounted(() => {
  fetchArtistList()
  loadData()
})
</script>

<style scoped>
.dimension-input-page {
  max-width: 1100px;
  margin: 0 auto;
  padding: 32px 24px;
  background: #faf9f5;
  min-height: 100vh;
}

/* 页面头部 */
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 28px;
  gap: 16px;
}

.header-title-group { flex: 1; }

.page-title {
  font-size: 28px;
  font-weight: 600;
  color: #141413;
  margin: 0 0 6px;
  font-family: "Noto Serif SC", "STKaiti", serif;
}

.page-subtitle {
  font-size: 13px;
  color: #8a8070;
  margin: 0 0 10px;
}

.header-ornament {
  display: flex;
  align-items: center;
  gap: 12px;
}

.ornament-line {
  flex: 1;
  max-width: 80px;
  height: 1px;
  background: linear-gradient(90deg, transparent, #b8a47e, transparent);
}

.ornament-dot { color: #b8a47e; font-size: 12px; }

/* 进度徽章 */
.progress-badge {
  display: flex;
  align-items: baseline;
  gap: 2px;
  background: #fff;
  border: 1px solid #e8e6dc;
  border-radius: 10px;
  padding: 8px 16px;
  font-size: 14px;
}

.progress-num {
  font-size: 22px;
  font-weight: 700;
  color: #c96442;
  font-family: "Noto Serif SC", serif;
}

.progress-sep { color: #d0cbc4; margin: 0 1px; }
.progress-total { font-size: 16px; color: #3d3d3a; }
.progress-label { font-size: 12px; color: #8a8070; margin-left: 4px; }

/* 加载状态 */
.loading-state {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 60px;
  color: #8a8070;
}

/* 筛选栏 */
.filter-bar {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}

.year-filter {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.year-btn {
  padding: 5px 12px;
  border-radius: 6px;
  border: 1px solid #e8e6dc;
  background: #fff;
  color: #5e5d59;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.15s;
}

.year-btn:hover { border-color: #c96442; color: #c96442; }
.year-btn.active {
  background: #c96442;
  border-color: #c96442;
  color: #fff;
  font-weight: 600;
}

.status-filter {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-left: 8px;
  padding-left: 8px;
  border-left: 1px solid #e8e6dc;
}

.status-btn {
  padding: 5px 12px;
  border-radius: 6px;
  border: 1px solid #e8e6dc;
  background: #fff;
  color: #5e5d59;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.15s;
}

.status-btn:hover { border-color: #b8a47e; color: #b8a47e; }
.status-btn.active {
  background: #f8f6f0;
  border-color: #b8a47e;
  color: #8a7a60;
  font-weight: 600;
}

.filter-stats { display: flex; gap: 8px; margin-left: auto; }

.stat-chip {
  font-size: 12px;
  padding: 3px 10px;
  border-radius: 10px;
}

.stat-chip.filled { background: #f0ede8; color: #7a6a5a; }
.stat-chip.empty { background: #fff3e8; color: #b85a30; }

/* 册页提示 */
.album-tip {
  background: linear-gradient(135deg, #fffdf8, #faf8f2);
  border: 1px solid #f0e8d8;
  border-left: 3px solid #b8a47e;
  border-radius: 8px;
  padding: 10px 16px;
  font-size: 13px;
  color: #7a6a5a;
  margin-bottom: 20px;
}

.album-tip-icon { color: #b8a47e; margin-right: 6px; }

/* 年份区块 */
.year-section { margin-bottom: 32px; }

.year-section-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
  padding-bottom: 6px;
  border-bottom: 1px solid #e8e6dc;
}

.year-label {
  font-size: 18px;
  font-weight: 700;
  color: #141413;
  font-family: "Noto Serif SC", serif;
}

.year-period { font-size: 13px; color: #8a8070; }
.year-count { font-size: 12px; color: #b0aeaa; margin-left: auto; }

/* 记录行 */
.record-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  border-radius: 8px;
  margin-bottom: 6px;
  background: #fff;
  border: 1px solid #e8e6dc;
  transition: border-color 0.15s;
}

.record-row:hover { border-color: #d0cbc4; }

.record-row.saved { border-color: #c8ddc0; background: #f9fbf7; }

/* 缩略图 */
.record-thumb {
  width: 50px;
  height: 50px;
  object-fit: cover;
  border-radius: 6px;
  border: 1px solid #e8e6dc;
  flex-shrink: 0;
}

.record-thumb-placeholder {
  width: 50px;
  height: 50px;
  border-radius: 6px;
  background: #f0ede8;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  color: #b0aeaa;
  flex-shrink: 0;
}

/* 记录信息 */
.record-info {
  display: flex;
  flex-direction: column;
  gap: 3px;
  min-width: 120px;
  flex: 1;
}

.record-title {
  font-size: 14px;
  color: #1d1c1a;
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 180px;
}

.record-meta { font-size: 12px; color: #8a8070; }
.char-count { margin-left: 6px; }

/* 尺寸输入 */
.dim-inputs {
  display: flex;
  align-items: center;
  gap: 4px;
}

.dim-input {
  width: 72px;
  padding: 6px 8px;
  border: 1px solid #d0cbc4;
  border-radius: 6px;
  font-size: 13px;
  text-align: center;
  background: #faf9f5;
  color: #3d3d3a;
  transition: border-color 0.15s;
  font-family: 'JetBrains Mono', monospace;
}

.dim-input:focus {
  outline: none;
  border-color: #c96442;
  background: #fff;
}

.dim-input.filled {
  background: #f0f7ee;
  border-color: #a0c090;
  color: #4a6a3a;
  font-weight: 600;
}

.dim-input::placeholder { color: #c0bbb4; font-weight: 400; }

.dim-sep { color: #b0aeaa; font-size: 13px; }
.dim-unit { font-size: 12px; color: #8a8070; }

/* 尺寸显示 */
.record-dims {
  font-size: 13px;
  color: #5e5d59;
  font-family: 'JetBrains Mono', monospace;
  min-width: 100px;
  text-align: center;
}

.dim-display { color: #4a6a3a; font-weight: 600; }

/* 状态图标 */
.record-status { width: 24px; text-align: center; }
.status-filled { color: #5a9a4a; font-size: 16px; font-weight: bold; }
.status-empty { color: #d0cbc4; font-size: 16px; }

/* 册页卡片 */
.album-card {
  background: #fff;
  border: 1px solid #e0d8cc;
  border-radius: 10px;
  margin-bottom: 10px;
  overflow: hidden;
}

.album-card-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  background: #faf8f2;
  cursor: pointer;
  user-select: none;
  border-bottom: 1px solid transparent;
  transition: background 0.15s;
}

.album-card-header:hover { background: #f5f3ec; }

.album-toggle-icon {
  font-size: 10px;
  color: #8a8070;
  width: 14px;
}

.album-name {
  font-size: 14px;
  font-weight: 600;
  color: #3d3d3a;
  font-family: "Noto Serif SC", serif;
}

.album-status {
  font-size: 12px;
  margin-left: auto;
  padding: 2px 8px;
  border-radius: 10px;
}

.status-all { background: #e8f4e0; color: #5a9a4a; }
.status-partial { background: #fef3e0; color: #b87a30; }
.status-none { background: #f0ede8; color: #8a8070; }

.album-badge-filled {
  color: #5a9a4a;
  font-size: 14px;
  font-weight: bold;
}

.album-card-body { padding: 12px 16px; }

.album-batch-input {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 10px 12px;
  background: #faf8f2;
  border: 1px solid #e0d8cc;
  border-radius: 8px;
  margin-bottom: 10px;
}

.batch-label { font-size: 13px; color: #5e5d59; font-weight: 500; }
.batch-hint { font-size: 11px; color: #b0aeaa; margin-left: 6px; }

.album-items { display: flex; flex-direction: column; gap: 4px; }

.album-record { background: #fdfcfa; }

.sync-to-album-btn {
  flex-shrink: 0;
  padding: 3px 10px;
  border-radius: 6px;
  border: 1px solid #d0cbc4;
  background: #faf8f2;
  color: #7a6a5a;
  font-size: 11px;
  cursor: pointer;
  transition: all 0.15s;
}

.sync-to-album-btn:hover {
  border-color: #c96442;
  color: #c96442;
  background: #fff8f4;
}
</style>
