/**
 * OpenSeadragon 按需加载器
 *
 * 首次调用时动态创建 <script> 加载 /openseadragon/openseadragon.js，
 * 后续调用直接返回缓存的 Promise（脚本只加载一次）。
 * 15 秒超时防止永久挂起。
 */

let _loadPromise = null

export function ensureOpenSeadragon() {
  if (_loadPromise) return _loadPromise

  _loadPromise = new Promise((resolve) => {
    if (window.OpenSeadragon) { resolve(window.OpenSeadragon); return }

    const script = document.createElement('script')
    script.src = '/openseadragon/openseadragon.js'
    const timer = setTimeout(() => { _loadPromise = null; resolve(window.OpenSeadragon || null) }, 15000)
    script.onload = () => { clearTimeout(timer); resolve(window.OpenSeadragon || null) }
    script.onerror = () => { clearTimeout(timer); _loadPromise = null; resolve(null) }
    document.head.appendChild(script)
  })

  return _loadPromise
}
