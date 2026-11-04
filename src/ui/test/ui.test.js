// Unit tests for the DOM-free parts of the UI (node --test).
import { StringStream } from '@codemirror/language'
import assert from 'node:assert/strict'
import { execFileSync } from 'node:child_process'
import { mkdtempSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { test } from 'node:test'
import { makeZip } from '../../../scripts/bundle_py.mjs'
import { expandReplacement, findMatches, findPattern } from '../find.js'
import { exportJson, exportMpl, exportPde, importFile, looksLikePde, mplToCells, mwToCells } from '../io.js'
import { enclosingCall, flexUserNames, mapleUserNames, toDiagnostics } from '../lang/assist.js'
import { flexSectionAt, flexStreamParser } from '../lang/flex.js'
import { checkMapleBrackets, mapleStreamParser } from '../lang/maple.js'
import { MAPLE_DOCS, MAPLE_PACKAGES } from '../lang/maple_docs.js'
import { renderMarkdown } from '../markdown.js'
import { capOutputs } from '../output.js'
import { arrowSegments, bounds2d, gridZ, meshToGrid, specToLayout, specToTraces } from '../plot.js'
import * as model from '../store.js'

function tokens(parser, text) {
  const state = parser.startState(2)
  const out = []
  for (const line of text.split('\n')) {
    const s = new StringStream(line, 2, 2)
    while (!s.eol()) {
      const style = parser.token(s, state)
      if (style) out.push([s.current(), style])
      s.start = s.pos
    }
  }
  return out
}

test('store: cell operations and undo record', () => {
  const nb = model.newNotebook('t')
  const a = nb.cells[0]
  const b = model.insertCell(nb, 1, model.newCell('flexpde', 'TITLE'))
  assert.ok(model.moveCell(nb, b.id, -1))
  assert.deepEqual(nb.cells.map((c) => c.id), [b.id, a.id])
  assert.ok(!model.moveCell(nb, b.id, -1))
  const dup = model.duplicateCell(nb, b.id)
  assert.notEqual(dup.id, b.id)
  assert.equal(dup.source, 'TITLE')
  const rec = model.deleteCell(nb, b.id)
  assert.equal(rec.index, 0)
  model.deleteCell(nb, dup.id)
  model.deleteCell(nb, a.id)
  assert.equal(nb.cells.length, 1, 'never empty')
  assert.throws(() => model.newCell('python'))
})

test('store: file round trip validates input', () => {
  const nb = model.newNotebook('x', [model.newCell('maple', 'a := 1;'), model.newCell('markdown', '# hi')])
  nb.cells[0].outputs = [{ kind: 'math', text: 'a := 1' }, { bogus: true }]
  nb.cells[0].execCount = 3
  const back = model.fromFile(JSON.parse(exportJson(nb)))
  assert.equal(back.name, 'x')
  assert.deepEqual(back.cells.map((c) => c.type), ['maple', 'markdown'])
  assert.equal(back.cells[0].outputs.length, 1)
  assert.equal(back.cells[0].execCount, 3)
  assert.throws(() => model.fromFile({ cells: [] }))
})

test('store: localStorage persistence with quota fallback', () => {
  const data = new Map()
  let limit = Infinity
  const storage = {
    getItem: (k) => data.get(k) ?? null,
    setItem: (k, v) => { if (v.length > limit) throw new Error('quota'); data.set(k, v) },
    removeItem: (k) => data.delete(k),
  }
  const st = new model.NotebookStore(storage)
  const nb = model.newNotebook('big')
  nb.cells[0].outputs = [{ kind: 'plot', spec: { curves: [{ x: new Array(5000).fill(1) }] } }, { kind: 'math', text: 'x' }]
  limit = 2000
  assert.ok(st.save(nb))
  assert.deepEqual(st.load(nb.id).cells[0].outputs.map((o) => o.kind), ['math'])
  assert.equal(st.list()[0].name, 'big')
  st.setSetting('theme', 'dark')
  assert.equal(st.getSetting('theme'), 'dark')
  st.remove(nb.id)
  assert.equal(st.list().length, 0)
  assert.equal(st.load(nb.id), null)
})

test('io: .mpl splits on blank lines, .pde detection', () => {
  assert.deepEqual(mplToCells('restart:\na:=1;\n\n\nb:=2;\n').map((c) => c.source), ['restart:\na:=1;', 'b:=2;'])
  const pde = "TITLE 'x'\nVARIABLES u\nEQUATIONS u: dt(u)=1\nEND\n"
  assert.ok(looksLikePde(pde))
  assert.equal(importFile('a.txt', pde).cells[0].type, 'flexpde')
  assert.equal(importFile('a.txt', 'x := 1;').cells[0].type, 'maple')
  const nb = importFile('lab.pde', pde)
  assert.equal(nb.name, 'lab')
  assert.equal(exportPde(nb), pde.trim() + '\n')
  assert.equal(exportPde(model.newNotebook()), null)
})

test('io: Maple .mw worksheet extraction', () => {
  const mw = `<?xml version="1.0"?><Worksheet>
  <Group><Input><Text-field prompt="&gt; " style="Maple Input" layout="Normal"><Font family="Monospaced">restart: m:=2:</Font></Text-field></Input></Group>
  <Group><Input><Text-field style="Maple Input">F := m*a;</Text-field><Text-field style="Maple Input">solve(F &lt; 3, a);</Text-field></Input>
    <Output><Text-field style="2D Output">ignored</Text-field></Output></Group>
  <Text-field style="Heading 2" layout="Heading 2">Part &amp; b</Text-field>
  <Text-field style="Text" layout="Normal">Some prose.</Text-field>
  <Group><Input><Text-field style="2D Input"><Equation executable="true" input-equation="x := sqrt(2);" style="2D Input">base64junk</Equation></Text-field></Input></Group>
  </Worksheet>`
  const cells = mwToCells(mw)
  assert.deepEqual(cells.map((c) => [c.type, c.source]), [
    ['maple', 'restart: m:=2:'],
    ['maple', 'F := m*a;\nsolve(F < 3, a);'],
    ['markdown', '## Part & b\n\nSome prose.'],
    ['maple', 'x := sqrt(2);'],
  ])
})

test('io: export .mpl keeps markdown as comments and skips FlexPDE', () => {
  const nb = model.newNotebook('n', [model.newCell('markdown', 'Intro\nline'), model.newCell('maple', 'a:=1;'), model.newCell('flexpde', 'TITLE')])
  assert.equal(exportMpl(nb), '# Intro\n# line\n\na:=1;\n')
})

test('maple tokenizer classifies names', () => {
  const t = Object.fromEntries(tokens(mapleStreamParser, 'restart: sol := dsolve({x(t)}, numeric); # hi\nwith(plots): Pi; "s" proc(a) local b; end proc; u &x v'))
  assert.equal(t.restart, 'keyword')
  assert.equal(t.sol, 'variableName.definition')
  assert.equal(t[':='], 'definitionOperator')
  assert.equal(t.dsolve, 'variableName.standard')
  assert.equal(t['# hi'], 'lineComment')
  assert.equal(t.plots, 'namespace')
  assert.equal(t.Pi, 'atom')
  assert.equal(t['"s"'], 'string')
  assert.equal(t.proc, 'definitionKeyword')
  assert.equal(t['&x'], 'operator')
})

test('flex tokenizer: sections, comments, labels', () => {
  const t = tokens(flexStreamParser, "TITLE 'a' { multi\nline }\nSELECT ngrid=1\nINITIAL VALUES\nEQUATIONS\n  v: dt(v) = -g ! c\nPLOTS\n  history(v) at (0)")
  const map = Object.fromEntries(t)
  assert.equal(map.TITLE, 'heading')
  assert.equal(map['INITIAL VALUES'], 'heading')
  assert.equal(map['line }'], 'blockComment')
  assert.equal(map.ngrid, 'propertyName')
  assert.equal(map.dt, 'variableName.standard')
  assert.equal(map['! c'], 'lineComment')
  assert.equal(map.history, 'keyword')
  assert.equal(t.find(([s]) => s === 'v')[1], 'labelName')
  assert.equal(flexSectionAt("TITLE 'x'\nSELECT\n  ngr", 20), 'SELECT')
  assert.equal(flexSectionAt('PLOTS\n  history(x)\n  ', 22), 'PLOTS')
})

test('maple bracket lint', () => {
  assert.deepEqual(checkMapleBrackets('plot(sin(x), x = 0 .. [1]); # (\n"a(" (* ) *)'), [])
  const d = checkMapleBrackets('f(x]; g(')
  assert.deepEqual(d.map((x) => x.from).sort((a, b) => a - b), [1, 3, 7])
  assert.match(checkMapleBrackets('print("abc);')[0].message, /Unterminated string/)
})

test('assist: enclosing call, user names, diagnostics', () => {
  assert.deepEqual(enclosingCall('plot(sin(x), x = 0 .. 1, col'), { name: 'plot', arg: 2, pkg: undefined, start: 0 })
  assert.equal(enclosingCall('a := plots:-odeplot(s, [t, x(t)], ').pkg, 'plots')
  assert.equal(enclosingCall('dsolve({diff(x(t), t) = 1, x(0) = 0}, ').name, 'dsolve')
  assert.equal(enclosingCall('f(1); g'), null)
  assert.deepEqual([...mapleUserNames('m := 2: ode:=diff(x(t),t)=1; f := proc(a) local k, j; end;')], ['m', 'ode', 'f', 'k', 'j'])
  const names = flexUserNames('VARIABLES\n r(threshold=1e-2) = vector(rx, ry)\nDEFINITIONS\n m = 2 { c }\n')
  assert.ok(names.has('r') && names.has('rx') && names.has('ry') && names.has('m'))
  const doc = { lines: 3, line: (n) => ({ from: (n - 1) * 10, to: (n - 1) * 10 + 5 }) }
  assert.deepEqual(toDiagnostics(doc, [{ line: 9, msg: 'x' }])[0], { from: 20, to: 25, severity: 'error', message: 'x' })
})

test('maple docs cover the course functions', () => {
  const names = new Set(MAPLE_DOCS.map((d) => d.name))
  assert.ok(MAPLE_DOCS.length >= 250, `only ${MAPLE_DOCS.length} entries`)
  for (const f of ['diff', 'dsolve', 'solve', 'fsolve', 'subs', 'evalf', 'int', 'plot', 'odeplot', 'BasisFormat', 'Normalize',
    'assign', 'rhs', 'piecewise', 'semilogplot', 'loglogplot', 'maximize', 'Matrix', 'assume', 'arcsin', 'D', 'display', 'seq', 'coeff'])
    assert.ok(names.has(f), f)
  for (const members of Object.values(MAPLE_PACKAGES)) for (const m of members) assert.ok(names.has(m), m)
})

test('markdown renders math and escapes html', () => {
  const html = renderMarkdown('**F** = $m a$ and $$x^2$$ <script>alert(1)</script> [x](javascript:alert(1)) cost $5')
  assert.match(html, /<strong>F<\/strong>/)
  assert.match(html, /class="katex"/)
  assert.match(html, /katex-display/)
  assert.ok(!html.includes('<script>'))
  assert.ok(!html.includes('javascript:'))
  assert.match(html, /cost \$5/)
})

test('plot helpers', () => {
  assert.deepEqual(gridZ({ x: [0, 1, 2], y: [0, 1], z: [[1, 2], [3, 4], [5, 6]] }), [[1, 3, 5], [2, 4, 6]])
  const g = meshToGrid({ x: [0, 1, 0, 1], y: [0, 0, 1, 1], tri: [[0, 1, 2], [1, 3, 2]], values: [0, 1, 1, 2] }, 3)
  assert.deepEqual(g.z, [[0, 0.5, 1], [0.5, 1, 1.5], [1, 1.5, 2]])
  const a = arrowSegments({ x: [0, 1], y: [0, 0], u: [1, 0], v: [0, 0] }, 0.5)
  assert.equal(a.x.length, 7)
  assert.equal(a.x[1], 0.5)
  assert.deepEqual(bounds2d([{ curves: [{ x: [0, 2], y: [1, -1] }] }, { curves: [{ x: [5], y: [3] }] }]), [0, 5, -1, 3])
  const spec = { type: '2d', xlog: true, xrange: [1, 100], scaling: 'constrained', curves: [{ x: [1, 10], y: [1, 2], style: 'point', legend: 'p' }] }
  const [tr] = specToTraces(spec)
  assert.equal(tr.mode, 'markers')
  const lay = specToLayout(spec, { fg: '#000', muted: '#888', grid: '#eee', bg: '#fff' })
  assert.equal(lay.xaxis.type, 'log')
  assert.deepEqual(lay.xaxis.range, [0, 2])
  assert.equal(lay.yaxis.scaleanchor, 'x')
  assert.equal(specToTraces({ type: 'surface', mesh: { x: [0, 1, 0], y: [0, 0, 1], tri: [[0, 1, 2]], values: [1, 2, 3] } })[0].type, 'mesh3d')
  assert.equal(specToTraces({ type: 'contour', grid: { x: [0, 1], y: [0, 1], z: [[0, 1], [1, 2]] } })[0].type, 'contour')
})

test('bundle_py zip is readable by Python zipfile', () => {
  const dir = mkdtempSync(join(tmpdir(), 'sfzip-'))
  const file = join(dir, 't.zip')
  writeFileSync(file, makeZip([{ name: 'pkg/__init__.py', data: Buffer.from('X = 42\n') }, { name: 'pkg/m.py', data: Buffer.from('é = 1\n'.repeat(50)) }]))
  const out = execFileSync('python', ['-c', `import sys, zipfile; z = zipfile.ZipFile(sys.argv[1]); assert z.testzip() is None; sys.path.insert(0, sys.argv[1]); import pkg; print(pkg.X, len(z.read('pkg/m.py')))`, file]).toString()
  assert.equal(out.trim(), `42 ${Buffer.byteLength('é = 1\n'.repeat(50))}`)
})

test('capOutputs keeps the head, the tail and a count of what it drops', () => {
  const few = [{ kind: 'math', text: 'a' }]
  assert.equal(capOutputs(few), few)
  const many = Array.from({ length: 1000 }, (_, i) => ({ kind: 'math', text: String(i) }))
  const c = capOutputs(many)
  assert.equal(c.length, 300)
  assert.equal(c[278].text, '278')
  assert.deepEqual(c[279], { kind: 'warning', text: 'Warning, 701 outputs not shown' })
  assert.equal(c.at(-1).text, '999')
})

test('find: pattern options, matches and replacement expansion', () => {
  const spans = (text, q, o) => findMatches(text, findPattern(q, o)).map((x) => text.slice(x.from, x.to))
  assert.equal(findPattern(''), null)
  assert.deepEqual(spans('x := a.b; X(a+b)', 'x'), ['x', 'X'])
  assert.deepEqual(spans('x := a.b; X(a+b)', 'x', { matchCase: true }), ['x'])
  assert.deepEqual(spans('a.b a+b', 'a.b'), ['a.b'])                       // literal: '.' is not a wildcard
  assert.deepEqual(spans('a.b a+b', 'a.b', { regex: true }), ['a.b', 'a+b'])
  assert.deepEqual(spans('diff(dt, t)', 't', { wholeWord: true }), ['t'])
  assert.deepEqual(spans('abc', 'x*', { regex: true }), [])               // empty matches are skipped
  assert.throws(() => findPattern('(', { regex: true }), SyntaxError)
  const [hit] = findMatches('x(t) = 3', findPattern(String.raw`(\w)\((\w)\)`, { regex: true }))
  assert.equal(expandReplacement('$2[$1] $$ $& $9', hit.m, true), 't[x] $ x(t) $9')
  assert.equal(expandReplacement('$1', hit.m, false), '$1')
  assert.equal(expandReplacement('$10|$0', hit.m, true), 'x0|$0')  // like String.replace with 2 groups
  assert.deepEqual(spans('a;\nb;\nc', ';$', { regex: true }), [';', ';'])  // ^ and $ per line
})
