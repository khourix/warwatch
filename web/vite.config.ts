import { defineConfig, type Plugin } from 'vite'
import react from '@vitejs/plugin-react'
import tailwind from '@tailwindcss/vite'
import fs from 'node:fs'
import path from 'node:path'

// The app reads data/v1/ at the site root (site/data/v1 in production, written by run.py every 30 minutes).
// In dev, WW_SITE points at a built site folder (python3 warwatch/run.py --demo buildup --out <dir>/index.html) and is served at /.
function siteData(): Plugin {
  const root = process.env.WW_SITE ? path.resolve(process.env.WW_SITE) : ''
  return {
    name: 'ww-site-data',
    configureServer(server) {
      if (!root) return
      server.middlewares.use((req, res, next) => {
        const url = (req.url || '').split('?')[0]
        if (!/^\/(data|img)\//.test(url) && !/^\/[\w.-]+\.(svg|png)$/.test(url)) return next()
        const file = path.join(root, decodeURIComponent(url))
        if (!file.startsWith(root) || !fs.existsSync(file)) return next()
        res.setHeader('Content-Type', file.endsWith('.json') ? 'application/json' : file.endsWith('.svg') ? 'image/svg+xml' : file.endsWith('.png') ? 'image/png' : 'image/jpeg')
        fs.createReadStream(file).pipe(res)
      })
    },
  }
}

export default defineConfig({
  base: './',
  plugins: [react(), tailwind(), siteData()],
  build: { outDir: 'dist', assetsDir: 'assets', chunkSizeWarningLimit: 1200, sourcemap: !!process.env.WW_SOURCEMAP },
})
