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
    port: 8080,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:3000',
        changeOrigin: true
      },
      '/static': {
        target: 'http://127.0.0.1:3000',
        changeOrigin: true
      },
      '/dzi': {
        target: 'http://127.0.0.1:3000',
        changeOrigin: true
      }
    },
    // 确保 .mjs 文件正确服务
    fs: {
      allow: ['.']
    }
  }
})
