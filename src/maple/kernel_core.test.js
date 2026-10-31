// Boots the real Pyodide (from public/pyodide, as the browser does) under Node and drives
// kernel_core. Uses py/symflex_maple when it has a Session, otherwise a tiny stub engine.
// Skipped when public/pyodide has not been set up (npm run setup).
import assert from 'node:assert/strict'
import { existsSync, readFileSync } from 'node:fs'
import { join } from 'node:path'
import { test } from 'node:test'
import { fileURLToPath } from 'node:url'
import { bundlePy, makeZip } from '../../scripts/bundle_py.mjs'
import { createKernel } from './kernel_core.js'

const root = fileURLToPath(new URL('../../', import.meta.url))
const indexURL = join(root, 'public', 'pyodide') + '/'
const realEngine = existsSync(join(root, 'py/symflex_maple/__init__.py')) &&
  /\bSession\b/.test(readFileSync(join(root, 'py/symflex_maple/__init__.py'), 'utf8'))

const STUB = `
class Session:
    def __init__(self): self.vars = {}
    def run(self, code):
        if code.strip() == 'boom': raise ValueError('bad')
        print('stray')
        return [{'kind': 'math', 'text': code.strip().rstrip(';'), 'latex': 'x'}]
    def complete(self, prefix): return [{'label': n, 'kind': 'variable'} for n in ['alpha', 'beta'] if n.startswith(prefix)]
    def reset(self): self.vars = {}
`

function engineZip() {
  if (realEngine && bundlePy({ quiet: true })) return readFileSync(join(root, 'public/symflex_maple.zip'))
  return makeZip([{ name: 'symflex_maple/__init__.py', data: Buffer.from(STUB) }])
}

test('kernel_core boots pyodide and runs cells', { skip: !existsSync(indexURL + 'pyodide.asm.wasm'), timeout: 180000 }, async () => {
  const { loadPyodide } = await import('pyodide')
  const steps = []
  const k = await createKernel({
    loadPyodide, indexURL,
    fetchEngine: async () => { const b = engineZip(); return b.buffer.slice(b.byteOffset, b.byteOffset + b.length) },
    onProgress: (pct) => steps.push(pct),
  })
  assert.equal(steps.at(-1), 100)
  if (realEngine) {
    const outs = k.run('a := 2 + 3;')
    assert.equal(outs[0].kind, 'math')
    assert.match(outs[0].text, /a := 5/)
    assert.ok(Array.isArray(k.complete('a')))
  } else {
    const outs = k.run('x+1;')
    assert.deepEqual(outs.map((o) => o.kind), ['print', 'math'])
    assert.equal(outs[1].text, 'x+1')
    assert.equal(k.run('boom')[0].kind, 'error')
    assert.deepEqual(k.complete('al').map((i) => i.label), ['alpha'])
  }
  k.reset()
  await k.reload()
})
