// App shell: wires the notebook tabs, kernels, menus, sidebar, find bar, files and theme.
import 'katex/dist/katex.min.css'
import './styles.css'
import { showContextMenu } from './contextmenu.js'
import { FindBar } from './find.js'
import { exportHtml, exportJson, exportMpl, exportPde, importFile } from './io.js'
import { FlexRunner, MapleKernel } from './kernel.js'
import { renderMarkdown } from './markdown.js'
import { NotebookView } from './notebook.js'
import { outputsToHtml } from './output.js'
import { plotImage, rethemePlots } from './plot.js'
import { initSidebar } from './sidebar.js'
import { newCell, newNotebook, NotebookStore } from './store.js'

const $ = (sel) => document.querySelector(sel)
const store = new NotebookStore()

// ---- toasts

function toast(msg, kind = 'info', action) {
  const t = document.createElement('div')
  t.className = `toast toast-${kind}`
  t.textContent = msg
  if (action) {
    const b = document.createElement('button')
    b.type = 'button'
    b.className = 'btn btn-small'
    b.textContent = action.label
    b.onclick = () => { action.run(); t.remove() }
    t.append(b)
  }
  $('#toasts').append(t)
  setTimeout(() => t.classList.add('out'), kind === 'error' ? 7000 : 3500)
  setTimeout(() => t.remove(), kind === 'error' ? 7400 : 3900)
}

// ---- theme

function applyTheme(theme) {
  document.documentElement.dataset.theme = theme
  store.setSetting('theme', theme)
  rethemePlots()
}
const currentTheme = () => document.documentElement.dataset.theme ||
  (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light')

// ---- kernels + view

// One Maple kernel (one Maple session) and one FlexPDE runner shared by every tab.
const kernel = new MapleKernel()
const flex = new FlexRunner()

const pill = $('#kernel-pill')
kernel.addEventListener('status', ({ detail: d }) => {
  pill.dataset.state = d.status
  $('#boot-progress').hidden = d.status !== 'loading'
  $('#boot-progress').style.setProperty('--pct', `${Math.max(3, d.pct ?? 0)}%`)
  pill.textContent = d.status === 'loading' ? `Maple: ${d.msg || 'loading'} ${Math.round(d.pct ?? 0)}%`
    : d.status === 'error' ? 'Maple: failed' : `Maple: ${d.status}`
  pill.title = d.status === 'error' ? d.msg : kernel.interruptible ? 'Interrupts supported' : 'Interrupt restarts the kernel'
  // Show the exception line, not the whole traceback (the cell output has the full text).
  if (d.status === 'error') toast(`Maple kernel failed to start: ${String(d.msg).trim().split('\n').at(-1)}`, 'error')
})
// ---- notebook tabs: one NotebookView per open notebook, built the first time its tab is shown

const tabs = []    // [{id, name, nb?, view?}] in strip order; nb is held only until the view exists
let view = null    // the active tab's view; null when no tab is open
const tabOf = (id) => tabs.find((t) => t.id === id)
const strip = $('#tabstrip')

const syncBusy = () => { $('#btn-stop').disabled = !view?.running }
const syncMode = () => {
  $('#mode-pill').textContent = view?.mode === 'edit' ? 'Edit' : 'Command'
  $('#mode-pill').dataset.mode = view?.mode ?? 'command'
}
let onViewIdle = () => {}

function makeView(nb) {
  const root = Object.assign(document.createElement('div'), { className: 'notebook', hidden: true })
  root.setAttribute('aria-label', 'Notebook cells')
  $('#notebooks').append(root)
  const v = new NotebookView({
    root, kernel, flex, toast,
    lineNumbers: store.getSetting('lineNumbers', false),
    save: (nb) => { if (!store.save(nb)) toast('Could not autosave: browser storage is full or disabled', 'warn'); sidebar.refresh() },
  })
  const busy = () => {
    strip.querySelector(`[data-id="${v.nb.id}"]`)?.classList.toggle('busy', !!v.running)
    if (v === view) syncBusy()
  }
  v.addEventListener('busy', busy)
  v.addEventListener('idle', () => { busy(); onViewIdle() })
  v.addEventListener('mode', () => { if (v === view) syncMode() })
  v.addEventListener('change', () => { if (v === view) find.schedule() })
  v.open(nb)
  return v
}

function persistTabs() {
  store.setSetting('tabs', tabs.map((t) => t.id))
  if (view) store.setSetting('last', view.nb.id)
}

function renderTabs() {
  strip.replaceChildren(...tabs.map((t) => {
    const on = t.view != null && t.view === view
    const el = document.createElement('div')
    el.className = 'tab' + (t.view?.running ? ' busy' : '')
    Object.assign(el, { draggable: true, tabIndex: on ? 0 : -1, title: t.name })
    el.dataset.id = t.id
    el.setAttribute('role', 'tab')
    el.setAttribute('aria-selected', String(on))
    el.setAttribute('aria-controls', 'notebooks')
    const name = Object.assign(document.createElement('span'), { className: 'tab-name', textContent: t.name })
    const close = Object.assign(document.createElement('button'), { type: 'button', className: 'tab-close', textContent: '✕', tabIndex: -1 })
    close.setAttribute('aria-label', `Close ${t.name}`)
    el.append(Object.assign(document.createElement('span'), { className: 'spinner tab-spin' }), name, close)
    return el
  }))
  strip.querySelector('[aria-selected="true"]')?.scrollIntoView({ block: 'nearest', inline: 'nearest' })
}

/** Shows a tab (building its view on first show). focus: move keyboard focus into the notebook. */
function activate(id, { focus = true } = {}) {
  const t = tabOf(id)
  if (!t) return
  if (!t.view) {
    const nb = t.nb ?? store.load(id)
    if (!nb) { toast('Notebook not found', 'error'); return closeTab(id) }
    t.view = makeView(nb)
    delete t.nb
  }
  for (const o of tabs) if (o.view) o.view.root.hidden = o !== t
  $('#empty-state').hidden = true
  view = t.view
  $('#nb-name').value = view.nb.name
  $('#nb-name').disabled = false
  document.title = `${view.nb.name} · SymFlex`
  persistTabs()
  renderTabs()
  sidebar.refresh()
  syncBusy()
  syncMode()
  find.refresh({ restart: true })
  if (focus) view.command()
}

/** Opens notebooks in new tabs right of the active one (or switches to an open one), then shows the first. */
function openNotebooks(list) {
  if (!list.length) return
  if (narrow.matches) setSidebarHidden(true)
  let at = view ? tabs.findIndex((t) => t.view === view) + 1 : tabs.length
  for (const nb of list) {
    if (tabOf(nb.id)) continue
    store.save(nb)
    tabs.splice(at++, 0, { id: nb.id, name: nb.name, nb })
  }
  activate(list[0].id)
}
const openNotebook = (nb) => openNotebooks([nb])

function openById(id) {
  if (tabOf(id)) {
    if (narrow.matches) setSidebarHidden(true)
    return activate(id)
  }
  const nb = store.load(id)
  if (nb) openNotebook(nb)
  else toast('Notebook not found', 'error')
}

/** discard: the notebook is being deleted, so it is not saved on the way out. */
function closeTab(id, { discard = false } = {}) {
  const i = tabs.findIndex((t) => t.id === id)
  if (i < 0) return
  const [t] = tabs.splice(i, 1)
  t.view?.dispose({ discard })
  if (!view || t.view === view) {  // also when no tab is active (a tab failed to load)
    view = null
    const next = tabs[i] ?? tabs[i - 1]
    if (next) return activate(next.id)
    $('#empty-state').hidden = false
    $('#nb-name').value = ''
    $('#nb-name').disabled = true
    document.title = 'SymFlex'
    find.close()
    syncBusy()
    syncMode()
    sidebar.refresh()
  }
  persistTabs()
  renderTabs()
  if (document.activeElement === document.body) view?.command()  // the clicked close button is gone
}

// Close the active tab last, so the fallback is a surviving tab rather than one about to close.
const closeTabs = (ids) => {
  const active = view?.nb.id
  for (const id of ids) if (id !== active) closeTab(id)
  if (ids.includes(active)) closeTab(active)
}

strip.addEventListener('click', (e) => {
  const tab = e.target.closest('.tab')
  if (!tab) return
  if (e.target.closest('.tab-close')) closeTab(tab.dataset.id)
  else if (tabOf(tab.dataset.id)?.view !== view) activate(tab.dataset.id)
})
strip.addEventListener('mousedown', (e) => { if (e.button === 1) e.preventDefault() })  // no autoscroll on middle click
strip.addEventListener('auxclick', (e) => {
  const tab = e.target.closest('.tab')
  if (tab && e.button === 1) closeTab(tab.dataset.id)
})
$('.tabbar').addEventListener('dblclick', (e) => { if (e.target === e.currentTarget || e.target === strip) commands.new() })
strip.addEventListener('wheel', (e) => {
  if (!e.deltaY || e.deltaX) return
  strip.scrollLeft += e.deltaY
  e.preventDefault()
}, { passive: false })
strip.addEventListener('keydown', (e) => {
  const tab = e.target.closest('.tab')
  if (!tab) return
  const i = tabs.findIndex((t) => t.id === tab.dataset.id)
  const d = { ArrowLeft: -1, ArrowRight: 1 }[e.key]
  if (d) {
    e.preventDefault()
    const next = tabs[(i + d + tabs.length) % tabs.length]
    activate(next.id, { focus: false })
    strip.querySelector(`[data-id="${next.id}"]`)?.focus()
  } else if (e.key === 'Enter' || e.key === ' ') {
    e.preventDefault()
    view?.command()
  } else if (e.key === 'Delete') {
    e.preventDefault()
    closeTab(tab.dataset.id)
    strip.querySelector('[aria-selected="true"]')?.focus()
  }
})
strip.addEventListener('contextmenu', (e) => {
  const tab = e.target.closest('.tab')
  if (!tab) return
  const i = tabs.findIndex((t) => t.id === tab.dataset.id)
  const ids = (list) => list.map((t) => t.id)
  showContextMenu(e, [
    { label: 'Close', run: () => closeTab(tab.dataset.id) },
    { label: 'Close other tabs', run: () => closeTabs(ids(tabs.filter((_, j) => j !== i))), disabled: tabs.length < 2 },
    { label: 'Close tabs to the right', run: () => closeTabs(ids(tabs.slice(i + 1))), disabled: i === tabs.length - 1 },
    { label: 'Close all tabs', run: () => closeTabs(ids(tabs)) },
    '-',
    { label: 'New notebook', run: () => commands.new() },
  ], tab)
})

// Drag a tab to reorder.
let dragId = null
strip.addEventListener('dragstart', (e) => {
  const tab = e.target.closest('.tab')
  if (!tab) return
  dragId = tab.dataset.id
  e.dataTransfer.effectAllowed = 'move'
  e.dataTransfer.setData('application/x-symflex-tab', dragId)  // not text: dropping on an editor must not insert it
})
const dropSide = (e, tab) => (e.clientX < tab.getBoundingClientRect().left + tab.offsetWidth / 2 ? 'before' : 'after')
const clearDrop = () => strip.querySelectorAll('.drop-before, .drop-after').forEach((t) => t.classList.remove('drop-before', 'drop-after'))
strip.addEventListener('dragover', (e) => {
  const tab = e.target.closest('.tab')
  if (!dragId || !tab) return
  e.preventDefault()
  clearDrop()
  if (tab.dataset.id !== dragId) tab.classList.add(`drop-${dropSide(e, tab)}`)
})
strip.addEventListener('dragleave', (e) => { if (!strip.contains(e.relatedTarget)) clearDrop() })
strip.addEventListener('drop', (e) => {
  const tab = e.target.closest('.tab')
  clearDrop()
  if (!dragId || !tab || tab.dataset.id === dragId) return
  e.preventDefault()
  e.stopPropagation()  // not a file drop
  const [moved] = tabs.splice(tabs.findIndex((t) => t.id === dragId), 1)
  const at = tabs.findIndex((t) => t.id === tab.dataset.id) + (dropSide(e, tab) === 'after' ? 1 : 0)
  tabs.splice(at, 0, moved)
  persistTabs()
  renderTabs()
})
strip.addEventListener('dragend', () => { dragId = null; clearDrop() })

$('#nb-name').addEventListener('change', (e) => {
  if (!view) return
  view.nb.name = e.target.value.trim() || 'Untitled'
  e.target.value = view.nb.name
  tabOf(view.nb.id).name = view.nb.name
  document.title = `${view.nb.name} · SymFlex`
  renderTabs()
  view.save()
})
$('#nb-name').addEventListener('keydown', (e) => { if (e.key === 'Enter') e.target.blur() })

// ---- files

function download(name, text, type = 'text/plain') {
  const url = URL.createObjectURL(new Blob([text], { type }))
  const a = Object.assign(document.createElement('a'), { href: url, download: name })
  a.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
const safeName = () => (view.nb.name || 'notebook').replace(/[\\/:*?"<>|]+/g, '_')

async function importFiles(files) {
  for (const f of files) {
    try {
      const nb = importFile(f.name, await f.text())
      openNotebook(nb)
      toast(`Opened ${f.name}`)
    } catch (e) {
      toast(`Could not open ${f.name}: ${e.message}`, 'error')
    }
  }
}
$('#file-input').addEventListener('change', (e) => { importFiles([...e.target.files]); e.target.value = '' })
window.addEventListener('dragover', (e) => { if (e.dataTransfer?.types.includes('Files')) e.preventDefault() })
window.addEventListener('drop', (e) => {
  if (!e.dataTransfer?.files.length) return
  e.preventDefault()
  importFiles([...e.dataTransfer.files])
})

async function exportStaticHtml() {
  const nb = view.nb
  const images = new Map()
  for (const c of nb.cells) {
    const divs = view.views.get(c.id)?.out.querySelectorAll('.sf-plot') ?? []
    images.set(c.id, await Promise.all([...divs].map((d) => plotImage(d).catch(() => null))))
  }
  const html = exportHtml(nb, (c) => (c.type === 'markdown' ? renderMarkdown(c.source, 'mathml') : outputsToHtml(c.outputs, images.get(c.id))))
  download(`${safeName()}.html`, html, 'text/html')
}

// ---- commands (menus, toolbar, shortcuts)

const commands = {
  new: () => openNotebook(newNotebook('Untitled')),
  open: () => $('#file-input').click(),
  'save-json': () => download(`${safeName()}.symflex.json`, exportJson(view.nb), 'application/json'),
  'export-mpl': () => download(`${safeName()}.mpl`, exportMpl(view.nb)),
  'export-pde': () => {
    const text = exportPde(view.nb, view.selectedId)
    text ? download(`${safeName()}.pde`, text) : toast('This notebook has no FlexPDE cell', 'warn')
  },
  'export-html': () => exportStaticHtml().catch((e) => toast(`Export failed: ${e.message}`, 'error')),
  'insert-above': () => view.insert('above'),
  'insert-below': () => view.insert('below'),
  duplicate: () => view.duplicate(),
  'move-up': () => view.move(-1),
  'move-down': () => view.move(1),
  delete: () => view.delete(),
  'undo-delete': () => view.undoDelete(),
  'type-maple': () => view.changeType('maple'),
  'type-flexpde': () => view.changeType('flexpde'),
  'type-markdown': () => view.changeType('markdown'),
  collapse: () => view.toggleCollapse(),
  clear: () => view.clearOutputs(),
  run: () => view.run(view.selectedId, 'none'),
  'run-advance': () => view.run(view.selectedId, 'next'),
  'run-all': () => view.runAll(),
  'run-above': () => view.runAbove(),
  'run-below': () => view.runBelow(),
  interrupt: () => view.stopAll(),
  restart: () => view.restart(),
  'restart-run-all': () => view.restart(true),
  'toggle-theme': () => applyTheme(currentTheme() === 'dark' ? 'light' : 'dark'),
  'toggle-lines': () => {
    const on = !store.getSetting('lineNumbers', false)
    for (const t of tabs) t.view?.setLineNumbers(on)
    store.setSetting('lineNumbers', on)
  },
  shortcuts: () => $('#shortcuts').showModal(),
  find: () => find.open(),
  replace: () => find.open(true),
}
// Commands that work with no notebook open; the rest need the active view.
const GLOBAL_COMMANDS = new Set(['new', 'open', 'toggle-theme', 'toggle-lines', 'shortcuts'])

function closeMenus(except) {
  for (const m of document.querySelectorAll('.menu.open')) {
    if (m === except) continue
    m.classList.remove('open')
    m.querySelector('.menu-btn').setAttribute('aria-expanded', 'false')
  }
}

document.addEventListener('click', (e) => {
  const menuBtn = e.target.closest('.menu-btn')
  if (menuBtn) {
    const menu = menuBtn.parentElement
    closeMenus(menu)
    const open = menu.classList.toggle('open')
    menuBtn.setAttribute('aria-expanded', String(open))
    if (open) menu.querySelector('[role=menuitem]')?.focus()
    return
  }
  const cmd = e.target.closest('[data-cmd]')
  closeMenus()
  if (cmd && commands[cmd.dataset.cmd] && (view || GLOBAL_COMMANDS.has(cmd.dataset.cmd))) {
    const wasEdit = view?.mode === 'edit'
    commands[cmd.dataset.cmd]()
    // Toolbar clicks steal focus from the editor; return it so typing continues.
    if (wasEdit && view?.mode === 'edit' && cmd.closest('.toolbar')) view.edit()
  }
})

// Arrow-key navigation inside open menus.
document.addEventListener('keydown', (e) => {
  const menu = e.target.closest?.('.menu.open')
  if (!menu) return
  const items = [...menu.querySelectorAll('[role=menuitem]')]
  const i = items.indexOf(document.activeElement)
  if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
    e.preventDefault()
    items[(i + (e.key === 'ArrowDown' ? 1 : -1) + items.length) % items.length].focus()
  } else if (e.key === 'Escape') {
    e.stopPropagation()
    closeMenus()
    menu.querySelector('.menu-btn').focus()
  }
}, true)

document.addEventListener('keydown', (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's') {
    e.preventDefault()
    if (view) store.save(view.nb) ? toast('Saved') : toast('Save failed: storage unavailable', 'error')
    return
  }
  const typing = e.target.closest?.('.cm-editor, input, textarea, select, dialog, [role=tab], [role=menu]')
  if (!typing && view?.mode !== 'edit' && !e.ctrlKey && !e.metaKey && !e.altKey && (e.key === 'h' || e.key === '?')) {
    e.preventDefault()
    commands.shortcuts()
  }
})
$('#shortcuts').addEventListener('click', (e) => {
  if (e.target.closest('[data-close]') || e.target === e.currentTarget) e.currentTarget.close()
})

const narrow = matchMedia('(max-width: 800px)')
// On narrow screens the sidebar is an overlay: it starts closed and its state is not remembered.
function setSidebarHidden(hidden) {
  document.body.classList.toggle('sidebar-hidden', hidden)
  $('#sidebar-toggle').setAttribute('aria-expanded', String(!hidden))
  if (!narrow.matches) store.setSetting('sidebarHidden', hidden)
}
$('#sidebar-toggle').addEventListener('click', () => setSidebarHidden(!document.body.classList.contains('sidebar-hidden')))
if (narrow.matches || store.getSetting('sidebarHidden', false)) setSidebarHidden(true)

// Sidebar width: drag the handle (or focus it and use the arrow keys); double-click resets.
const resizer = $('#sidebar-resize')
function setSidebarWidth(px, persist = false) {
  const w = Math.round(Math.min(Math.max(px, 200), 640, innerWidth * 0.7))
  document.documentElement.style.setProperty('--sidebar-w', `${w}px`)
  resizer.setAttribute('aria-valuenow', String(w))
  if (persist) {
    store.setSetting('sidebarWidth', w)
    dispatchEvent(new Event('resize'))  // plots re-fit to the new notebook width
  }
}
setSidebarWidth(store.getSetting('sidebarWidth', 290))
resizer.addEventListener('pointerdown', (e) => {
  if (e.button !== 0) return
  e.preventDefault()
  const x0 = e.clientX, w0 = $('#sidebar').offsetWidth
  let w = w0
  const move = (ev) => setSidebarWidth(w = w0 + ev.clientX - x0)
  resizer.setPointerCapture(e.pointerId)
  document.body.classList.add('resizing')
  resizer.addEventListener('pointermove', move)
  resizer.addEventListener('lostpointercapture', () => {
    resizer.removeEventListener('pointermove', move)
    document.body.classList.remove('resizing')
    setSidebarWidth(w, true)
  }, { once: true })
})
resizer.addEventListener('dblclick', () => setSidebarWidth(290, true))
addEventListener('resize', () => setSidebarWidth(store.getSetting('sidebarWidth', 290)))  // re-clamp to the window
resizer.addEventListener('keydown', (e) => {
  const d = { ArrowLeft: -20, ArrowRight: 20 }[e.key]
  if (!d) return
  e.preventDefault()
  setSidebarWidth($('#sidebar').offsetWidth + d, true)
})

// ---- sidebar + find bar

const sidebar = initSidebar({
  store, toast,
  openById,
  openNotebook,
  openNotebooks,
  closeTab,
  currentId: () => view?.nb.id,
  insertText: (text) => view?.insertText(text),
})
const find = new FindBar({ parent: $('#notebooks'), getView: () => view })

// ---- dev: hot-reload the Python engine when py/ changes (vite plugin event)

if (import.meta.hot) {
  let stale = false
  const reloadEngine = async () => {
    // Never swap the engine under a running notebook; retry when both kernel and queue are idle.
    if (!stale || kernel.status !== 'idle' || tabs.some((t) => t.view?.running)) return
    stale = false
    try {
      await kernel.reloadEngine()
      for (const t of tabs) if (t.view) t.view.counter = 0
      toast('Maple engine reloaded (kernel state reset)')
    } catch (e) { toast(`Engine reload failed: ${e.message}`, 'error') }
  }
  import.meta.hot.on('symflex:py-updated', () => { stale = true; reloadEngine() })
  kernel.addEventListener('status', reloadEngine)
  onViewIdle = reloadEngine
}

// ---- boot: reopen the tabs of the last session

const names = new Map(store.list().map((e) => [e.id, e.name]))
const last = store.getSetting('last', null)
const savedTabs = (store.getSetting('tabs', null) ?? [last]).filter((id) => names.has(id))
if (savedTabs.length) {
  tabs.push(...savedTabs.map((id) => ({ id, name: names.get(id) })))
  activate(savedTabs.includes(last) ? last : savedTabs[0])
} else {
  const first = store.list()[0]
  openNotebook((first && store.load(first.id)) || welcomeNotebook())
}

function welcomeNotebook() {
  return newNotebook('Welcome', [
    newCell('markdown', '# Welcome to SymFlex\n\nA notebook for **Maple 2024** (1-D input) and **FlexPDE 8** problems from EP 2CD4. ' +
      'All Maple cells share one session, like a worksheet. Press `Shift+Enter` to run a cell, `Esc` then `H` for shortcuts, ' +
      'and browse the course examples in the sidebar.\n\nText cells support math: $F = m\\,a$.'),
    newCell('maple', 'restart:\nm := 2: g := 9.81:\nW := m*g;\nsol := dsolve({diff(x(t), t, t) = -g, x(0) = 0, D(x)(0) = 10}, x(t));\nplot(rhs(sol), t = 0 .. 2, labels = ["t (s)", "x (m)"]);'),
    newCell('flexpde', "TITLE 'Projectile'\nCOORDINATES cartesian1\nVARIABLES\n  y(threshold = 1e-3)\n  v(threshold = 1e-3)\n" +
      'SELECT ngrid = 1\nDEFINITIONS\n  g = 9.81\nINITIAL VALUES\n  y = 0  v = 10\nEQUATIONS\n  y: dt(y) = v\n  v: dt(v) = -g\n' +
      'BOUNDARIES\n  REGION 1 START(0) LINE TO (1)\nTIME 0 TO 5 HALT (y < 0)\nPLOTS\n  for t = 0 by endtime/50 to endtime\n' +
      '  history(y) at (0)\nEND'),
  ])
}
