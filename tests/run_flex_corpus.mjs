#!/usr/bin/env node
// Runs every corpus/cases/**/*.pde (or corpus/raw/**/*.pde when there are no cases) through the
// SymFlex FlexPDE engine and compares with corpus/golden/<source>/<case>.json (real FlexPDE 8).
//
// Verdicts per case:
//   PASS  every compared quantity within the strict tolerance: reports/final values relative 1e-3
//         or absolute 1e-6, end_time within one plot interval, history series within 1e-2 of the
//         series range (interpolated in time), fields (sampled) within 1e-2 of their range.
//   NEAR  only "trajectory" tolerances hold: values that miss the strict test are still within
//         1e-2 of the range the quantity sweeps (golden history series or our variable range),
//         match golden history interpolated at our end time (a HALT one step earlier/later than
//         FlexPDE's own step sequence), or for derived reports without a series, 1e-2 relative.
//   FAIL  anything else; ERR-OK when both engines report an error (same line = exact).
// Usage: node tests/run_flex_corpus.mjs [filter] [--json out.json] [--verbose]
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const { runFlex } = await import(pathToFileURL(path.join(ROOT, 'src/flex/index.js')).href);

const args = process.argv.slice(2);
const verbose = args.includes('--verbose');
const jsonOut = args.includes('--json') ? args[args.indexOf('--json') + 1] : null;
const filter = args.find((a, i) => !a.startsWith('--') && args[i - 1] !== '--json');

const findPde = dir => (fs.existsSync(dir) ? fs.readdirSync(dir, { withFileTypes: true }).flatMap(d =>
  d.isDirectory() ? findPde(path.join(dir, d.name)) : d.name.toLowerCase().endsWith('.pde') ? [path.join(dir, d.name)] : []) : []);
let files = findPde(path.join(ROOT, 'corpus/cases'));
if (!files.length) files = findPde(path.join(ROOT, 'corpus/raw'));
files.sort();
if (filter) files = files.filter(f => f.replace(/\\/g, '/').includes(filter));

const fmt = v => (typeof v === 'number' ? v.toPrecision(7) : String(v));
const norm = s => String(s).toLowerCase().replace(/\s+/g, '');
const close = (a, b, rel = 1e-3, abs = 1e-6) => Number.isFinite(a) && Number.isFinite(b) && (Math.abs(a - b) <= abs || Math.abs(a - b) <= rel * Math.abs(b));
const range = v => { const f = v.filter(Number.isFinite); return f.length ? Math.max(...f) - Math.min(...f) : 0; };
function interp(xs, ys, x) {
  if (!xs.length || x < xs[0] - 1e-12 * Math.abs(x) || x > xs[xs.length - 1] + 1e-12 * Math.abs(x)) return NaN;
  let lo = 0, hi = xs.length - 1;
  while (hi - lo > 1) { const m = (lo + hi) >> 1; if (xs[m] <= x) lo = m; else hi = m; }
  if (xs[hi] === xs[lo]) return ys[lo];
  const s = Math.min(1, Math.max(0, (x - xs[lo]) / (xs[hi] - xs[lo])));
  return ys[lo] + s * (ys[hi] - ys[lo]);
}

// Same rewrite the golden generator applies for FlexPDE 8 ("report rx" -> "report val(rx,P0)").
function patchBareReports(src) {
  const m = /\bstart\b\s*(?:(['"]).*?\1)?\s*\(([^)]*)\)/i.exec(src.replace(/\{[^}]*\}/g, ''));
  const p0 = m ? m[2] : '0';
  return src.replace(/^(\s*report\s+)(?!val\s*\()([^!'"\n]+?)(\s*(?:!.*)?)$/gim,
    (all, a, e, c) => (e.trim().toLowerCase() === 't' ? all : `${a}val(${e},${p0})${c}`));
}

function sampleField(f, px, py) {
  const X = f.x, Y = f.y;
  if (!f.tri || !f.tri[0] || f.tri[0].length === 2) { // 1D
    const idx = X.map((x, i) => i).sort((a, b) => X[a] - X[b]);
    return interp(idx.map(i => X[i]), idx.map(i => f.values[i]), px);
  }
  for (const [a, b, c] of f.tri) {
    const det = (Y[b] - Y[c]) * (X[a] - X[c]) + (X[c] - X[b]) * (Y[a] - Y[c]);
    const l0 = ((Y[b] - Y[c]) * (px - X[c]) + (X[c] - X[b]) * (py - Y[c])) / det;
    const l1 = ((Y[c] - Y[a]) * (px - X[c]) + (X[a] - X[c]) * (py - Y[c])) / det;
    const l2 = 1 - l0 - l1;
    if (Math.min(l0, l1, l2) >= -1e-6) return l0 * f.values[a] + l1 * f.values[b] + l2 * f.values[c];
  }
  return NaN;
}

function plotInterval(src) {
  const m = /for\s+t\s*=\s*([^\n]*?)\bby\b\s*([^\n]*?)\bto\b/i.exec(src.replace(/!.*$/gm, ''));
  return m ? m[2].trim() : null;
}

const rows = [];
for (const file of files) {
  const rel = path.relative(ROOT, file).replace(/\\/g, '/');
  const source = path.basename(path.dirname(file)), name = path.basename(file, path.extname(file));
  const gfile = path.join(ROOT, 'corpus/golden', source, name + '.json');
  const golden = fs.existsSync(gfile) ? JSON.parse(fs.readFileSync(gfile, 'utf8')) : null;
  let src = fs.readFileSync(file, 'latin1');
  const t0 = Date.now();
  let res = await runFlex(src);
  const notes = [];
  if (golden && golden.patched && res.errors.some(e => /no Location Specified/.test(e.msg))) {
    notes.push(`FlexPDE 8 error reproduced (line ${res.errors[0].line}); compared patched script`);
    src = patchBareReports(src);
    res = await runFlex(src);
  }
  const ms = Date.now() - t0;
  const row = { case: `${source}/${name}`, file: rel, verdict: 'NO-GOLDEN', ms, notes, checks: 0, strictFail: [], nearFail: [] };
  rows.push(row);
  if (!golden) {
    row.verdict = res.errors.length ? 'NO-GOLDEN(err)' : 'NO-GOLDEN';
    if (res.errors.length) notes.push(res.errors.map(e => `L${e.line}: ${e.msg}`).join('; '));
    continue;
  }
  const gErr = golden.status !== 'ok';
  if (gErr || res.errors.length) {
    if (gErr && res.errors.length) {
      const gl = (golden.errors[0] || '').match(/Line (\d+)/);
      const same = gl && +gl[1] === res.errors[0].line;
      row.verdict = 'ERR-OK';
      notes.push(`${same ? 'same line' : 'different line'}: ours "${res.errors[0].msg}" vs "${golden.errors[0]}"`);
    } else {
      row.verdict = 'FAIL';
      notes.push(gErr ? `golden error "${golden.errors[0]}" but we ran` : `our error: L${res.errors[0].line} ${res.errors[0].msg}`);
    }
    continue;
  }
  const strict = (ok, what) => { row.checks++; if (!ok) row.strictFail.push(what); return ok; };
  const nearFail = what => row.nearFail.push(what);
  // golden history lookup by series label (for relaxed checks)
  const gSeries = new Map();
  for (const h of golden.history || []) for (const s of h.series) if (!gSeries.has(norm(s.label))) gSeries.set(norm(s.label), { t: h.t, v: s.values });
  const tEnd = res.final.t;
  let dtPlotTol = null;
  // end time
  if (golden.end_time != null) {
    const pi = plotInterval(src);
    let dtPlot = null;
    if (pi) { try { dtPlot = Function('endtime', `return ${pi.replace(/\^/g, '**')}`)(golden.end_time); } catch { dtPlot = null; } }
    const tol = Number.isFinite(dtPlot) && dtPlot > 0 ? dtPlot * 1.0001 : 1e-3 * Math.abs(golden.end_time);
    dtPlotTol = tol;
    const ok = Number.isFinite(tEnd) && Math.abs(tEnd - golden.end_time) <= Math.max(tol, 1e-9);
    if (!strict(ok, `end_time ${tEnd} vs ${golden.end_time}`)) nearFail(`end_time ${tEnd} vs ${golden.end_time}`);
  }
  if (golden.halted !== undefined && !strict(!!res.halted === !!golden.halted, `halted ${res.halted} vs ${golden.halted}`)) nearFail('halted');
  // reports
  const ours = new Map(res.reports.map(r => [norm(r.label), r.value]));
  const oursExpr = new Map(res.reports.map(r => [norm(r.label), norm(r.expr || r.label)]));
  const ranges = new Map(Object.entries(res.final.range || {}).map(([k, v]) => [k.toLowerCase(), v[1] - v[0]]));
  const finals = new Map(Object.entries(res.final.values || {}).map(([k, v]) => [k.toLowerCase(), v]));
  for (const g of golden.reports || []) {
    if (g.value == null) continue;
    const key = norm(g.label);
    let mine = ours.get(key);
    const vm = /^val\(([a-z_]\w*)(?:,[^)]*)?\)$/.exec(key);
    if (mine === undefined && vm) mine = finals.get(vm[1]);
    if (mine === undefined && key === 't') mine = tEnd;
    if (mine === undefined && res.fields && vm && res.fields[Object.keys(res.fields).find(k => k.toLowerCase() === vm[1])]) {
      const f = res.fields[Object.keys(res.fields).find(k => k.toLowerCase() === vm[1])];
      const p = /\bstart\b\s*\(([^)]*)\)/i.exec(src);
      const pt = p ? p[1].split(',').map(Number) : [0, 0];
      mine = sampleField(f, pt[0], pt[1] ?? 0);
    }
    if (mine === undefined) { strict(false, `report ${g.label} missing`); nearFail(`report ${g.label} missing`); continue; }
    if (strict(close(mine, g.value), `${g.label}: ${fmt(mine)} vs ${fmt(g.value)}`)) continue;
    // relaxed: same trajectory (golden history at our end time) or within 1e-2 of the range the
    // quantity sweeps during the run (golden history series, else our own variable range)
    const ex = oursExpr.get(key) || key;
    const inner = (/^(?:val|eval)\((.*?)(?:,[^,()]*)+\)$/.exec(ex) || [null, ex])[1];
    const sKey = vm ? vm[1] : inner;
    const gs = gSeries.get(sKey);
    let ok = false;
    if (gs) {
      const atOurEnd = interp(gs.t, gs.v, tEnd);
      ok = close(mine, atOurEnd, 1e-3, 1e-3 * range(gs.v)) || Math.abs(mine - g.value) <= 1e-2 * range(gs.v);
    }
    if (!ok && ranges.has(sKey)) ok = Math.abs(mine - g.value) <= 1e-2 * ranges.get(sKey);
    if (!ok && sKey === 't' && dtPlotTol != null) ok = Math.abs(mine - g.value) <= dtPlotTol;
    // derived quantities (e.g. KE) with no series to scale against: 1% relative
    if (!ok && !gs && !ranges.has(sKey) && sKey !== 't') ok = close(mine, g.value, 1e-2, 1e-6);
    if (!ok) nearFail(`${g.label}: ${fmt(mine)} vs ${fmt(g.value)}`);
  }
  // history series (golden entries are in history-statement order)
  const ourHist = res.plots.filter(p => p.type === '2d' && p.curves.length && p.curves[0].t);
  (golden.history || []).forEach((h, hi) => {
    const P = ourHist[hi];
    if (!P) { strict(false, `history #${hi} missing`); nearFail(`history #${hi} missing`); return; }
    for (const s of h.series) {
      const c = P.curves.find(cv => norm(cv.legend) === norm(s.label)) || P.curves[h.series.indexOf(s)];
      if (!c) { strict(false, `series ${s.label} missing`); nearFail(`series ${s.label}`); continue; }
      const rg = range(s.values) || Math.max(...s.values.map(Math.abs), 1e-12);
      let worst = 0;
      const tLim = Math.min(c.t[c.t.length - 1], h.t[h.t.length - 1]);
      h.t.forEach((t, k) => {
        if (t > tLim || s.values[k] == null) return;
        const y = interp(c.t, c.y, t);
        if (Number.isFinite(y)) worst = Math.max(worst, Math.abs(y - s.values[k]) / rg);
      });
      if (!strict(worst <= 1e-2, `history ${s.label} max dev ${worst.toExponential(1)} of range`) && worst > 5e-2) nearFail(`history ${s.label} ${worst.toExponential(1)}`);
    }
  });
  // fields on the golden 21x21 grid
  for (const [v, g] of Object.entries(golden.fields || {})) {
    const mine = res.fields && res.fields[Object.keys(res.fields).find(k => k.toLowerCase() === v.toLowerCase())];
    if (!mine) { strict(false, `field ${v} missing`); nearFail(`field ${v}`); continue; }
    const vals = [], diffs = [];
    if (g.y && g.y.length) g.y.forEach((y, j) => g.x.forEach((x, i) => {
      const gv = g.values[j][i];
      if (gv == null) return;
      vals.push(gv);
      diffs.push(Math.abs(sampleField(mine, x, y) - gv));
    }));
    else g.x.forEach((x, i) => { if (g.values[i] == null) return; vals.push(g.values[i]); diffs.push(Math.abs(sampleField(mine, x, 0) - g.values[i])); });
    const rg = range(vals);
    const worst = Math.max(0, ...diffs.filter(Number.isFinite));
    const ok = rg > 0 ? worst <= 1e-2 * rg : worst <= 1e-6;
    if (!strict(ok, `field ${v} max dev ${worst.toExponential(2)} (range ${rg.toExponential(2)})`)) nearFail(`field ${v}`);
  }
  row.verdict = !row.strictFail.length ? 'PASS' : !row.nearFail.length ? 'NEAR' : 'FAIL';
}

const pad = (s, n) => String(s).padEnd(n);
console.log(pad('case', 40) + pad('verdict', 15) + pad('ms', 7) + 'details');
for (const r of rows) {
  const det = [...r.notes, ...(r.verdict === 'PASS' ? [] : r.verdict === 'NEAR' ? r.strictFail : r.nearFail)];
  console.log(pad(r.case, 40) + pad(r.verdict, 15) + pad(r.ms, 7) + (verbose ? det.join(' | ') : det.slice(0, 3).join(' | ').slice(0, 200)));
}
const count = v => rows.filter(r => r.verdict === v).length;
console.log(`\n${rows.length} cases: ${count('PASS')} PASS, ${count('NEAR')} NEAR, ${count('ERR-OK')} ERR-OK, ${count('FAIL')} FAIL, ${rows.filter(r => r.verdict.startsWith('NO-GOLDEN')).length} without golden`);
if (jsonOut) fs.writeFileSync(jsonOut, JSON.stringify(rows, null, 1));
process.exitCode = count('FAIL') ? 1 : 0;
