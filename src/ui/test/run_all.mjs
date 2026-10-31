// `npm test`: runs every suite that exists and prints a summary. Missing suites are skipped
// (the Maple and FlexPDE runners are owned by the engine components).
import { spawnSync } from 'node:child_process'
import { existsSync, readdirSync } from 'node:fs'
import { join, relative } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = fileURLToPath(new URL('../../../', import.meta.url))
const p = (...a) => join(root, ...a)

function files(dir, re) {
  if (!existsSync(dir)) return []
  return readdirSync(dir, { recursive: true }).map(String).filter((f) => re.test(f)).map((f) => join(dir, f))
}

const flexTests = files(p('tests/flex'), /(^|[\/])(test_[^\/]*|[^\/]*[._-]test)\.m?js$/)
const suites = [
  ['UI + kernel unit tests', 'node', ['--test', ...files(p('src'), /\.test\.js$/)]],
  ['FlexPDE unit tests', 'node', ['--test', ...flexTests], flexTests.length > 0],
  ['Maple corpus', 'python', [p('tests/run_maple_corpus.py')], existsSync(p('tests/run_maple_corpus.py'))],
  ['FlexPDE corpus', 'node', [p('tests/run_flex_corpus.mjs')], existsSync(p('tests/run_flex_corpus.mjs'))],
  ['Pyodide parity', 'node', [p('tests/pyodide_parity.mjs')], existsSync(p('public/pyodide/pyodide.asm.wasm'))],
]

const results = []
for (const [name, cmd, args, present = true] of suites) {
  if (!present) { results.push([name, 'skipped (missing)']); continue }
  console.log(`\n=== ${name}: ${cmd} ${args.map((a) => relative(root, a) || a).join(' ')}`)
  const r = spawnSync(cmd, args, { cwd: root, stdio: 'inherit' })
  results.push([name, r.error ? `error (${r.error.message})` : r.status === 0 ? 'pass' : `FAIL (exit ${r.status})`])
}
console.log('\nSummary')
for (const [name, status] of results) console.log(`  ${name.padEnd(26)} ${status}`)
process.exit(results.some(([, s]) => /FAIL|error/.test(s)) ? 1 : 0)
