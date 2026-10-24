import { defineConfig } from 'vitest/config'

// 本机 hosts 未映射 localhost，显式使用 127.0.0.1 避免 vitest 启动时 DNS 解析失败
export default defineConfig({
  server: {
    host: '127.0.0.1',
  },
  test: {
    environment: 'node',
  },
})
