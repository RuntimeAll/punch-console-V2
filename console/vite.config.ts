import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// 知识工厂 V2.1 原型 —— 前端先行，mock 数据，无后端依赖
// 🔴 端口/代理靶子可用环境变量顶掉，缺省仍是主位常驻那对（4300 页面 / 4310 读 API）。
//    为什么要这两个口子：改读 API 时得在 4311+ 起副本自测，**绝不许撞主位常驻的 4300/4310**。
//    起测试实例：CONSOLE_PORT=4312 KB_API_PORT=4311 pnpm exec vite --port 4312 --strictPort --host 127.0.0.1
const CONSOLE_PORT = Number(process.env.CONSOLE_PORT || 4300)
const KB_API_PORT = Number(process.env.KB_API_PORT || 4310)

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      // 约定：源码内一律用 '@/xxx' 绝对引用，禁止 '../../..' 深层相对路径
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    port: CONSOLE_PORT,
    strictPort: true,
    proxy: {
      // 🔴 真库页的取数口：kb 薄读 API（node console/server/kb-read-api.mjs），只读、只在本机。
      //    mock 页不经过这里，代理挂了也只影响 /kb/* 那几页。
      '/api/kb': {
        target: `http://127.0.0.1:${KB_API_PORT}`,
        changeOrigin: false,
      },
    },
  },
})
