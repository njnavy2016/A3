import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    host: true,
    port: 3000,
    proxy: {
      '/api': { target: 'http://backend:8000', changeOrigin: true },
      '/agent-api': { target: 'http://agent:8100', changeOrigin: true, rewrite: (p) => p.replace(/^\/agent-api/, '/api/v1') }
    }
  }
})
