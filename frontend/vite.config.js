import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'

function http2Preload() {
  return {
    name: 'http2-preload',
    transformIndexHtml(html, { bundle }) {
      if (!bundle) return
      const entryChunk = Object.values(bundle).find(c => c.isEntry)
      if (!entryChunk) return
      const links = []
      if (entryChunk.fileName) {
        links.push({ tag: 'link', attrs: { rel: 'modulepreload', href: '/' + entryChunk.fileName }, injectTo: 'head' })
      }
      const entryName = entryChunk.name
      for (const [, chunk] of Object.entries(bundle)) {
        if (chunk.type === 'asset' && chunk.fileName?.endsWith('.css') && chunk.name?.replace(/\.css$/, '') === entryName) {
          links.push({ tag: 'link', attrs: { rel: 'preload', href: '/' + chunk.fileName, as: 'style' }, injectTo: 'head' })
        }
      }
      return links
    }
  }
}

export default defineConfig({
  plugins: [
    vue(),
    http2Preload(),
  ],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src')
    }
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          'echarts': ['echarts'],
          'element-plus': ['element-plus', '@element-plus/icons-vue'],
        }
      }
    },
    chunkSizeWarningLimit: 600,
  },
  server: {
    host: '0.0.0.0',
    port: 8080,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8001',
        changeOrigin: true
      },
      '/static': {
        target: 'http://127.0.0.1:8001',
        changeOrigin: true
      },
      '/dzi': {
        target: 'http://127.0.0.1:8001',
        changeOrigin: true
      }
    },
    fs: {
      allow: ['.']
    }
  }
})
