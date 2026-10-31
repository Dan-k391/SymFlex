// IntelliSense for both languages: completion sources, hover docs, signature help, linting.
import { StateField } from '@codemirror/state'
import { EditorView, hoverTooltip, showTooltip } from '@codemirror/view'
import { flexSectionAt } from './flex.js'
import { FLEX_COORDINATES, FLEX_DOC_INDEX, FLEX_FUNCTIONS, FLEX_KEYWORDS, FLEX_PLOTS, FLEX_SECTIONS, FLEX_SELECT } from './flex_docs.js'
import { checkMapleBrackets } from './maple.js'
import { MAPLE_CONSTANTS, MAPLE_DOC_INDEX, MAPLE_DOCS, MAPLE_KEYWORDS, MAPLE_OPTIONS, MAPLE_PACKAGES } from './maple_docs.js'

const PLOT_FUNCS = new Set(['plot', 'plot3d', 'display', 'odeplot', 'animate', 'pointplot', 'pointplot3d', 'spacecurve',
  'implicitplot', 'contourplot', 'densityplot', 'fieldplot', 'arrow', 'textplot', 'polarplot', 'logplot',
  'semilogplot', 'loglogplot', 'listplot', 'complexplot', 'DEplot', 'dfieldplot', 'phaseportrait'])

/** Info panel DOM for a doc entry {name, sig, doc, pkg?, ex?}. */
export function docNode(d) {
  const el = document.createElement('div')
  el.className = 'sf-doc'
  const sig = document.createElement('div')
  sig.className = 'sf-doc-sig'
  sig.textContent = d.sig || d.name
  el.append(sig)
  if (d.pkg) { const p = document.createElement('div'); p.className = 'sf-doc-pkg'; p.textContent = d.pkg; el.append(p) }
  const p = document.createElement('div'); p.textContent = d.doc || ''; el.append(p)
  if (d.ex) { const ex = document.createElement('pre'); ex.className = 'sf-doc-ex'; ex.textContent = d.ex; el.append(ex) }
  return el
}

// ---- text analysis helpers (pure; exported for tests)

/** Name of the innermost unclosed call around the end of `before`, and the argument index. */
export function enclosingCall(before) {
  let depth = 0, arg = 0
  for (let i = before.length - 1; i >= 0; i--) {
    const c = before[i]
    if (c === ')' || c === ']' || c === '}') depth++
    else if (c === '[' || c === '{') { if (depth) depth--; else return null }
    else if (c === '(') {
      if (depth) { depth--; continue }
      const m = /([A-Za-z_][A-Za-z0-9_]*)(\[[^\]]*\])?\s*$/.exec(before.slice(0, i))
      if (!m) return null
      const pkg = /([A-Za-z_]+)\s*:-\s*$/.exec(before.slice(0, m.index))
      return { name: m[1], arg, pkg: pkg?.[1], start: m.index }
    } else if (c === ',' && !depth) arg++
    else if (c === ';') return null
  }
  return null
}

/** Names assigned in Maple source: x := ..., f := proc, f := (x) -> ..., local names. */
export function mapleUserNames(text) {
  const names = new Set()
  for (const m of text.matchAll(/([A-Za-z_][A-Za-z0-9_]*)\s*:=/g)) names.add(m[1])
  for (const m of text.matchAll(/\blocal\s+([^;]+);/g)) for (const n of m[1].split(',')) names.add(n.trim().split(/\s/)[0])
  return names
}

/** Names defined in FlexPDE source (DEFINITIONS, VARIABLES, vector components). */
export function flexUserNames(text) {
  const names = new Set()
  const clean = text.replace(/\{[^}]*\}|![^\n]*|'[^']*'/g, ' ')
  for (const m of clean.matchAll(/^\s*([A-Za-z_][A-Za-z0-9_]*)\s*(\(|=)/gm)) names.add(m[1])
  for (const m of clean.matchAll(/vector\s*\(([^)]*)\)/gi)) for (const n of m[1].split(',')) if (/^\s*[A-Za-z_]\w*\s*$/.test(n)) names.add(n.trim())
  for (const s of FLEX_SECTIONS) names.delete(s[0])
  return names
}

// ---- Maple completion

const mapleFunctionOptions = MAPLE_DOCS.map((d) => ({
  label: d.name, type: d.name === 'restart' ? 'keyword' : 'function',
  detail: d.pkg ? `${d.sig}  · ${d.pkg}` : d.sig, info: () => docNode(d),
  boost: d.pkg && d.pkg !== '' ? -1 : 0,
}))
const mapleStaticOptions = [
  ...mapleFunctionOptions,
  ...Object.keys(MAPLE_PACKAGES).map((p) => ({ label: p, type: 'namespace', detail: 'package', boost: -2 })),
  ...MAPLE_CONSTANTS.map(([n, doc]) => ({ label: n, type: 'constant', info: doc })),
  ...MAPLE_KEYWORDS.map((k) => ({ label: k, type: 'keyword', boost: -3 })),
]

/**
 * @param {object} o
 * @param {() => Iterable<string>} [o.userNames]  names from the notebook text
 * @param {(prefix: string) => Promise<Array>} [o.kernelComplete]  names known to the kernel
 */
export function mapleCompletionSource({ userNames = () => [], kernelComplete } = {}) {
  return async (ctx) => {
    const line = ctx.state.doc.lineAt(ctx.pos)
    const before = line.text.slice(0, ctx.pos - line.from)
    const word = ctx.matchBefore(/&?[A-Za-z_][A-Za-z0-9_]*/)
    const from = word ? word.from : ctx.pos

    let m = /with\(\s*([A-Za-z_]*)$/.exec(before)
    if (m) return { from: ctx.pos - m[1].length, options: Object.keys(MAPLE_PACKAGES).map((p) => ({ label: p, type: 'namespace', detail: 'package' })) }

    m = /([A-Za-z_]+)(\[[A-Za-z0-9_]+\])?\s*:-\s*([A-Za-z_]*)$/.exec(before)
    if (m) {
      const key = m[2] ? m[1] + m[2] : m[1]
      const members = MAPLE_PACKAGES[key] ?? MAPLE_PACKAGES[m[1]] ?? []
      return { from: ctx.pos - m[3].length, options: members.map((n) => {
        const d = MAPLE_DOC_INDEX.get(n)
        return { label: n, type: 'function', detail: d?.sig, info: d ? () => docNode(d) : undefined }
      }) }
    }

    if (!word && !ctx.explicit) return null
    const textBefore = ctx.state.doc.sliceString(Math.max(0, ctx.pos - 2000), from)
    const call = enclosingCall(textBefore)
    const options = []
    if (call) {
      const fn = call.name
      for (const [label, target, doc] of MAPLE_OPTIONS) {
        if (target === fn || (target === '*' && PLOT_FUNCS.has(fn)))
          options.push({ label, type: 'property', info: doc, boost: 5, apply: label.endsWith('= ') ? label : undefined })
      }
    }
    const seen = new Set(mapleStaticOptions.map((o) => o.label))
    for (const n of userNames()) if (!seen.has(n)) { seen.add(n); options.push({ label: n, type: 'variable', boost: 3 }) }
    if (kernelComplete && word && word.text.length >= 1) {
      try {
        const items = await Promise.race([kernelComplete(word.text), new Promise((r) => setTimeout(() => r([]), 300))])
        for (const it of items || []) {
          if (!it?.label || seen.has(it.label)) continue
          seen.add(it.label)
          options.push({ label: it.label, type: it.kind === 'function' ? 'function' : 'variable', detail: it.detail, info: it.doc, boost: 2 })
        }
      } catch { /* kernel busy or not ready: static completions only */ }
    }
    return { from, options: [...options, ...mapleStaticOptions], validFor: /^&?[A-Za-z_][A-Za-z0-9_]*$/ }
  }
}

// ---- FlexPDE completion

const flexSectionOptions = FLEX_SECTIONS.map(([n, doc, ex]) => ({ label: n, type: 'keyword', info: () => docNode({ name: n, sig: n, doc, ex }), boost: 2 }))
const flexFunctionOptions = FLEX_FUNCTIONS.map(([n, sig, doc]) => ({ label: n, type: 'function', detail: sig, info: doc }))
const flexPlotOptions = FLEX_PLOTS.map(([n, sig, doc]) => ({ label: n, type: 'method', detail: sig, info: doc, boost: 3 }))
const flexSelectOptions = FLEX_SELECT.map(([n, type, def, doc]) => ({ label: n, type: 'property', detail: `${type}, default ${def}`, info: doc, boost: 4 }))
const flexKeywordOptions = FLEX_KEYWORDS.map((k) => ({ label: k, type: 'keyword', boost: -1 }))

export function flexCompletionSource() {
  return (ctx) => {
    const word = ctx.matchBefore(/[A-Za-z_][A-Za-z0-9_]*/)
    if (!word && !ctx.explicit) return null
    const from = word ? word.from : ctx.pos
    const text = ctx.state.doc.toString()
    const section = flexSectionAt(text, from)
    const line = ctx.state.doc.lineAt(ctx.pos)
    const lineStart = !line.text.slice(0, from - line.from).trim()
    if (/^\s*COORDINATES\s+\w*$/i.test(line.text.slice(0, ctx.pos - line.from)))
      return { from, options: FLEX_COORDINATES.map((c) => ({ label: c, type: 'constant' })) }
    const options = []
    if (section === 'SELECT') options.push(...flexSelectOptions)
    if (/^(PLOTS|MONITORS|HISTORIES|SUMMARY)/.test(section)) options.push(...flexPlotOptions)
    if (lineStart) options.push(...flexSectionOptions)
    for (const n of flexUserNames(text)) options.push({ label: n, type: 'variable', boost: 3 })
    options.push(...flexFunctionOptions, ...flexKeywordOptions)
    return { from, options, validFor: /^[A-Za-z_][A-Za-z0-9_]*$/ }
  }
}

// ---- hover + signature help

function lookup(lang, word) {
  if (lang === 'maple') return MAPLE_DOC_INDEX.get(word)
  return FLEX_DOC_INDEX.get(word.toLowerCase())
}

export function docHover(lang) {
  return hoverTooltip((view, pos) => {
    const { from, to, text } = view.state.doc.lineAt(pos)
    let s = pos - from, e = pos - from
    while (s > 0 && /[\w&]/.test(text[s - 1])) s--
    while (e < text.length && /\w/.test(text[e])) e++
    const word = text.slice(s, e)
    const d = word && lookup(lang, word)
    if (!d) return null
    return { pos: from + s, end: Math.min(to, from + e), above: true, create: () => ({ dom: docNode(d) }) }
  }, { hoverTime: 350 })
}

/** Shows the signature of the call surrounding the cursor (like VS Code parameter hints). */
export function signatureHelp(lang) {
  const compute = (state) => {
    const sel = state.selection.main
    if (!sel.empty) return null
    const before = state.doc.sliceString(Math.max(0, sel.head - 1500), sel.head)
    const call = enclosingCall(before)
    const d = call && lookup(lang, call.name)
    if (!d?.sig || !/\(/.test(d.sig)) return null
    return {
      pos: sel.head, above: true, strictSide: true, arrow: false,
      create: () => {
        const dom = document.createElement('div')
        dom.className = 'sf-sighelp'
        dom.textContent = d.sig
        return { dom }
      },
    }
  }
  return StateField.define({
    create: compute,
    update: (value, tr) => (tr.docChanged || tr.selection ? compute(tr.state) : value),
    provide: (f) => showTooltip.from(f),
  })
}

// ---- lint

export function mapleLintSource() {
  return (view) => checkMapleBrackets(view.state.doc.toString())
}

/**
 * Converts engine diagnostics ({line, msg} or {line, col, message, severity}) to CodeMirror
 * diagnostics. Lines are 1-based; out-of-range lines clamp to the document.
 */
export function toDiagnostics(doc, items) {
  return (items || []).map((it) => {
    const n = Math.min(Math.max(1, it.line || 1), doc.lines)
    const line = doc.line(n)
    const from = it.col ? Math.min(line.to, line.from + it.col - 1) : line.from
    return { from, to: it.col && it.endCol ? Math.min(line.to, line.from + it.endCol - 1) : line.to,
      severity: it.severity || 'error', message: it.msg || it.message || String(it) }
  })
}

export const assistTheme = EditorView.baseTheme({
  '.cm-tooltip.cm-tooltip-hover, .cm-tooltip-autocomplete-info': { maxWidth: '420px' },
})
