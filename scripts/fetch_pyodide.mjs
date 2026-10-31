// Vendors the Pyodide runtime plus the sympy/mpmath wheels into public/pyodide/ so the
// app works offline. Idempotent: files already present with the right hash are skipped.
import { createHash } from 'node:crypto'
import { copyFileSync, existsSync, mkdirSync, readFileSync, statSync, writeFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = join(dirname(fileURLToPath(import.meta.url)), '..')
const src = join(root, 'node_modules', 'pyodide')
const dest = join(root, 'public', 'pyodide')
const WANTED = ['sympy', 'mpmath']
const RUNTIME = ['pyodide.mjs', 'pyodide.js', 'pyodide.asm.mjs', 'pyodide.asm.wasm',
  'python_stdlib.zip', 'pyodide-lock.json']

const sha256 = (buf) => createHash('sha256').update(buf).digest('hex')

export async function fetchPyodide() {
  if (!existsSync(src)) throw new Error('node_modules/pyodide missing: run npm install first')
  mkdirSync(dest, { recursive: true })
  for (const f of RUNTIME) {
    const from = join(src, f), to = join(dest, f)
    if (!existsSync(from)) continue
    if (existsSync(to) && statSync(to).size === statSync(from).size) continue
    copyFileSync(from, to)
    console.log(`copied ${f}`)
  }

  const { version } = JSON.parse(readFileSync(join(src, 'package.json'), 'utf8'))
  const lock = JSON.parse(readFileSync(join(src, 'pyodide-lock.json'), 'utf8'))
  const cdn = `https://cdn.jsdelivr.net/pyodide/v${version}/full/`

  // Resolve the transitive dependency closure of the wanted packages.
  const todo = [...WANTED], seen = new Set()
  while (todo.length) {
    const name = todo.pop()
    if (seen.has(name)) continue
    const pkg = lock.packages[name]
    if (!pkg) throw new Error(`package ${name} not in pyodide-lock.json`)
    seen.add(name)
    todo.push(...pkg.depends)
  }

  for (const name of seen) {
    const { file_name, sha256: want } = lock.packages[name]
    const to = join(dest, file_name)
    if (existsSync(to) && sha256(readFileSync(to)) === want) continue
    console.log(`downloading ${file_name}`)
    const res = await fetch(cdn + file_name)
    if (!res.ok) throw new Error(`${cdn + file_name}: HTTP ${res.status}`)
    const buf = Buffer.from(await res.arrayBuffer())
    if (sha256(buf) !== want) throw new Error(`${file_name}: sha256 mismatch`)
    writeFileSync(to, buf)
  }
  console.log(`pyodide ${version} ready in public/pyodide (${[...seen].join(', ')})`)
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) {
  fetchPyodide().catch((e) => { console.error(e.message); process.exit(1) })
}
