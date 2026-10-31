// PlotSpec (see ARCHITECTURE.md) -> Plotly figures. Plotly is loaded lazily on first plot.
const PALETTE = ['#2563eb', '#dc2626', '#16a34a', '#9333ea', '#ea580c', '#0891b2', '#db2777', '#65a30d']
const DASH = { solid: 'solid', dash: 'dash', dot: 'dot', dashdot: 'dashdot', longdash: 'longdash', spacedash: 'dash', spacedot: 'dot' }

let plotlyPromise
export const loadPlotly = () => (plotlyPromise ??= import('plotly.js-dist-min').then((m) => m.default ?? m))

// ---- pure helpers (exported for tests)

/** [min, max] without spreading (safe for large FEM arrays). */
const extent = (a) => a.reduce(([lo, hi], v) => (v == null ? [lo, hi] : [Math.min(lo, v), Math.max(hi, v)]), [Infinity, -Infinity])

/** Grid z in Plotly orientation: z[j][i] is the value at (x[i], y[j]). Transposes z[i][j] input. */
export function gridZ(grid) {
  const { x, y, z } = grid
  if (z.length === x.length && x.length !== y.length && z[0]?.length === y.length)
    return y.map((_, j) => x.map((_, i) => z[i][j]))
  return z
}

/** Resamples triangle-mesh data onto an n x n grid by barycentric interpolation (null outside). */
export function meshToGrid(mesh, n = 60) {
  const { x, y, tri, values } = mesh
  const [x0, x1] = extent(x), [y0, y1] = extent(y)
  const gx = Array.from({ length: n }, (_, i) => x0 + ((x1 - x0) * i) / (n - 1))
  const gy = Array.from({ length: n }, (_, j) => y0 + ((y1 - y0) * j) / (n - 1))
  const z = gy.map(() => new Array(n).fill(null))
  const dx = (x1 - x0) / (n - 1) || 1, dy = (y1 - y0) / (n - 1) || 1
  for (const [a, b, c] of tri) {
    const det = (y[b] - y[c]) * (x[a] - x[c]) + (x[c] - x[b]) * (y[a] - y[c])
    if (!det) continue
    const i0 = Math.max(0, Math.floor((Math.min(x[a], x[b], x[c]) - x0) / dx))
    const i1 = Math.min(n - 1, Math.ceil((Math.max(x[a], x[b], x[c]) - x0) / dx))
    const j0 = Math.max(0, Math.floor((Math.min(y[a], y[b], y[c]) - y0) / dy))
    const j1 = Math.min(n - 1, Math.ceil((Math.max(y[a], y[b], y[c]) - y0) / dy))
    for (let j = j0; j <= j1; j++) for (let i = i0; i <= i1; i++) {
      const l1 = ((y[b] - y[c]) * (gx[i] - x[c]) + (x[c] - x[b]) * (gy[j] - y[c])) / det
      const l2 = ((y[c] - y[a]) * (gx[i] - x[c]) + (x[a] - x[c]) * (gy[j] - y[c])) / det
      const l3 = 1 - l1 - l2
      if (l1 >= -1e-9 && l2 >= -1e-9 && l3 >= -1e-9) z[j][i] = l1 * values[a] + l2 * values[b] + l3 * values[c]
    }
  }
  return { x: gx, y: gy, z }
}

/** Arrow shafts + heads as one polyline with null breaks, scaled so the longest is `len`. */
export function arrowSegments({ x, y, u, v }, len) {
  const mags = u.map((ui, k) => Math.hypot(ui, v[k]))
  const max = extent(mags)[1] || 1
  if (!len) {
    const [xa, xb] = extent(x), [ya, yb] = extent(y)
    const span = Math.max(xb - xa, yb - ya) || 1
    len = span / Math.max(4, Math.sqrt(x.length))
  }
  const sx = [], sy = []
  for (let k = 0; k < x.length; k++) {
    if (!mags[k]) continue
    const s = len / max, ex = x[k] + u[k] * s, ey = y[k] + v[k] * s
    const ang = Math.atan2(ey - y[k], ex - x[k]), h = 0.3 * mags[k] * s
    sx.push(x[k], ex, null, ex - h * Math.cos(ang - 0.45), ex, ex - h * Math.cos(ang + 0.45), null)
    sy.push(y[k], ey, null, ey - h * Math.sin(ang - 0.45), ey, ey - h * Math.sin(ang + 0.45), null)
  }
  return { x: sx, y: sy }
}

function finite(arr) { return (arr || []).filter((v) => typeof v === 'number' && Number.isFinite(v)) }

/** [xmin, xmax, ymin, ymax] over a list of 2-D specs (used to fix animation axes). */
export function bounds2d(specs) {
  let xs = [], ys = []
  for (const s of specs) {
    for (const c of s.curves || []) { xs.push(finite(c.x)); ys.push(finite(c.y)) }
    if (s.arrows) { xs.push(finite(s.arrows.x)); ys.push(finite(s.arrows.y)) }
  }
  xs = xs.flat(); ys = ys.flat()
  if (!xs.length) return null
  return [...extent(xs), ...extent(ys)]
}

// ---- figure construction

function themeColors() {
  const cs = getComputedStyle(document.documentElement)
  const v = (n) => cs.getPropertyValue(n).trim()
  return { fg: v('--fg') || '#1f2328', muted: v('--muted') || '#6b7280', grid: v('--plot-grid') || '#e5e7eb', bg: v('--plot-bg') || '#fff' }
}

const is3d = (spec) => spec.type === '3d' || spec.type === 'surface'

export function specToTraces(spec) {
  const traces = []
  const three = is3d(spec)
  ;(spec.curves || []).forEach((c, k) => {
    const color = c.color || PALETTE[k % PALETTE.length]
    const points = c.style === 'point'
    const base = {
      x: c.x, y: c.y, name: c.legend || '', showlegend: !!c.legend,
      mode: points ? 'markers' : 'lines',
      line: { color, width: three ? 4 : Math.max(1, (c.thickness ?? 1) * 1.6), dash: DASH[c.dash] || 'solid' },
      marker: { color, size: three ? 3 : 6 },
      hovertemplate: three ? undefined : '(%{x:.4g}, %{y:.4g})<extra></extra>',
    }
    traces.push(three && c.z?.length ? { ...base, type: 'scatter3d', z: c.z } : { ...base, type: 'scatter' })
  })
  const scale = 'Viridis'
  if (spec.grid?.z?.length) {
    const z = gridZ(spec.grid)
    if (spec.type === 'contour') traces.push({ type: 'contour', x: spec.grid.x, y: spec.grid.y, z, colorscale: scale, contours: { coloring: 'heatmap', showlabels: true } })
    else traces.push({ type: 'surface', x: spec.grid.x, y: spec.grid.y, z, colorscale: scale, showscale: true })
  }
  if (spec.mesh?.tri?.length) {
    const m = spec.mesh
    if (spec.type === 'contour') {
      const g = meshToGrid(m)
      traces.push({ type: 'contour', ...g, colorscale: scale, connectgaps: false, contours: { coloring: 'heatmap', showlabels: true } })
    } else {
      traces.push({ type: 'mesh3d', x: m.x, y: m.y, z: m.values, i: m.tri.map((t) => t[0]), j: m.tri.map((t) => t[1]),
        k: m.tri.map((t) => t[2]), intensity: m.values, colorscale: scale, showscale: true })
    }
  }
  if (spec.arrows?.x?.length) {
    const seg = arrowSegments(spec.arrows)
    traces.push({ type: 'scatter', mode: 'lines', ...seg, line: { color: PALETTE[0], width: 1.4 }, hoverinfo: 'skip', showlegend: false })
  }
  return traces
}

const axisTitle = (t) => (t ? { text: String(t) } : undefined)
const logRange = (r, log) => (r && log ? r.map((v) => Math.log10(v)) : r)

export function specToLayout(spec, colors = themeColors(), fixed = null) {
  const axis = (title, log, range) => ({
    title: axisTitle(title), type: log ? 'log' : 'linear', range: logRange(range, log) ?? undefined,
    gridcolor: colors.grid, zerolinecolor: colors.muted, linecolor: colors.muted, color: colors.fg,
    exponentformat: 'power', automargin: true,
  })
  const layout = {
    title: spec.title ? { text: String(spec.title), font: { size: 15 } } : undefined,
    paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: colors.bg,
    font: { family: 'Inter, system-ui, sans-serif', color: colors.fg, size: 12 },
    margin: { l: 56, r: 24, t: spec.title ? 44 : 20, b: 48 },
    showlegend: (spec.curves || []).some((c) => c.legend),
    legend: { orientation: 'h', y: -0.18 },
    hovermode: 'closest',
  }
  if (is3d(spec)) {
    const a = (t) => ({ title: axisTitle(t), gridcolor: colors.grid, color: colors.fg, backgroundcolor: colors.bg })
    layout.scene = { xaxis: a(spec.xlabel), yaxis: a(spec.ylabel), zaxis: a(spec.zlabel), aspectmode: spec.scaling === 'constrained' ? 'data' : 'cube' }
    layout.margin = { l: 0, r: 0, t: spec.title ? 40 : 0, b: 0 }
  } else {
    const xr = spec.xrange ?? (fixed && [fixed[0], fixed[1]]), yr = spec.yrange ?? (fixed && [fixed[2], fixed[3]])
    layout.xaxis = axis(spec.xlabel, spec.xlog, xr)
    layout.yaxis = axis(spec.ylabel, spec.ylog, yr)
    if (spec.scaling === 'constrained') Object.assign(layout.yaxis, { scaleanchor: 'x', scaleratio: 1 })
  }
  return layout
}

const CONFIG = { responsive: true, displaylogo: false, modeBarButtonsToRemove: ['lasso2d', 'select2d', 'toggleSpikelines'] }

/** Renders a PlotSpec into `el` (cleared). Returns the plot div. */
export async function renderPlot(el, spec) {
  const Plotly = await loadPlotly()
  el.replaceChildren()
  const div = document.createElement('div')
  div.className = 'sf-plot'
  div.style.height = is3d(spec) ? '440px' : '380px'
  el.append(div)
  const frames = spec.frames?.length ? spec.frames.map((f) => ({ ...spec, frames: undefined, ...f })) : null
  if (!frames) {
    await Plotly.newPlot(div, specToTraces(spec), specToLayout(spec), CONFIG)
    div._sfSpec = spec
    return div
  }

  const fixed = is3d(spec) ? null : bounds2d(frames)
  const show = (i) => Plotly.react(div, specToTraces(frames[i]), specToLayout(frames[i], themeColors(), fixed), CONFIG)
  await show(0)
  div._sfSpec = spec

  const bar = document.createElement('div')
  bar.className = 'sf-anim'
  const play = document.createElement('button')
  play.type = 'button'
  play.className = 'btn btn-small'
  play.textContent = 'Play'
  play.setAttribute('aria-label', 'Play animation')
  const slider = document.createElement('input')
  slider.type = 'range'
  slider.min = 0
  slider.max = frames.length - 1
  slider.value = 0
  slider.setAttribute('aria-label', 'Animation frame')
  const label = document.createElement('span')
  label.className = 'sf-anim-label'
  const setLabel = (i) => { label.textContent = `${+i + 1} / ${frames.length}` }
  setLabel(0)
  let timer = null
  const stop = () => { clearInterval(timer); timer = null; play.textContent = 'Play' }
  slider.oninput = () => { show(+slider.value); setLabel(slider.value) }
  play.onclick = () => {
    if (timer) return stop()
    play.textContent = 'Pause'
    timer = setInterval(() => {
      if (!div.isConnected) return stop()
      slider.value = (+slider.value + 1) % frames.length
      slider.oninput()
    }, 1000 / 12)
  }
  bar.append(play, slider, label)
  el.append(bar)
  return div
}

/** Re-applies theme colours to every rendered plot (after a light/dark switch). */
export async function rethemePlots(root = document) {
  const divs = root.querySelectorAll('.sf-plot')
  if (!divs.length) return
  const Plotly = await loadPlotly()
  const c = themeColors()
  for (const d of divs) {
    if (!d._sfSpec) continue
    const upd = { paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: c.bg, 'font.color': c.fg }
    if (d.layout?.xaxis) Object.assign(upd, { 'xaxis.gridcolor': c.grid, 'yaxis.gridcolor': c.grid, 'xaxis.color': c.fg, 'yaxis.color': c.fg })
    Plotly.relayout(d, upd)
  }
}

/** PNG data URL of a rendered plot (static HTML export). */
export async function plotImage(div) {
  const Plotly = await loadPlotly()
  return Plotly.toImage(div, { format: 'png', width: 800, height: 450 })
}
