// PlotSpec builders (see docs/ARCHITECTURE.md). `sol` is the solution interface shared by the ODE
// and FEM paths: { states:[{t}], setState(k), ctx, mesh, nodal(fn) -> values, at(pt, fn) -> value }.
import { scalar, isVec } from './expr.js';

const num = v => (Number.isFinite(v) ? v : null);

export function historyPlot(item, sol, compile) {
  const pts = item.at && item.at.length ? item.at : [null];
  const fns = item.args.map(a => compile(a));
  const vs = item.vs ? compile(item.vs) : null;
  const curves = [];
  const K = sol.states.length;
  for (const [ai, f] of fns.entries()) {
    for (const p of pts) {
      const P = p ? p.map(c => sol.constant(c)) : null;
      const x = new Array(K), y = new Array(K);
      for (let k = 0; k < K; k++) {
        sol.setState(k);
        const ev = g => scalar(P ? sol.ctx.at(P, g) : g(sol.ctx));
        y[k] = num(ev(f));
        x[k] = vs ? num(ev(vs)) : sol.states[k].t;
      }
      let legend = item.args[ai].label;
      if (pts.length > 1 && P) legend += ` at (${P.join(',')})`;
      // t: sample times (kept also for `vs` plots so histories can be compared in time)
      curves.push({ x, y, legend, style: 'line', t: sol.states.map(s => s.t) });
    }
  }
  const spec = base(item, item.as || item.args.map(a => a.label).join(', '), vs ? item.vs.label : 't', '');
  spec.curves = curves;
  if (item.window) {
    const w = item.window.map(e => sol.constant(e));
    const tEnd = sol.states[K - 1].t;
    spec.xrange = w.length === 2 ? w : [tEnd - w[0], tEnd];
  }
  return spec;
}

export function elevationPlot(item, sol, compile) {
  const a = (item.from || [0]).map(c => sol.constant(c));
  const b = (item.to || item.from || [1]).map(c => sol.constant(c));
  const N = 101;
  const len = Math.hypot(b[0] - a[0], (b[1] ?? 0) - (a[1] ?? 0));
  const curves = item.args.map(e => {
    const f = compile(e);
    const x = [], y = [];
    for (let i = 0; i < N; i++) {
      const s = i / (N - 1);
      const p = [a[0] + s * (b[0] - a[0]), (a[1] ?? 0) + s * ((b[1] ?? 0) - (a[1] ?? 0))];
      x.push(sol.mesh?.dim === 1 ? p[0] : s * len);
      y.push(num(scalar(sol.at(p, f))));
    }
    return { x, y, legend: e.label, style: 'line' };
  });
  const spec = base(item, item.as || item.args.map(e => e.label).join(', '), sol.mesh?.dim === 1 ? 'x' : 'distance', '');
  spec.curves = curves;
  return spec;
}

export function fieldPlot(item, sol, compile, type) {
  const m = sol.mesh;
  const f = compile(item.args[0]);
  const spec = base(item, item.as || item.args[0].label, 'x', 'y');
  spec.type = type;
  spec.scaling = 'constrained';
  if (m.dim === 1) { // a contour of a 1D problem is just its elevation
    spec.type = '2d';
    spec.scaling = 'unconstrained';
    const vals = sol.nodal(g => scalar(f(g)));
    spec.curves = [{ x: m.x.slice(), y: vals.map(num), legend: item.args[0].label, style: 'line' }];
    return spec;
  }
  const values = sol.nodal(g => scalar(f(g)));
  spec.zlabel = item.args[0].label;
  spec.mesh = { x: m.x.slice(), y: m.y.slice(), tri: m.tri.map(t => t.slice()), values: values.map(num) };
  return spec;
}

export function vectorPlot(item, sol, compile) {
  const m = sol.mesh;
  const f = compile(item.args.length > 1 ? { k: 'call', f: 'vector', args: item.args, tok: item.args[0].tok } : item.args[0]);
  const spec = base(item, item.as || item.args.map(a => a.label).join(', '), 'x', 'y');
  spec.type = 'vector';
  spec.scaling = 'constrained';
  const n = item.points ? Math.max(3, Math.round(sol.constant(item.points))) : 21;
  const [x0, x1, y0, y1] = m.bbox;
  const X = [], Y = [], U = [], V = [];
  for (let i = 0; i < n; i++) for (let j = 0; j < n; j++) {
    const p = [x0 + (x1 - x0) * (i + 0.5) / n, y0 + (y1 - y0) * (j + 0.5) / n];
    if (!m.contains(p)) continue;
    const v = sol.at(p, f);
    let u = isVec(v) ? v[0] : v, w = isVec(v) ? v[1] : 0;
    if (!Number.isFinite(u) || !Number.isFinite(w)) continue;
    X.push(p[0]); Y.push(p[1]); U.push(u); V.push(w);
  }
  if (item.norm) { // all arrows the same length; magnitude kept for colouring
    const mag = U.map((u, k) => Math.hypot(u, V[k]));
    spec.arrows = { x: X, y: Y, u: U.map((u, k) => (mag[k] ? u / mag[k] : 0)), v: V.map((w, k) => (mag[k] ? w / mag[k] : 0)), magnitude: mag, norm: true };
  } else spec.arrows = { x: X, y: Y, u: U, v: V };
  return spec;
}

export function gridPlot(item, sol) {
  const m = sol.mesh;
  const spec = base(item, item.as || 'Grid', 'x', 'y');
  spec.scaling = 'constrained';
  const x = [], y = [];
  if (m.dim === 1) {
    spec.curves = [{ x: m.x.slice(), y: m.x.map(() => 0), legend: 'nodes', style: 'point' }];
    return spec;
  }
  const seen = new Set();
  for (const t of m.tri) for (let k = 0; k < 3; k++) {
    const a = t[k], b = t[(k + 1) % 3];
    const key = a < b ? a * 1e7 + b : b * 1e7 + a;
    if (seen.has(key)) continue;
    seen.add(key);
    x.push(m.x[a], m.x[b], null); y.push(m.y[a], m.y[b], null);
  }
  spec.curves = [{ x, y, legend: 'mesh', style: 'line', thickness: 0.5 }];
  return spec;
}

function base(item, title, xlabel, ylabel) {
  return { type: '2d', title, xlabel, ylabel, zlabel: '', xlog: false, ylog: false, xrange: null, yrange: null,
    scaling: 'unconstrained', curves: [], line: item.line };
}
