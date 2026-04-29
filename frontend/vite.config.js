import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'

export default defineConfig({
  plugins: [
    vue(),
  ],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src')
    }
  },
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8001',
        changeOrigin: true
      },
      '/static': {
        target: 'http://127.0.0.1:8001',
        changeOrigin: true
      }
    },
    // 确保 .mjs 文件正确服务
    fs: {
      allow: ['.']
    }
  }
})
