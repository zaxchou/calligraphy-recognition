import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus, { ElMessage } from 'element-plus'
import 'element-plus/dist/index.css'
import zhCn from 'element-plus/dist/locale/zh-cn.mjs'
import enLocale from 'element-plus/dist/locale/en.mjs'
import '@fontsource/noto-serif-sc/chinese-simplified-400.css'
import '@fontsource/noto-serif-sc/chinese-simplified-600.css'
import '@fontsource/noto-serif-sc/chinese-simplified-700.css'
import './styles/claude-design.css'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'

import App from './App.vue'
import router from './router'
import { siteConfig, loadSiteConfig } from './config'
import i18n from './locales/index'

// ── 全局增强 fetch：自动携带 JWT Authorization header ──
const _origFetch = window.fetch
window.fetch = function (input, init) {
  init = init || {}
  init.headers = init.headers || {}
  const token = localStorage.getItem('auth_token')
  if (token) {
    if (init.headers instanceof Headers) {
      if (!init.headers.has('Authorization')) {
        init.headers.set('Authorization', `Bearer ${token}`)
      }
    } else if (typeof init.headers === 'object') {
      init.headers['Authorization'] = `Bearer ${token}`
    }
  }
  return _origFetch.call(window, input, init)
}

// ── ElMessage 位置 patch：强制右上角，自动消失 ──
const messageDefaults = { duration: 2000, offset: 16 }
function wrapMsg(fn) {
  return (opts) => fn.call(ElMessage, { ...messageDefaults, ...(typeof opts === 'string' ? { message: opts } : opts) })
}
ElMessage.success = wrapMsg(ElMessage.success.bind(ElMessage))
ElMessage.error   = wrapMsg(ElMessage.error.bind(ElMessage))
ElMessage.warning = wrapMsg(ElMessage.warning.bind(ElMessage))
ElMessage.info    = wrapMsg(ElMessage.info.bind(ElMessage))

// MutationObserver：任何 .el-message 出现时立即挪到右上角
const _msgObserver = new MutationObserver((mutations) => {
  for (const m of mutations) {
    for (const node of m.addedNodes) {
      if (node.nodeType !== 1) continue
      const targets = node.classList?.contains('el-message') ? [node] : node.querySelectorAll?.('.el-message') || []
      for (const el of targets) {
        el.style.top = '60px'
        el.style.right = '16px'
        el.style.left = 'auto'
        el.style.transform = 'none'
        el.classList.remove('is-center')
        el.classList.add('is-right')
      }
    }
  }
})
_msgObserver.observe(document.body, { childList: true, subtree: true })

// Element Plus locale 跟随 i18n 切换
const epLocales = { zh: zhCn, en: enLocale }
function getEpLocale() { return epLocales[i18n.global.locale.value] || zhCn }

async function init() {
  await loadSiteConfig()
  document.title = siteConfig.htmlTitle

  const app = createApp(App)

  for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
    app.component(key, component)
  }

  app.use(createPinia())
  app.use(ElementPlus, { locale: getEpLocale() })
  app.use(i18n)
  app.use(router)
  app.mount('#app')
}

init()
