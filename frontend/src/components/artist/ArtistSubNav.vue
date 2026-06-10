<template>
  <nav class="asn-bar">
    <router-link
      v-for="tab in tabs"
      :key="tab.name"
      :to="tab.to"
      class="asn-tab"
      :class="{ active: currentRoute === tab.name }"
    >
      <span class="asn-icon" v-html="tab.icon"></span>
      <span class="asn-label">{{ tab.label }}</span>
      <span v-if="currentRoute === tab.name" class="asn-indicator"></span>
    </router-link>
  </nav>
</template>

<script setup>
import { computed, ref, onMounted } from 'vue'

const props = defineProps({
  artistName: { type: String, required: true },
  currentRoute: { type: String, required: true },
  artist: { type: Object, default: null },
})

const API_BASE = import.meta.env.VITE_API_BASE || '/api/v1'

const TAB_ICONS = {
  概览: '&#x25CB;',      /* ◯ */
  作品: '&#x25C7;',      /* ◇ */
  印章: '&#x25CE;',      /* ◎ */
  文献: '&#x25A1;',      /* □ */
  分析: '&#x2727;',      /* ✧ */
  行旅: '&#x27E1;',      /* ⟡ */
}

const DEFAULT_TABS = [
  { label: '概览', name: 'ArtistOverview', icon: TAB_ICONS['概览'] },
  { label: '作品', name: 'ArtistWorks', icon: TAB_ICONS['作品'] },
  { label: '印章', name: 'ArtistSeals', icon: TAB_ICONS['印章'] },
  { label: '文献', name: 'ArtistLiterature', icon: TAB_ICONS['文献'] },
  { label: '分析', name: 'ArtistAnalysis', icon: TAB_ICONS['分析'] },
]

const hasMapTab = ref(false)
const artistData = ref(null)

const tabs = computed(() => {
  const list = DEFAULT_TABS.map(t => ({
    ...t,
    to: { name: t.name, params: { name: props.artistName } },
  }))
  if (hasMapTab.value) {
    list.push({
      label: '行旅',
      name: 'ArtistMap',
      icon: TAB_ICONS['行旅'],
      to: { name: 'ArtistMap', params: { name: props.artistName } },
    })
  }
  return list
})

function parseJsonField(field) {
  try {
    const parsed = typeof field === 'string' ? JSON.parse(field) : field
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

function checkChronology(data) {
  if (!data) return
  const chron = parseJsonField(data.art_chronology)
  hasMapTab.value = chron.length >= 5
}

onMounted(async () => {
  // 优先使用传入的 artist，否则自己取
  if (props.artist) {
    checkChronology(props.artist)
  } else {
    try {
      const res = await fetch(`${API_BASE}/artists/by-name/${encodeURIComponent(props.artistName)}`)
      if (res.ok) {
        const result = await res.json()
        artistData.value = result.artist
        checkChronology(result.artist)
      }
    } catch (e) {
      // 静默失败，行旅 tab 不显示
    }
  }
})
</script>

<style scoped>
.asn-bar {
  display: flex;
  gap: 2px;
  padding: 12px 0;
  margin-bottom: 24px;
  border-bottom: 1px solid var(--border-cream, #f0eee6);
  overflow-x: auto;
  scrollbar-width: none;
}
.asn-bar::-webkit-scrollbar { display: none; }

.asn-tab {
  position: relative;
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 18px;
  font-size: 13px;
  color: var(--olive-gray, #5e5d59);
  text-decoration: none;
  border-radius: 9999px;
  transition: all 0.2s ease;
  white-space: nowrap;
  cursor: pointer;
  font-family: var(--font-sans, 'PingFang SC', sans-serif);
  font-weight: 450;
  letter-spacing: 0.02em;
}

.asn-tab:hover {
  background: var(--parchment, #f5f4ed);
  color: var(--near-black, #141413);
}

.asn-tab.active {
  background: rgba(201, 100, 66, 0.08);
  color: var(--cinnabar, #c96442);
  font-weight: 600;
}

.asn-icon {
  font-size: 14px;
  line-height: 1;
  opacity: 0.7;
  display: inline-flex;
  align-items: center;
}
.asn-tab.active .asn-icon {
  opacity: 1;
}

.asn-label {
  line-height: 1;
}

.asn-indicator {
  position: absolute;
  bottom: -1px;
  left: 50%;
  transform: translateX(-50%);
  width: 60%;
  height: 2px;
  background: var(--cinnabar, #c96442);
  border-radius: 2px 2px 0 0;
}

@media (max-width: 768px) {
  .asn-bar {
    gap: 0;
    padding: 10px 0;
  }
  .asn-tab {
    padding: 6px 12px;
    font-size: 12px;
  }
}
</style>
