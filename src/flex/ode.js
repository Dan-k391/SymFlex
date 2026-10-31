// Spatially uniform problems (the course's ngrid=1 ODE systems): every unknown is one scalar,
// equations are residuals lhs - rhs = 0 solved implicitly each step by Newton's method.
import { PointCtx, assignEquations } from './model.js';
import { isVec } from './expr.js';
import { FlexError } from './lexer.js';

export function buildOdeSystem(model, thr) {
  const eqs = assignEquations(model);
  const n = model.unknowns.length;
  const ctx = new PointCtx(model);
  const fns = eqs.map(e => ({ e, f: model.compiler.compile({ k: 'bin', op: '-', a: e.lhs, b: e.rhs, tok: e.lhs.tok }) }));
  const R = new Float64Array(n);
  const residual = Y => {
    ctx.set(Y);
    for (const { e, f } of fns) {
      const r = f(ctx);
      if (isVec(r)) {
        if (e.rows.length === 1) throw new FlexError('A Scalar Value is required.', e.line, e.col);
        e.rows.forEach((row, k) => { R[row] = r[k]; });
      } else {
        if (e.rows.length > 1) throw new FlexError('Vector equation expected for a vector variable', e.line, e.col);
        R[e.rows[0]] = r;
      }
    }
    return R;
  };
  const J = Array.from({ length: n }, () => new Float64Array(n));
  const solve = (tNew, c, Y1, Y2, guess, h, t1, t2) => {
    ctx.t = tNew; ctx.deltat = h;
    ctx.lv = c ? { c, Y1, Y2, t1, t2 } : null; // c=null: steady (dt terms vanish)
    const Y = Float64Array.from(guess);
    let jacAge = Infinity, prevNorm = Infinity;
    for (let it = 0; it < 30; it++) {
      const r0 = Float64Array.from(residual(Y));
      if (!r0.every(Number.isFinite)) return null;
      if (jacAge > 3) { // finite-difference Jacobian, refreshed when convergence is slow
        for (let j = 0; j < n; j++) {
          const yj = Y[j];
          const d = 1e-7 * Math.max(Math.abs(yj), thr[j], 1e-12);
          Y[j] = yj + d;
          const r1 = residual(Y);
          for (let i = 0; i < n; i++) J[i][j] = (r1[i] - r0[i]) / d;
          Y[j] = yj;
        }
        jacAge = 0;
      }
      const dY = luSolve(J, r0);
      if (!dY) return null;
      let norm = 0;
      for (let i = 0; i < n; i++) {
        Y[i] -= dY[i];
        norm = Math.max(norm, Math.abs(dY[i]) / Math.max(thr[i], Math.abs(Y[i]), 1e-300));
      }
      if (!Number.isFinite(norm)) return null;
      if (norm < 1e-11) return Y;
      jacAge = norm > 0.25 * prevNorm ? Infinity : jacAge + 1;
      prevNorm = norm;
    }
    return null;
  };
  return { n, thr, solve, ctx };
}

// Dense Gaussian elimination with partial pivoting; returns x with A x = b (A, b preserved).
export function luSolve(A, b) {
  const n = b.length;
  const M = A.map(r => Float64Array.from(r));
  const x = Float64Array.from(b);
  for (let k = 0; k < n; k++) {
    let p = k, best = Math.abs(M[k][k]);
    for (let i = k + 1; i < n; i++) if (Math.abs(M[i][k]) > best) { best = Math.abs(M[i][k]); p = i; }
    if (!(best > 0)) return null;
    if (p !== k) { [M[k], M[p]] = [M[p], M[k]]; [x[k], x[p]] = [x[p], x[k]]; }
    const piv = M[k][k];
    for (let i = k + 1; i < n; i++) {
      const f = M[i][k] / piv;
      if (f === 0) continue;
      const Mi = M[i], Mk = M[k];
      for (let j = k; j < n; j++) Mi[j] -= f * Mk[j];
      x[i] -= f * x[k];
    }
  }
  for (let k = n - 1; k >= 0; k--) {
    let s = x[k];
    for (let j = k + 1; j < n; j++) s -= M[k][j] * x[j];
    x[k] = s / M[k][k];
  }
  return x;
}
