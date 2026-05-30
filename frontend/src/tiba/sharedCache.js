// 模块级共享缓存：题跋分析全量作品列表
// 同 session 内所有组件共享同一份数据，避免重复 API 请求
const _sharedAnalyticsCache = { data: null }

export function getSharedAnalyticsData() {
  return _sharedAnalyticsCache.data
}

export function setSharedAnalyticsData(data) {
  _sharedAnalyticsCache.data = data
}

export function clearSharedAnalyticsData() {
  _sharedAnalyticsCache.data = null
}
