import { test } from 'node:test';
import assert from 'node:assert/strict';
import { lintFlex } from '../../src/flex/index.js';

test('lint reports syntax errors, undefined names and missing END', () => {
  assert.deepEqual(lintFlex("TITLE 'a'\nVARIABLES u\nEQUATIONS dt(u)=1\nBOUNDARIES REGION 1 START(0) LINE TO (1)\nTIME 0 TO 1\nEND"), []);
  const e1 = lintFlex("TITLE 'a'\n  oops\n");
  assert.equal(e1[0].line, 2);
  assert.equal(e1[0].severity, 'error');
  const e2 = lintFlex('VARIABLES u\nDEFINITIONS a = b + 1\nEQUATIONS dt(u)=a\nEND');
  assert.match(e2[0].msg, /Undefined Name: B/);
  assert.equal(e2[0].col, 17);
  const e3 = lintFlex('VARIABLES u\nEQUATIONS dt(u)=1\nBOUNDARIES REGION 1 START(0) LINE TO (1)\nTIME 0 TO 1');
  assert.ok(e3.some(e => e.severity === 'warning' && /END/.test(e.msg)));
});
