import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { artistsApi } from '../api/artists'
import { pinyin } from 'pinyin-pro'

const CACHE_TTL = 5 * 60 * 1000

export const useArtistStore = defineStore('artist', () => {
  const list = ref([])
  const total = ref(0)
  const periods = ref([])
  const schools = ref([])
  const letterNames = ref([])
  const statsSummary = ref(null)
  const lastFetchTime = ref(0)
  const lastMetaTime = ref(0)
  const lastFetchKey = ref('')           // 缓存键：JSON params，避免同参数重复请求
  const lastFetchList = ref([])          // 缓存上一次的成功结果，filter 切换时先显示旧数据

  function isStale() {
    return Date.now() - lastFetchTime.value > CACHE_TTL
  }

  function isMetaStale() {
    return Date.now() - lastMetaTime.value > 30 * 60 * 1000
  }

  async function loadMeta() {
    if (!isMetaStale() && periods.value.length > 0 && schools.value.length > 0) return
    const [pRes, sRes, lRes, ssRes] = await Promise.allSettled([
      artistsApi.periods(),
      artistsApi.schools(),
      artistsApi.letterIndex(),
      artistsApi.statsSummary(),
    ])
    if (pRes.status === 'fulfilled' && pRes.value?.periods) periods.value = pRes.value.periods
    if (sRes.status === 'fulfilled' && sRes.value?.schools) schools.value = sRes.value.schools
    if (lRes.status === 'fulfilled' && lRes.value?.names) letterNames.value = lRes.value.names
    if (ssRes.status === 'fulfilled') statsSummary.value = ssRes.value
    lastMetaTime.value = Date.now()
  }

  async function fetchPage(page = 1, filters = {}) {
    const paramsKey = JSON.stringify({ page, sort: filters.sort || 'created_at', dynasty: filters.dynasty || '', school: filters.school || '', keyword: filters.keyword || '', names: filters.names || '' })

    // 首页 + 相同参数 + 缓存未过期 → 直接返回缓存
    if (page === 1 && !isStale() && lastFetchKey.value === paramsKey && lastFetchList.value.length > 0) {
      list.value = lastFetchList.value
      return { artists: list.value, total: total.value }
    }

    const params = {
      page,
      page_size: 40,
      sort: filters.sort || 'created_at',
    }
    if (filters.dynasty) params.dynasty = filters.dynasty
    if (filters.school) params.school = filters.school
    if (filters.keyword) params.keyword = filters.keyword
    if (filters.names) params.names = filters.names

    const data = await artistsApi.list(params)
    if (page === 1) {
      list.value = data.artists || []
    } else {
      const existingIds = new Set(list.value.map(a => a.id))
      for (const a of data.artists || []) {
        if (!existingIds.has(a.id)) list.value.push(a)
      }
    }
    total.value = data.total || 0
    lastFetchTime.value = Date.now()
    lastFetchKey.value = paramsKey
    lastFetchList.value = list.value
    return data
  }

  async function fetchAll(filters = {}) {
    const paramsKey = JSON.stringify({ sort: filters.sort || 'created_at', dynasty: filters.dynasty || '', school: filters.school || '', keyword: filters.keyword || '', names: filters.names || '' })

    // 相同参数 + 缓存未过期 → 直接返回缓存，不发起请求
    if (!isStale() && lastFetchKey.value === paramsKey && lastFetchList.value.length > 0) {
      list.value = lastFetchList.value
      return { artists: list.value, total: total.value }
    }

    const params = {
      page: 1,
      page_size: 2000,
      sort: filters.sort || 'created_at',
    }
    if (filters.dynasty) params.dynasty = filters.dynasty
    if (filters.school) params.school = filters.school
    if (filters.keyword) params.keyword = filters.keyword
    if (filters.names) params.names = filters.names

    const data = await artistsApi.list(params)
    list.value = data.artists || []
    total.value = data.total || 0
    lastFetchTime.value = Date.now()
    lastFetchKey.value = paramsKey
    lastFetchList.value = list.value
    return data
  }

  function clear() {
    list.value = []
    total.value = 0
    lastFetchTime.value = 0
    lastFetchKey.value = ''
    lastFetchList.value = []
  }

  const hasMore = computed(() => list.value.length < total.value)

  const letterGroups = computed(() => {
    const map = {}
    for (const name of letterNames.value) {
      if (!name) continue
      const py = pinyin(name, { toneType: 'none', type: 'array' })
      const first = py[0]?.charAt(0) || ''
      const letter = /[a-zA-Z]/.test(first) ? first.toUpperCase() : '#'
      if (!map[letter]) map[letter] = 0
      map[letter]++
    }
    const order = 'ABCDEFGHJKLMNOPQRSTWXYZ'.split('')
    const result = []
    for (const l of order) {
      if (map[l]) result.push({ letter: l, count: map[l] })
    }
    if (map['#']) result.push({ letter: '#', count: map['#'] })
    return result
  })

  return { list, total, periods, schools, letterNames, letterGroups, statsSummary, lastFetchTime,
           isStale, isMetaStale, loadMeta, fetchPage, fetchAll, clear, hasMore }
})
