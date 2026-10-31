// Renders cell outputs: Maple output dicts and FlexPDE results.
import { escapeHtml } from './io.js'
import { renderMath } from './markdown.js'
import { renderPlot } from './plot.js'

const el = (tag, cls, text) => {
  const e = document.createElement(tag)
  if (cls) e.className = cls
  if (text != null) e.textContent = text
  return e
}

function copyButton(text, toast) {
  const b = el('button', 'out-copy', 'Copy')
  b.type = 'button'
  b.title = text
  b.setAttribute('aria-label', 'Copy 1-D Maple text')
  b.onclick = async () => {
    try { await navigator.clipboard.writeText(text); toast?.('Copied 1-D output') } catch { toast?.('Clipboard unavailable', 'warn') }
  }
  return b
}

function mathOutput(o, toast) {
  const box = el('div', 'out-math')
  const body = el('div', 'out-math-body')
  if (o.latex) body.innerHTML = renderMath(o.latex, true)
  else body.append(el('code', 'out-math-text', o.text))
  box.append(body, copyButton(o.text ?? '', toast))
  return box
}

/** Renders one Maple output dict. Plots render asynchronously into their placeholder. */
export function renderOutput(o, { toast, onJump } = {}) {
  switch (o.kind) {
    case 'math': return mathOutput(o, toast)
    case 'print': return el('pre', 'out-print', o.text)
    case 'warning': return el('pre', 'out-warning', o.text)
    case 'error': return el('pre', 'out-error', o.text)
    case 'plot': {
      const box = el('div', 'out-plot')
      renderPlot(box, o.spec).catch((e) => box.replaceChildren(el('pre', 'out-error', `Plot error: ${e.message}`)))
      return box
    }
    case 'flex': return renderFlexResult(o.result, { onJump })
    default: return el('pre', 'out-print', o.text ?? JSON.stringify(o))
  }
}

/** A loop ended by ';' can print thousands of results; rendering or saving them all freezes the page. */
export function capOutputs(outputs, max = 300, tail = 20) {
  if (outputs.length <= max) return outputs
  return [...outputs.slice(0, max - tail - 1), { kind: 'warning', text: `Warning, ${outputs.length - max + 1} outputs not shown` }, ...outputs.slice(-tail)]
}

export function renderOutputs(container, outputs, opts) {
  container.replaceChildren(...capOutputs(outputs).map((o) => renderOutput(o, opts)))
}

const fmt = (v) => (typeof v === 'number' ? (Number.isInteger(v) ? String(v) : v.toPrecision(6).replace(/\.?0+(e|$)/, '$1')) : String(v))

/**
 * FlexPDE result: errors (click to jump to the line), reports table, final values, plots,
 * collapsible run log.
 * @param {object} r  runFlex result
 * @param {object} opts  {onJump(line)}
 */
export function renderFlexResult(r = {}, { onJump } = {}) {
  const box = el('div', 'flex-result')
  if (r.title) box.append(el('div', 'flex-title', r.title))
  for (const e of r.errors || []) {
    const row = el('button', e.severity === 'warning' ? 'out-warning flex-error' : 'out-error flex-error')
    row.type = 'button'
    row.textContent = e.line ? `Line ${e.line}: ${e.msg}` : e.msg
    if (e.line && onJump) row.onclick = () => onJump(e.line)
    else row.disabled = true
    box.append(row)
  }
  if (r.halted) box.append(el('div', 'out-warning', 'Run halted by HALT condition.'))
  const rows = [...(r.reports || []).map((x) => [x.label, x.value])]
  if (r.final?.values) for (const [k, v] of Object.entries(r.final.values)) rows.push([`${k} (t = ${fmt(r.final.t)})`, v])
  if (rows.length) {
    const table = el('table', 'flex-table')
    table.innerHTML = '<thead><tr><th scope="col">Quantity</th><th scope="col">Value</th></tr></thead>'
    const tb = el('tbody')
    for (const [k, v] of rows) {
      const tr = el('tr')
      tr.append(el('td', null, k), el('td', 'num', fmt(v)))
      tb.append(tr)
    }
    table.append(tb)
    box.append(table)
  }
  for (const spec of r.plots || []) box.append(renderOutput({ kind: 'plot', spec }))
  if (r.log?.length) {
    const d = el('details', 'flex-log')
    d.append(el('summary', null, `Run log (${r.log.length} lines)`), el('pre', null, r.log.join('\n')))
    box.append(d)
  }
  return box
}

/** Static HTML for one cell's outputs (export). `images` maps plot index -> PNG data URL. */
export function outputsToHtml(outputs, images = []) {
  let p = 0
  const plot = () => (images[p] ? `<img alt="plot" src="${images[p++]}">` : (p++, '<p><em>[plot]</em></p>'))
  return outputs.map((o) => {
    switch (o.kind) {
      case 'math': return `<div class="math">${o.latex ? renderMath(o.latex, true, 'mathml') : `<code>${escapeHtml(o.text)}</code>`}</div>`
      case 'print': return `<div class="print">${escapeHtml(o.text)}</div>`
      case 'warning': return `<div class="warning">${escapeHtml(o.text)}</div>`
      case 'error': return `<div class="error">${escapeHtml(o.text)}</div>`
      case 'plot': return plot()
      case 'flex': {
        const r = o.result || {}
        const errs = (r.errors || []).map((e) => `<div class="error">${e.line ? `Line ${e.line}: ` : ''}${escapeHtml(e.msg)}</div>`).join('')
        const reps = (r.reports || []).map((x) => `<tr><td>${escapeHtml(x.label)}</td><td>${escapeHtml(fmt(x.value))}</td></tr>`).join('')
        return errs + (reps ? `<table>${reps}</table>` : '') + (r.plots || []).map(plot).join('')
      }
      default: return ''
    }
  }).join('\n')
}
