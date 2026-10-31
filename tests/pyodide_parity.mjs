// Browser-runtime parity: runs corpus cases through the Maple engine in Pyodide (offline, from
// public/pyodide, exactly as src/maple/worker.js does) and in CPython, and compares the outputs.
//
// Usage: node tests/pyodide_parity.mjs [substring filters...] [--all] [--timeout S]
// Default selection: the first case of every source plus every case using plots or numeric dsolve.
// Statements are run one Session.run each (the golden statement split), like tests/run_maple_corpus.py.
// Verdicts: SAME (identical JSON), NEAR (numbers within 1e-8 relative), HASHDEP (differs, but CPython
// itself gives the Pyodide output under another PYTHONHASHSEED: engine nondeterminism, not a runtime
// difference), DIFF, TIMEOUT (in either runtime). Exits nonzero on DIFF or when Pyodide fails to load.
import { spawn } from 'node:child_process'
import { copyFileSync, existsSync, readdirSync, readFileSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { createInterface } from 'node:readline'
import { fileURLToPath } from 'node:url'
import { isMainThread, parentPort, Worker, workerData } from 'node:worker_threads'
import { bundlePy } from '../scripts/bundle_py.mjs'
import { createKernel } from '../src/maple/kernel_core.js'

const root = fileURLToPath(new URL('../', import.meta.url))
const indexURL = join(root, 'public', 'pyodide') + '/'
const snapshot = join(tmpdir(), `symflex_parity_${process.pid}.zip`)

async function pyodideWorker() {
  // Pyodide side, in a worker thread so a hung case can be terminated.
  const t0 = performance.now()
  const { loadPyodide } = await import('pyodide')
  const kernel = await createKernel({
    loadPyodide, indexURL,
    fetchEngine: async () => {
      const b = readFileSync(workerData)
      return b.buffer.slice(b.byteOffset, b.byteOffset + b.length)
    },
  })
  parentPort.postMessage({ ready: performance.now() - t0 })
  parentPort.on('message', (stmts) => {
    // Fresh Session per case, as on the CPython side (restart keeps interface() settings).
    kernel.pyodide.runPython("_sf_session = sys.modules['symflex_maple'].Session()")
    const t = performance.now()
    const outs = stmts.map((code) => kernel.run(code))
    parentPort.postMessage({ outs, time: (performance.now() - t) / 1000 })
  })
}

// CPython side: one JSON line in (statement list), one JSON line out, fresh Session per case.
// Stray stdout is captured and prepended as a print output, as kernel_core does in Pyodide.
const PY_HELPER = `
import sys, io, json, time, contextlib
sys.path.insert(0, sys.argv[1])
from symflex_maple import Session
out = sys.stdout
for line in sys.stdin:
    s, outs, t = Session(), [], time.perf_counter()
    for code in json.loads(line):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            try:
                r = s.run(code)
            except Exception as e:
                r = [{'kind': 'error', 'text': f'Error, (internal) {type(e).__name__}: {e}'}]
        r = json.loads(json.dumps(r, default=str))
        if buf.getvalue():
            r.insert(0, {'kind': 'print', 'text': buf.getvalue().rstrip('\\n')})
        outs.append(r)
    out.write(json.dumps({'outs': outs, 'time': time.perf_counter() - t}) + '\\n')
    out.flush()
`

function startPython(seed = 0) {
  const proc = spawn('python', ['-c', PY_HELPER, snapshot], {
    cwd: root, stdio: ['pipe', 'pipe', 'inherit'], env: { ...process.env, PYTHONUTF8: '1', PYTHONHASHSEED: String(seed) },
  })
  const waiting = []
  createInterface({ input: proc.stdout }).on('line', (l) => waiting.shift()?.(JSON.parse(l)))
  proc.on('exit', () => { while (waiting.length) waiting.shift()(null) })
  return {
    send: (stmts) => new Promise((res) => { waiting.push(res); proc.stdin.write(JSON.stringify(stmts) + '\n') }),
    kill: () => proc.kill(),
  }
}

function startPyodide() {
  const w = new Worker(fileURLToPath(import.meta.url), { workerData: snapshot })
  let pending = null
  w.on('message', (m) => pending?.(m))
  w.on('error', (e) => pending?.({ error: String(e?.message ?? e) }))
  w.on('exit', () => pending?.(null))
  const next = () => new Promise((res) => { pending = res })
  return {
    ready: next(),
    send: (stmts) => { const p = next(); w.postMessage(stmts); return p },
    kill: () => w.terminate(),
  }
}

/** Runs one case on a lazily (re)started runner; on timeout the runner is killed and dropped. */
function supervised(start) {
  let r = null
  const run = async (stmts, ms) => {
    r ??= start()
    if (r.ready) {
      const t0 = performance.now()
      const m = await r.ready
      if (!m || m.error) throw new Error(`Pyodide failed to load: ${m?.error ?? 'worker exited'}`)
      r.loadTime = (performance.now() - t0) / 1000
      r.ready = null
      supervised.loads.push(r.loadTime)
    }
    let timer
    const res = await Promise.race([r.send(stmts), new Promise((ok) => { timer = setTimeout(() => ok(null), ms) })])
    clearTimeout(timer)
    if (!res) { r.kill(); r = null }
    return res
  }
  run.kill = () => { r?.kill(); r = null }
  return run
}
supervised.loads = []

const isNum = (v) => typeof v === 'number'
const NUM_RE = /-?(?:\d+\.?\d*|\.\d+)(?:e[-+]?\d+)?/gi

/** 'same' | 'near' | 'diff': deep equality, numbers (also inside strings) within 1e-8 relative. */
function compare(a, b) {
  if (JSON.stringify(a) === JSON.stringify(b)) return 'same'
  const close = (x, y) => x === y || Math.abs(x - y) <= 1e-8 * Math.max(Math.abs(x), Math.abs(y), 1e-300)
  const near = (x, y) => {
    if (isNum(x) && isNum(y)) return close(x, y)
    if (typeof x === 'string' && typeof y === 'string') {
      if (x.replace(NUM_RE, '#') !== y.replace(NUM_RE, '#')) return false
      const nx = x.match(NUM_RE) ?? [], ny = y.match(NUM_RE) ?? []
      return nx.every((n, i) => close(Number(n), Number(ny[i])))
    }
    if (Array.isArray(x) && Array.isArray(y)) return x.length === y.length && x.every((v, i) => near(v, y[i]))
    if (x && y && typeof x === 'object' && typeof y === 'object') {
      const k = Object.keys(x)
      if (k.length !== Object.keys(y).length) return false
      // Adaptive plot sampling can pick other points after a last-bit difference: compare the curves.
      if (Array.isArray(x.x) && Array.isArray(x.y) && Array.isArray(y.x) && sameCurve(x, y))
        return k.every((key) => key === 'x' || key === 'y' || near(x[key], y[key]))
      return k.every((key) => near(x[key], y[key]))
    }
    return x === y
  }
  return near(a, b) ? 'near' : 'diff'
}

/** Curves {x, y} agree within 1e-6 of their y scale at every sample of either (linear interpolation). */
function sameCurve(a, b) {
  const ys = [...a.y, ...b.y].filter(isNum)
  const span = Math.max(Math.max(...ys) - Math.min(...ys), ...ys.map(Math.abs)) || 1
  const at = (c, t) => {
    let i = c.x.findIndex((v) => v >= t)
    if (i < 0) i = c.x.length - 1
    if (i === 0 || c.x[i] === t) return c.y[i]
    return c.y[i - 1] + ((c.y[i] - c.y[i - 1]) * (t - c.x[i - 1])) / (c.x[i] - c.x[i - 1])
  }
  const ok = (p, q) => p.x.every((t, i) => isNum(t) && isNum(p.y[i]) && Math.abs(at(q, t) - p.y[i]) <= 1e-6 * span)
  return a.x.every(isNum) && b.x.every(isNum) && ok(a, b) && ok(b, a)
}

function selectCases(filters, all) {
  const cases = []
  for (const source of readdirSync(join(root, 'corpus', 'cases')).sort()) {
    const dir = join(root, 'corpus', 'cases', source)
    if (!existsSync(dir) || !source.match(/^\w+$/)) continue
    const files = readdirSync(dir).filter((f) => f.endsWith('.mpl')).sort()
    files.forEach((f, i) => {
      const name = `${source}/${f.slice(0, -4)}`
      const code = readFileSync(join(dir, f), 'utf8')
      const wanted = filters.length ? filters.some((s) => name.includes(s))
        : all || i === 0 || /\b(plots?|odeplot|animate|display|pointplot|numeric)\b/.test(code)
      if (!wanted) return
      const gold = join(root, 'corpus', 'golden', source, f.replace(/\.mpl$/, '.json'))
      const stmts = existsSync(gold)
        ? JSON.parse(readFileSync(gold, 'utf8')).statements.map((s) => s.src + (s.terminator || ';'))
        : [code]
      cases.push({ name, stmts })
    })
  }
  return cases
}

/** Worst per-statement verdict of two runs of the same case. */
function caseVerdict(a, b) {
  const order = ['same', 'near', 'diff']
  return a.map((o, k) => compare(o, b[k])).reduce((v, r) => (order.indexOf(r) > order.indexOf(v) ? r : v), 'same')
}

/** True when CPython reproduces the Pyodide outputs under some other hash seed. */
async function hashDependent(stmts, pyo, timeout) {
  for (let seed = 1; seed <= 8; seed++) {
    const run = supervised(() => startPython(seed))
    const r = await run(stmts, timeout)
    run.kill()
    if (r && caseVerdict(r.outs, pyo.outs) !== 'diff') return true
  }
  return false
}

function firstDiff(a, b) {
  for (let k = 0; k < Math.max(a.length, b.length); k++) {
    if (compare(a[k], b[k]) === 'diff') return { k, cpython: a[k], pyodide: b[k] }
  }
}

async function main() {
  const args = process.argv.slice(2)
  const ti = args.indexOf('--timeout')
  const timeout = (ti >= 0 ? Number(args.splice(ti, 2)[1]) : 90) * 1000
  const all = args.includes('--all')
  const filters = args.filter((a) => !a.startsWith('--'))

  if (!existsSync(indexURL + 'pyodide.asm.wasm')) {
    console.error('public/pyodide missing: run npm run setup')
    process.exit(1)
  }
  bundlePy({ quiet: true })
  // Both runtimes import this one copy (CPython via zipimport), so engine edits during the run cannot skew the comparison.
  copyFileSync(join(root, 'public', 'symflex_maple.zip'), snapshot)
  process.on('exit', () => rmSync(snapshot, { force: true }))
  const cases = selectCases(filters, all)
  console.log(`Pyodide parity: ${cases.length} cases, timeout ${timeout / 1000}s per case`)

  const runPy = supervised(startPython), runPyo = supervised(startPyodide)
  const counts = { same: 0, near: 0, hashdep: 0, diff: 0, timeout: 0 }
  const diffs = []
  let tPy = 0, tPyo = 0
  for (const c of cases) {
    const [py, pyo] = await Promise.all([runPy(c.stmts, timeout), runPyo(c.stmts, timeout)])
    let verdict = !py || !pyo ? 'timeout' : caseVerdict(py.outs, pyo.outs)
    if (verdict === 'diff' && await hashDependent(c.stmts, pyo, timeout)) verdict = 'hashdep'
    counts[verdict]++
    if (py) tPy += py.time
    if (pyo) tPyo += pyo.time
    const t = (r) => (r ? `${r.time.toFixed(2)}s` : 'timeout').padStart(8)
    console.log(`${verdict.toUpperCase().padEnd(8)} ${c.name.padEnd(40)} cpython ${t(py)}  pyodide ${t(pyo)}`)
    if (verdict === 'diff' || verdict === 'hashdep') {
      const d = firstDiff(py.outs, pyo.outs)
      diffs.push({ name: c.name, verdict, src: c.stmts[d.k], ...d })
    }
  }
  for (const d of diffs) {
    console.log(`\n--- ${d.verdict.toUpperCase()} ${d.name} statement ${d.k + 1}: ${d.src}`)
    console.log(`cpython: ${JSON.stringify(d.cpython).slice(0, 400)}`)
    console.log(`pyodide: ${JSON.stringify(d.pyodide).slice(0, 400)}`)
  }
  const loads = supervised.loads.map((s) => `${s.toFixed(1)}s`).join(', ')
  console.log(`\nPyodide load (runtime + sympy + engine): ${loads}`)
  console.log(`Total run time: cpython ${tPy.toFixed(1)}s, pyodide ${tPyo.toFixed(1)}s (x${(tPyo / Math.max(tPy, 1e-9)).toFixed(2)})`)
  console.log(Object.entries(counts).map(([k, v]) => `${k.toUpperCase()} ${v}`).join('  '))
  process.exit(counts.diff ? 1 : 0)
}

if (isMainThread) await main()
else await pyodideWorker()
