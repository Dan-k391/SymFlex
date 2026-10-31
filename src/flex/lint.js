// Lightweight diagnostics for the editor: syntax errors (first one, as FlexPDE reports it),
// undefined names and a few FlexPDE 8 semantic rules, without solving anything.
import { parseFlex } from './parser.js';
import { FlexError, tokenize } from './lexer.js';
import { buildModel } from './model.js';

export function lintFlex(text) {
  const out = [];
  const push = (e, severity = 'error') => out.push({ line: e.line || 1, col: e.col || 1, msg: e.message, severity });
  try { tokenize(text); } catch (e) { if (e instanceof FlexError) { push(e); return out; } throw e; }
  let P;
  try { P = parseFlex(text); } catch (e) { if (e instanceof FlexError) { push(e); return out; } throw e; }
  if (!P.hasEnd) out.push({ line: lastLine(text), col: 1, msg: 'Missing END', severity: 'warning' });
  let model;
  try { model = buildModel(P); } catch (e) { if (e instanceof FlexError) { push(e); return out; } throw e; }
  const C = model.compiler;
  const tryCompile = n => { try { C.compile(n); } catch (e) { if (e instanceof FlexError) push(e); else throw e; } };
  for (const e of model.equations) { tryCompile(e.lhs); tryCompile(e.rhs); }
  for (const iv of P.initial) tryCompile(iv.expr);
  if (P.time) for (const h of P.time.halt) tryCompile(h);
  for (const b of P.plots) for (const it of b.items) {
    for (const e of it.exprs || it.args || []) if (e.k !== 'str') tryCompile(e);
    if (it.vs) tryCompile(it.vs);
    if (it.type === 'report' && it.exprs.some(e => C.fieldDep(e)))
      out.push({ line: it.line, col: it.col, msg: 'A Scalar Evaluation has encountered a Field value with no Location Specified (use val(expr, x) )', severity: 'error' });
  }
  if (!P.equations.length && P.variables.length) out.push({ line: 1, col: 1, msg: 'No EQUATIONS section', severity: 'warning' });
  return out;
}

const lastLine = t => t.split('\n').length;
