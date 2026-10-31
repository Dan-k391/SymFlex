// Maple 1-D input language for CodeMirror (stream tokenizer) plus a bracket/string linter.
import { StreamLanguage } from '@codemirror/language'
import { MAPLE_CONSTANTS, MAPLE_DOCS, MAPLE_KEYWORDS, MAPLE_PACKAGES } from './maple_docs.js'

const KEYWORDS = new Set(MAPLE_KEYWORDS)
const CONTROL = new Set(['if', 'then', 'elif', 'else', 'fi', 'for', 'from', 'to', 'by', 'do', 'od', 'while',
  'in', 'return', 'break', 'next', 'try', 'catch', 'finally', 'end', 'error'])
const OPERATOR_WORDS = new Set(['and', 'or', 'not', 'xor', 'implies', 'mod', 'union', 'intersect', 'minus', 'subset'])
const DEFINE = new Set(['proc', 'local', 'global', 'option', 'options', 'description', 'module', 'export', 'uses'])
const BUILTINS = new Set(MAPLE_DOCS.map((d) => d.name))
const PACKAGES = new Set(Object.keys(MAPLE_PACKAGES).map((p) => p.replace(/\[.*/, '')))
const CONSTANTS = new Set(MAPLE_CONSTANTS.map(([n]) => n))
const IDENT = /^[A-Za-z_~][A-Za-z0-9_~]*/

export const mapleStreamParser = {
  name: 'maple',
  startState: () => ({ comment: false }),
  token(stream, state) {
    if (state.comment) {
      if (stream.skipTo('*)')) { stream.pos += 2; state.comment = false } else stream.skipToEnd()
      return 'blockComment'
    }
    if (stream.eatSpace()) return null
    if (stream.match('(*')) { state.comment = true; return 'blockComment' }
    if (stream.eat('#')) { stream.skipToEnd(); return 'lineComment' }
    const ch = stream.peek()
    if (ch === '"') {
      stream.next()
      while (!stream.eol()) { const c = stream.next(); if (c === '\\') stream.next(); else if (c === '"') return 'string' }
      return 'string'
    }
    if (ch === '`') { stream.next(); stream.skipTo('`') ? stream.next() : stream.skipToEnd(); return 'variableName.special' }
    if (ch === "'") { stream.next(); return 'meta' }  // unevaluation quote
    if (stream.match(/^(\d+\.?\d*|\.\d+)([eE][-+]?\d+)?/)) return 'number'
    if (stream.match(':=')) return 'definitionOperator'
    if (stream.match(/^(->|\.\.|:-|::|<>|<=|>=|\|\||@@|&x|&\*|&[A-Za-z]+)/)) return 'operator'
    if (stream.match(/^[-+*\/^=<>!$@%|.]/)) return 'operator'
    if (stream.match(/^[()[\]{}]/)) return 'bracket'
    if (stream.match(/^[;:,]/)) return 'punctuation'
    if (stream.match(IDENT)) {
      const w = stream.current()
      if (KEYWORDS.has(w)) return OPERATOR_WORDS.has(w) ? 'operatorKeyword' : DEFINE.has(w) ? 'definitionKeyword' : CONTROL.has(w) ? 'controlKeyword' : 'keyword'
      if (w === 'restart') return 'keyword'
      if (stream.match(/^\s*:=/, false)) return 'variableName.definition'
      if (CONSTANTS.has(w)) return w === 'true' || w === 'false' || w === 'FAIL' ? 'bool' : 'atom'
      if (PACKAGES.has(w)) return 'namespace'
      if (BUILTINS.has(w)) return 'variableName.standard'
      if (stream.match(/^\s*\(/, false)) return 'variableName.function'
      return 'variableName'
    }
    stream.next()
    return null
  },
  languageData: {
    commentTokens: { line: '#', block: { open: '(*', close: '*)' } },
    closeBrackets: { brackets: ['(', '[', '{', '"', '`'] },
    indentOnInput: /^\s*(end|fi|od|else|elif|catch|finally)\b/,
  },
  indent(state, textAfter, cx) {
    // Indent one unit inside proc/if/do blocks by counting openers on the previous lines.
    const before = cx.state.doc.sliceString(0, cx.pos).replace(/#.*$/gm, '').replace(/"(\\.|[^"\\])*"/g, '')
    const open = (before.match(/\b(proc|module|then|do|try)\b/g) || []).length
    const close = (before.match(/\b(end|fi|od)\b/g) || []).length
    const dedent = /^\s*(end|fi|od|else|elif|catch|finally)\b/.test(textAfter) ? 1 : 0
    return Math.max(0, open - close - dedent) * cx.unit
  },
}

export const mapleLanguage = StreamLanguage.define(mapleStreamParser)

const PAIRS = { ')': '(', ']': '[', '}': '{' }

/** Unbalanced brackets, unterminated strings/comments: [{from, to, severity, message}]. */
export function checkMapleBrackets(text) {
  const diags = [], stack = []
  for (let i = 0; i < text.length; i++) {
    const c = text[i]
    if (c === '#') { while (i < text.length && text[i] !== '\n') i++; continue }
    if (c === '(' && text[i + 1] === '*') {
      const end = text.indexOf('*)', i + 2)
      if (end < 0) { diags.push({ from: i, to: i + 2, severity: 'error', message: 'Unterminated comment' }); break }
      i = end + 1; continue
    }
    if (c === '"' || c === '`') {
      let j = i + 1
      while (j < text.length && text[j] !== c) j += text[j] === '\\' && c === '"' ? 2 : 1
      if (j >= text.length) { diags.push({ from: i, to: i + 1, severity: 'error', message: c === '"' ? 'Unterminated string' : 'Unterminated name quote' }); break }
      i = j; continue
    }
    if ('([{'.includes(c)) stack.push(i)
    else if (PAIRS[c]) {
      if (stack.length && text[stack.at(-1)] === PAIRS[c]) stack.pop()
      else diags.push({ from: i, to: i + 1, severity: 'error', message: `Unexpected '${c}'` + (stack.length ? ` (expected closer for '${text[stack.at(-1)]}')` : '') })
    }
  }
  for (const i of stack) diags.push({ from: i, to: i + 1, severity: 'error', message: `Unclosed '${text[i]}'` })
  return diags
}
