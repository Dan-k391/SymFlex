// Notebook find and replace (Ctrl+F, Ctrl+H, F3): searches every cell of the open notebook and
// highlights the matches in the cell editors.
import { showFindMatches } from './editor.js'

/** Compiles the query to a global RegExp, or null when empty. Throws SyntaxError on a bad regex. */
export function findPattern(query, { matchCase = false, wholeWord = false, regex = false } = {}) {
  if (!query) return null
  const src = regex ? query : query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  return new RegExp(wholeWord ? `\\b(?:${src})\\b` : src, matchCase ? 'gm' : 'gim')  // m: ^ and $ match per line
}

/** Non-empty matches of a global RegExp: [{from, to, m}]. */
export function findMatches(text, re) {
  const out = []
  for (const m of text.matchAll(re)) if (m[0]) out.push({ from: m.index, to: m.index + m[0].length, m })
  return out
}

/** Replacement for one match: in regex mode $&, $1.. and $$ expand like String.replace ($10 is $1 then 0 with < 10 groups). */
export const expandReplacement = (tpl, m, regex) => (!regex ? tpl
  : tpl.replace(/\$(\$|&|\d{1,2})/g, (s, k) => {
    if (k === '$') return '$'
    if (k === '&') return m[0]
    const group = (n) => n > 0 && n < m.length
    if (group(+k)) return m[+k] ?? ''
    return k.length === 2 && group(+k[0]) ? (m[+k[0]] ?? '') + k[1] : s
  }))

const h = (tag, attrs = {}, ...kids) => {
  const e = document.createElement(tag)
  for (const [k, v] of Object.entries(attrs)) {
    if (k.startsWith('on')) e.addEventListener(k.slice(2), v)
    else e.setAttribute(k, v)
  }
  e.append(...kids)
  return e
}

export class FindBar {
  /**
   * @param {object} o
   * @param {HTMLElement} o.parent
   * @param {() => import('./notebook.js').NotebookView | null} o.getView  the active notebook
   */
  constructor({ parent, getView }) {
    this.getView = getView
    this.opts = { matchCase: false, wholeWord: false, regex: false }
    this.matches = []          // [{cellId, from, to, m}] in notebook order
    this.current = -1
    this.painted = new Map()   // editor -> {key, doc} last drawn, to skip redundant dispatches

    const opt = (name, label, text) => h('button', {
      type: 'button', class: 'find-opt', 'aria-pressed': 'false', title: label, 'aria-label': label,
      onclick: (e) => {
        this.opts[name] = !this.opts[name]
        e.currentTarget.setAttribute('aria-pressed', String(this.opts[name]))
        this.refresh({ restart: true })
      },
    }, text)
    const btn = (label, text, onclick, cls = 'icon-btn') => h('button', { type: 'button', class: cls, title: label, 'aria-label': label, onclick }, text)

    this.input = h('input', { type: 'text', placeholder: 'Find', 'aria-label': 'Find in notebook', spellcheck: 'false', autocomplete: 'off' })
    this.replaceInput = h('input', { type: 'text', placeholder: 'Replace', 'aria-label': 'Replace with', spellcheck: 'false', autocomplete: 'off' })
    this.count = h('span', { class: 'find-count', 'aria-live': 'polite' })
    this.toggle = btn('Toggle replace (Ctrl+H)', '›', () => this.#setReplace(!this.replaceOpen), 'icon-btn find-toggle')
    this.prevBtn = btn('Previous match (Shift+Enter)', '↑', () => this.next(-1))
    this.nextBtn = btn('Next match (Enter)', '↓', () => this.next(1))
    this.replaceBtn = btn('Replace (Enter)', 'Replace', () => this.replaceOne(), 'btn btn-small')
    this.replaceAllBtn = btn('Replace all (Ctrl+Enter)', 'All', () => this.replaceAll(), 'btn btn-small')
    this.replaceRow = h('div', { class: 'find-row' },
      h('div', { class: 'find-field' }, this.replaceInput), this.replaceBtn, this.replaceAllBtn)
    this.el = h('div', { class: 'findbar', role: 'search', 'aria-label': 'Find in notebook' },
      this.toggle,
      h('div', { class: 'find-rows' },
        h('div', { class: 'find-row' },
          h('div', { class: 'find-field' }, this.input,
            opt('matchCase', 'Match case (Alt+C)', 'Aa'), opt('wholeWord', 'Whole word (Alt+W)', 'ab'), opt('regex', 'Regular expression (Alt+R)', '.*')),
          this.count, this.prevBtn, this.nextBtn, btn('Close (Esc)', '✕', () => this.close())),
        this.replaceRow))
    this.el.hidden = true
    this.#setReplace(false)
    parent.append(this.el)

    this.input.addEventListener('input', () => this.refresh({ restart: true }))
    this.el.addEventListener('keydown', (e) => this.#barKey(e))
    window.addEventListener('keydown', (e) => this.#globalKey(e), true)
  }

  get isOpen() { return !this.el.hidden }

  open(replace = false) {
    const view = this.getView()
    if (!view) return
    if (!this.isOpen) this.returnFocus = document.activeElement
    const ed = view.views.get(view.selectedId)?.editor
    const sel = ed?.hasFocus && ed.state.sliceDoc(ed.state.selection.main.from, ed.state.selection.main.to)
    if (sel && !sel.includes('\n')) this.input.value = sel
    this.el.hidden = false
    if (replace) this.#setReplace(true)
    ;(replace && this.input.value ? this.replaceInput : this.input).focus()
    if (!replace || !this.input.value) this.input.select()
    this.refresh({ restart: true })
  }

  /** Hides the bar; the current match (if any) becomes the editor selection. */
  close() {
    if (!this.isOpen) return
    const hit = this.matches[this.current]
    this.el.hidden = true
    this.matches = []
    this.current = -1
    this.#paint()
    const view = this.getView()
    if (hit && view?.views.has(hit.cellId)) view.selectRange(hit.cellId, hit.from, hit.to)
    else if (this.returnFocus?.isConnected && this.returnFocus.checkVisibility?.()) this.returnFocus.focus()
    else view?.command()
  }

  /** Re-runs the search soon (cells changed); never inside an editor update. */
  schedule() {
    if (!this.isOpen) return
    clearTimeout(this.timer)
    this.timer = setTimeout(() => this.refresh(), 60)
  }

  /**
   * Re-runs the search. restart: the query changed, so jump to the first match from the selected cell;
   * otherwise keep the current match (or the next one after `anchor`).
   */
  refresh({ restart = false, anchor } = {}) {
    if (!this.isOpen) return
    const view = this.getView()
    if (!view) return this.close()
    let re = null
    this.error = false
    try { re = findPattern(this.input.value, this.opts) } catch { this.error = true }
    const pos = new Map(view.nb.cells.map((c, i) => [c.id, i]))
    const prev = this.matches[this.current]
    const jump = restart || !!anchor  // background refreshes (typing elsewhere) must not scroll
    anchor ??= restart ? { cellId: view.selectedId, at: 0 } : prev && { cellId: prev.cellId, at: prev.from }
    this.matches = []
    if (re) {
      for (const c of view.nb.cells) {
        const ed = view.views.get(c.id)?.editor
        if (ed) for (const hit of findMatches(ed.state.doc.toString(), re)) this.matches.push({ cellId: c.id, ...hit })
      }
    }
    const key = (cellId, at) => (pos.get(cellId) ?? 0) * 2 ** 32 + at
    const from = anchor ? key(anchor.cellId, anchor.at) : 0
    const i = this.matches.findIndex((x) => key(x.cellId, x.from) >= from)
    this.current = this.matches.length ? (i < 0 ? 0 : i) : -1
    this.#paint()
    this.#showCount()
    if (jump) this.#reveal()
  }

  next(dir = 1) {
    if (!this.isOpen) this.open()
    const n = this.matches.length
    if (!n) return
    this.current = (this.current + dir + n) % n
    this.#paint()
    this.#showCount()
    // F3 while typing in a cell: move the caret too, so the cell being edited and the selected cell agree.
    const hit = this.matches[this.current]
    if (document.activeElement?.closest?.('.cm-editor')) this.getView().selectRange(hit.cellId, hit.from, hit.to)
    else this.#reveal()
  }

  replaceOne() {
    const hit = this.matches[this.current]
    const ed = hit && this.getView()?.views.get(hit.cellId)?.editor
    if (!ed) return
    const insert = expandReplacement(this.replaceInput.value, hit.m, this.opts.regex)
    ed.dispatch({ changes: { from: hit.from, to: hit.to, insert } })
    this.refresh({ anchor: { cellId: hit.cellId, at: hit.from + insert.length } })
  }

  replaceAll() {
    const view = this.getView()
    if (!view || !this.matches.length) return
    const byCell = new Map()
    for (const x of this.matches) byCell.set(x.cellId, [...(byCell.get(x.cellId) ?? []), x])
    const n = this.matches.length
    for (const [cellId, hits] of byCell) {
      view.views.get(cellId)?.editor.dispatch({
        changes: hits.map((x) => ({ from: x.from, to: x.to, insert: expandReplacement(this.replaceInput.value, x.m, this.opts.regex) })),
      })
    }
    clearTimeout(this.timer)  // the edits scheduled a refresh that would overwrite the message
    this.refresh()
    this.count.textContent = `Replaced ${n}`
  }

  #setReplace(on) {
    this.replaceOpen = on
    this.replaceRow.hidden = !on
    this.toggle.setAttribute('aria-expanded', String(on))
    this.toggle.classList.toggle('open', on)
  }

  #showCount() {
    const q = this.input.value, n = this.matches.length
    this.count.textContent = this.error ? 'Invalid regex' : !q ? '' : n ? `${this.current + 1} of ${n}` : 'No results'
    this.count.classList.toggle('none', !!q && !n)
    for (const b of [this.prevBtn, this.nextBtn, this.replaceBtn, this.replaceAllBtn]) b.disabled = !n
  }

  #reveal() {
    const hit = this.matches[this.current]
    if (hit) this.getView()?.reveal(hit.cellId, hit.from)
  }

  /** Draws this.matches into the editors; clears editors that no longer have any. */
  #paint() {
    const view = this.getView()
    const ranges = new Map()
    this.matches.forEach((x, i) => {
      const ed = view?.views.get(x.cellId)?.editor
      if (!ed) return
      if (!ranges.has(ed)) ranges.set(ed, [])
      ranges.get(ed).push([x.from, x.to, i === this.current])
    })
    const painted = new Map()
    for (const [ed, r] of ranges) {
      const key = JSON.stringify(r), was = this.painted.get(ed)
      if (was?.key !== key || was.doc !== ed.state.doc) showFindMatches(ed, r)
      painted.set(ed, { key, doc: ed.state.doc })
    }
    for (const ed of this.painted.keys()) if (!ranges.has(ed) && ed.dom.isConnected) showFindMatches(ed, [])
    this.painted = painted
  }

  #barKey(e) {
    const inReplace = e.target === this.replaceInput
    if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); this.close() }
    else if (e.key === 'Enter' && inReplace) { e.preventDefault(); (e.ctrlKey || e.metaKey ? this.replaceAll() : this.replaceOne()) }
    else if (e.key === 'Enter' && e.target === this.input) { e.preventDefault(); this.next(e.shiftKey ? -1 : 1) }
    else if (e.altKey && !e.ctrlKey && ['c', 'w', 'r'].includes(e.key.toLowerCase())) {
      e.preventDefault()
      this.el.querySelectorAll('.find-opt')[['c', 'w', 'r'].indexOf(e.key.toLowerCase())].click()
    }
  }

  #globalKey(e) {
    const k = e.key.toLowerCase()
    if ((e.ctrlKey || e.metaKey) && !e.altKey && !e.shiftKey && k === 'f') {
      e.preventDefault(); e.stopPropagation(); this.open()
    } else if (e.ctrlKey && !e.altKey && !e.shiftKey && k === 'h') {
      e.preventDefault(); e.stopPropagation(); this.open(true)
    } else if (e.key === 'F3' && this.isOpen) {
      e.preventDefault(); e.stopPropagation(); this.next(e.shiftKey ? -1 : 1)
    }
  }
}
