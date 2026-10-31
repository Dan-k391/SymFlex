import { test } from 'node:test';
import assert from 'node:assert/strict';
import { ivp, runFlex, report } from './helpers.mjs';

// Semantics checked against FlexPDE 8.01 (SUMMARY export of the same expressions).
test('operator precedence and built-in functions match FlexPDE', async () => {
  const res = await runFlex(ivp({
    vars: 'u(threshold=1e-3)',
    defs: `a = -2^2  b = 2^3^2  c = if 1>2 then 5 else if 2>1 then 7 else 9  d = 7/2*2
      e = mod(-3,2)  f = sign(-3) + abs(-2) + max(1,2,3)  k = magnitude(vector(3,4)) + dot(vector(1,2),vector(3,4))
      cr = cross(vector(1,2),vector(3,4))  fn(p,q) = p*10+q`,
    eqs: 'u: dt(u) = 1', time: '0 TO 1',
    plots: `for t = endtime
      report a report b report c report d report e report f report k report zcomp(cr) report fn(2,3)
      report atan2(1,2) report ustep(1) report pi report (1 < 2) + 1 as 'rel' report xcomp(vector(5,6)) report ycomp(vector(5,6))`,
  }));
  assert.deepEqual(res.errors, []);
  const want = { a: -4, b: 64, c: 7, d: 7, e: -1, f: 4, k: 16, 'zcomp(cr)': -2, 'fn(2,3)': 23, 'atan2(1,2)': Math.atan2(1, 2),
    'ustep(1)': 1, pi: Math.PI, rel: 2, 'xcomp(vector(5,6))': 5, 'ycomp(vector(5,6))': 6 };
  for (const [k, v] of Object.entries(want)) assert.ok(Math.abs(report(res, k) - v) < 1e-12, `${k}=${report(res, k)}`);
});

test('undefined names and bare fields are reported like FlexPDE 8', async () => {
  let res = await runFlex(ivp({ vars: 's v', defs: 'xcm = xb*mbmtotal  xb = 1', eqs: 's: dt(s)=v v: dt(v)=-s', time: '0 TO 1' }));
  assert.equal(res.errors.length, 1);
  assert.match(res.errors[0].msg, /Undefined Name: MBMTOTAL/);
  assert.equal(res.errors[0].line, 7);
  res = await runFlex(ivp({ vars: 's v', init: 's=1', eqs: 's: dt(s)=v v: dt(v)=-s', time: '0 TO 1', plots: 'for t=0 by 0.1 to endtime\nreport s' }));
  assert.match(res.errors[0].msg, /Field value with no Location Specified/);
  assert.equal(res.errors[0].line, 17);
  assert.equal(res.errors[0].col, 8);
});
