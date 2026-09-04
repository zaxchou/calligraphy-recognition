// v2.0 i18n 减法：vue-i18n 移除，改为此零依赖 shim。
// 支持 zh/en 切换（语言按钮），词表为扁平键名（'card.emotion': '情绪解读'）。
import { ref } from 'vue'
import zh from './zh'
import en from './en'

const DICTS = { zh, en }

// URL 里的语言参数：search 里的 ?lang= 优先；hash 路由下书签常见 #/path?lang=en，
// 也兜底读取（仅在没有已存偏好时生效，避免切换后被旧链接的 hash 参数覆盖回来）。
function readUrlLang() {
  try {
    const sp = new URLSearchParams(location.search)
    const searchLang = sp.get('lang')
    if (searchLang === 'zh' || searchLang === 'en') return searchLang
    if (!localStorage.getItem('lang')) {
      const qi = location.hash.indexOf('?')
      if (qi >= 0) {
        const hashLang = new URLSearchParams(location.hash.slice(qi + 1)).get('lang')
        if (hashLang === 'zh' || hashLang === 'en') return hashLang
      }
    }
  } catch { /* non-browser env */ }
  return null
}
const urlLang = typeof location !== 'undefined' ? readUrlLang() : null
if (urlLang) localStorage.setItem('lang', urlLang)
export const locale = ref(localStorage.getItem('lang') || 'zh')

function format(template, params) {
  if (!params) return template
  return String(template).replace(/\{(\w+)\}/g, (_, k) => params[k] ?? `{${k}}`)
}

export function translate(key, params) {
  const dict = DICTS[locale.value] || zh
  // 优先扁平键直查（zh.js 的实际结构：398 个扁平键名），再回退嵌套下钻
  let node = dict[key]
  if (typeof node !== 'string') {
    node = key.split('.').reduce((acc, seg) => (acc == null ? acc : acc[seg]), dict)
  }
  // 当前语言缺失时回退中文
  if (typeof node !== 'string' && dict !== zh) node = zh[key]
  if (typeof node !== 'string') return key
  return format(node, params)
}

export function useI18n() {
  return { t: translate, locale }
}

export function switchLang(lang) {
  locale.value = lang || (locale.value === 'zh' ? 'en' : 'zh')
  localStorage.setItem('lang', locale.value)
  syncHtmlLang()
  // 整页刷新保证全站语言一致：原生 fetch 的 Accept-Language 头（模块初始化时读取）、
  // echarts 一次性构建的轴标签等不会因热切换残留旧语言。
  // 同时清掉 URL 里的 ?lang= 种子（search 与 hash 内），避免刷新后参数把切换结果覆盖回去。
  if (typeof location !== 'undefined' && typeof history !== 'undefined') {
    try {
      const url = new URL(location.href)
      url.searchParams.delete('lang')
      if (url.hash.includes('?')) {
        const [pathPart, queryPart] = url.hash.split('?')
        const q = new URLSearchParams(queryPart)
        q.delete('lang')
        url.hash = pathPart + (q.toString() ? '?' + q.toString() : '')
      }
      history.replaceState(null, '', url.pathname + url.search + url.hash)
    } catch { /* 忽略 URL 清理失败 */ }
    location.reload()
  }
}

function syncHtmlLang() {
  try {
    document.documentElement.setAttribute('lang', locale.value === 'en' ? 'en' : 'zh-CN')
  } catch { /* non-browser env */ }
}
syncHtmlLang()

export default {
  install(app) {
    app.config.globalProperties.$t = translate
  },
}
