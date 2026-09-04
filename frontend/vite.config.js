import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    host: '0.0.0.0',
    proxy: {
      '/screen': 'http://127.0.0.1:8000',
      '/history': 'http://127.0.0.1:8000',
      '/audit': 'http://127.0.0.1:8000',
      '/health': 'http://127.0.0.1:8000'
    }
  }
})
