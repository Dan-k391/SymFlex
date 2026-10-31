// Web worker running the FlexPDE engine (src/flex) off the main thread.
//   in:  {type:'run', id, code} | {type:'lint', id, code}
//   out: {type:'progress', id, msg} | {type:'result', id, result} | {type:'lint', id, diagnostics}
import * as flex from '../flex/index.js'

self.onmessage = async ({ data: { type, id, code } }) => {
  if (type === 'lint') {
    let diagnostics = []
    try { diagnostics = typeof flex.lintFlex === 'function' ? await flex.lintFlex(code) : [] } catch { /* lint is best effort */ }
    return postMessage({ type: 'lint', id, diagnostics })
  }
  try {
    const result = await flex.runFlex(code, { onProgress: (msg) => postMessage({ type: 'progress', id, msg }) })
    postMessage({ type: 'result', id, result })
  } catch (e) {
    postMessage({ type: 'result', id, result: { title: '', log: [String(e?.stack ?? e)], errors: [{ line: e?.line ?? 0, msg: String(e?.message ?? e) }], reports: [], plots: [] } })
  }
}
