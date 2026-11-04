// Sidebar: saved notebooks, course examples browser, function reference.
import { showContextMenu } from './contextmenu.js'
import { mplToCells } from './io.js'
import { FLEX_FUNCTIONS, FLEX_PLOTS, FLEX_SECTIONS, FLEX_SELECT } from './lang/flex_docs.js'
import { MAPLE_DOCS } from './lang/maple_docs.js'
import { newCell, newNotebook } from './store.js'

const $ = (sel) => document.querySelector(sel)
const h = (tag, cls, text) => {
  const e = document.createElement(tag)
  if (cls) e.className = cls
  if (text != null) e.textContent = text
  return e
}

const ago = (t) => {
  const s = (Date.now() - t) / 1000
  return s < 60 ? 'just now' : s < 3600 ? `${Math.floor(s / 60)} min ago` : s < 86400 ? `${Math.floor(s / 3600)} h ago` : new Date(t).toLocaleDateString()
}

/** Builds a notebook from one examples.json item: an intro text cell then its code. */
export function exampleToNotebook(group, ex) {
  const intro = `### ${ex.title}\n\n*${group.title}*` + (ex.context ? `\n\n> ${ex.context}` : '')
  const code = ex.kind === 'pde' ? [newCell('flexpde', ex.code)] : mplToCells(ex.code)
  // Title first so narrow tabs of one section still tell the examples apart.
  return newNotebook(`${ex.title} (${group.title})`.slice(0, 80), [newCell('markdown', intro), ...code])
}

export function initSidebar({ store, toast, openById, openNotebook, openNotebooks, closeTab, currentId, insertText }) {
  // ---- tabs
  const tabs = [...document.querySelectorAll('.sidebar [role=tab]')]
  const selectTab = (tab) => {
    for (const t of tabs) {
      const on = t === tab
      t.setAttribute('aria-selected', String(on))
      t.tabIndex = on ? 0 : -1
      $('#' + t.getAttribute('aria-controls')).hidden = !on
    }
    store.setSetting('tab', tab.id)
    if (tab.id === 'tab-examples') loadExamples()
    if (tab.id === 'tab-help') renderHelp()
  }
  tabs.forEach((t, i) => {
    t.addEventListener('click', () => selectTab(t))
    t.addEventListener('keydown', (e) => {
      const d = e.key === 'ArrowRight' ? 1 : e.key === 'ArrowLeft' ? -1 : 0
      if (d) { const n = tabs[(i + d + tabs.length) % tabs.length]; selectTab(n); n.focus() }
    })
  })

  // ---- notebooks
  function refresh() {
    const list = $('#nb-list')
    list.replaceChildren(...store.list().map((e) => {
      const li = h('li', e.id === currentId() ? 'active' : '')
      const open = h('button', 'nb-open')
      open.type = 'button'
      open.append(h('span', 'nb-title', e.name), h('span', 'nb-meta', ago(e.modified)))
      open.onclick = () => openById(e.id)
      if (e.id === currentId()) open.setAttribute('aria-current', 'true')
      const del = h('button', 'icon-btn nb-del', '✕')
      del.type = 'button'
      del.title = `Delete ${e.name}`
      del.setAttribute('aria-label', `Delete notebook ${e.name}`)
      del.onclick = () => {
        if (!confirm(`Delete notebook "${e.name}"? This cannot be undone.`)) return
        closeTab(e.id, { discard: true })
        store.remove(e.id)
        refresh()
      }
      li.append(open, del)
      return li
    }))
  }

  // ---- examples
  let examples = null
  async function loadExamples() {
    if (examples) return
    try {
      const res = await fetch(new URL('examples.json', document.baseURI))
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      examples = await res.json()
      renderExamples()
    } catch (e) {
      $('#ex-list').replaceChildren(h('p', 'muted', `No examples available (${e.message}). Run python scripts/build_examples.py.`))
    }
  }

  function renderExamples() {
    const q = $('#ex-search').value.trim().toLowerCase()
    const groups = examples.map((g) => {
      const items = g.items.filter((ex) => !q || `${ex.title} ${ex.context} ${ex.code}`.toLowerCase().includes(q))
      if (!items.length) return null
      const d = h('details', 'ex-group')
      d.open = !!q
      const sum = h('summary', null)
      sum.append(h('span', null, g.title), h('span', 'count', String(items.length)))
      sum.title = 'Right-click to open every example in this section'
      const n = items.length, s = n === 1 ? '' : 's'
      sum.addEventListener('contextmenu', (e) => showContextMenu(e, [
        { label: `Open all ${n} example${s} in tabs`, run: () => {
          openNotebooks(items.map((ex) => exampleToNotebook(g, ex)))
          toast(`Opened ${n} example${s} from ${g.title}`)
        } },
        { label: `Combine ${n} example${s} into one notebook`, run: () => {
          openNotebook(newNotebook(g.title, items.flatMap((ex) => exampleToNotebook(g, ex).cells)))
          toast(`Combined ${n} example${s} from ${g.title}`)
        } },
      ]))
      const ul = h('ul')
      for (const ex of items) {
        const b = h('button', 'ex-item')
        b.type = 'button'
        b.append(h('span', `badge badge-${ex.kind}`, ex.kind === 'pde' ? 'PDE' : 'MPL'), h('span', 'ex-title', ex.title))
        b.title = ex.context || ex.title
        b.onclick = () => { openNotebook(exampleToNotebook(g, ex)); toast(`Opened example: ${ex.title}`) }
        const li = h('li')
        li.append(b)
        ul.append(li)
      }
      d.append(sum, ul)
      return d
    }).filter(Boolean)
    $('#ex-list').replaceChildren(...(groups.length ? groups : [h('p', 'muted', 'No matching examples')]))
  }
  $('#ex-search').addEventListener('input', () => examples && renderExamples())

  // ---- reference
  const entries = [
    ...MAPLE_DOCS.map((d) => ({ lang: 'Maple', ...d })),
    ...FLEX_SECTIONS.map(([name, doc, ex]) => ({ lang: 'FlexPDE', name, sig: `${name} section`, doc, ex })),
    ...FLEX_FUNCTIONS.map(([name, sig, doc]) => ({ lang: 'FlexPDE', name, sig, doc })),
    ...FLEX_PLOTS.map(([name, sig, doc]) => ({ lang: 'FlexPDE', name, sig, doc, pkg: 'PLOTS' })),
    ...FLEX_SELECT.map(([name, type, def, doc]) => ({ lang: 'FlexPDE', name, sig: `SELECT ${name} = …`, doc: `${doc} Default: ${def}.`, pkg: 'SELECT' })),
  ]
  function renderHelp() {
    const q = $('#help-search').value.trim().toLowerCase()
    const hits = entries.filter((e) => !q || e.name.toLowerCase().includes(q) || e.doc.toLowerCase().includes(q))
      .sort((a, b) => (q ? (b.name.toLowerCase().startsWith(q) - a.name.toLowerCase().startsWith(q)) : 0))
      .slice(0, 150)
    $('#help-list').replaceChildren(...hits.map((e) => {
      const d = h('details', 'help-item')
      const sum = h('summary')
      sum.append(h('code', null, e.name), h('span', `badge badge-${e.lang === 'Maple' ? 'mpl' : 'pde'}`, e.pkg || e.lang))
      d.append(sum, h('div', 'help-sig', e.sig), h('p', null, e.doc))
      if (e.ex) {
        d.append(h('pre', 'help-ex', e.ex))
        const ins = h('button', 'btn btn-small', 'Insert example')
        ins.type = 'button'
        ins.onclick = () => insertText(e.ex)
        d.append(ins)
      }
      return d
    }))
  }
  $('#help-search').addEventListener('input', renderHelp)

  const saved = tabs.find((t) => t.id === store.getSetting('tab', 'tab-notebooks')) || tabs[0]
  selectTab(saved)
  return { refresh }
}
