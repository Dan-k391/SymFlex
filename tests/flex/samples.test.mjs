// Student-style variations and small FEM problems checked against analytic solutions and real
// FlexPDE 8.01 (values from FlexPDE8n -S on the same scripts, .work/flex/fem and .work/flex/probe*).
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { runFlex, report } from './helpers.mjs';

const near = (a, b, tol, what) => assert.ok(Math.abs(a - b) <= tol, `${what}: ${a} vs ${b}`);
const square = 'START(0,0) VALUE(u)=0 LINE TO (1,0) TO (1,1) TO (0,1) TO CLOSE';

test('Poisson on the unit square: u = sin(pi x) sin(pi y) (FlexPDE 1.000004, 0.707103, 0.405285)', async () => {
  const res = await runFlex(`VARIABLES u
DEFINITIONS s = 2*pi^2*sin(pi*x)*sin(pi*y)
EQUATIONS div(grad(u)) + s = 0
BOUNDARIES REGION 1 ${square}
PLOTS summary report val(u,0.5,0.5) report val(u,0.25,0.5) report integral(u)
END`);
  assert.deepEqual(res.errors, []);
  near(report(res, 'val(u,0.5,0.5)'), 1, 6e-3, 'centre');
  near(report(res, 'val(u,0.25,0.5)'), Math.SQRT1_2, 6e-3, 'quarter');
  near(report(res, 'integral(u)'), 4 / Math.PI ** 2, 3e-3, 'integral');
});

test('quarter disk with ARC(CENTER) ANGLE=90, VALUE on the arc, NATURAL on the axes: u = 1 - r^2', async () => {
  const res = await runFlex(`VARIABLES u
DEFINITIONS u0 = 1 - r^2
EQUATIONS div(grad(u)) + 4 = 0
BOUNDARIES REGION 1 START(0,0) NATURAL(u)=0 LINE TO (1,0) VALUE(u)=u0 ARC(CENTER=0,0) ANGLE=90 NATURAL(u)=0 LINE TO CLOSE
PLOTS summary report val(u,0,0) report val(u,0.5,0.5) report integral(u) report integral(1)
END`);
  near(report(res, 'val(u,0,0)'), 1, 2e-3, 'u(0,0)');
  near(report(res, 'val(u,0.5,0.5)'), 0.5, 2e-3, 'u(.5,.5)');
  near(report(res, 'integral(u)'), Math.PI / 8, 2e-3, 'integral(u)'); // FlexPDE 0.392699
  near(report(res, 'integral(1)'), Math.PI / 4, 3e-3, 'area'); // polygonal arc
});

test('full circle ARC ANGLE=360 TO CLOSE, and ARC TO chains', async () => {
  for (const arc of ['ARC(CENTER=0,0) ANGLE=360 TO CLOSE', 'ARC(CENTER=0,0) TO (0,1) TO (-1,0) TO (0,-1) TO CLOSE']) {
    const res = await runFlex(`VARIABLES u
EQUATIONS del2(u) + 4 = 0
BOUNDARIES REGION 1 START(1,0) VALUE(u)=0 ${arc}
PLOTS summary report val(u,0,0) report integral(1)
END`);
    assert.deepEqual(res.errors, [], arc);
    near(report(res, 'val(u,0,0)'), 1, 5e-3, arc);
    near(report(res, 'integral(1)'), Math.PI, 1e-2, arc);
  }
});

test('NATURAL(u)=g is the outward flux on a 2x1 box (FlexPDE 1.5, 3.0 exactly)', async () => {
  const res = await runFlex(`VARIABLES u
EQUATIONS div(grad(u)) = 0
BOUNDARIES REGION 1 START(0,0) VALUE(u)=0 LINE TO (2,0) NATURAL(u)=0 LINE TO (2,1) NATURAL(u)=3 LINE TO (0,1) NATURAL(u)=0 LINE TO CLOSE
PLOTS summary report val(u,1,0.5) report val(u,1,1)
END`);
  near(report(res, 'val(u,1,0.5)'), 1.5, 1e-9, 'mid');
  near(report(res, 'val(u,1,1)'), 3, 1e-9, 'top');
});

test('transient 2D heat equation with VALUE boundaries (FlexPDE u(0.5,0.5,0.1) = 0.137658)', async () => {
  const res = await runFlex(`VARIABLES u(threshold=1e-3)
INITIAL VALUES u = sin(pi*x)*sin(pi*y)
EQUATIONS dt(u) = div(grad(u))
BOUNDARIES REGION 1 ${square}
TIME 0 TO 0.1
PLOTS for t = 0 by 0.02 to endtime summary report val(u,0.5,0.5)
HISTORIES history(u) at (0.5,0.5)
END`);
  assert.equal(res.final.t, 0.1);
  near(report(res, 'val(u,0.5,0.5)'), 0.137658, 2e-3, 'u(.5,.5)'); // exact exp(-0.2 pi^2) = 0.13891
  assert.ok(res.plots.at(-1).curves[0].t.includes(0.04));
});

test('student variations: section order, semicolons, comments, SELECT options, staged()', async () => {
  const run = async src => { const r = await runFlex(src); assert.deepEqual(r.errors, [], src); return r; };
  // INITIAL VALUES after BOUNDARIES / TIME, DEFINITIONS first (FlexPDE accepts these)
  let r = await run(`DEFINITIONS k = 2
VARIABLES v
EQUATIONS v: dt(v) = -k*v;
BOUNDARIES REGION 1 START(0,0) LINE TO (1,0) TO (1,1) TO (0,1) TO CLOSE
TIME 0 TO 1
INITIAL VALUES v = 1 { block comment } ! line comment
/* c-style comment */
SELECT ngrid=1 errlim=staged(1e-2, 1e-4) painted regrid=off threads=4 prefer_stability
PLOTS for t=0 by 0.5 to endtime summary report val(v,0,0)
END`);
  near(report(r, 'val(v,0,0)'), Math.exp(-2), 1e-4, 'v(1)');
  r = await run(`TITLE 'm' SELECT ngrid=1 VARIABLES s(threshold=1e-4) v(threshold=1e-4) INITIAL VALUES s=1 v=0
EQUATIONS s: dt(s)=v v: dt(v)=-4*s BOUNDARIES REGION 1 START(0,0) LINE TO (1,0) TO (1,1) TO (0,1) TO CLOSE
TIME 0 TO 1 PLOTS for t=0 by 0.1 to endtime summary report val(s,0,0) END`);
  near(report(r, 'val(s,0,0)'), Math.cos(2), 2e-3, 's(1)');
});

test('parse errors carry FlexPDE 8 wording and line/col', async () => {
  const err = async src => (await runFlex(src)).errors[0];
  const tail = 'BOUNDARIES REGION 1 START(0,0) LINE TO (1,0) TO (1,1) TO (0,1) TO CLOSE\nTIME 0 TO 1\nEND';
  // FlexPDE: Line 3 Col 1: FlexPDE grammar does not allow 'BOUNDARIES' in this location.
  for (const eq of ['u: dt(u) = 3 *', 'u: dt(u) = sin(t']) {
    const e = await err(`VARIABLES u\nEQUATIONS ${eq}\n${tail}`);
    assert.deepEqual([e.line, e.col, e.msg], [3, 1, "FlexPDE grammar does not allow 'BOUNDARIES' in this location."]);
  }
  let e = await err(`VARIABLES u\nEQUATION u: dt(u) = 1\n${tail}`); // FlexPDE: Line 2 Col 1 ... 'EQUATION'
  assert.deepEqual([e.line, e.col], [2, 1]);
  assert.match(e.msg, /'EQUATION'.*EQUATIONS\?/);
  e = await err(`GLOBAL VARIABLES u\nEQUATIONS u: dt(u) = 1\n${tail}`); // FlexPDE: Line 1 Col 8
  assert.deepEqual([e.line, e.col, e.msg], [1, 8, 'Section Must follow VARIABLES']);
  e = await err(`VARIABLES u\nEQUATIONS u: dt(u) = foo(t)\n${tail}`); // FlexPDE: Line 2 Col 22: Undefined Name: FOO
  assert.deepEqual([e.line, e.col, e.msg], [2, 22, 'Undefined Name: FOO']);
  e = await err('VARIABLES u\nEQUATIONS div(grad(u))=0\nBOUNDARIES REGION 1 START(0,0) LINE TO (1,0) TO (2,0) TO CLOSE\nEND');
  assert.match(e.msg, /enclose no area/);
});
