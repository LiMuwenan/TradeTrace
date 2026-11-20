import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// 开发时把 /api 转发到后端，避免跨域配置漂移。生产部署计划由 FastAPI 托管构建产物。
export default defineConfig({
  plugins: [vue()],
  server: {
    // 显式绑定 IPv4：默认的 localhost 在 Windows 上可能只监听 ::1，导致代理与 CORS 白名单对不上
    host: '127.0.0.1',
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
})
