import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue()],
  server: {
    proxy: {
      '/admin-api': { target: 'http://localhost:8002', changeOrigin: true },
      '/qa-api': { target: 'http://localhost:8003', changeOrigin: true },
    },
  },
})
