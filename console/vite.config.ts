import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// 知识工厂 V2.1 原型 —— 前端先行，mock 数据，无后端依赖
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      // 约定：源码内一律用 '@/xxx' 绝对引用，禁止 '../../..' 深层相对路径
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    port: 4300,
    strictPort: true,
  },
})
