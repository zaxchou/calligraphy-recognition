// v2.0 i18n 减法：vue-i18n 移除，改为此零依赖 shim。
// 保留 zh 词表与 $t / useI18n 接口（含 {param} 插值），站点当前仅面向中文用户。
import { ref } from 'vue'
import zh from './zh'

const locale = ref('zh')

function format(template, params) {
  if (!params) return template
  return String(template).replace(/\{(\w+)\}/g, (_, k) => params[k] ?? `{${k}}`)
}

export function translate(key, params) {
  // 优先扁平键直查（zh.js 的实际结构：398 个扁平键名），再回退嵌套下钻
  let node = zh[key]
  if (typeof node !== 'string') {
    node = key.split('.').reduce((acc, seg) => (acc == null ? acc : acc[seg]), zh)
  }
  if (typeof node !== 'string') return key
  return format(node, params)
}

export function useI18n() {
  return { t: translate, locale }
}

// 兼容旧调用（语言切换按钮已移除，保留 no-op 防御）
export function switchLang() {}

export default {
  install(app) {
    app.config.globalProperties.$t = translate
  },
}
