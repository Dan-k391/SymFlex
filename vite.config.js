import { normalize } from 'node:path'
import { defineConfig } from 'vite'
import { bundlePy, PY_DIR } from './scripts/bundle_py.mjs'

// Cross-origin isolation enables SharedArrayBuffer, which Pyodide uses for interrupts.
const isolation = {
  'Cross-Origin-Opener-Policy': 'same-origin',
  'Cross-Origin-Embedder-Policy': 'require-corp',
}

/** Re-zips py/symflex_maple on start and whenever it changes, then tells the page to reload the engine. */
function pythonEngine() {
  const pyDir = normalize(PY_DIR).toLowerCase()
  return {
    name: 'symflex-python-engine',
    buildStart() { bundlePy({ quiet: true }) },
    configureServer(server) {
      server.watcher.add(PY_DIR)
      let timer
      const onChange = (file) => {
        const f = normalize(file).toLowerCase()
        if (!f.startsWith(pyDir) || !f.endsWith('.py')) return
        clearTimeout(timer)
        timer = setTimeout(() => {
          if (bundlePy({ quiet: true })) server.ws.send({ type: 'custom', event: 'symflex:py-updated' })
        }, 200)
      }
      server.watcher.on('change', onChange).on('add', onChange).on('unlink', onChange)
    },
  }
}

export default defineConfig({
  base: './',
  plugins: [pythonEngine()],
  server: { port: 5173, headers: isolation },
  preview: { port: 4173, headers: isolation },
  worker: { format: 'es' },
  build: { target: 'es2022', chunkSizeWarningLimit: 5000 },
})
