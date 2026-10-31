// Turns a parsed problem into compiled pieces: unknown layout, definitions, equations, constants.
import { Compiler, isVec, scalar } from './expr.js';
import { FlexError } from './lexer.js';

let GEN = 1;
export const nextGen = () => ++GEN;

// Minimal evaluation context with spatially uniform fields (used for constants, initial values
// and the ngrid=1 ODE mode). FEM uses its own context with the same interface.
export class PointCtx {
  constructor(model, Y = null) {
    this.model = model;
    this.t = 0; this.x = 0; this.y = 0; this.z = 0;
    this.gen = nextGen(); this.cv = []; this.cg = [];
    this.Y = Y; this.lv = null; this.region = 1; this.deltat = 0;
    this.endtime = model.endtime ?? 0; this.args = null;
  }
  bump() { this.gen = nextGen(); }
  set(Y, t) { this.Y = Y; if (t !== undefined) this.t = t; this.gen = nextGen(); }
  v(i) {
    if (!this.Y) throw new FlexError('A variable cannot be used in a constant expression');
    return this.Y[i];
  }
  g() { return [0, 0, 0]; }
  dtv(i) {
    const L = this.lv;
    if (!L) return 0;
    return L.c[0] * this.Y[i] + L.c[1] * L.Y1[i] + (L.Y2 ? L.c[2] * L.Y2[i] : 0);
  }
  dtExpr(f) {
    const L = this.lv;
    if (!L) return 0;
    const { Y, t } = this;
    const acc = (s, c, v) => (isVec(v) ? (s === 0 ? [0, 0, 0] : s).map((a, k) => a + c * v[k]) : s + c * v);
    let s = acc(0, L.c[0], f(this));
    this.set(L.Y1, L.t1); s = acc(s, L.c[1], f(this));
    if (L.Y2) { this.set(L.Y2, L.t2); s = acc(s, L.c[2], f(this)); }
    this.set(Y, t);
    return s;
  }
  at(pt, f) {
    const { x, y, z } = this;
    this.x = pt[0] ?? 0; this.y = pt[1] ?? 0; this.z = pt[2] ?? 0; this.bump();
    try { return f(this); } finally { this.x = x; this.y = y; this.z = z; this.bump(); }
  }
  shift(dir, h, f) {
    const k = dir === 0 ? 'x' : dir === 1 ? 'y' : 'z';
    const s = this[k];
    this[k] = s + h; this.bump();
    try { return f(this); } finally { this[k] = s; this.bump(); }
  }
  integrate(f) { // uniform fields: value at the domain centroid times its measure
    const m = this.model.domain;
    const v = this.at(m.centroid, f);
    return isVec(v) ? v.map(c => c * m.measure) : v * m.measure;
  }
  extremum(f) { return f(this); }
}

export function buildModel(P) {
  const vars = new Map();
  const unknowns = []; // [{name, key, thr(node|null)}]
  for (const v of P.variables) {
    if (vars.has(v.key)) throw new FlexError(`Duplicate variable ${v.name.toUpperCase()}`, v.line, v.col);
    if (v.comps) {
      const idxs = v.comps.map(c => {
        vars.set(c.key, { idx: unknowns.length });
        unknowns.push({ name: c.name, key: c.key, thr: v.thr, parent: v.key });
        return unknowns.length - 1;
      });
      vars.set(v.key, { idxs, name: v.name });
    } else {
      vars.set(v.key, { idx: unknowns.length, name: v.name });
      unknowns.push({ name: v.name, key: v.key, thr: v.thr });
    }
  }
  const defs = new Map();
  for (const d of P.defs) defs.set(d.key, d);
  const regionDefs = new Map();
  P.regions.forEach((r, ri) => {
    const num = r.number ?? ri + 1;
    for (const d of r.defs) {
      if (!regionDefs.has(d.key)) regionDefs.set(d.key, new Map());
      regionDefs.get(d.key).set(num, d);
    }
  });
  const dim = /1$/.test(P.coords) ? 1 : 2;
  const model = { P, vars, unknowns, defs, regionDefs, dim, endtime: 0, domain: { centroid: [0, 0], measure: 1 } };
  const equations = transformSecondOrder(P, model);
  model.compiler = new Compiler({ vars, defs, dim, regionDefs });
  model.equations = equations;
  model.constant = node => scalar(model.compiler.compile(node)(new PointCtx(model)), node.tok);
  // compile every definition up front so undefined names are reported like FlexPDE does
  for (const d of P.defs) if (d.expr && !d.params) model.compiler.defRef(d.key, { tok: { line: d.line, col: d.col } });
  for (const d of P.defs) if (d.expr && d.params) model.compiler.defEntry(d.key, { tok: { line: d.line, col: d.col } });
  if (P.time) model.endtime = model.constant(P.time.to);
  return model;
}

// dt(dt(u)) -> dt(u__dt) with the extra unknown u__dt and equation dt(u) = u__dt.
function transformSecondOrder(P, model) {
  const eqs = P.equations.map(e => ({ ...e }));
  const added = new Map();
  const visit = n => {
    if (!n || typeof n !== 'object') return n;
    if (n.k === 'call' && n.f === 'dt' && n.args[0]?.k === 'call' && n.args[0].f === 'dt' && n.args[0].args[0]?.k === 'name') {
      const base = n.args[0].args[0];
      const v = model.vars.get(base.id);
      if (v) {
        const key = `${base.id}__dt`;
        if (!added.has(key)) {
          added.set(key, base);
          const add = idx => { model.unknowns.push({ name: `dt(${model.unknowns[idx].name})`, key: `${model.unknowns[idx].key}__dt`, thr: model.unknowns[idx].thr, hidden: true }); return model.unknowns.length - 1; };
          if (v.idxs) model.vars.set(key, { idxs: v.idxs.map(add) });
          else model.vars.set(key, { idx: add(v.idx) });
          eqs.push({ label: key, lhs: { k: 'call', f: 'dt', args: [base], tok: base.tok }, rhs: { k: 'name', id: key, text: key, tok: base.tok }, line: base.tok.line });
        }
        return { k: 'call', f: 'dt', args: [{ k: 'name', id: key, text: key, tok: base.tok }], tok: n.tok };
      }
    }
    const out = { ...n };
    for (const k of ['a', 'b', 'c']) if (n[k]) out[k] = visit(n[k]);
    if (n.args) out.args = n.args.map(visit);
    return out;
  };
  for (const e of eqs) { e.lhs = visit(e.lhs); e.rhs = visit(e.rhs); }
  return eqs;
}

// Assign each equation to the unknown rows it determines (labels first, then declaration order).
export function assignEquations(model) {
  const { vars, unknowns } = model;
  const taken = new Set();
  const topVars = []; // declared variables (vector components are owned by their vector)
  for (const [k, v] of vars) {
    if (v.idxs) topVars.push(k);
    else if (!unknowns[v.idx].parent) topVars.push(k);
  }
  const out = [];
  for (const e of model.equations) {
    if (e.label) {
      if (!vars.has(e.label)) throw new FlexError(`Undefined Name: ${e.label.toUpperCase()}`, e.line, e.col);
      taken.add(e.label);
    }
  }
  for (const e of model.equations) {
    let key = e.label;
    if (!key) {
      key = topVars.find(k => !taken.has(k));
      if (!key) throw new FlexError('More equations than variables', e.line, e.col);
      taken.add(key);
    }
    const v = vars.get(key);
    out.push({ ...e, var: key, rows: v.idxs ? v.idxs : [v.idx] });
  }
  const covered = new Set(out.flatMap(e => e.rows));
  const missing = unknowns.filter((u, i) => !covered.has(i));
  if (missing.length) throw new FlexError(`No equation for variable ${missing[0].name.toUpperCase()}`);
  return out;
}
