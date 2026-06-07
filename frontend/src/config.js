/**
 * 墨林百科 — 全局站点配置
 *
 * 优先级：后端 API > localStorage > 硬编码默认值
 * 管理员在后台编辑后，全站即时生效，无需重新部署。
 */
import { reactive } from 'vue'

const API_BASE = import.meta.env.VITE_API_BASE || '/api/v1'

/** 硬编码默认值（后端不可用时回退） */
const DEFAULTS = {
  title: '墨林百科',
  subtitle: '中国画与书法智能研究库',
  full_title: '墨林百科 - 中国画与书法智能研究库',
  domain: 'molin.wiki',
  footer: '墨林百科 © 2026',
  author: '周豪 Zax',
  readonly: 'false',
}

// 从 DEFAULTS 派生前端需要的驼峰别名
function derive(config) {
  return {
    ...config,
    fullTitle: config.full_title || config.fullTitle || '',
    htmlTitle: config.full_title || config.htmlTitle || '',
  }
}

/** 响应式站点配置 — 组件模板可直接绑定 */
export const siteConfig = reactive(derive({ ...DEFAULTS }))

/** 是否已从 API 加载 */
let _loaded = false

/**
 * 从后端 API 拉取站点配置并合并到 siteConfig。
 * 在 main.js 中 app.mount() 之前调用一次。
 */
export async function loadSiteConfig() {
  if (_loaded) return
  _loaded = true

  try {
    const resp = await fetch(`${API_BASE}/site-settings`)
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
    const data = await resp.json()
    const settings = data.settings || {}
    // 合并：API 有值的覆盖默认值
    const merged = { ...DEFAULTS, ...settings }
    Object.assign(siteConfig, derive(merged))
  } catch (e) {
    // API 不可用 — 使用默认值（已设置）
    console.warn('站点配置 API 不可用，使用默认值:', e.message)
    // 尝试从 localStorage 读取缓存
    try {
      const cached = localStorage.getItem('molin_site_config')
      if (cached) {
        const parsed = JSON.parse(cached)
        Object.assign(siteConfig, derive({ ...DEFAULTS, ...parsed }))
      }
    } catch { /* ignore */ }
  }
}

export default siteConfig
