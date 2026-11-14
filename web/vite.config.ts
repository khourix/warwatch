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

// The fonts the first screen sets its text in (Switzer for the interface, Sentient upright and italic for the dispatch) are asked for
// from index.html with the page, not when the CSS is read, so the dispatch does not reflow when they arrive on a slow connection.
// A font that fetch-fonts.mjs could not download is not in the build and is simply not preloaded. The links go at the end of the
// head, after the <base> pages.py adds, so they resolve against the site root on every address.
const PRELOAD = /^assets\/(switzer-normal|sentient-normal|sentient-italic)-[\w-]+\.woff2$/
function preloadFonts(): Plugin {
  return {
    name: 'ww-preload-fonts',
    transformIndexHtml: {
      order: 'post',
      handler(_html, ctx) {
        if (!ctx.bundle) return
        return Object.keys(ctx.bundle).filter(f => PRELOAD.test(f)).sort().map(f => ({
          tag: 'link', injectTo: 'head' as const, attrs: { rel: 'preload', as: 'font', type: 'font/woff2', crossorigin: '', href: './' + f },
        }))
      },
    },
  }
}

export default defineConfig({
  base: './',
  plugins: [react(), tailwind(), siteData(), preloadFonts()],
  build: { outDir: 'dist', assetsDir: 'assets', chunkSizeWarningLimit: 1200, sourcemap: !!process.env.WW_SOURCEMAP },
})
