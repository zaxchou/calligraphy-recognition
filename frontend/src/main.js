import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
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
