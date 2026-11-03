// vite.config.ts — Vite 7 + Vue 3；dev 期间 /api/v1 由 mock 中间件直接应答（真实 HTTP）。
import { fileURLToPath, URL } from 'node:url';
import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';
import { apiMiddleware } from './mock/api.mjs';

export default defineConfig({
  plugins: [
    vue(),
    {
      name: 'qwatch-mock-api',
      configureServer(server) {
        server.middlewares.use(apiMiddleware());
      },
    },
  ],
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  server: { host: '127.0.0.1', port: 5173, strictPort: true },
  build: {
    target: 'es2020',
    chunkSizeWarningLimit: 1400,
    rollupOptions: {
      output: {
        manualChunks: {
          vendor: ['vue', 'vue-router', 'pinia', 'dayjs'],
          naive: ['naive-ui'],
          charts: ['echarts'],
        },
      },
    },
  },
});
