// v2.0 i18n 减法：vue-i18n 移除，改为此零依赖 shim。
// 支持 zh/en 切换（语言按钮），词表为扁平键名（'card.emotion': '情绪解读'）。
import { ref } from 'vue'
import zh from './zh'
import en from './en'

const DICTS = { zh, en }
// URL 参数优先（?lang=en 可直接分享英文版链接），其次 localStorage
try {
  const urlLang = new URLSearchParams(location.search).get('lang')
  if (urlLang === 'zh' || urlLang === 'en') localStorage.setItem('lang', urlLang)
} catch { /* non-browser env */ }
const locale = ref(localStorage.getItem('lang') || 'zh')

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
}

export default {
  install(app) {
    app.config.globalProperties.$t = translate
  },
}
