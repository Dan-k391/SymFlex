import { test } from 'node:test';
import assert from 'node:assert/strict';
import { ivp, runFlex, report } from './helpers.mjs';

const projectile = `TITLE 'Projectile Motion'
COORDINATES cartesian2
VARIABLES vx(threshold=0.1) vy(threshold=0.1) xd(threshold=0.1) yd(threshold=0.1)
SELECT ngrid = 1
DEFINITIONS vi = 21  theta_i = 60*pi/180  g = 9.8
INITIAL VALUES vx = vi*cos(theta_i)  vy = vi*sin(theta_i)  xd = 0  yd = 0
EQUATIONS vx: dt(vx) = 0  vy: dt(vy) = -g  xd: dt(xd) = vx  yd: dt(yd) = vy
BOUNDARIES REGION 1 START(0,0) LINE TO (1,0) TO (1,1) TO (0,1) TO CLOSE
TIME 0 TO 50 halt yd<0
PLOTS for t = 0 by 0.1 to endtime
  history(xd,yd) at (0,0)
SUMMARY report val(xd,0,0) as 'xd' report val(yd,0,0) as 'yd' report t
END`;

test('projectile: halts at the end of the plot-time step where yd<0, like FlexPDE (t=3.8)', async () => {
  const res = await runFlex(projectile);
  assert.deepEqual(res.errors, []);
  assert.equal(res.halted, true);
  assert.ok(Math.abs(report(res, 't') - 3.8) < 1e-12);
  const t = 3.8, vx = 21 * Math.cos(Math.PI / 3), vy0 = 21 * Math.sin(Math.PI / 3);
  // analytic values; FlexPDE 8 itself reports xd=39.89825, yd=-1.643989 because of its start-up step
  assert.ok(Math.abs(report(res, 'xd') - vx * t) < 5e-3);
  assert.ok(Math.abs(report(res, 'yd') - (vy0 * t - 4.9 * t * t)) < 5e-3);
  assert.ok(Math.abs(report(res, 'xd') - 39.89825) < 1e-3);
  assert.ok(Math.abs(report(res, 'yd') - -1.643989) < 1e-3);
  // history sampled at every step, including all plot times and the final time
  const c = res.plots[0].curves[0];
  for (const tp of [0, 0.1, 1.5, 3.7, 3.8]) assert.ok(c.x.some(x => Math.abs(x - tp) < 1e-9), `missing t=${tp}`);
  assert.equal(c.x[c.x.length - 1], res.final.t);
});

test('damped oscillator matches the analytic solution when errlim is tightened', async () => {
  const m = 1.9, k = 300, b = 10;
  const res = await runFlex(ivp({
    vars: 's(threshold=1e-6) v(threshold=1e-6)', select: 'errlim=1e-6',
    defs: `m=${m} k=${k} b=${b}`, init: 's = 0.1 v = 0',
    eqs: 's: dt(s) = v  v: dt(v) = (-k*s - b*v)/m', time: '0 TO 0.5',
    plots: 'for t = 0 by endtime/50 to endtime\nreport val(s,0) report val(v,0)',
  }));
  const w0 = Math.sqrt(k / m), z = b / (2 * Math.sqrt(m * k)), wd = w0 * Math.sqrt(1 - z * z), t = 0.5;
  const s = 0.1 * Math.exp(-z * w0 * t) * (Math.cos(wd * t) + z * w0 / wd * Math.sin(wd * t));
  const v = -0.1 * Math.exp(-z * w0 * t) * (w0 * w0 / wd) * Math.sin(wd * t);
  assert.ok(Math.abs(report(res, 'val(s,0)') - s) < 2e-6, `${report(res, 'val(s,0)')} vs ${s}`);
  assert.ok(Math.abs(report(res, 'val(v,0)') - v) < 2e-5, `${report(res, 'val(v,0)')} vs ${v}`);
});

test('default errlim reproduces the FlexPDE BDF2 phase error (lab3_09 SHM: v(0.5)=0.0017853)', async () => {
  const res = await runFlex(ivp({
    vars: 's(threshold=1e-3) v(threshold=1e-3)', defs: 'm=1.9 k=300', init: 's=0.1 v=0',
    eqs: 's: dt(s) = v  v: dt(v) = -k*s/m', time: '0 TO 0.5',
    plots: 'for t= 0 by endtime/50 to endtime\nhistory(s) at (0)\nreport val(s,0) report val(v,0)',
  }));
  assert.ok(Math.abs(report(res, 'val(s,0)') - 0.099998) < 2e-6);
  assert.ok(Math.abs(report(res, 'val(v,0)') - 0.0017853) < 1e-4); // exact solution: 3e-5
});

test('vector variables, magnitude/dot and halt on a component', async () => {
  const res = await runFlex(ivp({
    vars: 'r(threshold=1e-3) = vector(rx,ry)\n v(threshold=1e-3) = vector(vx,vy)',
    defs: 'g = vector(0,-9.81)  speed = magnitude(v)  KE = 0.5*dot(v,v)',
    init: 'r = vector(0,0)  v = 20*vector(cos(pi/4), sin(pi/4))',
    eqs: 'r: dt(r) = v  v: dt(v) = g', time: '0 TO 10 halt (ry < 0)',
    plots: 'for t = 0 by endtime/50 to endtime\nhistory(ry) at (0) vs rx\nreport val(rx,0) report val(KE,0) report t',
  }));
  assert.deepEqual(res.errors, []);
  assert.equal(res.halted, true);
  const tf = 2 * 20 * Math.SQRT1_2 / 9.81; // 2.883 s; plot interval 0.2 -> FlexPDE halts at 3.0
  assert.ok(Math.abs(report(res, 't') - Math.ceil(tf / 0.2) * 0.2) < 1e-9);
  assert.ok(Math.abs(report(res, 'val(rx,0)') - 20 * Math.SQRT1_2 * report(res, 't')) < 1e-2);
  const p = res.plots[0];
  assert.equal(p.xlabel, 'rx');
  assert.equal(p.curves[0].t.length, p.curves[0].x.length);
});

test('second-order dt(dt(x)) with if-then-else forcing', async () => {
  const res = await runFlex(ivp({
    vars: 'x(threshold=1e-6)', select: 'errlim=1e-6', defs: 'F = if t < 1 then 1 else 0', init: 'x = 0',
    eqs: 'x: dt(dt(x)) = F', time: '0 TO 2',
    plots: 'for t = 0 by 0.5 to endtime\nreport val(x,0)',
  }));
  assert.deepEqual(res.errors, []);
  assert.ok(Math.abs(report(res, 'val(x,0)') - 1.5) < 1e-3); // 0.5 + 1*1
});
