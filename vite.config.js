import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  base: '/',
  server: {
    // Keep browser-relative API URLs on FastAPI during development. Without
    // this, Vite serves index.html for /satellite/* and JSON parsing fails.
    proxy: {
      '/satellite': 'http://127.0.0.1:8000',
      '/satellite-data': 'http://127.0.0.1:8000',
      '/aoi': 'http://127.0.0.1:8000',
      '/shoreline': 'http://127.0.0.1:8000',
      '/xgboost': 'http://127.0.0.1:8000',
      '/health': 'http://127.0.0.1:8000',
    },
  },
})
