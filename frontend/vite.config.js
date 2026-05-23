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
        target: 'https://124.223.17.29',
        changeOrigin: true,
        secure: false
      },
      '/static': {
        target: 'https://124.223.17.29',
        changeOrigin: true,
        secure: false
      },
      '/dzi': {
        target: 'https://124.223.17.29',
        changeOrigin: true,
        secure: false
      }
    },
    // 确保 .mjs 文件正确服务
    fs: {
      allow: ['.']
    }
  }
})
