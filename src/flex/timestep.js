// FlexPDE-style implicit time stepper: variable-step BDF2 (Gear) with a cubic-term error
// estimate, the way FlexPDE 8 does it (see docs/flexpde_help/interpretingerrorestimates.html).
// Everything below was reverse-engineered from FlexPDE 8.01 debug logs (CYCLE / DTP / "Max Time
// Err" lines of <name>_output/<name>_debug.txt); it follows their step sequences to ~0.1%:
//   E = max_i |y_i - P_i| / max(threshold_i, errlim*|y_i|) * h/(h + hPrev),  x = E/errlim,
//   q = x^(-1/4), with P the quadratic through the three previous accepted points extrapolated to
//   the new time (for constant steps E = |cubic term|/2; FlexPDE scales it by h^2*(t - t[-3])).
// The nominal step H is steered by a filtered ratio F (desired H / current H):
//   every ordinary accepted step: F += 0.2*(q - F); when F leaves [0.98, 1.02] the step changes,
//   H *= min(F, 1.25) and F is divided by the same ratio (so a capped growth keeps the remainder);
//   a step is rejected when q < 0.7 (x > 4.16): retry with H *= q, F /= q, and the next accepted
//   step leaves F alone; plot times are hit exactly: if the remaining interval is <= 1.25 H the
//   step is stretched or clipped onto it and does not update F (H resumes afterwards).
// HALT conditions are checked at the end of every accepted step, so the halt time is a step end.

const GROWTH_MAX = 1.25; // max step growth, also the max stretch onto a plot time
const RELAX = 0.2;
const DEADBAND = 0.02;
const Q_FAIL = 0.7;
const Q_MAX = 1e4; // E can be exactly 0 here (FlexPDE always sees roundoff)

export function bdfCoefs(h, hPrev) {
  if (!hPrev) return [1 / h, -1 / h, 0];
  const w = h / hPrev;
  return [(1 + 2 * w) / ((1 + w) * h), -(1 + w) / h, (w * w) / ((1 + w) * h)];
}

// sys: { n, thr:Float64Array, solve(tNew, coefs, Y1, Y2, guess, h, t1, t2) -> Float64Array|null }
//   (Y1, Y2 are the states at t1, t2 used by the BDF formula; Y2 is null for implicit Euler)
// opts: { t0, t1, Y0, errlim, h0, landTimes:[...], limit, minDt, onStep(t, Y, info)->bool(halt),
//         maxSteps, shouldStop(), trace:[] (receives {t, h, E, ok} per attempt, for debugging) }
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
  const scale = (i, v) => Math.max(thr[i], errlim * Math.abs(v), 1e-30);

  const errMeasure = (Ynew, P, w) => {
    let E = 0, iv = 0;
    for (let i = 0; i < n; i++) {
      const e = Math.abs(Ynew[i] - P[i]) * w / scale(i, Ynew[i]);
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

  // ---- start-up, reverse-engineered from FlexPDE 8.01 debug logs (STARTUP HALF-STEP / SECOND
  // HALF-STEP / WHOLE-STEP lines). Each attempt with step d (initially 1e-4*span, or TIME .. BY d)
  // takes implicit Euler steps Y0 -> Ya (d) -> Yb (d) and Y0 -> Yf (2d), and keeps
  // Y2d = Yb + (Yb - Yf)/3 at t0+2d. After a rejected attempt FlexPDE starts the second half-step
  // from Y0 instead of Ya (stale state) and stores Y0 as the value at t0+d; this skews the start
  // (e.g. dt(u)=c gives u(2d) = c*2d/3), and that offset persists in every reported value. The
  // attempts alternate between two internal states, and the error measure is
  //   M = max |B - Yf| / max(thr, errlim|y|) / errlim  (B: the stale second half-step from Y0),
  // tripled on attempts 1, 3, 5...; the attempt is accepted when M <= 12, else d is cut 10x when
  // M > 300 and 2x otherwise. The first regular step is d*min(1, sqrt(3/M)). A first half-step
  // that changes some variable by more than 200 thresholds is abandoned (10x cut, same parity).
  let d = Math.min(opts.h0 ?? 1e-4 * span, limit, (lands[0] - t) / 2);
  const t0 = t, Y0 = Y;
  let H, Y2d, Yd;
  for (let attempt = 0; ; attempt++) {
    if (attempt > 80 || d < tiny) throw new Error('Initial time step failed');
    const stale = attempt % 2 === 1;
    const Ya = sys.solve(t0 + d, bdfCoefs(d), Y0, null, Y0, d, t0, null);
    if (Ya && !stale && Ya.some((v, i) => Math.abs(v - Y0[i]) > 200 * scale(i, v))) { // "Large-Error Escape"
      d /= 10; fails++; attempt--; continue;
    }
    const Yf = Ya && sys.solve(t0 + 2 * d, bdfCoefs(2 * d), Y0, null, Ya, 2 * d, t0, null);
    const B = Yf && sys.solve(t0 + 2 * d, bdfCoefs(d), Y0, null, Y0, d, t0 + d, null);
    if (!B) { d /= 2; fails++; attempt--; continue; }
    let M = 0;
    for (let i = 0; i < n; i++) M = Math.max(M, Math.abs(B[i] - Yf[i]) / scale(i, Yf[i]) / errlim);
    if (!stale) M *= 3;
    if (M <= 12) {
      const Yb = stale ? B : sys.solve(t0 + 2 * d, bdfCoefs(d), Ya, null, Ya, d, t0 + d, null) || B;
      Y2d = Yb.map((v, i) => v + (v - Yf[i]) / 3);
      Yd = stale ? Y0 : Ya;
      H = Math.min(d * Math.min(1, Math.sqrt(3 / M)), limit);
      break;
    }
    d /= M > 300 ? 10 : 2;
    fails++;
  }
  hist.push({ t: t0 + d, Y: Yd });
  if (opts.trace) opts.trace.push({ t: t0, h: 2 * d, E: 0, ok: true });
  if (accept(t0 + 2 * d, Y2d, { h: 2 * d, E: 0 })) return finish(true, 'halt');
  while (li < lands.length && lands[li] <= t + tiny) li++;
  let F = 1;
  let skip = false; // the step after a rejection does not update F
  let first = true; // first regular step: BDF2 through a virtual point Y2d - h*dY/dt(Y2d)
  const eps = 1e-7 * d;
  const Ye = sys.solve(t + eps, bdfCoefs(eps), Y, null, Y, eps, t, null);
  const rate = Ye ? Ye.map((v, i) => (v - Y[i]) / eps) : new Float64Array(n);

  // ---- BDF2 steps
  while (t < t1 - tiny) {
    if (steps >= maxSteps) return finish(false, 'maxsteps');
    if (opts.shouldStop && opts.shouldStop()) return finish(false, 'stopped');
    const land = lands[li];
    const landing = land - t <= GROWTH_MAX * H * (1 + 1e-9);
    const tNew = landing ? land : t + H;
    const hTry = tNew - t;
    const last = hist[hist.length - 1], prev = hist[hist.length - 2];
    const P = predict(hist, tNew, n);
    const Ynew = first
      ? sys.solve(tNew, bdfCoefs(hTry, hTry), last.Y, last.Y.map((v, i) => v - hTry * rate[i]), P, hTry, last.t, last.t - hTry)
      : sys.solve(tNew, bdfCoefs(hTry, last.t - prev.t), last.Y, prev.Y, P, hTry, last.t, prev.t);
    if (!Ynew) {
      fails++;
      H = hTry * 0.25;
      if (opts.minDt && H < opts.minDt) return finish(true, 'mindt');
      if (H < tiny) throw new Error('Time step underflow');
      continue;
    }
    const [E, iv] = errMeasure(Ynew, P, hTry / (hTry + last.t - prev.t));
    const q = E > 0 ? Math.min(Q_MAX, (E / errlim) ** -0.25) : Q_MAX;
    const ok = !(q < Q_FAIL && hTry > 1e-12 * span);
    if (opts.trace) opts.trace.push({ t, h: hTry, E: E / errlim, ok });
    if (!ok) {
      fails++;
      H = hTry * q;
      F = Math.min(F / q, Q_MAX);
      skip = true;
      log.push(`STEP FAILED at Dt= ${hTry.toPrecision(4)}. RETRY at Dt= ${H.toPrecision(4)}`);
      if (opts.minDt && H < opts.minDt) return finish(true, 'mindt');
      continue;
    }
    first = false;
    if (accept(tNew, Ynew, { h: hTry, E, iv })) return finish(true, 'halt');
    if (landing) li++;
    if (skip || landing) skip = false;
    else {
      F += RELAX * (q - F);
      if (F > 1 + DEADBAND || F < 1 - DEADBAND) {
        const r = Math.min(F, GROWTH_MAX);
        H = Math.min(H * r, limit);
        F /= r;
      }
    }
  }
  return finish(false, 'end');
}

// quadratic through the last three accepted points (the start-up provides three)
function predict(hist, tNew, n) {
  const [a, b, c] = hist.slice(-3);
  const la = ((tNew - b.t) * (tNew - c.t)) / ((a.t - b.t) * (a.t - c.t));
  const lb = ((tNew - a.t) * (tNew - c.t)) / ((b.t - a.t) * (b.t - c.t));
  const lc = ((tNew - a.t) * (tNew - b.t)) / ((c.t - a.t) * (c.t - b.t));
  const P = new Float64Array(n);
  for (let i = 0; i < n; i++) P[i] = la * a.Y[i] + lb * b.Y[i] + lc * c.Y[i];
  return P;
}
