import { createApp } from 'vue'
import { createPinia } from 'pinia'
import DOMPurify from 'dompurify'
import { ElMessage, ElLoadingDirective } from 'element-plus'
// Element Plus 按需导入（vite unplugin），仅手动补充"命令式调用"组件的样式
import 'element-plus/es/components/message/style/css'
import 'element-plus/es/components/message-box/style/css'
import 'element-plus/es/components/loading/style/css'
import zhCn from 'element-plus/dist/locale/zh-cn.mjs'
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
  init.headers['Accept-Language'] = localStorage.getItem('lang') || 'zh'
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

// Element Plus 组件经 unplugin 按需注入；locale 由 App.vue 的 el-config-provider 提供
async function init() {
  await loadSiteConfig()
  document.title = siteConfig.htmlTitle

  const app = createApp(App)

  for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
    app.component(key, component)
  }

  app.directive('loading', ElLoadingDirective)
  // XSS 防护（v2.0）：所有 v-html 内容经 $sanitize 消毒（模板层统一包裹）
  app.config.globalProperties.$sanitize = (html) =>
    DOMPurify.sanitize(html ?? '', { ADD_ATTR: ['target'] })
  app.use(createPinia())
  app.use(i18n)
  app.use(router)
  app.mount('#app')
}

init()
