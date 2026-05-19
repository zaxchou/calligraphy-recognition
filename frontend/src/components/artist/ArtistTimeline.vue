<template>
  <div class="dt-timeline">
    <div v-for="group in dynastyGroups" :key="group.key" class="dt-section">
      <div class="dt-era-header" @click="toggleExpanded(group.key)">
        <div class="dt-era-left">
          <span class="dt-era-name">{{ group.label }}</span>
          <span class="dt-era-range">{{ group.range }}</span>
        </div>
        <div class="dt-era-counts">
          <span class="dt-era-count">{{ group.artworkCount }} 件</span>
          <span class="dt-era-divider">/</span>
          <span class="dt-era-count">{{ group.count }} 位</span>
        </div>
        <el-icon class="dt-expand-icon" :class="{ expanded: isExpanded(group.key, group.count) }">
          <ArrowDown />
        </el-icon>
      </div>

      <div v-show="isExpanded(group.key, group.count)" class="dt-era-body">
        <div v-for="py in group.pyGroups" :key="py.letter" class="dt-py-group">
          <div class="dt-py-letter">{{ py.letter }}</div>
          <div class="dt-py-names">
            <button
              v-for="artist in py.artists"
              :key="artist.id"
              class="dt-artist-btn"
              @click="$emit('select', artist.name)"
            >
              <span class="dt-artist-name">{{ artist.name }}</span>
              <span v-if="artist.alias" class="dt-artist-alias">({{ artist.alias }})</span>
              <span class="dt-artist-count" v-if="artist.artwork_count">{{ artist.artwork_count }}件</span>
            </button>
          </div>
        </div>
        <div v-if="group.pyGroups.length === 0" class="dt-empty">暂无艺术家</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { ArrowDown } from '@element-plus/icons-vue'
import { pinyin } from 'pinyin-pro'

const props = defineProps({
  artists: { type: Array, default: () => [] },
})

defineEmits(['select'])

const DYNASTY_ORDER = [
  { key: '先秦', label: '先秦', range: '前221年以前', norm: /先.?秦/ },
  { key: '秦汉', label: '秦汉', range: '前221-220', norm: /秦|汉|两汉|西汉|东汉/ },
  { key: '魏晋南北朝', label: '魏晋南北朝', range: '220-589', norm: /三.?国|晋|北魏|东晋|西晋|南朝|北朝|陈|隋/ },
  { key: '隋唐', label: '隋唐', range: '581-907', norm: /唐/ },
  { key: '五代十国', label: '五代十国', range: '907-960', norm: /五代|南唐|后梁|前蜀|后蜀/ },
  { key: '辽金', label: '辽金', range: '916-1234', norm: /辽|金/ },
  { key: '宋', label: '宋', range: '960-1279', norm: /宋|北宋|南宋/ },
  { key: '元', label: '元', range: '1271-1368', norm: /元/ },
  { key: '明', label: '明', range: '1368-1644', norm: /明/ },
  { key: '清', label: '清', range: '1644-1911', norm: /清/ },
  { key: '近现代', label: '近现代', range: '1911-1949', norm: /民.?国|现代|近.?现|晚.?清/ },
  { key: '当代', label: '当代', range: '1949至今', norm: /当代|现今/ },
]

function normalizeDynasty(raw) {
  if (!raw) return '年代不详'
  for (const d of DYNASTY_ORDER) {
    if (d.norm.test(raw)) return d.key
  }
  return '年代不详'
}

function getPinyinFirst(name) {
  if (!name) return '#'
  const py = pinyin(name, { toneType: 'none', type: 'array' })
  const first = py[0]?.charAt(0) || ''
  return /[a-zA-Z]/.test(first) ? first.toUpperCase() : '#'
}

const expandedMap = ref({})

function autoExpand() {
  const map = {}
  for (const artist of props.artists) {
    const key = normalizeDynasty(artist.dynasty || '')
    map[key] = true
  }
  // If filtering reduces to just a few dynasties, expand those; otherwise keep collapsed
  const keys = Object.keys(map)
  if (props.artists.length > 0) {
    if (keys.length <= 6) {
      expandedMap.value = map
    } else {
      expandedMap.value = {}
    }
  } else {
    expandedMap.value = {}
  }
}

watch(() => props.artists, () => {
  autoExpand()
}, { deep: true })

function toggleExpanded(key) {
  expandedMap.value = { ...expandedMap.value, [key]: !expandedMap.value[key] }
}

function isExpanded(key, count) {
  if (expandedMap.value[key] !== undefined) return expandedMap.value[key]
  return false
}

const dynastyGroups = computed(() => {
  const map = {}
  for (const d of DYNASTY_ORDER) {
    map[d.key] = { ...d, artists: [], artworkCount: 0, count: 0 }
  }
  map['年代不详'] = { key: '年代不详', label: '年代不详', range: '', artists: [], artworkCount: 0, count: 0 }

  for (const artist of props.artists) {
    const raw = artist.dynasty || ''
    const key = normalizeDynasty(raw)
    const target = map[key] || map['年代不详']
    target.artists.push(artist)
    target.count++
    target.artworkCount += artist.artwork_count || 0
  }

  const result = []
  for (const d of DYNASTY_ORDER) {
    const group = map[d.key]
    if (group.artists.length === 0) continue
    const pyMap = {}
    for (const a of group.artists) {
      const letter = getPinyinFirst(a.name)
      if (!pyMap[letter]) pyMap[letter] = []
      pyMap[letter].push(a)
    }
    const pyOrder = 'ABCDEFGHJKLMNOPQRSTWXYZ'.split('')
    group.pyGroups = []
    for (const l of pyOrder) {
      if (pyMap[l]) {
        pyMap[l].sort((a, b) => a.name.localeCompare(b.name, 'zh'))
        group.pyGroups.push({ letter: l, artists: pyMap[l] })
      }
    }
    if (pyMap['#']) {
      pyMap['#'].sort((a, b) => a.name.localeCompare(b.name, 'zh'))
      group.pyGroups.push({ letter: '#', artists: pyMap['#'] })
    }
    result.push(group)
  }

  const unknown = map['年代不详']
  if (unknown.artists.length > 0) {
    unknown.pyGroups = []
    unknown.artists.sort((a, b) => a.name.localeCompare(b.name, 'zh'))
    unknown.pyGroups.push({ letter: '?', artists: unknown.artists })
    result.push(unknown)
  }

  return result
})
</script>

<style scoped>
.dt-timeline {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.dt-section {
  border-bottom: 1px solid #edeae1;
}

.dt-era-header {
  display: flex;
  align-items: center;
  padding: 16px 0;
  cursor: pointer;
  gap: 12px;
  user-select: none;
}

.dt-era-left {
  display: flex;
  align-items: baseline;
  gap: 8px;
  min-width: 200px;
}

.dt-era-name {
  font-family: 'Noto Serif SC', 'KaiTi', serif;
  font-size: 1.25rem;
  font-weight: 700;
  color: #3a3222;
}

.dt-era-range {
  font-size: 0.75rem;
  color: #a09b8e;
}

.dt-era-counts {
  display: flex;
  align-items: baseline;
  gap: 4px;
  margin-left: auto;
  margin-right: 8px;
  font-size: 0.85rem;
}

.dt-era-count {
  color: #c45a3c;
  font-weight: 600;
}

.dt-era-divider {
  color: #ccc;
}

.dt-expand-icon {
  font-size: 14px;
  color: #aaa;
  transition: transform 0.25s;
}
.dt-expand-icon.expanded {
  transform: rotate(180deg);
}

.dt-era-body {
  padding: 0 0 16px 8px;
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
}

.dt-py-group {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  gap: 6px;
}

.dt-py-letter {
  width: 28px;
  height: 28px;
  border-radius: 6px;
  background: #c45a3c;
  color: #fff;
  font-size: 0.8rem;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  margin-right: 4px;
}

.dt-py-names {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px;
}

.dt-artist-btn {
  background: #faf8f4;
  border: 1px solid #e8e4da;
  border-radius: 6px;
  padding: 4px 10px;
  cursor: pointer;
  font-size: 0.82rem;
  color: #5a4a38;
  display: inline-flex;
  align-items: baseline;
  gap: 4px;
  white-space: nowrap;
  transition: all 0.15s;
}
.dt-artist-btn:hover {
  border-color: #c45a3c;
  background: #fff;
  color: #c45a3c;
}

.dt-artist-name {
  font-weight: 500;
}

.dt-artist-alias {
  font-size: 0.72rem;
  color: #a09b8e;
}

.dt-artist-count {
  font-size: 0.65rem;
  color: #b0a090;
  margin-left: 2px;
}

.dt-empty {
  color: #ccc;
  font-size: 0.85rem;
  padding: 8px 0;
}
</style>
