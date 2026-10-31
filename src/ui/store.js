// Notebook model and localStorage persistence. Pure data: no DOM here.

export const CELL_TYPES = ['maple', 'flexpde', 'markdown']
const PREFIX = 'symflex.'

export const uid = () => Math.random().toString(36).slice(2, 10) + Date.now().toString(36).slice(-4)

export function newCell(type = 'maple', source = '') {
  if (!CELL_TYPES.includes(type)) throw new Error(`unknown cell type ${type}`)
  return { id: uid(), type, source, outputs: [], execCount: null, collapsed: false }
}

export function newNotebook(name = 'Untitled', cells = [newCell()]) {
  const now = Date.now()
  return { id: uid(), name, created: now, modified: now, cells }
}

// ---- cell operations (mutate the notebook, return what the UI needs)

export const indexOf = (nb, id) => nb.cells.findIndex((c) => c.id === id)

export function insertCell(nb, index, cell = newCell()) {
  nb.cells.splice(Math.max(0, Math.min(index, nb.cells.length)), 0, cell)
  return cell
}

/** Removes a cell; returns an undo record {cell, index}. Keeps at least one cell. */
export function deleteCell(nb, id) {
  const index = indexOf(nb, id)
  if (index < 0) return null
  const [cell] = nb.cells.splice(index, 1)
  if (!nb.cells.length) nb.cells.push(newCell())
  return { cell, index }
}

export function moveCell(nb, id, delta) {
  const i = indexOf(nb, id), j = i + delta
  if (i < 0 || j < 0 || j >= nb.cells.length) return false
  ;[nb.cells[i], nb.cells[j]] = [nb.cells[j], nb.cells[i]]
  return true
}

export function duplicateCell(nb, id) {
  const i = indexOf(nb, id)
  const copy = { ...structuredClone(nb.cells[i]), id: uid() }
  nb.cells.splice(i + 1, 0, copy)
  return copy
}

export function setCellType(cell, type) {
  if (!CELL_TYPES.includes(type) || cell.type === type) return false
  cell.type = type
  cell.outputs = []
  cell.execCount = null
  return true
}

export function clearOutputs(nb) {
  for (const c of nb.cells) { c.outputs = []; c.execCount = null }
}

// ---- file format (.symflex.json)

export function toFile(nb) {
  return { format: 'symflex', version: 1, name: nb.name,
    cells: nb.cells.map(({ type, source, outputs, execCount, collapsed }) => ({ type, source, outputs, execCount, collapsed })) }
}

/** Validates untrusted JSON and returns a fresh notebook. */
export function fromFile(data, fallbackName = 'Imported') {
  if (!data || data.format !== 'symflex' || !Array.isArray(data.cells)) throw new Error('not a SymFlex notebook')
  const cells = data.cells.map((c) => {
    const cell = newCell(CELL_TYPES.includes(c?.type) ? c.type : 'maple', String(c?.source ?? ''))
    if (Array.isArray(c.outputs)) cell.outputs = c.outputs.filter((o) => o && typeof o.kind === 'string')
    cell.execCount = Number.isInteger(c.execCount) ? c.execCount : null
    cell.collapsed = !!c.collapsed
    return cell
  })
  return newNotebook(String(data.name || fallbackName), cells.length ? cells : [newCell()])
}

// ---- localStorage

export class NotebookStore {
  constructor(storage = globalThis.localStorage) { this.storage = storage }

  #get(key) {
    try { return JSON.parse(this.storage.getItem(PREFIX + key)) } catch { return null }
  }

  #set(key, value) {
    try { this.storage.setItem(PREFIX + key, JSON.stringify(value)); return true } catch { return false }
  }

  /** [{id, name, modified}] newest first. */
  list() {
    return (this.#get('index') || []).sort((a, b) => b.modified - a.modified)
  }

  load(id) {
    const nb = this.#get('nb.' + id)
    return nb && Array.isArray(nb.cells) ? nb : null
  }

  /** Saves; when the quota is exceeded retries without plot outputs. Returns false on failure. */
  save(nb) {
    nb.modified = Date.now()
    let ok = this.#set('nb.' + nb.id, nb)
    if (!ok) {
      const slim = { ...nb, cells: nb.cells.map((c) => ({ ...c, outputs: c.outputs.filter((o) => o.kind !== 'plot' && o.kind !== 'flex') })) }
      ok = this.#set('nb.' + nb.id, slim)
    }
    const index = this.list().filter((e) => e.id !== nb.id)
    index.push({ id: nb.id, name: nb.name, modified: nb.modified })
    this.#set('index', index)
    return ok
  }

  remove(id) {
    try { this.storage.removeItem(PREFIX + 'nb.' + id) } catch { /* storage unavailable */ }
    this.#set('index', this.list().filter((e) => e.id !== id))
  }

  getSetting(key, fallback) { return this.#get('setting.' + key) ?? fallback }
  setSetting(key, value) { this.#set('setting.' + key, value) }
}
