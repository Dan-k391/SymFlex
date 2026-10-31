import { test } from 'node:test';
import assert from 'node:assert/strict';
import { tokenize } from '../../src/flex/lexer.js';
import { parseFlex } from '../../src/flex/parser.js';

test('comments: line, nested braces and /* */ are skipped; strings and numbers lexed', () => {
  const toks = tokenize("a { x { nested } y } = 1.5e-3 ! tail\n /* c */ 'str' \"q'\" .5");
  assert.deepEqual(toks.map(t => t.type), ['id', 'op', 'num', 'str', 'str', 'num', 'eof']);
  assert.equal(toks[2].value, 1.5e-3);
  assert.equal(toks[4].value, "q'");
  assert.equal(toks[5].value, 0.5);
  assert.equal(toks[3].line, 2);
});

test('free-form statements: several definitions and labelled equations per line', () => {
  const P = parseFlex(`TITLE "T"
VARIABLES r(threshold=1e-2) = vector(rx, ry)  v(1e-3)=vector(vx,vy) w
DEFINITIONS q1=5e-3 	q2 = -20e-6  m=2  f(a, b) = a*b
  c = if t < 1 then 2 else if t < 2 then 3 else 4
EQUATIONS r: dt(r) = v   v: dt(v) = vector(0,-9.8)  dt(w) = 1
BOUNDARIES REGION 1 START(0,0) LINE TO (1,0) TO (1,1) TO CLOSE
Time 0 by 0.1 to 10 halt (ry < 0)
PLOTS for t = 0 by endtime/50 to endtime
  history(ry) at (0) vs rx as 'traj' report val(rx, 0) as "X"
  report t
END`);
  assert.equal(P.title, 'T');
  assert.deepEqual(P.variables.map(v => v.key), ['r', 'v', 'w']);
  assert.deepEqual(P.variables[0].comps.map(c => c.key), ['rx', 'ry']);
  assert.equal(P.variables[1].thr.v, 1e-3);
  assert.deepEqual(P.defs.map(d => d.key), ['q1', 'q2', 'm', 'f', 'c']);
  assert.deepEqual(P.defs[3].params, ['a', 'b']);
  assert.equal(P.defs[4].expr.k, 'if');
  assert.equal(P.defs[4].expr.b.k, 'if'); // else-if nests
  assert.deepEqual(P.equations.map(e => e.label), ['r', 'v', null]);
  assert.equal(P.time.by.v, 0.1);
  assert.equal(P.time.to.v, 10);
  assert.equal(P.time.halt.length, 1);
  const items = P.plots[0].items;
  assert.equal(items[0].type, 'history');
  assert.equal(items[0].vs.label, 'rx');
  assert.equal(items[0].as, 'traj');
  assert.equal(items[1].label, 'X');
  assert.equal(items[2].label, 't');
  assert.equal(P.regions[0].paths[0].segs.length, 3);
  assert.ok(P.hasEnd);
});

test('boundary conditions attach to the segments that follow them', () => {
  const P = parseFlex(`VARIABLES u
EQUATIONS div(grad(u)) = 0
BOUNDARIES REGION 1
  START(0,0) VALUE(u)=0 LINE TO (1,0) NATURAL(u)=1 LINE TO (1,1) TO (0,1) LOAD(u)=0 LINE TO CLOSE
END`);
  const segs = P.regions[0].paths[0].segs;
  assert.deepEqual(segs.map(s => s.bcs.map(b => b.type + ':' + b.var).join()), ['value:u', 'natural:u', 'natural:u', 'natural:u']);
  assert.ok(segs[3].close);
});

test('grammar errors carry FlexPDE wording and positions', () => {
  assert.throws(() => parseFlex("title 'x'\nintro\nSELECT ngrid=1"), e => e.line === 2 && e.col === 1 && /does not allow '<identifier>'/.test(e.message));
  assert.throws(() => parseFlex('DEFINITIONS\n g = 2*-3'), e => e.line === 2 && e.col === 8 && /'<minus>'/.test(e.message));
});
