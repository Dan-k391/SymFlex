// FlexPDE 8 emulator entry point (pure ES module; runs in Node and in a Web Worker).
//   runFlex(scriptText, {onProgress}) -> {title, log, errors, reports, final, plots, halted, fields}
//   lintFlex(text) -> [{line, col, msg, severity}]
import { parseFlex } from './parser.js';
import { FlexError } from './lexer.js';
import { buildModel, PointCtx } from './model.js';
import { buildOdeSystem } from './ode.js';
import { buildFemSystem } from './fem.js';
import { buildGeometry, buildMesh } from './mesh.js';
import { integrate, bdfCoefs } from './timestep.js';
import { historyPlot, elevationPlot, fieldPlot, vectorPlot, gridPlot } from './plots.js';
import { scalar, isVec } from './expr.js';
export { lintFlex } from './lint.js';
export { BUILTIN_NAMES } from './expr.js'; // for editor completion

const SPATIAL = new Set(['dx', 'dy', 'dz', 'grad', 'div', 'curl', 'del2', 'dxx', 'dyy', 'dxy', 'dyx']);
const FIELD_MSG = 'A Scalar Evaluation has encountered a Field value with no Location Specified';
const DEFAULT_THRESHOLD = 1e-6;

export async function runFlex(scriptText, { onProgress, maxSteps } = {}) {
  const result = { title: '', log: [], errors: [], reports: [], final: { t: null, values: {} }, plots: [], halted: false };
  const progress = msg => { result.log.push(msg); if (onProgress) onProgress(msg); };
  try {
    await solveProblem(scriptText, result, progress, maxSteps);
  } catch (e) {
    if (e instanceof FlexError) result.errors.push({ line: e.line || 0, col: e.col || 0, msg: e.message });
    else result.errors.push({ line: 0, col: 0, msg: `Internal error: ${e && e.message ? e.message : e}` });
  }
  return result;
}

async function solveProblem(text, result, progress, maxSteps) {
  const P = parseFlex(text);
  result.title = P.title;
  const model = buildModel(P);
  const C = model.compiler;
  const sel = k => (P.select[k] ? model.constant(P.select[k]) : undefined);
  const errlim = sel('terrlim') ?? sel('errlim') ?? 0.002;
  const ngrid = sel('ngrid') ?? 10;
  const thr = Float64Array.from(model.unknowns, u => (u.thr ? model.constant(u.thr) : DEFAULT_THRESHOLD));
  const geom = buildGeometry(model);
  model.domain = { centroid: geom.centroid, measure: geom.measure };
  const spatial = model.equations.some(e => usesSpatial(e.lhs, model) || usesSpatial(e.rhs, model));
  const plotBlocks = P.plots.filter(b => b.section !== 'monitors');
  checkLocations(plotBlocks, model);

  const T = P.time;
  const t0 = T ? model.constant(T.from) : 0;
  const t1 = T ? model.endtime : 0;
  const landTimes = T ? plotTimes(P.plots, model, t0, t1) : [];
  progress(`${spatial ? 'FEM' : 'ODE'} problem: ${model.unknowns.length} variable(s)`);

  let sol;
  if (!spatial) {
    const sys = buildOdeSystem(model, thr);
    const Y0 = initialValues(model, sys.ctx, t0);
    sol = pointSolution(model, geom, ngrid);
    if (T) {
      const halts = compileHalts(T, model);
      const out = integrate(sys, {
        t0, t1, Y0, errlim, h0: T.by ? model.constant(T.by) : undefined, landTimes, maxSteps,
        limit: T.limit ? model.constant(T.limit) : undefined, minDt: halts.minDt,
        onStep(t, Y) {
          sol.states.push({ t, Y: Float64Array.from(Y) });
          if (sol.states.length % 2000 === 0) progress(`Step ${sol.states.length} Time= ${t.toPrecision(6)}`);
          return halts.cond.length > 0 && halts.test(sol, sol.states.length - 1);
        },
      });
      sol.states.unshift({ t: t0, Y: Y0 });
      finishRun(out, result, progress);
    } else {
      const Y = sys.solve(0, null, null, null, Y0, 0) || Y0;
      sol.states.push({ t: 0, Y });
    }
    const last = sol.states[sol.states.length - 1];
    result.final.t = last.t;
    result.final.range = {}; // [min, max] of each variable over the run (for scale-aware checks)
    model.unknowns.forEach((u, i) => {
      if (u.hidden) return;
      result.final.values[u.name] = last.Y[i];
      let lo = Infinity, hi = -Infinity;
      for (const st of sol.states) { lo = Math.min(lo, st.Y[i]); hi = Math.max(hi, st.Y[i]); }
      result.final.range[u.name] = [lo, hi];
    });
  } else {
    const mesh = buildMesh(geom, ngrid);
    progress(`Mesh: ${mesh.x.length} nodes, ${mesh.tri.length} cells`);
    const sys = buildFemSystem(model, mesh, thr);
    const nv = sys.nv;
    const U0 = new Float64Array(sys.n);
    const ictx = sys.ctx;
    ictx.U = U0; ictx.t = t0;
    const inits = P.initial.map(iv => ({ v: model.vars.get(iv.key), f: C.compile(iv.expr), iv }));
    for (let nd = 0; nd < mesh.x.length; nd++) {
      const pt = [mesh.x[nd], mesh.y[nd]];
      for (const { v, f, iv } of inits) {
        if (!v) throw new FlexError(`Undefined Name: ${iv.name.toUpperCase()}`, iv.line, iv.col);
        const val = ictx.at(pt, f);
        if (v.idxs) v.idxs.forEach((i, k) => { U0[nd * nv + i] = val[k]; });
        else U0[nd * nv + v.idx] = scalar(val);
      }
    }
    sol = femSolution(model, mesh, sys.ctx);
    if (T) {
      const halts = compileHalts(T, model);
      const out = integrate(sys, {
        t0, t1, Y0: U0, errlim, h0: T.by ? model.constant(T.by) : undefined, landTimes, maxSteps,
        limit: T.limit ? model.constant(T.limit) : undefined, minDt: halts.minDt,
        onStep(t, Y) {
          sol.states.push({ t, Y: Float64Array.from(Y) });
          if (sol.states.length % 50 === 0) progress(`Step ${sol.states.length} Time= ${t.toPrecision(6)}`);
          return halts.cond.length > 0 && halts.test(sol, sol.states.length - 1);
        },
      });
      sol.states.unshift({ t: t0, Y: U0 });
      finishRun(out, result, progress);
    } else {
      const U = sys.solve(0, null, null, null, U0, 0);
      if (!U) throw new FlexError('Solution did not converge');
      sol.states.push({ t: 0, Y: U });
    }
    const last = sol.states[sol.states.length - 1];
    result.final.t = T ? last.t : null;
    result.fields = {};
    model.unknowns.forEach((u, k) => {
      result.fields[u.name] = { x: Array.from(mesh.x), y: Array.from(mesh.y), tri: mesh.tri.map(t => t.slice()), values: Array.from({ length: mesh.x.length }, (_, nd) => last.Y[nd * nv + k]) };
    });
  }

  // ---- reports and plots at the final state
  sol.setState(sol.states.length - 1);
  const compile = node => C.compile(node);
  for (const block of plotBlocks) for (const item of block.items) {
    if (item.type === 'report') {
      for (const e of item.exprs) {
        if (e.k === 'str') { result.reports.push({ label: e.v, value: null }); continue; }
        const v = compile(e)(sol.ctx);
        result.reports.push({ label: item.exprs.length > 1 ? e.label : item.label, value: scalar(v, e.tok), expr: e.label });
      }
      continue;
    }
    const spec = makePlot(item, sol, compile);
    sol.setState(sol.states.length - 1);
    if (spec) result.plots.push(spec);
  }
  if (!P.hasEnd) result.log.push('Warning: no END statement');
}

function finishRun(out, result, progress) {
  result.halted = out.halted;
  progress(`${out.steps} steps, ${out.fails} retries`);
  if (out.halted) progress(out.reason === 'mindt' ? 'Halt: timestep below minimum' : 'Halt on User Condition');
  if (out.reason === 'maxsteps') result.errors.push({ line: 0, col: 0, msg: 'Step limit reached' });
}

function makePlot(item, sol, compile) {
  switch (item.type) {
    case 'history': return historyPlot(item, sol, compile);
    case 'elevation': return elevationPlot(item, sol, compile);
    case 'contour': return fieldPlot(item, sol, compile, 'contour');
    case 'surface': return fieldPlot(item, sol, compile, 'surface');
    case 'vector': return vectorPlot(item, sol, compile);
    case 'grid': return gridPlot(item, sol);
    default: return null; // summary, table, export, ...
  }
}

function usesSpatial(node, model, seen = new Set()) {
  if (!node || typeof node !== 'object') return false;
  if (node.k === 'call') {
    if (SPATIAL.has(node.f)) return true;
    if (['val', 'eval', 'integral', 'integrate'].includes(node.f)) return false;
    const d = model.defs.get(node.f);
    if (d && d.params && !seen.has(node.f)) { seen.add(node.f); if (usesSpatial(d.expr, model, seen)) return true; }
    return node.args.some(a => usesSpatial(a, model, seen));
  }
  if (node.k === 'name') {
    const d = model.defs.get(node.id);
    if (d && d.expr && !seen.has(node.id)) { seen.add(node.id); return usesSpatial(d.expr, model, seen); }
    return false;
  }
  return ['a', 'b', 'c'].some(k => usesSpatial(node[k], model, seen));
}

// FlexPDE 8 refuses scalar output (REPORT, HISTORY without AT) of field values without a location.
function checkLocations(blocks, model) {
  const C = model.compiler;
  for (const b of blocks) for (const it of b.items) {
    if (it.type === 'report') {
      for (const e of it.exprs) if (C.fieldDep(e)) throw new FlexError(FIELD_MSG, it.line, it.col);
    } else if (it.type === 'history' && !(it.at && it.at.length)) {
      for (const e of it.args) if (C.fieldDep(e)) throw new FlexError(FIELD_MSG, e.tok.line, e.tok.col);
    }
  }
}

function plotTimes(blocks, model, t0, t1) {
  const out = [];
  for (const b of blocks) {
    if (!b.times) continue;
    let cur = null;
    for (const s of b.times) {
      if (s.at) { cur = model.constant(s.at); out.push(cur); continue; }
      const by = model.constant(s.by), to = model.constant(s.to);
      if (!(by > 0)) continue;
      const n = Math.floor((to - cur) / by + 1e-9);
      for (let i = 1; i <= n && out.length < 1e6; i++) out.push(cur + i * by);
      cur = to;
      if (Math.abs(out[out.length - 1] - to) > 1e-9 * Math.abs(by)) out.push(to);
    }
  }
  return [...new Set(out)].filter(x => x > t0 && x <= t1).sort((a, b) => a - b);
}

function compileHalts(T, model) {
  const C = model.compiler;
  const cond = [];
  let minDt;
  for (const h of T.halt) {
    if (isCondition(h)) cond.push(C.compile(h));
    else minDt = model.constant(h);
  }
  return {
    cond, minDt,
    test(sol, k) {
      sol.setState(k);
      const ctx = sol.ctx;
      return cond.some(f => (sol.mesh && sol.isFem ? ctx.at(model.domain.centroid, f) : f(ctx)) ? true : false);
    },
  };
}
const isCondition = n => (n.k === 'bin' && ['<', '>', '<=', '>=', '=', '<>', 'and', 'or'].includes(n.op)) || n.k === 'not';

function initialValues(model, ctx, t0) {
  const Y = new Float64Array(model.unknowns.length);
  ctx.set(Y, t0);
  for (const iv of model.P.initial) {
    const v = model.vars.get(iv.key);
    if (!v) throw new FlexError(`Undefined Name: ${iv.name.toUpperCase()}`, iv.line, iv.col);
    const val = model.compiler.compile(iv.expr)(ctx);
    if (v.idxs) {
      if (!isVec(val)) throw new FlexError('Vector value expected', iv.line, iv.col);
      v.idxs.forEach((i, k) => { Y[i] = val[k]; });
    } else Y[v.idx] = scalar(val, iv.expr.tok);
    ctx.set(Y, t0);
  }
  return Y;
}

// Solution views used by plots and reports.
function levelsFor(states, k) {
  if (k < 1) return null;
  const h = states[k].t - states[k - 1].t;
  if (!(h > 0)) return null;
  const hp = k >= 2 ? states[k - 1].t - states[k - 2].t : 0;
  return { c: bdfCoefs(h, hp > 0 ? hp : 0), Y1: states[k - 1].Y, Y2: hp > 0 ? states[k - 2].Y : null, t1: states[k - 1].t, t2: k >= 2 ? states[k - 2].t : 0 };
}

function pointSolution(model, geom, ngrid) {
  const ctx = new PointCtx(model);
  let mesh = null;
  const sol = {
    states: [], ctx, isFem: false, constant: model.constant,
    setState(k) { const s = this.states[k]; ctx.lv = levelsFor(this.states, k); ctx.deltat = ctx.lv ? s.t - ctx.lv.t1 : 0; ctx.set(s.Y, s.t); },
    get mesh() { return mesh || (mesh = buildMesh(geom, Math.min(ngrid, 10) > 1 ? Math.max(ngrid, 10) : 10)); },
    at: (pt, f) => ctx.at(pt, f),
    nodal(f) { const m = this.mesh; return Array.from(m.x, (x, i) => ctx.at([x, m.y[i]], f)); },
  };
  return sol;
}

function femSolution(model, mesh, ctx) {
  return {
    states: [], ctx, mesh, isFem: true, constant: model.constant,
    setState(k) { const s = this.states[k]; ctx.U = s.Y; ctx.t = s.t; ctx.lv = levelsFor(this.states, k); ctx.deltat = ctx.lv ? s.t - ctx.lv.t1 : 0; ctx.bump(); },
    at: (pt, f) => ctx.at(pt, f),
    nodal: f => ctx.nodal(f),
  };
}
