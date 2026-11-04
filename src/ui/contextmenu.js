// Right-click menus (notebook tabs, example sections). One at a time; closes on outside click,
// Escape, scroll or resize. Styled like the menu bar's pop-ups.
let open = null

export function closeContextMenu() {
  open?.remove()
  open = null
}

/**
 * @param {MouseEvent} e  the contextmenu event; keyboard ones (menu key, Shift+F10) open at the element
 * @param {Array<{label: string, run: () => void, disabled?: boolean} | '-'>} items
 * @param {HTMLElement} [origin]  element the menu belongs to (gets focus back on Escape)
 */
export function showContextMenu(e, items, origin = e.currentTarget) {
  e.preventDefault()
  closeContextMenu()
  for (const m of document.querySelectorAll('.menu.open')) {  // menu-bar dropdowns
    m.classList.remove('open')
    m.querySelector('.menu-btn')?.setAttribute('aria-expanded', 'false')
  }
  const menu = document.createElement('div')
  menu.className = 'menu-pop context-menu'
  menu.setAttribute('role', 'menu')
  for (const it of items) {
    if (it === '-') { menu.append(document.createElement('hr')); continue }
    const b = document.createElement('button')
    b.type = 'button'
    b.setAttribute('role', 'menuitem')
    b.textContent = it.label
    b.disabled = !!it.disabled
    b.onclick = () => { closeContextMenu(); it.run() }
    menu.append(b)
  }
  document.body.append(menu)
  let x = e.clientX, y = e.clientY
  if (!x && !y) { const r = origin.getBoundingClientRect(); x = r.left + 8; y = r.bottom }
  menu.style.left = `${Math.max(4, Math.min(x, innerWidth - menu.offsetWidth - 4))}px`
  menu.style.top = `${Math.max(4, Math.min(y, innerHeight - menu.offsetHeight - 4))}px`
  open = menu
  menu.querySelector('button:not(:disabled)')?.focus()
  menu.addEventListener('keydown', (ev) => {
    const btns = [...menu.querySelectorAll('button:not(:disabled)')]
    const i = btns.indexOf(document.activeElement)
    if (ev.key === 'ArrowDown' || ev.key === 'ArrowUp') {
      ev.preventDefault()
      btns[(i + (ev.key === 'ArrowDown' ? 1 : -1) + btns.length) % btns.length]?.focus()
    } else if (ev.key === 'Escape' || ev.key === 'Tab') {
      ev.preventDefault()
      ev.stopPropagation()
      closeContextMenu()
      origin?.focus?.()
    }
  })
}

addEventListener('pointerdown', (e) => { if (open && !open.contains(e.target)) closeContextMenu() }, true)
addEventListener('resize', closeContextMenu)
addEventListener('blur', closeContextMenu)
document.addEventListener('scroll', (e) => { if (open && !open.contains(e.target)) closeContextMenu() }, true)
