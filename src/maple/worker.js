// Pyodide web worker hosting the Python Maple engine. Protocol (see ARCHITECTURE.md, "UI"):
//   in:  {type:'init', baseUrl, interruptBuffer?} | {type:'run', id, code}
//        {type:'complete', id, prefix} | {type:'reset', id} | {type:'reload', id}
//   out: {type:'progress', pct, msg} | {type:'ready', interrupts} | {type:'fatal', message}
//        {type:'result', id, outputs} | {type:'items', id, items} | {type:'done', id}
import { createKernel } from './kernel_core.js'

let kernel = null

const handlers = {
  async init({ baseUrl, interruptBuffer }) {
    const indexURL = new URL('pyodide/', baseUrl).href
    // Loaded at runtime from the vendored copy so the bundler never touches Pyodide.
    const { loadPyodide } = await import(/* @vite-ignore */ indexURL + 'pyodide.mjs')
    kernel = await createKernel({
      loadPyodide,
      indexURL,
      interruptBuffer,
      fetchEngine: async () => {
        const res = await fetch(new URL(`symflex_maple.zip?v=${Date.now()}`, baseUrl))
        if (!res.ok) throw new Error(`symflex_maple.zip: HTTP ${res.status} (run npm run setup)`)
        return res.arrayBuffer()
      },
      onProgress: (pct, msg) => postMessage({ type: 'progress', pct, msg }),
    })
    postMessage({ type: 'ready', interrupts: !!interruptBuffer })
  },
  run: ({ id, code }) => postMessage({ type: 'result', id, outputs: kernel.run(code) }),
  complete: ({ id, prefix }) => postMessage({ type: 'items', id, items: kernel.complete(prefix) }),
  reset: ({ id }) => { kernel.reset(); postMessage({ type: 'done', id }) },
  reload: async ({ id }) => { await kernel.reload(); postMessage({ type: 'done', id }) },
}

self.onmessage = async ({ data }) => {
  try {
    await handlers[data.type](data)
  } catch (e) {
    const message = String(e?.message ?? e)
    if (data.type === 'init') postMessage({ type: 'fatal', message })
    else if (data.type === 'run') postMessage({ type: 'result', id: data.id, outputs: [{ kind: 'error', text: `Error, (kernel) ${message}` }] })
    else postMessage({ type: data.type === 'complete' ? 'items' : 'done', id: data.id, items: [], error: message })
  }
}
