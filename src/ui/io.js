// Import / export between notebooks and .mpl, .pde, .txt, .mw and .symflex.json files.
import { fromFile, newCell, newNotebook, toFile } from './store.js'

const ENTITIES = { amp: '&', lt: '<', gt: '>', quot: '"', apos: "'", nbsp: ' ' }
const decode = (s) => s.replace(/&(#x[0-9a-f]+|#\d+|\w+);/gi, (m, e) =>
  e[0] === '#' ? String.fromCodePoint(e[1] === 'x' || e[1] === 'X' ? parseInt(e.slice(2), 16) : +e.slice(1)) : ENTITIES[e] ?? m)
const stripTags = (s) => decode(s.replace(/<[^>]*>/g, ''))

export const looksLikePde = (text) =>
  /^\s*(TITLE|COORDINATES|VARIABLES|DEFINITIONS|EQUATIONS|BOUNDARIES)\b/im.test(text) && /^\s*END\s*$/im.test(text)

/** Splits Maple source into cells at blank lines (Maple .mpl files carry no cell boundaries). */
export function mplToCells(text) {
  return text.replace(/\r\n?/g, '\n').split(/\n\s*\n/).map((s) => s.replace(/^\n+|\s+$/g, ''))
    .filter(Boolean).map((s) => newCell('maple', s))
}

/**
 * Extracts cells from a Maple .mw worksheet: 1-D input from <Input> groups (2-D input via the
 * input-equation attribute), and text paragraphs as markdown cells.
 */
export function mwToCells(xml) {
  const cells = []
  // <Output> blocks are matched only to skip the Text-fields inside them.
  const re = /<Input>([\s\S]*?)<\/Input>|<Output>[\s\S]*?<\/Output>|<Text-field([^>]*)>([\s\S]*?)<\/Text-field>/g
  let m
  while ((m = re.exec(xml))) {
    if (m[0].startsWith('<Output>')) continue
    if (m[1] !== undefined) {
      const lines = []
      for (const f of m[1].matchAll(/<Text-field[^>]*>([\s\S]*?)<\/Text-field>/g)) {
        const eq = [...f[1].matchAll(/input-equation="([^"]*)"/g)].map((e) => decode(e[1]))
        lines.push(eq.length ? eq.join('\n') : stripTags(f[1]))
      }
      const code = lines.join('\n').replace(/\s+$/, '')
      if (code.trim()) cells.push(newCell('maple', code))
    } else {
      const text = stripTags(m[3]).trim()
      if (!text) continue
      const heading = /style="Heading (\d)"/.exec(m[2])
      const md = heading ? '#'.repeat(+heading[1]) + ' ' + text : /style="Title"/.test(m[2]) ? '# ' + text : text
      const last = cells.at(-1)
      if (last?.type === 'markdown') last.source += '\n\n' + md
      else cells.push(newCell('markdown', md))
    }
  }
  return cells
}

/** Returns a notebook for an imported file, by extension. */
export function importFile(name, text) {
  const base = name.replace(/\.[^.]+$/, '').replace(/\.symflex$/, '')
  const ext = name.toLowerCase().match(/\.([^.]+)$/)?.[1]
  if (ext === 'json') return fromFile(JSON.parse(text), base)
  let cells
  if (ext === 'mw') cells = mwToCells(text)
  else if (ext === 'pde' || (ext !== 'mpl' && looksLikePde(text))) cells = [newCell('flexpde', text.replace(/\r\n?/g, '\n').trim())]
  else cells = mplToCells(text)
  if (!cells.length) throw new Error(`no code found in ${name}`)
  return newNotebook(base, cells)
}

export function exportMpl(nb) {
  return nb.cells.filter((c) => c.type !== 'flexpde').map((c) =>
    c.type === 'markdown' ? c.source.split('\n').map((l) => '# ' + l).join('\n') : c.source).join('\n\n') + '\n'
}

/** A .pde holds one problem: the given cell if it is FlexPDE, else the first FlexPDE cell. */
export function exportPde(nb, cellId) {
  const cell = nb.cells.find((c) => c.id === cellId && c.type === 'flexpde') ?? nb.cells.find((c) => c.type === 'flexpde')
  return cell ? cell.source + '\n' : null
}

export const exportJson = (nb) => JSON.stringify(toFile(nb), null, 1)

export const escapeHtml = (s) => String(s).replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`)

/**
 * Static HTML rendering. `renderCell(cell)` returns the cell's rendered output/markdown HTML,
 * so this module stays independent of KaTeX/Plotly.
 */
export function exportHtml(nb, renderCell, css = '') {
  const body = nb.cells.map((c) => {
    const inner = renderCell(c)
    if (c.type === 'markdown') return `<section class="md">${inner}</section>`
    const label = c.execCount != null ? `[${c.execCount}]` : '[ ]'
    return `<section class="cell"><div class="in"><span class="n">${label}</span><pre>${escapeHtml(c.source)}</pre></div>` +
      `<div class="out">${inner}</div></section>`
  }).join('\n')
  return `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>${escapeHtml(nb.name)}</title><style>
body{font:15px/1.55 Inter,system-ui,sans-serif;max-width:900px;margin:2rem auto;padding:0 16px;color:#1f2328;background:#fff}
pre{font:13px/1.5 "JetBrains Mono",Consolas,monospace;background:#f6f8fa;border:1px solid #e3e6ea;border-radius:6px;padding:10px;overflow:auto;margin:0}
.cell{margin:1rem 0}.in{display:flex;gap:8px}.in pre{flex:1}.n{color:#8b949e;font:12px monospace;min-width:3em;padding-top:10px}
.out{margin-left:3.5em}.math{text-align:center;margin:.4rem 0;overflow-x:auto}.print{white-space:pre-wrap;font-family:monospace}
.error{color:#cf222e;font-family:monospace;white-space:pre-wrap}.warning{color:#9a6700;font-family:monospace;white-space:pre-wrap}
img{max-width:100%}table{border-collapse:collapse}td,th{border:1px solid #ddd;padding:2px 8px}${css}
</style></head><body><h1>${escapeHtml(nb.name)}</h1>
${body}
</body></html>`
}
