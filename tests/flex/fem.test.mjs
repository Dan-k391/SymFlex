import { test } from 'node:test';
import assert from 'node:assert/strict';
import { runFlex, report } from './helpers.mjs';

test('Poisson with VALUE and NATURAL boundaries matches the analytic solution', async () => {
  const res = await runFlex(`TITLE 'Poisson'
SELECT ngrid = 10
VARIABLES u
DEFINITIONS k = 2  s = 4
EQUATIONS div(k*grad(u)) + s = 0
BOUNDARIES REGION 1
  START(-1,-1) NATURAL(u)=0 LINE TO (1,-1) VALUE(u)=0 LINE TO (1,1) NATURAL(u)=0 LINE TO (-1,1) VALUE(u)=0 LINE TO CLOSE
PLOTS contour(u) surface(u) elevation(u) from (-1,0) to (1,0)
  report val(u,0,0) report integral(u) report integral(1)
END`);
  assert.deepEqual(res.errors, []);
  assert.ok(Math.abs(report(res, 'val(u,0,0)') - 1) < 5e-3); // u = 1 - x^2
  assert.ok(Math.abs(report(res, 'integral(u)') - 8 / 3) < 2e-2);
  assert.ok(Math.abs(report(res, 'integral(1)') - 4) < 1e-9);
  const [c, s, e] = res.plots;
  assert.equal(c.type, 'contour');
  assert.equal(s.type, 'surface');
  assert.equal(c.mesh.x.length, c.mesh.values.length);
  assert.equal(e.type, '2d');
  assert.equal(e.curves[0].y.length, 101);
  assert.equal(res.fields.u.values.length, res.fields.u.x.length);
});

test('natural BC sets the outward flux: du/dn = g', async () => {
  const res = await runFlex(`VARIABLES u
SELECT ngrid = 6
EQUATIONS div(grad(u)) = 0
BOUNDARIES REGION 1
  START(0,0) VALUE(u)=0 LINE TO (1,0) NATURAL(u)=0 LINE TO (1,1) NATURAL(u)=2 LINE TO (0,1) NATURAL(u)=0 LINE TO CLOSE
PLOTS report val(u,0.5,0.5) report val(u,0.3,1)
END`);
  assert.ok(Math.abs(report(res, 'val(u,0.5,0.5)') - 1) < 1e-6); // u = 2y
  assert.ok(Math.abs(report(res, 'val(u,0.3,1)') - 2) < 1e-6);
});

test("course 'New Problem' template: Laplace with only natural BCs gives u=0 and plots vwind", async () => {
  const res = await runFlex(`TITLE 'New Problem'
COORDINATES cartesian2
select ngrid = 13
VARIABLES u
DEFINITIONS vwind= 6*exp(-sqrt(r/50))*Vector(x, -y/(x^2+.01)+r/2)
EQUATIONS div(grad(u))=0
BOUNDARIES REGION 1 START(0,0) LINE TO (2,0) TO (2,3) TO (0,3) TO CLOSE
MONITORS
PLOTS vector(vwind) norm
vector(vwind)
END`);
  assert.deepEqual(res.errors, []);
  assert.equal(res.plots.length, 2);
  assert.ok(res.fields.u.values.every(v => Math.abs(v) < 1e-12));
  const [a, b] = res.plots;
  assert.equal(a.type, 'vector');
  assert.ok(a.arrows.x.length > 100);
  const m = a.arrows.u.map((u, i) => Math.hypot(u, a.arrows.v[i]));
  assert.ok(m.every(v => Math.abs(v - 1) < 1e-9)); // NORM
  const r = Math.hypot(b.arrows.x[0], b.arrows.y[0]);
  assert.ok(Math.abs(b.arrows.u[0] - 6 * Math.exp(-Math.sqrt(r / 50)) * b.arrows.x[0]) < 1e-9);
});

test('transient 1D heat equation decays like exp(-pi^2 k t)', async () => {
  const res = await runFlex(`TITLE 'Heat 1D'
COORDINATES cartesian1
SELECT ngrid = 20
VARIABLES u(threshold=1e-3)
DEFINITIONS k = 0.1
INITIAL VALUES u = sin(pi*x)
EQUATIONS u: dt(u) = div(k*grad(u))
BOUNDARIES REGION 1 START(0) POINT VALUE(u)=0 LINE TO (1) POINT VALUE(u)=0
TIME 0 TO 1
PLOTS for t = 0 by 0.1 to endtime
  history(u) at (0.5)
  report val(u,0.5)
END`);
  assert.deepEqual(res.errors, []);
  assert.ok(Math.abs(report(res, 'val(u,0.5)') - Math.exp(-(Math.PI ** 2) * 0.1)) < 1e-3);
  assert.equal(res.final.t, 1);
});
