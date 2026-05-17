import api from './index'

export const artistsApi = {
  list(params) {
    return api.get('/artists', { params })
  },
  getByName(name) {
    return api.get(`/artists/by-name/${encodeURIComponent(name)}`)
  },
  getById(id) {
    return api.get(`/artists/${id}`)
  },
  periods() {
    return api.get('/artists/periods')
  },
  schools() {
    return api.get('/artists/schools')
  },
  letterIndex() {
    return api.get('/artists/letter-index')
  },
  statsSummary() {
    return api.get('/artists/stats-summary')
  },
  getStats(artistId) {
    return api.get(`/artists/${artistId}/stats`)
  },
  getWorks(artistId, params) {
    return api.get(`/artists/${artistId}/works`, { params })
  },
}
