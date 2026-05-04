import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import fs from 'fs'
import path from 'path'

const versionFile = path.resolve(__dirname, '../VERSION')
const appVersion = process.env.APP_VERSION
  || (fs.existsSync(versionFile) ? fs.readFileSync(versionFile, 'utf-8').trim() : 'dev')

export default defineConfig({
  define: {
    __APP_VERSION__: JSON.stringify(appVersion),
  },
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        ws: true,
      },
    },
  },
})
