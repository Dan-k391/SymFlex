// App shell: wires the notebook view, kernels, menus, sidebar, files and theme.
import 'katex/dist/katex.min.css'
import './styles.css'
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

const kernel = new MapleKernel()
const flex = new FlexRunner()
const view = new NotebookView({
  root: $('#notebook'), kernel, flex, toast,
  lineNumbers: store.getSetting('lineNumbers', false),
  save: (nb) => { if (!store.save(nb)) toast('Could not autosave: browser storage is full or disabled', 'warn'); sidebar.refresh() },
})

const pill = $('#kernel-pill')
kernel.addEventListener('status', ({ detail: d }) => {
  pill.dataset.state = d.status
  pill.textContent = d.status === 'loading' ? `Maple: ${d.msg || 'loading'} ${Math.round(d.pct ?? 0)}%`
    : d.status === 'error' ? 'Maple: failed' : `Maple: ${d.status}`
  pill.title = d.status === 'error' ? d.msg : kernel.interruptible ? 'Interrupts supported' : 'Interrupt restarts the kernel'
  // Show the exception line, not the whole traceback (the cell output has the full text).
  if (d.status === 'error') toast(`Maple kernel failed to start: ${String(d.msg).trim().split('\n').at(-1)}`, 'error')
})
const syncBusy = () => { $('#btn-stop').disabled = !view.running }
view.addEventListener('busy', syncBusy)
view.addEventListener('idle', syncBusy)
view.addEventListener('mode', () => {
  $('#mode-pill').textContent = view.mode === 'edit' ? 'Edit' : 'Command'
  $('#mode-pill').dataset.mode = view.mode
})

// ---- notebooks

function openNotebook(nb) {
  view.open(nb)
  $('#nb-name').value = nb.name
  store.setSetting('last', nb.id)
  store.save(nb)
  sidebar.refresh()
  document.title = `${nb.name} · SymFlex`
}

function openById(id) {
  const nb = store.load(id)
  if (nb) openNotebook(nb)
  else toast('Notebook not found', 'error')
}

$('#nb-name').addEventListener('change', (e) => {
  view.nb.name = e.target.value.trim() || 'Untitled'
  e.target.value = view.nb.name
  document.title = `${view.nb.name} · SymFlex`
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
    const on = !view.lineNumbers
    view.setLineNumbers(on)
    store.setSetting('lineNumbers', on)
  },
  shortcuts: () => $('#shortcuts').showModal(),
}

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
  if (cmd && commands[cmd.dataset.cmd]) {
    const wasEdit = view.mode === 'edit'
    commands[cmd.dataset.cmd]()
    // Toolbar clicks steal focus from the editor; return it so typing continues.
    if (wasEdit && view.mode === 'edit' && cmd.closest('.toolbar')) view.edit()
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
    store.save(view.nb) ? toast('Saved') : toast('Save failed: storage unavailable', 'error')
    return
  }
  const typing = e.target.closest?.('.cm-editor, input, textarea, select, dialog')
  if (!typing && view.mode === 'command' && !e.ctrlKey && !e.metaKey && !e.altKey && (e.key === 'h' || e.key === '?')) {
    e.preventDefault()
    commands.shortcuts()
  }
})
$('#shortcuts').addEventListener('click', (e) => {
  if (e.target.closest('[data-close]') || e.target === e.currentTarget) e.currentTarget.close()
})

$('#sidebar-toggle').addEventListener('click', (e) => {
  const hidden = document.body.classList.toggle('sidebar-hidden')
  e.currentTarget.setAttribute('aria-expanded', String(!hidden))
  store.setSetting('sidebarHidden', hidden)
})
if (store.getSetting('sidebarHidden', matchMedia('(max-width: 800px)').matches)) {
  document.body.classList.add('sidebar-hidden')
  $('#sidebar-toggle').setAttribute('aria-expanded', 'false')
}

// ---- sidebar

const sidebar = initSidebar({
  store, toast,
  openById,
  openNotebook,
  currentId: () => view.nb?.id,
  insertText: (text) => view.insertText(text),
})

// ---- dev: hot-reload the Python engine when py/ changes (vite plugin event)

if (import.meta.hot) {
  import.meta.hot.on('symflex:py-updated', async () => {
    if (kernel.status !== 'idle') return toast('Maple engine changed: restart the kernel to load it', 'warn')
    try {
      await kernel.reloadEngine()
      view.counter = 0
      toast('Maple engine reloaded (kernel state reset)')
    } catch (e) { toast(`Engine reload failed: ${e.message}`, 'error') }
  })
}

// ---- boot

const last = store.getSetting('last', null)
const existing = (last && store.load(last)) || (store.list()[0] && store.load(store.list()[0].id))
openNotebook(existing || welcomeNotebook())

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
