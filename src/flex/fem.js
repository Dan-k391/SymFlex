// P1 finite elements (1D segments / 2D triangles) for PDE problems.
// Each equation residual lhs - rhs is split into divergence terms c*div(V), which are integrated by
// parts (-∫ c V·∇φ + boundary flux), and source terms S (∫ S φ). NATURAL(u)=g supplies the boundary
// flux (default 0), VALUE(u)=g replaces the nodal equation. Nonlinear problems are handled by
// Newton iteration with element-level finite-difference Jacobians; linear systems are solved by
// banded LU after reverse Cuthill-McKee ordering.
import { scalar, isVec } from './expr.js';
import { FlexError } from './lexer.js';
import { nextGen, assignEquations } from './model.js';

const DIV_OPS = new Set(['div', 'del2', 'dxx', 'dyy', 'dxy', 'dyx']);
const OPAQUE = new Set(['val', 'eval', 'integral', 'integrate', 'area_integral', 'line_integral', 'bintegral', 'globalmax', 'globalmin']);

export class FemCtx {
  constructor(model, mesh, nv) {
    this.model = model; this.mesh = mesh; this.nv = nv;
    this.t = 0; this.x = 0; this.y = 0; this.z = 0;
    this.gen = nextGen(); this.cv = []; this.cg = [];
    this.U = null; this.lv = null; this.region = 1; this.deltat = 0; this.args = null;
    this.endtime = model.endtime;
    this.e = 0; this.l = [1, 0, 0];
    const m = mesh;
    // element geometry: measure and shape-function gradients
    this.G = m.tri.map(t => {
      if (m.dim === 1) { const L = m.x[t[1]] - m.x[t[0]]; return [[-1 / L, 0], [1 / L, 0]]; }
      const [a, b, c] = t, X = m.x, Y = m.y;
      const det = (X[b] - X[a]) * (Y[c] - Y[a]) - (X[c] - X[a]) * (Y[b] - Y[a]);
      return [[(Y[b] - Y[c]) / det, (X[c] - X[b]) / det], [(Y[c] - Y[a]) / det, (X[a] - X[c]) / det], [(Y[a] - Y[b]) / det, (X[b] - X[a]) / det]];
    });
    this.area = m.tri.map(t => {
      if (m.dim === 1) return m.x[t[1]] - m.x[t[0]];
      const [a, b, c] = t, X = m.x, Y = m.y;
      return Math.abs((X[b] - X[a]) * (Y[c] - Y[a]) - (X[c] - X[a]) * (Y[b] - Y[a])) / 2;
    });
  }
  bump() { this.gen = nextGen(); }
  place(e, l) { // move the evaluation point to element e with barycentric weights l
    this.e = e; this.l = l;
    const t = this.mesh.tri[e];
    let x = 0, y = 0;
    for (let a = 0; a < t.length; a++) { x += l[a] * this.mesh.x[t[a]]; y += l[a] * this.mesh.y[t[a]]; }
    this.x = x; this.y = this.mesh.dim === 1 ? 0 : y;
    this.region = this.mesh.triRegion[e];
    this.gen = nextGen();
  }
  v(k) {
    const t = this.mesh.tri[this.e], l = this.l, U = this.U, nv = this.nv;
    let s = 0;
    for (let a = 0; a < t.length; a++) s += l[a] * U[t[a] * nv + k];
    return s;
  }
  g(k) {
    const t = this.mesh.tri[this.e], G = this.G[this.e], U = this.U, nv = this.nv;
    let gx = 0, gy = 0;
    for (let a = 0; a < t.length; a++) { const u = U[t[a] * nv + k]; gx += G[a][0] * u; gy += G[a][1] * u; }
    return [gx, gy, 0];
  }
  dtv(k) {
    const L = this.lv;
    if (!L) return 0;
    const t = this.mesh.tri[this.e], l = this.l, nv = this.nv;
    let s = 0;
    for (let a = 0; a < t.length; a++) {
      const i = t[a] * nv + k;
      s += l[a] * (L.c[0] * this.U[i] + L.c[1] * L.Y1[i] + (L.Y2 ? L.c[2] * L.Y2[i] : 0));
    }
    return s;
  }
  dtExpr(f) {
    const L = this.lv;
    if (!L) return 0;
    const { U, t } = this;
    const acc = (s, c, v) => (isVec(v) ? (s === 0 ? [0, 0, 0] : s).map((a, k) => a + c * v[k]) : s + c * v);
    let s = acc(0, L.c[0], f(this));
    this.U = L.Y1; this.t = L.t1; this.bump(); s = acc(s, L.c[1], f(this));
    if (L.Y2) { this.U = L.Y2; this.t = L.t2; this.bump(); s = acc(s, L.c[2], f(this)); }
    this.U = U; this.t = t; this.bump();
    return s;
  }
  save() { return [this.e, this.l, this.x, this.y, this.region]; }
  restore(s) { [this.e, this.l, this.x, this.y, this.region] = s; this.bump(); }
  at(pt, f) {
    const loc = this.mesh.locate([pt[0], pt[1] ?? 0]);
    if (!loc) throw new FlexError(`Point (${pt.join(',')}) is outside the domain`);
    const s = this.save();
    this.place(loc.e, loc.l);
    if (this.mesh.dim === 2) { this.x = pt[0]; this.y = pt[1] ?? 0; } else this.x = pt[0];
    try { return f(this); } finally { this.restore(s); }
  }
  shift(dir, h, f) {
    const s = this.save();
    const G = this.G[this.e];
    this.l = this.l.map((la, a) => la + (G[a][dir] ?? 0) * h); // fields move with their gradient
    if (dir === 0) this.x += h; else if (dir === 1) this.y += h; else this.z += h;
    this.bump();
    try { return f(this); } finally { this.restore(s); }
  }
  integrate(f, where, kind) {
    const s = this.save();
    let acc = 0;
    const add = (v, w) => { acc = isVec(v) ? (acc === 0 ? [0, 0, 0] : acc).map((a, k) => a + w * v[k]) : acc + w * v; };
    try {
      if (kind === 'boundary') {
        for (const be of this.boundaryEdges()) for (const [l, w] of be.qp) { this.place(be.e, l); add(f(this), w); }
      } else {
        for (let e = 0; e < this.mesh.tri.length; e++) {
          if (where != null && this.mesh.triRegion[e] !== where) continue;
          for (const [l, w] of quad(this.mesh.dim)) { this.place(e, l); add(f(this), w * this.area[e]); }
        }
      }
    } finally { this.restore(s); }
    return acc;
  }
  extremum(f, max) {
    const s = this.save();
    let best = max ? -Infinity : Infinity;
    try {
      const m = this.mesh;
      for (let e = 0; e < m.tri.length; e++) for (let a = 0; a < m.tri[e].length; a++) {
        const l = m.tri[e].map((_, b) => (a === b ? 1 : 0));
        this.place(e, l);
        const v = scalar(f(this));
        best = max ? Math.max(best, v) : Math.min(best, v);
      }
    } finally { this.restore(s); }
    return best;
  }
  boundaryEdges() {
    if (this._bedges) return this._bedges;
    const m = this.mesh;
    const owner = new Map();
    m.tri.forEach((t, e) => {
      if (m.dim === 1) return;
      for (let k = 0; k < 3; k++) { const a = t[k], b = t[(k + 1) % 3]; owner.set(a < b ? `${a},${b}` : `${b},${a}`, [e, k, (k + 1) % 3]); }
    });
    const g = 1 / Math.sqrt(3);
    this._bedges = m.bedges.map(be => {
      const [e, ka, kb] = owner.get(be.a < be.b ? `${be.a},${be.b}` : `${be.b},${be.a}`);
      const t = m.tri[e];
      const len = Math.hypot(m.x[be.a] - m.x[be.b], m.y[be.a] - m.y[be.b]);
      const qp = [0.5 - g / 2, 0.5 + g / 2].map(s => {
        const l = [0, 0, 0];
        l[ka] = 1 - s; l[kb] = s;
        return [l, len / 2];
      });
      return { ...be, e, qp, nodes: [t[ka], t[kb]], local: [ka, kb] };
    });
    return this._bedges;
  }
  nodal(f) { // value at each node, averaged over the elements that share it
    const m = this.mesh, nn = m.x.length;
    const sum = new Float64Array(nn), cnt = new Float64Array(nn);
    const s = this.save();
    try {
      for (let e = 0; e < m.tri.length; e++) for (let a = 0; a < m.tri[e].length; a++) {
        const l = m.tri[e].map((_, b) => (a === b ? 1 : 0));
        this.place(e, l);
        const v = f(this);
        if (Number.isFinite(v)) { sum[m.tri[e][a]] += v; cnt[m.tri[e][a]]++; }
      }
    } finally { this.restore(s); }
    return Array.from(sum, (v, i) => (cnt[i] ? v / cnt[i] : NaN));
  }
}

const Q2 = [[[2 / 3, 1 / 6, 1 / 6], 1 / 3], [[1 / 6, 2 / 3, 1 / 6], 1 / 3], [[1 / 6, 1 / 6, 2 / 3], 1 / 3]];
const g3 = 1 / Math.sqrt(3);
const Q1 = [[[0.5 + g3 / 2, 0.5 - g3 / 2], 0.5], [[0.5 - g3 / 2, 0.5 + g3 / 2], 0.5]];
const quad = dim => (dim === 1 ? Q1 : Q2);

// ---------------------------------------------------------------- weak form
function containsDiv(n, model) {
  if (!n || typeof n !== 'object') return false;
  if (n.k === 'call') {
    if (DIV_OPS.has(n.f)) return true;
    if (OPAQUE.has(n.f)) return false;
    return n.args.some(a => containsDiv(a, model));
  }
  if (n.k === 'name') {
    const d = model.defs.get(n.id);
    return !!(d && d.expr && !d.params && !model.vars.has(n.id) && containsDiv(d.expr, model));
  }
  return ['a', 'b', 'c'].some(k => containsDiv(n[k], model));
}

// Split a residual into [{sign, coef(node|null), V(node)} | {sign, src(node)}].
function splitTerms(n, sign, model, out, coef = null) {
  const tok = n.tok;
  if (n.k === 'bin' && (n.op === '+' || n.op === '-')) {
    splitTerms(n.a, sign, model, out, coef);
    splitTerms(n.b, n.op === '-' ? -sign : sign, model, out, coef);
    return out;
  }
  if (n.k === 'neg') return splitTerms(n.a, -sign, model, out, coef);
  if (!containsDiv(n, model)) { out.push({ sign, src: coef ? { k: 'bin', op: '*', a: coef, b: n, tok } : n }); return out; }
  if (n.k === 'name') return splitTerms(model.defs.get(n.id).expr, sign, model, out, coef);
  if (n.k === 'bin' && (n.op === '*' || n.op === '/')) {
    const da = containsDiv(n.a, model), db = containsDiv(n.b, model);
    if (n.op === '*' && da && !db) return splitTerms(n.a, sign, model, out, mul(coef, n.b, tok));
    if (n.op === '*' && db && !da) return splitTerms(n.b, sign, model, out, mul(coef, n.a, tok));
    if (n.op === '/' && da && !db) return splitTerms(n.a, sign, model, out, mul(coef, { k: 'bin', op: '/', a: { k: 'num', v: 1, tok }, b: n.b, tok }, tok));
  }
  if (n.k === 'call') {
    const A = n.args;
    const vecOf = (...c) => ({ k: 'call', f: 'vector', args: c, tok });
    const call = (f, ...args) => ({ k: 'call', f, args, tok });
    const zero = { k: 'num', v: 0, tok };
    let V = null;
    if (n.f === 'div') V = A.length > 1 ? vecOf(...A) : A[0];
    else if (n.f === 'del2') V = call('grad', A[0]);
    else if (n.f === 'dxx') V = vecOf(call('dx', A[0]), zero);
    else if (n.f === 'dyy') V = vecOf(zero, call('dy', A[0]));
    else if (n.f === 'dxy' || n.f === 'dyx') V = vecOf(call('dy', A[0]), zero);
    if (V) {
      if (containsDiv(V, model)) throw new FlexError('Third and higher order spatial derivatives are not supported', tok?.line, tok?.col);
      out.push({ sign, coef, V });
      return out;
    }
  }
  throw new FlexError('Unsupported form of second-derivative term in equation (use div(...) at top level)', tok?.line, tok?.col);
}
const mul = (a, b, tok) => (a ? { k: 'bin', op: '*', a, b, tok } : b);

export function buildFemSystem(model, mesh, thr) {
  const eqs = assignEquations(model);
  const nv = model.unknowns.length;
  if (eqs.some(e => e.rows.length > 1)) throw new FlexError('Vector variables are only supported in ngrid=1 (ODE) problems');
  const ctx = new FemCtx(model, mesh, nv);
  const C = model.compiler;
  const eqTerms = eqs.map(e => {
    const terms = splitTerms({ k: 'bin', op: '-', a: e.lhs, b: e.rhs, tok: e.lhs.tok }, 1, model, []);
    return {
      row: e.rows[0],
      div: terms.filter(t => t.V).map(t => ({ sign: t.sign, V: C.compile(t.V), c: t.coef ? C.compile(t.coef) : null })),
      src: terms.filter(t => t.src).map(t => ({ sign: t.sign, f: C.compile(t.src) })),
    };
  });
  const nn = mesh.x.length, N = nn * nv;
  const dim = mesh.dim;
  const nodeElem = new Int32Array(nn).fill(-1);
  mesh.tri.forEach((t, e) => { for (const nd of t) if (nodeElem[nd] < 0) nodeElem[nd] = e; });
  const placeAtNode = nd => { const e = nodeElem[nd]; ctx.place(e, mesh.tri[e].map(n => (n === nd ? 1 : 0))); };
  // boundary conditions
  const varIdx = key => { const v = model.vars.get(key); return v && v.idx !== undefined ? v.idx : -1; };
  const dirichlet = new Map(); // dof -> compiled g
  const naturalEdges = []; // {be, k, g}
  const pointNatural = []; // {node, k, g}
  const compileBc = bc => C.compile(bc.expr);
  if (dim === 2) {
    for (const be of ctx.boundaryEdges()) for (const bc of be.bcs) {
      const k = varIdx(bc.var);
      if (k < 0) throw new FlexError(`Undefined Name: ${bc.var.toUpperCase()}`, bc.line);
      if (bc.type === 'value') { const g = compileBc(bc); for (const nd of be.nodes) dirichlet.set(nd * nv + k, g); }
    }
    for (const be of ctx.boundaryEdges()) for (const bc of be.bcs) {
      const k = varIdx(bc.var);
      if (bc.type === 'natural') naturalEdges.push({ be, k, g: compileBc(bc) });
    }
  }
  for (const [node, bcs] of mesh.nodeBcs) for (const bc of bcs) {
    const k = varIdx(bc.var);
    if (k < 0) throw new FlexError(`Undefined Name: ${bc.var.toUpperCase()}`, bc.line);
    if (bc.type === 'value') dirichlet.set(node * nv + k, compileBc(bc));
    else if (bc.type === 'natural') pointNatural.push({ node, k, g: compileBc(bc) });
  }
  const hasDirichlet = new Array(nv).fill(false);
  for (const dof of dirichlet.keys()) hasDirichlet[dof % nv] = true;
  // dof numbering with reverse Cuthill-McKee
  const perm = rcm(mesh);
  const dofOf = (node, k) => perm[node] * nv + k;
  let bw = 0;
  for (const t of mesh.tri) for (const a of t) for (const b of t) bw = Math.max(bw, Math.abs(perm[a] - perm[b]));
  const kl = (bw + 1) * nv - 1;
  const Q = quad(dim);

  const elemResidual = (e, out) => {
    const t = mesh.tri[e], G = ctx.G[e], w0 = ctx.area[e];
    out.fill(0);
    for (const [l, w] of Q) {
      ctx.place(e, l);
      for (const eq of eqTerms) {
        const k = eq.row;
        for (const d of eq.div) {
          const V = d.V(ctx);
          const c = d.c ? scalar(d.c(ctx)) : 1;
          const vx = isVec(V) ? V[0] : V, vy = isVec(V) ? V[1] : 0;
          for (let a = 0; a < t.length; a++) out[a * nv + k] -= d.sign * c * w * w0 * (vx * G[a][0] + vy * G[a][1]);
        }
        for (const s of eq.src) {
          const S = scalar(s.f(ctx)) * s.sign * w * w0;
          for (let a = 0; a < t.length; a++) out[a * nv + k] += S * l[a];
        }
      }
    }
  };
  const edgeResidual = (ne, out) => {
    out.fill(0);
    for (const [l, w] of ne.be.qp) {
      ctx.place(ne.be.e, l);
      const g = scalar(ne.g(ctx)) * w;
      out[0] += g * l[ne.be.local[0]];
      out[1] += g * l[ne.be.local[1]];
    }
  };

  // assemble residual R (and banded Jacobian when J is given) at state ctx.U
  const assemble = (withJ) => {
    const R = new Float64Array(N);
    const J = withJ ? new Band(N, kl) : null;
    const U = ctx.U;
    for (let e = 0; e < mesh.tri.length; e++) {
      const t = mesh.tri[e], m = t.length * nv;
      const r0 = new Float64Array(m), r1 = new Float64Array(m);
      elemResidual(e, r0);
      for (let a = 0; a < t.length; a++) for (let k = 0; k < nv; k++) R[dofOf(t[a], k)] += r0[a * nv + k];
      if (!withJ) continue;
      for (let b = 0; b < t.length; b++) for (let kb = 0; kb < nv; kb++) {
        const gi = t[b] * nv + kb, u = U[gi];
        const d = 1e-7 * Math.max(Math.abs(u), thr[kb], 1e-10);
        U[gi] = u + d;
        elemResidual(e, r1);
        U[gi] = u;
        const col = dofOf(t[b], kb);
        for (let a = 0; a < t.length; a++) for (let k = 0; k < nv; k++) {
          const v = (r1[a * nv + k] - r0[a * nv + k]) / d;
          if (v) J.add(dofOf(t[a], k), col, v);
        }
      }
    }
    for (const ne of naturalEdges) {
      const r0 = [0, 0], r1 = [0, 0];
      edgeResidual(ne, r0);
      const [na, nb] = ne.be.nodes;
      R[dofOf(na, ne.k)] += r0[0]; R[dofOf(nb, ne.k)] += r0[1];
      if (!withJ) continue;
      const t = mesh.tri[ne.be.e];
      for (const nd of t) for (let kb = 0; kb < nv; kb++) {
        const gi = nd * nv + kb, u = U[gi];
        const d = 1e-7 * Math.max(Math.abs(u), thr[kb], 1e-10);
        U[gi] = u + d; edgeResidual(ne, r1); U[gi] = u;
        const col = dofOf(nd, kb);
        J.add(dofOf(na, ne.k), col, (r1[0] - r0[0]) / d);
        J.add(dofOf(nb, ne.k), col, (r1[1] - r0[1]) / d);
      }
    }
    for (const pn of pointNatural) { // 1D end-point fluxes
      placeAtNode(pn.node);
      R[dofOf(pn.node, pn.k)] += scalar(pn.g(ctx));
    }
    // pure-Neumann variables: tiny mass term pins the free constant (FlexPDE returns the
    // zero-mean-like solution for e.g. div(grad(u))=0 with no VALUE conditions)
    if (withJ) for (let k = 0; k < nv; k++) if (!hasDirichlet[k]) {
      let dmax = 0;
      for (let nd = 0; nd < nn; nd++) dmax = Math.max(dmax, Math.abs(J.get(dofOf(nd, k), dofOf(nd, k))));
      const eps = 1e-10 * (dmax || 1);
      for (let nd = 0; nd < nn; nd++) { J.add(dofOf(nd, k), dofOf(nd, k), eps); R[dofOf(nd, k)] += eps * U[nd * nv + k]; }
    }
    for (const [gi, g] of dirichlet) {
      const nd = Math.floor(gi / nv), k = gi % nv;
      placeAtNode(nd);
      const row = dofOf(nd, k);
      R[row] = U[gi] - scalar(g(ctx));
      if (withJ) { J.clearRow(row); J.set(row, row, 1); }
    }
    return { R, J };
  };

  const scaleOf = U => {
    const s = new Float64Array(nv);
    for (let k = 0; k < nv; k++) {
      let m = thr[k];
      for (let nd = 0; nd < nn; nd++) m = Math.max(m, Math.abs(U[nd * nv + k]));
      s[k] = m || 1;
    }
    return s;
  };
  const newton = (guess, maxIt = 30) => {
    const U = Float64Array.from(guess);
    ctx.U = U;
    for (let it = 0; it < maxIt; it++) {
      const { R, J } = assemble(true);
      const dx = J.solve(R);
      if (!dx) return null;
      const sc = scaleOf(U);
      let norm = 0;
      for (let nd = 0; nd < nn; nd++) for (let k = 0; k < nv; k++) {
        const d = dx[dofOf(nd, k)];
        U[nd * nv + k] -= d;
        norm = Math.max(norm, Math.abs(d) / sc[k]);
      }
      if (!Number.isFinite(norm)) return null;
      if (norm < 1e-9) return U;
    }
    return null;
  };
  const solve = (tNew, c, Y1, Y2, guess, h, t1, t2) => {
    ctx.t = tNew; ctx.deltat = h;
    ctx.lv = c ? { c, Y1, Y2, t1, t2 } : null;
    return newton(guess);
  };
  return { n: N, nv, thr: Float64Array.from({ length: N }, (_, i) => thr[i % nv]), solve, ctx, newton };
}

// Reverse Cuthill-McKee node permutation: perm[node] = new index
function rcm(mesh) {
  const nn = mesh.x.length;
  const adj = Array.from({ length: nn }, () => new Set());
  for (const t of mesh.tri) for (const a of t) for (const b of t) if (a !== b) adj[a].add(b);
  const deg = adj.map(s => s.size);
  const order = [], seen = new Uint8Array(nn);
  for (;;) {
    let start = -1;
    for (let i = 0; i < nn; i++) if (!seen[i] && (start < 0 || deg[i] < deg[start])) start = i;
    if (start < 0) break;
    const q = [start]; seen[start] = 1;
    for (let h = 0; h < q.length; h++) {
      const nb = [...adj[q[h]]].filter(j => !seen[j]).sort((a, b) => deg[a] - deg[b]);
      for (const j of nb) { seen[j] = 1; q.push(j); }
    }
    order.push(...q);
  }
  order.reverse();
  const perm = new Int32Array(nn);
  order.forEach((node, i) => { perm[node] = i; });
  return perm;
}

// Banded matrix with room for partial-pivoting fill: row i stores columns [i-kl, i+2kl].
class Band {
  constructor(n, kl) { this.n = n; this.kl = kl; this.W = 3 * kl + 1; this.a = new Float64Array(n * this.W); }
  idx(i, j) { return i * this.W + (j - i + this.kl); }
  add(i, j, v) { this.a[this.idx(i, j)] += v; }
  set(i, j, v) { this.a[this.idx(i, j)] = v; }
  get(i, j) { return this.a[this.idx(i, j)]; }
  clearRow(i) { const s = i * this.W; this.a.fill(0, s, s + this.W); }
  solve(b) {
    const { n, kl, W, a } = this;
    const x = Float64Array.from(b);
    for (let k = 0; k < n; k++) {
      const iMax = Math.min(n - 1, k + kl);
      let p = k, best = Math.abs(a[this.idx(k, k)]);
      for (let i = k + 1; i <= iMax; i++) { const v = Math.abs(a[this.idx(i, k)]); if (v > best) { best = v; p = i; } }
      if (!(best > 0)) return null;
      const jMax = Math.min(n - 1, k + 2 * kl);
      if (p !== k) {
        for (let j = k; j <= jMax; j++) { const u = this.idx(k, j), w = this.idx(p, j); const tmp = a[u]; a[u] = a[w]; a[w] = tmp; }
        const tmp = x[k]; x[k] = x[p]; x[p] = tmp;
      }
      const piv = a[this.idx(k, k)];
      for (let i = k + 1; i <= iMax; i++) {
        const ik = this.idx(i, k);
        const f = a[ik] / piv;
        if (f === 0) continue;
        a[ik] = 0;
        const ri = i * W - i + kl, rk = k * W - k + kl;
        for (let j = k + 1; j <= jMax; j++) a[ri + j] -= f * a[rk + j];
        x[i] -= f * x[k];
      }
    }
    for (let k = n - 1; k >= 0; k--) {
      const rk = k * W - k + kl;
      let s = x[k];
      const jMax = Math.min(n - 1, k + 2 * kl);
      for (let j = k + 1; j <= jMax; j++) s -= a[rk + j] * x[j];
      x[k] = s / a[rk + k];
    }
    return x;
  }
}
