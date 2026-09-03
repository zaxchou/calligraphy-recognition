import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'
import AutoImport from 'unplugin-auto-import/vite'
import Components from 'unplugin-vue-components/vite'
import { ElementPlusResolver } from 'unplugin-vue-components/resolvers'

export default defineConfig({
  plugins: [
    vue(),
    // Element Plus 按需导入（v2.0 构建瘦身）：组件与样式按使用注入
    AutoImport({
      resolvers: [ElementPlusResolver()],
      dts: false,
    }),
    Components({
      resolvers: [ElementPlusResolver()],
      dts: false,
    }),
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
          // echarts 已按需注册（src/utils/echarts.js），随使用方分包，不再单独拆大包
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
