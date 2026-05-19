import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { artistsApi } from '../api/artists'

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
    return data
  }

  async function fetchAll(filters = {}) {
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
    return data
  }

  function clear() {
    list.value = []
    total.value = 0
    lastFetchTime.value = 0
  }

  const hasMore = computed(() => list.value.length < total.value)

  return { list, total, periods, schools, letterNames, statsSummary, lastFetchTime,
           isStale, isMetaStale, loadMeta, fetchPage, fetchAll, clear, hasMore }
})
