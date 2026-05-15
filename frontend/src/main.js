import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import zhCn from 'element-plus/dist/locale/zh-cn.mjs'
import '@fontsource/noto-serif-sc/chinese-simplified-400.css'
import '@fontsource/noto-serif-sc/chinese-simplified-600.css'
import '@fontsource/noto-serif-sc/chinese-simplified-700.css'
import './styles/claude-design.css'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'

import App from './App.vue'
import router from './router'
import { siteConfig, loadSiteConfig } from './config'

async function init() {
  // 1. 先从 API 拉取站点配置（标题、副标题等可由管理员在线修改）
  await loadSiteConfig()

  // 2. 设置全局默认标题
  document.title = siteConfig.htmlTitle

  // 3. 挂载应用
  const app = createApp(App)

  // 注册所有图标
  for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
    app.component(key, component)
  }

  app.use(createPinia())
  app.use(ElementPlus, { locale: zhCn })
  app.use(router)
  app.mount('#app')
}

init()
