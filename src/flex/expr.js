// Expression compiler: AST -> closures evaluated against a runtime context `ctx`.
// Values are numbers or 3-component vectors (JS arrays). Booleans are 1/0.
//
// The context supplies the solution state; compiled code only calls these members:
//   ctx.t, ctx.x, ctx.y, ctx.z, ctx.gen (bumped whenever anything above or the state changes),
//   ctx.v(i)        value of scalar unknown i at the current point
//   ctx.g(i)        gradient [gx, gy, gz] of unknown i at the current point
//   ctx.dtv(i)      time derivative of unknown i (implicit-step formula)
//   ctx.dtExpr(f)   time derivative of an arbitrary compiled expression
//   ctx.at(pt, f)   evaluate f at point pt (VAL/EVAL)
//   ctx.shift(dir, h, f)  evaluate f with the evaluation point moved by h along axis dir
//   ctx.integrate(f, where)  domain integral
//   ctx.region      current region number (region-specific definitions)
//   ctx.deltat, ctx.endtime
import { FlexError } from './lexer.js';

export const isVec = Array.isArray;
const vec = (a, b = 0, c = 0) => [a, b, c];
const scalar = (v, tok) => {
  if (!isVec(v)) return v;
  if (v[0] === 0 && v[1] === 0) return v[2]; // 2D cross products act as scalars
  throw new FlexError('A Scalar Value is required.', tok?.line, tok?.col);
};

function binop(op, a, b, tok) {
  if (!isVec(a) && !isVec(b)) {
    switch (op) {
      case '+': return a + b;
      case '-': return a - b;
      case '*': return a * b;
      case '/': return a / b;
      case '^': return pow(a, b);
      case '<': return a < b ? 1 : 0;
      case '>': return a > b ? 1 : 0;
      case '<=': return a <= b ? 1 : 0;
      case '>=': return a >= b ? 1 : 0;
      case '=': return a === b ? 1 : 0;
      case '<>': return a !== b ? 1 : 0;
    }
  }
  if (isVec(a) && isVec(b)) {
    switch (op) {
      case '+': return [a[0] + b[0], a[1] + b[1], a[2] + b[2]];
      case '-': return [a[0] - b[0], a[1] - b[1], a[2] - b[2]];
      case '*': return a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
    }
  } else if (isVec(a)) {
    switch (op) {
      case '*': return [a[0] * b, a[1] * b, a[2] * b];
      case '/': return [a[0] / b, a[1] / b, a[2] / b];
      case '^': if (b === 2) return a[0] * a[0] + a[1] * a[1] + a[2] * a[2]; break;
    }
  } else if (op === '*') return [a * b[0], a * b[1], a * b[2]];
  return binop(op, scalar(a, tok), scalar(b, tok), tok);
}

// FlexPDE evaluates negative bases with integer-valued exponents; others give NaN like C pow.
function pow(a, b) {
  if (b === 2) return a * a;
  if (b === 0.5) return Math.sqrt(a);
  return Math.pow(a, b);
}

const S = f => (args, tok) => f(...args.map(a => scalar(a, tok)));
const erf = x => { // Taylor series near 0, continued fraction for erfc further out
  const s = Math.sign(x); x = Math.abs(x);
  if (x < 2) { // Taylor series converges fast here
    let sum = x, term = x, n = 0;
    while (Math.abs(term) > 1e-17 * Math.abs(sum)) { n++; term *= -x * x / n; sum += term / (2 * n + 1); }
    return s * 2 / Math.sqrt(Math.PI) * sum;
  }
  // continued fraction for erfc
  let f = 0;
  for (let k = 60; k >= 1; k--) f = k / 2 / (x + f);
  return s * (1 - Math.exp(-x * x) / Math.sqrt(Math.PI) / (x + f));
};

// Plain functions of already-evaluated arguments.
export const FUNCS = {
  sin: S(Math.sin), cos: S(Math.cos), tan: S(Math.tan),
  asin: S(Math.asin), arcsin: S(Math.asin), acos: S(Math.acos), arccos: S(Math.acos),
  atan: S(Math.atan), arctan: S(Math.atan), atan2: S(Math.atan2), atan2v6: S((x, y) => Math.atan2(y, x)),
  sinh: S(Math.sinh), cosh: S(Math.cosh), tanh: S(Math.tanh),
  sech: S(x => 1 / Math.cosh(x)), csch: S(x => 1 / Math.sinh(x)), coth: S(x => 1 / Math.tanh(x)),
  exp: S(Math.exp), ln: S(Math.log), log: S(Math.log), log10: S(Math.log10), sqrt: S(Math.sqrt),
  abs: (a, tok) => isVec(a[0]) ? Math.hypot(...a[0]) : Math.abs(scalar(a[0], tok)),
  sign: S(x => (x > 0 ? 1 : x < 0 ? -1 : 0)),
  min: S((...v) => Math.min(...v)), max: S((...v) => Math.max(...v)),
  mod: S((a, b) => a % b), floor: S(Math.floor), ceil: S(Math.ceil), round: S(Math.round),
  erf: S(erf), erfc: S(x => 1 - erf(x)),
  ustep: S(x => (x > 0 ? 1 : 0)), uramp: S(x => (x > 0 ? x : 0)), upulse: S((a, b) => (a > 0 && b <= 0 ? 1 : 0)),
  random: S(x => Math.random() * x),
  vector: (a, tok) => vec(...a.map(v => scalar(v, tok))),
  magnitude: (a, tok) => a.length === 1 && isVec(a[0]) ? Math.hypot(a[0][0], a[0][1], a[0][2]) : Math.hypot(...a.map(v => scalar(v, tok))),
  dot: ([u, w]) => (isVec(u) && isVec(w) ? u[0] * w[0] + u[1] * w[1] + u[2] * w[2] : u * w),
  cross: ([u, w]) => [u[1] * w[2] - u[2] * w[1], u[2] * w[0] - u[0] * w[2], u[0] * w[1] - u[1] * w[0]],
  xcomp: ([u]) => (isVec(u) ? u[0] : u), ycomp: ([u]) => (isVec(u) ? u[1] : 0), zcomp: ([u]) => (isVec(u) ? u[2] : 0),
};

// Functions compiled specially (derivatives, point evaluation, integrals); listed for editors.
const SPECIAL = ['dt', 'dx', 'dy', 'dz', 'grad', 'div', 'del2', 'dxx', 'dyy', 'dxy', 'dyx', 'curl',
  'val', 'eval', 'integral', 'integrate', 'area_integral', 'vol_integral', 'line_integral', 'bintegral',
  'sintegral', 'vintegral', 'surf_integral', 'globalmax', 'globalmin'];
export const BUILTIN_NAMES = [...Object.keys(FUNCS), ...SPECIAL, 'pi', 't', 'x', 'y', 'z', 'r', 'theta', 'endtime', 'deltat'];
// shortcut: second derivatives outside the weak form are central differences of the P1 field,
// i.e. ~0 inside an element; upgrade to recovered (patch-averaged) gradients if plots need them.
const FD = 1e-6;

// Compiler. `env` describes names: env.vars (Map key -> {idx} | {idxs}), env.defs (Map key -> def),
// env.dim (1|2), env.regionDefs (Map key -> Map(regionNumber -> def)).
export class Compiler {
  constructor(env) {
    this.env = env;
    this.defFns = new Map(); // key -> compiled def evaluator
    this.defSlots = 0;
    this.compiling = new Set();
  }

  // Does `node` depend on a solution field outside VAL/EVAL/integrals? (scalar-context check)
  fieldDep(node, params = null, seen = new Set()) {
    if (!node || typeof node !== 'object') return false;
    switch (node.k) {
      case 'num': case 'str': return false;
      case 'name': {
        if (params && params.includes(node.id)) return false;
        if (this.env.vars.has(node.id)) return true;
        const d = this.env.defs.get(node.id);
        if (d && d.expr && !seen.has(node.id)) {
          seen.add(node.id);
          const r = this.fieldDep(d.expr, d.params, seen);
          seen.delete(node.id);
          return r;
        }
        return false;
      }
      case 'call': {
        if (['val', 'eval', 'integral', 'integrate', 'area_integral', 'vol_integral', 'line_integral', 'bintegral',
          'sintegral', 'vintegral', 'surf_integral', 'globalmax', 'globalmin'].includes(node.f)) return false;
        const d = this.env.defs.get(node.f);
        if (d && d.params && d.expr && !seen.has(node.f)) {
          seen.add(node.f);
          const r = this.fieldDep(d.expr, d.params, seen);
          seen.delete(node.f);
          if (r) return true;
        }
        return node.args.some(a => this.fieldDep(a, params, seen));
      }
      default: return ['a', 'b', 'c'].some(k => this.fieldDep(node[k], params, seen));
    }
  }

  compile(node, scope = null) {
    const env = this.env;
    switch (node.k) {
      case 'num': { const v = node.v; return () => v; }
      case 'str': { const v = node.v; return () => v; }
      case 'neg': {
        const a = this.compile(node.a, scope);
        return ctx => { const v = a(ctx); return isVec(v) ? [-v[0], -v[1], -v[2]] : -v; };
      }
      case 'not': { const a = this.compile(node.a, scope); return ctx => (a(ctx) ? 0 : 1); }
      case 'if': {
        const c = this.compile(node.c, scope), a = this.compile(node.a, scope), b = this.compile(node.b, scope);
        return ctx => (c(ctx) ? a(ctx) : b(ctx));
      }
      case 'bin': {
        const a = this.compile(node.a, scope), b = this.compile(node.b, scope), op = node.op, tok = node.tok;
        if (op === 'and') return ctx => (a(ctx) && b(ctx) ? 1 : 0);
        if (op === 'or') return ctx => (a(ctx) || b(ctx) ? 1 : 0);
        if (op === '+') return ctx => { const u = a(ctx), w = b(ctx); return typeof u === 'number' && typeof w === 'number' ? u + w : binop(op, u, w, tok); };
        if (op === '-') return ctx => { const u = a(ctx), w = b(ctx); return typeof u === 'number' && typeof w === 'number' ? u - w : binop(op, u, w, tok); };
        if (op === '*') return ctx => { const u = a(ctx), w = b(ctx); return typeof u === 'number' && typeof w === 'number' ? u * w : binop(op, u, w, tok); };
        if (op === '/') return ctx => { const u = a(ctx), w = b(ctx); return typeof u === 'number' && typeof w === 'number' ? u / w : binop(op, u, w, tok); };
        return ctx => binop(op, a(ctx), b(ctx), tok);
      }
      case 'name': return this.compileName(node, scope);
      case 'call': return this.compileCall(node, scope);
    }
    throw new FlexError('Bad expression', node.tok?.line, node.tok?.col);
  }

  compileName(node, scope) {
    const id = node.id, env = this.env;
    if (scope && scope.has(id)) { const j = scope.get(id); return ctx => ctx.args[j]; }
    if (env.vars.has(id)) {
      const v = env.vars.get(id);
      if (v.idxs) { const [i, j, k] = v.idxs; return k === undefined ? ctx => [ctx.v(i), ctx.v(j), 0] : ctx => [ctx.v(i), ctx.v(j), ctx.v(k)]; }
      const i = v.idx;
      return ctx => ctx.v(i);
    }
    if (env.defs.has(id) || (env.regionDefs && env.regionDefs.has(id))) return this.defRef(id, node);
    switch (id) {
      case 't': return ctx => ctx.t;
      case 'x': return ctx => ctx.x;
      case 'y': return ctx => ctx.y;
      case 'z': return ctx => ctx.z;
      case 'pi': return () => Math.PI;
      case 'r': return ctx => Math.hypot(ctx.x, ctx.y);
      case 'theta': return ctx => Math.atan2(ctx.y, ctx.x);
      case 'endtime': return ctx => ctx.endtime;
      case 'deltat': return ctx => ctx.deltat;
      case 'on': case 'true': return () => 1;
      case 'off': case 'false': return () => 0;
    }
    throw new FlexError(`Undefined Name: ${node.text.toUpperCase()}`, node.tok.line, node.tok.col);
  }

  // Definitions are compiled lazily (forward references are legal) and cached per ctx.gen.
  defRef(id, node) {
    const entry = this.defEntry(id, node);
    if (entry.params !== undefined) throw new FlexError(`Function ${id.toUpperCase()} needs arguments`, node.tok.line, node.tok.col);
    return entry.fn;
  }
  defEntry(id, node) {
    let entry = this.defFns.get(id);
    if (!entry) {
      entry = { fn: null, slot: this.defSlots++ };
      this.defFns.set(id, entry);
      const base = this.env.defs.get(id);
      const reg = this.env.regionDefs?.get(id);
      const compileDef = d => {
        if (!d.expr) throw new FlexError(`Undefined Name: ${d.name.toUpperCase()}`, node.tok.line, node.tok.col);
        if (this.compiling.has(d)) throw new FlexError(`Recursive definition: ${d.name.toUpperCase()}`, d.line, d.col);
        this.compiling.add(d);
        try { return this.compile(d.expr); } finally { this.compiling.delete(d); }
      };
      if (base && base.params) {
        const scope = new Map(base.params.map((p, j) => [p, j]));
        this.compiling.add(base);
        try { entry.params = base.params.length; entry.fn = this.compile(base.expr, scope); } finally { this.compiling.delete(base); }
      } else {
        const fb = base ? compileDef(base) : null;
        let raw = fb;
        if (reg) {
          const byRegion = new Map([...reg].map(([r, d]) => [r, compileDef(d)]));
          raw = ctx => { const f = byRegion.get(ctx.region); if (f) return f(ctx); if (!fb) throw new FlexError(`Undefined Name: ${id.toUpperCase()}`); return fb(ctx); };
        }
        const slot = entry.slot;
        entry.fn = ctx => {
          if (ctx.cg[slot] === ctx.gen) return ctx.cv[slot];
          const v = raw(ctx);
          ctx.cg[slot] = ctx.gen;
          ctx.cv[slot] = v;
          return v;
        };
      }
    }
    return entry;
  }

  compileCall(node, scope) {
    const f = node.f, env = this.env, tok = node.tok;
    const d = env.defs.get(f);
    if (d && d.params) { // user function: evaluate args, bind, evaluate body
      const entry = this.defEntry(f, node);
      if (node.args.length !== d.params.length) throw new FlexError(`Wrong number of arguments to ${f.toUpperCase()}`, tok.line, tok.col);
      const args = node.args.map(a => this.compile(a, scope));
      return ctx => {
        const saved = ctx.args;
        ctx.args = args.map(a => a(ctx));
        try { return entry.fn(ctx); } finally { ctx.args = saved; }
      };
    }
    if (env.vars.has(f) && node.args.length >= 1) { // u(x, y): point evaluation of a variable
      const inner = this.compileName({ k: 'name', id: f, text: f, tok }, scope);
      const pts = node.args.map(a => this.compile(a, scope));
      return ctx => ctx.at(pts.map(p => scalar(p(ctx), tok)), inner);
    }
    const A = () => node.args.map(a => this.compile(a, scope));
    switch (f) {
      case 'dt': {
        const a = node.args[0];
        if (a.k === 'name' && env.vars.has(a.id) && !(scope && scope.has(a.id))) {
          const v = env.vars.get(a.id);
          if (v.idxs) { const [i, j] = v.idxs; return ctx => [ctx.dtv(i), ctx.dtv(j), 0]; }
          const i = v.idx;
          return ctx => ctx.dtv(i);
        }
        const inner = this.compile(a, scope);
        return ctx => ctx.dtExpr(inner);
      }
      case 'dx': case 'dy': case 'dz': return this.deriv(node.args[0], { dx: 0, dy: 1, dz: 2 }[f], scope);
      case 'grad': {
        const gx = this.deriv(node.args[0], 0, scope), gy = this.deriv(node.args[0], 1, scope);
        return ctx => [scalar(gx(ctx), tok), env.dim > 1 ? scalar(gy(ctx), tok) : 0, 0];
      }
      case 'div': {
        const argNode = node.args.length > 1 ? { k: 'call', f: 'vector', args: node.args, tok } : node.args[0];
        const fx = this.deriv({ k: 'call', f: 'xcomp', args: [argNode], tok }, 0, scope);
        const fy = env.dim > 1 ? this.deriv({ k: 'call', f: 'ycomp', args: [argNode], tok }, 1, scope) : () => 0;
        return ctx => fx(ctx) + fy(ctx);
      }
      case 'del2': return this.compile({ k: 'call', f: 'div', args: [{ k: 'call', f: 'grad', args: node.args, tok }], tok }, scope);
      case 'dxx': return this.compile({ k: 'call', f: 'dx', args: [{ k: 'call', f: 'dx', args: node.args, tok }], tok }, scope);
      case 'dyy': return this.compile({ k: 'call', f: 'dy', args: [{ k: 'call', f: 'dy', args: node.args, tok }], tok }, scope);
      case 'dxy': case 'dyx': return this.compile({ k: 'call', f: 'dx', args: [{ k: 'call', f: 'dy', args: node.args, tok }], tok }, scope);
      case 'curl': {
        const a = node.args[0];
        const fy = this.deriv(a, 1, scope), fx = this.deriv(a, 0, scope);
        return ctx => { // scalar arg: curl(psi) = (dpsi/dy, -dpsi/dx); vector: z-component (2D)
          const gy = fy(ctx), gx = fx(ctx);
          if (isVec(gy)) return [0, 0, gx[1] - gy[0]];
          return [gy, -gx, 0];
        };
      }
      case 'val': case 'eval': {
        const [e, ...pts] = node.args;
        const inner = this.compile(e, scope);
        const P = pts.map(p => this.compile(p, scope));
        return ctx => ctx.at(P.map(p => scalar(p(ctx), tok)), inner);
      }
      case 'integral': case 'integrate': case 'area_integral': case 'vol_integral': case 'vintegral': {
        const inner = this.compile(node.args[0], scope);
        const where = node.args[1] ? this.compile(node.args[1], scope) : null;
        return ctx => ctx.integrate(inner, where ? where(ctx) : null);
      }
      case 'line_integral': case 'bintegral': case 'sintegral': case 'surf_integral': {
        const inner = this.compile(node.args[0], scope);
        const where = node.args[1] ? this.compile(node.args[1], scope) : null;
        return ctx => ctx.integrate(inner, where ? where(ctx) : null, 'boundary');
      }
      case 'globalmax': case 'globalmin': {
        const inner = this.compile(node.args[0], scope);
        return ctx => ctx.extremum(inner, f === 'globalmax');
      }
    }
    const fn = FUNCS[f];
    if (!fn) throw new FlexError(`Undefined Name: ${tok.text.toUpperCase()}`, tok.line, tok.col);
    const args = A();
    if (args.length === 1) { const a0 = args[0]; return ctx => fn([a0(ctx)], tok); }
    return ctx => fn(args.map(a => a(ctx)), tok);
  }

  // d/d(axis) of an expression. Unknowns use their element gradients; everything else is
  // differentiated by central differences of the evaluation point (fields move with their gradient).
  deriv(node, dir, scope) {
    if (node.k === 'name' && this.env.vars.has(node.id) && !(scope && scope.has(node.id))) {
      const v = this.env.vars.get(node.id);
      if (v.idxs) { const [i, j] = v.idxs; return ctx => [ctx.g(i)[dir], ctx.g(j)[dir], 0]; }
      const i = v.idx;
      return ctx => ctx.g(i)[dir];
    }
    if (node.k === 'num') return () => 0;
    const inner = this.compile(node, scope);
    return ctx => {
      const h = FD * (1 + Math.abs(dir === 0 ? ctx.x : dir === 1 ? ctx.y : ctx.z));
      const fp = ctx.shift(dir, h, inner), fm = ctx.shift(dir, -h, inner);
      return binop('/', binop('-', fp, fm), 2 * h);
    };
  }
}

export { scalar, binop };
