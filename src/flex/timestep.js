// FlexPDE-style implicit time stepper: variable-step BDF2 (Gear) with a cubic-term error
// estimate, the way FlexPDE 8 does it (see docs/flexpde_help/interpretingerrorestimates.html).
// Calibrated against FlexPDE 8.01 logs ("TIME ERR" column):
//   E = max_i |y_i - P_i| / (2 * max(threshold_i, errlim*|y_i|))
// where P is the quadratic through the three previous accepted points extrapolated to the new
// time. Steps grow by at most 1.25x, approach errlim gradually, and are clipped to land exactly on
// plot times (the pre-clip step size is resumed afterwards). HALT conditions are checked at the
// end of every accepted step, so the reported halt time is a step end, as in FlexPDE.

const GROWTH_MAX = 1.25;
const RELAX = 0.12; // controller relaxation fitted to FlexPDE step sequences
const ACCEPT = 3; // reject a step when E > ACCEPT*errlim
const START_CRIT = 0.03; // start-up step acceptance, fitted to FlexPDE logs

export function bdfCoefs(h, hPrev) {
  if (!hPrev) return [1 / h, -1 / h, 0];
  const w = h / hPrev;
  return [(1 + 2 * w) / ((1 + w) * h), -(1 + w) / h, (w * w) / ((1 + w) * h)];
}

// sys: { n, thr:Float64Array, solve(tNew, coefs, Y1, Y2, guess, h, t1, t2) -> Float64Array|null }
//   (Y1, Y2 are the states at t1, t2 used by the BDF formula; Y2 is null for implicit Euler)
// opts: { t0, t1, Y0, errlim, h0, landTimes:[...], limit, minDt, onStep(t, Y, info)->bool(halt),
//         maxSteps, shouldStop() }
export function integrate(sys, opts) {
  const { n, thr } = sys;
  const errlim = opts.errlim ?? 0.002;
  const t1 = opts.t1;
  const span = t1 - opts.t0;
  const tiny = 1e-12 * Math.max(Math.abs(t1), Math.abs(span), 1e-300);
  const lands = (opts.landTimes || []).filter(x => x > opts.t0 + tiny && x < t1 - tiny).sort((a, b) => a - b);
  lands.push(t1);
  let li = 0;
  const limit = opts.limit ?? Infinity;
  const maxSteps = opts.maxSteps ?? 2e6;

  const hist = [{ t: opts.t0, Y: Float64Array.from(opts.Y0) }]; // last 4 accepted states
  let t = opts.t0;
  let Y = hist[0].Y;
  let steps = 0, fails = 0;
  const log = [];

  const errMeasure = (Ynew, P) => {
    let E = 0, iv = 0;
    for (let i = 0; i < n; i++) {
      const e = Math.abs(Ynew[i] - P[i]) / (2 * Math.max(thr[i], errlim * Math.abs(Ynew[i]), 1e-30));
      if (e > E) { E = e; iv = i; }
    }
    return [E, iv];
  };
  const finish = (halted, reason) => ({ t, Y, halted, reason, steps, fails, log });
  const accept = (tNew, Ynew, info) => {
    hist.push({ t: tNew, Y: Ynew });
    if (hist.length > 4) hist.shift();
    t = tNew; Y = Ynew; steps++;
    return opts.onStep ? opts.onStep(t, Y, info) : false;
  };

  // ---- startup. FlexPDE 8 shrinks the initial step (h0 = 1e-4*span, or TIME ... BY h0) by 10x
  // while a first-order change estimate is far too large and by 2x when moderately large, then
  // takes a double step of 2*d whose increment is only one third of the true one (observed in
  // every FlexPDE 8.01 run: e.g. projectile vy(2.5e-4) = vy0 + (1/3)*g*2.5e-4). We mimic both,
  // since that start-up offset persists in the reported values.
  let d = Math.min(opts.h0 ?? 1e-4 * span, limit, (lands[0] - t) / 2);
  {
    const eps = 1e-7 * d;
    const Ye = sys.solve(t + eps, bdfCoefs(eps), Y, null, Y, eps, t, null);
    const F = Ye && Ye.map((v, i) => (v - Y[i]) / eps); // initial rates dY/dt
    for (let k = 0; F && k < 60; k++) {
      let e1 = 0;
      for (let i = 0; i < n; i++) e1 = Math.max(e1, Math.abs(F[i]) * d / Math.max(thr[i], errlim * Math.abs(Y[i]), 1e-30));
      if (e1 <= START_CRIT) break;
      d /= e1 > 5 * START_CRIT ? 10 : 2;
      fails++;
    }
  }
  for (let tries = 0; ; tries++) {
    const Ya = sys.solve(t + d, bdfCoefs(d), Y, null, Y, d, t, null);
    const Yb = Ya && sys.solve(t + 2 * d, bdfCoefs(d), Ya, null, Ya, d, t + d, null);
    if (Yb || tries > 40) {
      if (!Yb) throw new Error('Initial time step failed');
      const Yf = sys.solve(t + 2 * d, bdfCoefs(2 * d), Y, null, Y, 2 * d, t, null) || Yb;
      const Ys = Yb.map((v, i) => Y[i] + (2 * v - Yf[i] - Y[i]) / 3); // Richardson value, 1/3 increment
      if (accept(t + 2 * d, Ys, { h: 2 * d, E: 0 })) return finish(true, 'halt');
      break;
    }
    d /= 2;
    fails++;
  }
  while (li < lands.length && lands[li] <= t + tiny) li++;
  let h = d * 0.6;
  let warm = 2; // the first BDF2 steps see the start-up offset in their error estimate

  // ---- BDF2 steps
  while (t < t1 - tiny) {
    if (steps >= maxSteps) return finish(false, 'maxsteps');
    if (opts.shouldStop && opts.shouldStop()) return finish(false, 'stopped');
    let hTry = Math.min(h, limit);
    let tNew = t + hTry;
    let clipped = false;
    const land = lands[li];
    if (tNew >= land - 1e-9 * hTry) { tNew = land; clipped = tNew - t < hTry * (1 - 1e-9); hTry = tNew - t; }
    const Y1 = hist[hist.length - 1].Y, Y2 = hist[hist.length - 2].Y;
    const hLast = hist[hist.length - 1].t - hist[hist.length - 2].t;
    // predictor: quadratic through the last three points (or linear if only two)
    const P = predict(hist, tNew, n);
    const Ynew = sys.solve(tNew, bdfCoefs(hTry, hLast), Y1, Y2, P, hTry, hist[hist.length - 1].t, hist[hist.length - 2].t);
    if (!Ynew) {
      fails++;
      h = hTry * 0.25;
      if (opts.minDt && h < opts.minDt) return finish(true, 'mindt');
      if (h < tiny) throw new Error('Time step underflow');
      continue;
    }
    let [E, iv] = hist.length >= 3 ? errMeasure(Ynew, P) : [0, 0];
    if (warm > 0) { warm--; E = Math.min(E, errlim); }
    if (E > ACCEPT * errlim && hTry > 1e-12 * span) {
      fails++;
      h = hTry * Math.min(0.9, Math.max(0.1, Math.cbrt(errlim / E)));
      log.push(`STEP FAILED at Dt= ${hTry.toPrecision(4)}. RETRY at Dt= ${h.toPrecision(4)}`);
      if (opts.minDt && h < opts.minDt) return finish(true, 'mindt');
      continue;
    }
    if (accept(tNew, Ynew, { h: hTry, E, iv })) return finish(true, 'halt');
    if (tNew >= land - tiny) li++;
    if (!clipped) {
      const g = E > 0 ? Math.cbrt(1 + RELAX * (errlim / E - 1)) : GROWTH_MAX;
      h = hTry * Math.min(GROWTH_MAX, Math.max(0.5, g));
    }
  }
  return finish(false, 'end');
}

function predict(hist, tNew, n) {
  const m = hist.length;
  const P = new Float64Array(n);
  if (m >= 3) {
    const [a, b, c] = [hist[m - 3], hist[m - 2], hist[m - 1]];
    const la = ((tNew - b.t) * (tNew - c.t)) / ((a.t - b.t) * (a.t - c.t));
    const lb = ((tNew - a.t) * (tNew - c.t)) / ((b.t - a.t) * (b.t - c.t));
    const lc = ((tNew - a.t) * (tNew - b.t)) / ((c.t - a.t) * (c.t - b.t));
    for (let i = 0; i < n; i++) P[i] = la * a.Y[i] + lb * b.Y[i] + lc * c.Y[i];
  } else if (m === 2) {
    const [b, c] = [hist[0], hist[1]];
    const s = (tNew - c.t) / (c.t - b.t);
    for (let i = 0; i < n; i++) P[i] = c.Y[i] + s * (c.Y[i] - b.Y[i]);
  } else P.set(hist[0].Y);
  return P;
}
