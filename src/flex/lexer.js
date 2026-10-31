// Tokenizer for FlexPDE scripts. Comments: `! ...` to end of line, `{ ... }` and `/* ... */`
// (both nestable, each closed by its own kind). Identifiers are case-insensitive: `key` is the
// lower-cased form, `text` keeps the original spelling (used for report labels and messages).

export class FlexError extends Error {
  constructor(msg, line = 0, col = 0) {
    super(msg);
    this.line = line;
    this.col = col;
  }
}

const OPS = ['**', '//', '<=', '>=', '<>', '+', '-', '*', '/', '^', '(', ')', ',', ':', '=', '<', '>', '[', ']', ';'];

export function tokenize(src, { keepComments = false } = {}) {
  const toks = [];
  let i = 0, line = 1, col = 1;
  const n = src.length;
  const adv = (k = 1) => {
    for (let j = 0; j < k; j++) {
      if (src[i] === '\n') { line++; col = 1; } else col++;
      i++;
    }
  };
  while (i < n) {
    const c = src[i];
    if (c === '\n' || c === ' ' || c === '\t' || c === '\r' || c === '\f' || c === '\v') { adv(); continue; }
    const sl = line, sc = col, start = i;
    if (c === '!') {
      while (i < n && src[i] !== '\n') adv();
      if (keepComments) toks.push({ type: 'comment', line: sl, col: sc, pos: start, end: i });
      continue;
    }
    if (c === '{' || (c === '/' && src[i + 1] === '*')) {
      // nested block comments; each opener must be closed by its own kind
      const stack = [];
      do {
        if (src[i] === '{') { stack.push('}'); adv(); }
        else if (src[i] === '/' && src[i + 1] === '*') { stack.push('*/'); adv(2); }
        else if (src.startsWith(stack[stack.length - 1], i)) { adv(stack.pop().length); }
        else adv();
      } while (stack.length && i < n);
      if (stack.length) throw new FlexError('Unterminated comment', sl, sc);
      if (keepComments) toks.push({ type: 'comment', line: sl, col: sc, pos: start, end: i });
      continue;
    }
    if (c === "'" || c === '"') {
      adv();
      const s0 = i;
      while (i < n && src[i] !== c) adv();
      if (i >= n) throw new FlexError('Unterminated string', sl, sc);
      const value = src.slice(s0, i);
      adv();
      toks.push({ type: 'str', value, line: sl, col: sc, pos: start, end: i });
      continue;
    }
    if (/[0-9.]/.test(c) && (c !== '.' || /[0-9]/.test(src[i + 1] || ''))) {
      const m = /^(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?/.exec(src.slice(i, i + 64));
      adv(m[0].length);
      toks.push({ type: 'num', value: parseFloat(m[0]), text: m[0], line: sl, col: sc, pos: start, end: i });
      continue;
    }
    if (/[A-Za-z_]/.test(c)) {
      const m = /^[A-Za-z_][A-Za-z_0-9]*/.exec(src.slice(i, i + 256));
      adv(m[0].length);
      toks.push({ type: 'id', key: m[0].toLowerCase(), text: m[0], line: sl, col: sc, pos: start, end: i });
      continue;
    }
    if (c === '#') { // #include etc. are not supported: skip the directive line
      while (i < n && src[i] !== '\n') adv();
      continue;
    }
    const op = OPS.find(o => src.startsWith(o, i));
    if (!op) throw new FlexError(`Unexpected character '${c}'`, sl, sc);
    adv(op.length);
    if (op === ';') continue; // optional statement terminator (FlexPDE samples write "div(grad(u)) = 0;")
    toks.push({ type: 'op', value: op, line: sl, col: sc, pos: start, end: i });
  }
  toks.push({ type: 'eof', line, col, pos: n, end: n });
  return toks;
}

// FlexPDE-style name of a token for grammar errors ("does not allow '<minus>' ...").
export function tokenDesc(t) {
  if (t.type === 'eof') return '<end of file>';
  if (t.type === 'num') return Number.isInteger(t.value) && !/[.eE]/.test(t.text) ? '<integer>' : '<number>';
  if (t.type === 'str') return '<string>';
  if (t.type === 'id') return KEYWORDS.has(t.key) ? t.text.toUpperCase() : '<identifier>';
  return { '-': '<minus>', '+': '<plus>', '*': '<star>', '/': '<slash>', '^': '<caret>', '<': '<ltn>', '>': '<gtn>',
    '=': '<equals>', '(': '<lparen>', ')': '<rparen>', ',': '<comma>', ':': '<colon>' }[t.value] || `'${t.value}'`;
}

export const SECTION_WORDS = new Set(['title', 'coordinates', 'select', 'variables', 'global', 'definitions', 'initial',
  'equations', 'constraints', 'extrusion', 'boundaries', 'time', 'monitors', 'plots', 'histories', 'end',
  'materials', 'resolve', 'mesh']);

export const KEYWORDS = new Set([...SECTION_WORDS, 'and', 'or', 'not', 'if', 'then', 'else', 'region', 'start', 'line',
  'arc', 'to', 'close', 'finish', 'value', 'natural', 'halt', 'for', 'by', 'from', 'at', 'as', 'vs', 'versus', 'report',
  'history', 'contour', 'surface', 'elevation', 'vector', 'grid', 'summary', 'export', 'file', 'format', 'window',
  'norm', 'values', 'center', 'radius', 'angle', 'limit', 'critical', 'feature', 'exclude', 'point', 'load', 'label']);
