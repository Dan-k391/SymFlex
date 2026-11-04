// Notebook view: renders cells, Jupyter-style command/edit modes, execution queue.
import { setDiagnostics } from '@codemirror/lint'
import { EditorSelection } from '@codemirror/state'
import { EditorView } from '@codemirror/view'
import { createEditor, setLineNumbers } from './editor.js'
import { mapleUserNames, toDiagnostics } from './lang/assist.js'
import { renderMarkdown } from './markdown.js'
import { capOutputs, renderOutputs } from './output.js'
import * as model from './store.js'

const TYPE_LABEL = { maple: 'Maple', flexpde: 'FlexPDE', markdown: 'Text' }

const h = (tag, attrs = {}, ...kids) => {
  const e = document.createElement(tag)
  for (const [k, v] of Object.entries(attrs)) {
    if (k === 'class') e.className = v
    else if (k.startsWith('on')) e.addEventListener(k.slice(2), v)
    else e.setAttribute(k, v)
  }
  e.append(...kids)
  return e
}

const iconButton = (label, icon, onclick) =>
  h('button', { type: 'button', class: 'icon-btn', title: label, 'aria-label': label, onclick }, icon)

export class NotebookView extends EventTarget {
  /**
   * @param {object} o
   * @param {HTMLElement} o.root
   * @param {import('./kernel.js').MapleKernel} o.kernel
   * @param {import('./kernel.js').FlexRunner} o.flex
   * @param {(nb) => void} o.save   persist (debounced here)
   * @param {(msg, kind?) => void} o.toast
   */
  constructor({ root, kernel, flex, save, toast, lineNumbers = false }) {
    super()
    Object.assign(this, { root, kernel, flex, persist: save, toast, lineNumbers })
    this.views = new Map()     // cell id -> {el, editor, out, exec, input}
    this.queue = []
    this.running = null
    this.deleted = []
    this.counter = 0
    this.mode = 'command'
    this.lastKey = null
    root.addEventListener('keydown', (e) => this.#onKey(e))
    // Any notebook's Restart (or a Stop without interrupt support) wipes the shared Maple session.
    this.onKernelRestart = () => {
      this.counter = 0
      const queued = this.queue
      this.queue = []
      if (this.nb) for (const q of queued) { const c = this.nb.cells.find((x) => x.id === q); if (c) this.#renderCell(c) }
    }
    kernel.addEventListener('restart', this.onKernelRestart)
  }

  // ---- notebook lifecycle

  open(nb) {
    this.stopAll(true)
    this.nb = nb
    this.counter = Math.max(0, ...nb.cells.map((c) => c.execCount ?? 0))
    for (const v of this.views.values()) v.editor?.destroy()
    this.views.clear()
    this.root.replaceChildren(...nb.cells.map((c) => this.#buildCell(c)), this.#addBar())
    this.select(nb.cells[0].id)
  }

  #addBar() {
    const add = (type) => () => { const c = this.insertAt(this.nb.cells.length, type); this.edit(c.id) }
    return h('div', { class: 'add-bar' },
      h('button', { type: 'button', class: 'btn btn-ghost', onclick: add('maple') }, '+ Maple'),
      h('button', { type: 'button', class: 'btn btn-ghost', onclick: add('flexpde') }, '+ FlexPDE'),
      h('button', { type: 'button', class: 'btn btn-ghost', onclick: add('markdown') }, '+ Text'))
  }

  /** Debounced persist; also tells listeners (find) that cells changed. */
  save() {
    if (this.closed) return
    clearTimeout(this.saveTimer)
    this.saveTimer = setTimeout(() => this.persist(this.nb), 400)
    this.dispatchEvent(new Event('change'))
  }

  /** Tab closed: stops this notebook's runs, saves it (unless discarded) and frees the editors. */
  dispose({ discard = false } = {}) {
    this.stopAll()
    clearTimeout(this.saveTimer)
    if (!discard) this.persist(this.nb)
    this.closed = true
    this.kernel.removeEventListener('restart', this.onKernelRestart)
    for (const v of this.views.values()) v.editor?.destroy()
    this.views.clear()
    this.root.remove()
  }

  get cell() { return this.nb.cells.find((c) => c.id === this.selectedId) }

  // ---- cell DOM

  #buildCell(cell) {
    const exec = h('div', { class: 'cell-exec', 'aria-label': 'execution count' })
    const runBtn = iconButton('Run cell (Ctrl+Enter)', '▶', (e) => { e.stopPropagation(); this.run(cell.id, 'none') })
    runBtn.classList.add('run-btn')
    const typeSel = h('select', { class: 'cell-type', 'aria-label': 'Cell type', onchange: (e) => this.changeType(e.target.value, cell.id) },
      ...model.CELL_TYPES.map((t) => h('option', { value: t }, TYPE_LABEL[t])))
    typeSel.value = cell.type
    const tools = h('div', { class: 'cell-tools' },
      typeSel,
      iconButton('Move up', '↑', () => this.move(-1, cell.id)),
      iconButton('Move down', '↓', () => this.move(1, cell.id)),
      iconButton('Duplicate', '⧉', () => this.duplicate(cell.id)),
      iconButton('Collapse output (O)', '▾', () => this.toggleCollapse(cell.id)),
      iconButton('Delete (D,D)', '✕', () => this.delete(cell.id)))
    const input = h('div', { class: 'cell-input' })
    const out = h('div', { class: 'cell-output', 'aria-live': 'polite' })
    const collapsedBar = h('button', { type: 'button', class: 'collapsed-bar', onclick: () => this.toggleCollapse(cell.id) }, 'Output hidden: click to show')
    const el = h('div', { class: `cell type-${cell.type}`, 'data-id': cell.id, tabindex: '-1', role: 'group', 'aria-label': `${TYPE_LABEL[cell.type]} cell` },
      h('div', { class: 'cell-gutter' }, exec, runBtn),
      h('div', { class: 'cell-main' }, tools, input, out, collapsedBar))
    el.addEventListener('mousedown', (e) => {
      if (e.target.closest('.cell-tools, .cell-output button, .cell-output a, .cell-output input')) return
      if (this.selectedId !== cell.id) this.select(cell.id, { focus: false })
      if (!e.target.closest('.cell-input')) { this.mode = 'command'; this.#syncMode() }
    })
    const v = { el, input, out, exec, typeSel, editor: null }
    this.views.set(cell.id, v)
    this.#mountInput(cell)
    this.#renderCell(cell)
    return el
  }

  #mountInput(cell) {
    const v = this.views.get(cell.id)
    v.editor?.destroy()
    v.input.replaceChildren()
    v.el.className = `cell type-${cell.type}`
    v.typeSel.value = cell.type
    v.editor = createEditor({
      parent: v.input,
      type: cell.type,
      doc: cell.source,
      lineNumbers: this.lineNumbers,
      onChange: (text) => {
        cell.source = text
        if (cell.type === 'markdown') this.#renderMarkdown(cell)  // find's Replace can edit a rendered text cell
        this.save()
      },
      keys: {
        runAdvance: () => (this.run(cell.id, 'next'), true),
        runInPlace: () => (this.run(cell.id, 'none'), true),
        runInsert: () => (this.run(cell.id, 'insert'), true),
        escape: () => (this.command(), true),
        up: () => this.#neighbourEdit(cell.id, -1),
        down: () => this.#neighbourEdit(cell.id, 1),
      },
      assist: {
        userNames: () => mapleUserNames(this.nb.cells.filter((c) => c.type === 'maple').map((c) => c.source).join('\n')),
        kernelComplete: (p) => this.kernel.complete(p),
        flexLint: async (doc) => {
          try { return toDiagnostics(doc, await this.flex.lint(doc.toString())) } catch { return [] }
        },
      },
    })
    v.editor.contentDOM.addEventListener('focus', () => {
      if (this.selectedId !== cell.id) this.select(cell.id, { focus: false })
      this.mode = 'edit'
      this.#syncMode()
    })
    if (cell.type === 'markdown') {
      v.md = h('div', { class: 'md-rendered', ondblclick: () => this.edit(cell.id) })
      v.input.append(v.md)
      this.#renderMarkdown(cell)
    }
  }

  #renderMarkdown(cell) {
    const v = this.views.get(cell.id)
    const showEditor = !cell.source.trim() || (this.mode === 'edit' && this.selectedId === cell.id) || v.mdEditing
    v.md.innerHTML = showEditor ? '' : renderMarkdown(cell.source)
    v.md.hidden = showEditor
    v.input.classList.toggle('md-view', !showEditor)  // CSS hides the editor (.cm-editor forces display:flex)
  }

  #renderCell(cell) {
    const v = this.views.get(cell.id)
    const queued = this.queue.includes(cell.id) || this.running === cell.id
    v.exec.textContent = cell.type === 'markdown' ? '' : queued ? '[*]' : `[${cell.execCount ?? ' '}]`
    v.el.classList.toggle('running', queued)
    v.el.classList.toggle('collapsed', !!cell.collapsed && cell.outputs.length > 0)
    if (cell.type === 'markdown') return
    renderOutputs(v.out, cell.outputs, { toast: this.toast, onJump: (line) => this.jumpToLine(cell.id, line) })
  }

  jumpToLine(id, line) {
    const doc = this.views.get(id).editor.state.doc
    const l = doc.line(Math.min(Math.max(1, line), doc.lines))
    this.selectRange(id, l.from, l.to)
  }

  /** Edits a cell with [from, to) selected. */
  selectRange(id, from, to) {
    this.edit(id)
    this.views.get(id).editor.dispatch({ selection: EditorSelection.range(from, to), scrollIntoView: true })
  }

  /** Scrolls a position of a cell's source into view without taking focus (find); opens a rendered text cell. */
  reveal(id, pos) {
    const cell = this.nb.cells.find((c) => c.id === id), v = this.views.get(id)
    if (!cell || !v) return
    this.select(id, { focus: false, scroll: false })
    if (cell.type === 'markdown' && !v.mdEditing) { v.mdEditing = true; this.#renderMarkdown(cell) }
    v.editor.dispatch({ effects: EditorView.scrollIntoView(pos, { y: 'center' }) })
  }

  // ---- selection & modes

  select(id, { focus = true, scroll = true } = {}) {
    if (!this.views.has(id)) return
    const prev = this.selectedId
    this.selectedId = id
    for (const [cid, v] of this.views) v.el.classList.toggle('selected', cid === id)
    const v = this.views.get(id)
    if (prev && prev !== id) {
      const pc = this.nb.cells.find((c) => c.id === prev)
      if (pc?.type === 'markdown' && this.views.get(prev)) { this.views.get(prev).mdEditing = false; this.#renderMarkdown(pc) }
    }
    if (scroll) v.el.scrollIntoView({ block: 'nearest' })
    if (focus) {
      if (this.mode === 'edit') this.edit(id)
      else v.el.focus({ preventScroll: true })
    }
    this.dispatchEvent(new Event('select'))
  }

  edit(id = this.selectedId) {
    this.mode = 'edit'
    if (id !== this.selectedId) this.select(id, { focus: false })
    const cell = this.cell, v = this.views.get(id)
    if (cell.type === 'markdown') { v.mdEditing = true; this.#renderMarkdown(cell) }
    v.editor.focus()
    this.#syncMode()
  }

  command() {
    this.mode = 'command'
    const cell = this.cell, v = this.views.get(this.selectedId)
    if (cell?.type === 'markdown') { v.mdEditing = false; this.#renderMarkdown(cell) }
    v?.el.focus({ preventScroll: true })
    this.#syncMode()
  }

  #syncMode() {
    this.root.classList.toggle('mode-edit', this.mode === 'edit')
    for (const [cid, v] of this.views) v.el.classList.toggle('editing', this.mode === 'edit' && cid === this.selectedId)
    this.dispatchEvent(new Event('mode'))
  }

  #neighbourEdit(id, dir) {
    const i = model.indexOf(this.nb, id) + dir
    const target = this.nb.cells[i]
    if (!target) return false
    this.edit(target.id)
    const ed = this.views.get(target.id).editor
    const pos = dir < 0 ? ed.state.doc.length : 0
    ed.dispatch({ selection: { anchor: pos } })
    return true
  }

  selectRelative(dir) {
    const i = model.indexOf(this.nb, this.selectedId) + dir
    if (this.nb.cells[i]) this.select(this.nb.cells[i].id)
  }

  // ---- structure edits

  insertAt(index, type = 'maple', source = '') {
    const cell = model.insertCell(this.nb, index, model.newCell(type, source))
    const el = this.#buildCell(cell)
    const next = this.nb.cells[index + 1]
    this.root.insertBefore(el, next ? this.views.get(next.id).el : this.root.querySelector('.add-bar'))
    this.select(cell.id, { focus: false })
    this.save()
    return cell
  }

  insert(where, type = 'maple') {
    const i = model.indexOf(this.nb, this.selectedId)
    const cell = this.insertAt(where === 'above' ? i : i + 1, type)
    this.mode === 'edit' ? this.edit(cell.id) : this.command()
    return cell
  }

  delete(id = this.selectedId) {
    const i = model.indexOf(this.nb, id)
    const rec = model.deleteCell(this.nb, id)
    if (!rec) return
    if (this.queue.includes(id)) this.queue = this.queue.filter((q) => q !== id)
    this.deleted.push(rec)
    const v = this.views.get(id)
    v.editor.destroy()
    v.el.remove()
    this.views.delete(id)
    if (!this.views.size) {  // deleteCell added a fresh cell
      const c = this.nb.cells[0]
      this.root.prepend(this.#buildCell(c))
    }
    this.select(this.nb.cells[Math.min(i, this.nb.cells.length - 1)].id)
    this.mode = 'command'
    this.#syncMode()
    this.toast('Cell deleted. Press Z to undo.')
    this.save()
  }

  undoDelete() {
    const rec = this.deleted.pop()
    if (!rec) return this.toast('Nothing to undo')
    const cell = model.insertCell(this.nb, rec.index, rec.cell)
    const el = this.#buildCell(cell)
    const next = this.nb.cells[model.indexOf(this.nb, cell.id) + 1]
    this.root.insertBefore(el, next ? this.views.get(next.id).el : this.root.querySelector('.add-bar'))
    this.select(cell.id)
    this.save()
  }

  move(delta, id = this.selectedId) {
    if (!model.moveCell(this.nb, id, delta)) return
    const el = this.views.get(id).el
    if (delta < 0) el.previousElementSibling?.before(el)
    else el.nextElementSibling?.after(el)
    this.select(id, { focus: this.mode === 'command' })
    this.save()
  }

  duplicate(id = this.selectedId) {
    const copy = model.duplicateCell(this.nb, id)
    this.views.get(id).el.after(this.#buildCell(copy))
    this.select(copy.id)
    this.save()
  }

  changeType(type, id = this.selectedId) {
    const cell = this.nb.cells.find((c) => c.id === id)
    if (!model.setCellType(cell, type)) return
    this.#mountInput(cell)
    this.#renderCell(cell)
    this.views.get(id).el.classList.add('selected')
    this.save()
  }

  toggleCollapse(id = this.selectedId) {
    const cell = this.nb.cells.find((c) => c.id === id)
    cell.collapsed = !cell.collapsed
    this.#renderCell(cell)
    this.save()
  }

  clearOutputs() {
    model.clearOutputs(this.nb)
    for (const c of this.nb.cells) this.#renderCell(c)
    this.save()
  }

  setLineNumbers(on) {
    this.lineNumbers = on
    for (const v of this.views.values()) setLineNumbers(v.editor, on)
  }

  /** Inserts text at the cursor of the selected cell (help panel "Insert"). */
  insertText(text) {
    const v = this.views.get(this.selectedId)
    if (!v) return
    const ed = v.editor
    const { from, to } = ed.state.selection.main
    ed.dispatch({ changes: { from, to, insert: text }, selection: { anchor: from + text.length } })
    this.edit()
  }

  // ---- execution

  /** @param {'none'|'next'|'insert'} advance */
  run(id = this.selectedId, advance = 'none') {
    const cell = this.nb.cells.find((c) => c.id === id)
    if (!cell) return
    const wasEdit = this.mode === 'edit'
    if (cell.type === 'markdown') {
      this.views.get(id).mdEditing = false
      this.mode = 'command'
      this.#renderMarkdown(cell)
    } else this.enqueue([id])
    if (advance === 'insert' || (advance === 'next' && model.indexOf(this.nb, id) === this.nb.cells.length - 1)) {
      const c = this.insertAt(model.indexOf(this.nb, id) + 1, cell.type === 'markdown' ? 'maple' : cell.type)
      this.edit(c.id)
    } else if (advance === 'next') {
      this.mode = wasEdit && cell.type !== 'markdown' ? 'edit' : 'command'
      this.selectRelative(1)
    } else if (cell.type === 'markdown') this.command()
    this.#syncMode()
  }

  runAll() { this.enqueue(this.nb.cells.map((c) => c.id)) }
  runAbove() { this.enqueue(this.nb.cells.slice(0, model.indexOf(this.nb, this.selectedId)).map((c) => c.id)) }
  runBelow() { this.enqueue(this.nb.cells.slice(model.indexOf(this.nb, this.selectedId)).map((c) => c.id)) }

  enqueue(ids) {
    for (const id of ids) {
      const cell = this.nb.cells.find((c) => c.id === id)
      if (cell.type === 'markdown') { this.#renderMarkdown(cell); continue }
      if (!this.queue.includes(id) && this.running !== id) this.queue.push(id)
      this.#renderCell(cell)
    }
    this.#drain()
  }

  async #drain() {
    if (this.running) return
    while (this.queue.length) {
      const id = this.queue.shift()
      const cell = this.nb.cells.find((c) => c.id === id)
      if (!cell) continue
      this.running = id
      this.dispatchEvent(new Event('busy'))
      try {
        if (cell.type === 'maple') await this.#runMaple(cell)
        else await this.#runFlex(cell)
      } catch (e) {
        if (!e.interrupted) cell.outputs = [{ kind: 'error', text: `Error, ${e.message}` }]
        else if (this.running === id) cell.outputs = [...cell.outputs, { kind: 'warning', text: 'Warning, computation stopped' }]
      }
      if (this.running === id) {
        this.running = null
        if (this.views.has(id)) this.#renderCell(cell)
      }
      this.save()
    }
    this.running = null
    this.dispatchEvent(new Event('idle'))
  }

  async #runMaple(cell) {
    cell.outputs = capOutputs(await this.kernel.run(cell.source, this))
    cell.execCount = ++this.counter
  }

  async #runFlex(cell) {
    const v = this.views.get(cell.id)
    const live = h('div', { class: 'flex-progress' }, h('span', { class: 'spinner', 'aria-hidden': 'true' }), h('span', {}, 'Running FlexPDE…'))
    const t0 = performance.now()
    v.out.replaceChildren(live)
    const result = await this.flex.run(cell.source, (msg) => {
      const text = typeof msg === 'string' ? msg : msg?.msg ?? msg?.message ?? (msg?.t != null ? `t = ${(+msg.t).toPrecision(4)}` : JSON.stringify(msg))
      live.lastChild.textContent = `${text}   (${((performance.now() - t0) / 1000).toFixed(1)} s)`
    }, this)
    cell.outputs = [{ kind: 'flex', result }]
    cell.execCount = ++this.counter
    const ed = this.views.get(cell.id)?.editor
    if (ed && result?.errors?.length) ed.dispatch(setDiagnostics(ed.state, toDiagnostics(ed.state.doc, result.errors.filter((e) => e.line))))
  }

  /** Cancels the queue and stops whatever is running. */
  stopAll(silent = false) {
    const queued = this.queue
    this.queue = []
    const id = this.running
    if (this.nb) for (const q of queued) { const c = this.nb.cells.find((x) => x.id === q); if (c) this.#renderCell(c) }
    if (!id) return
    const cell = this.nb.cells.find((c) => c.id === id)
    if (cell?.type === 'flexpde') { this.flex.interrupt(this); return }
    // The kernel is shared: only interrupt when it is executing this notebook's cell.
    if (!this.kernel.isRunning(this)) { this.kernel.cancel(this); return }
    const survived = this.kernel.interrupt()
    if (!survived && !silent) {
      this.toast('Kernel restarted: Maple state was lost (no interrupt support in this browser context).', 'warn')
    }
  }

  async restart(thenRunAll = false) {
    this.stopAll(true)
    this.counter = 0
    await this.kernel.reset().catch(() => {})
    this.toast('Kernel restarted')
    if (thenRunAll) this.runAll()
  }

  // ---- command-mode keyboard

  #onKey(e) {
    if (e.target.closest?.('.cm-editor, input, select, textarea')) return
    if (this.mode !== 'command' || !this.nb) return
    const k = e.key, mod = e.ctrlKey || e.metaKey
    const double = (key) => { const hit = this.lastKey === key && Date.now() - this.lastKeyTime < 600; this.lastKey = hit ? null : key; this.lastKeyTime = Date.now(); return hit }
    const act = {
      Enter: () => (e.shiftKey ? this.run(undefined, 'next') : mod ? this.run(undefined, 'none') : e.altKey ? this.run(undefined, 'insert') : this.edit()),
      ArrowUp: () => (e.altKey ? this.move(-1) : this.selectRelative(-1)),
      ArrowDown: () => (e.altKey ? this.move(1) : this.selectRelative(1)),
      k: () => this.selectRelative(-1),
      j: () => this.selectRelative(1),
      a: () => this.insert('above'),
      b: () => this.insert('below'),
      d: () => double('d') && this.delete(),
      z: () => this.undoDelete(),
      m: () => this.changeType('markdown'),
      y: () => this.changeType('maple'),
      f: () => this.changeType('flexpde'),
      o: () => this.toggleCollapse(),
      i: () => double('i') && this.stopAll(),
      0: () => double('0') && this.restart(),
    }[k.length === 1 ? k.toLowerCase() : k]
    if (!act || (mod && k !== 'Enter')) return
    e.preventDefault()
    act()
  }
}
