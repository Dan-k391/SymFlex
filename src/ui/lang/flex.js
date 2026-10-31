// FlexPDE descriptor language for CodeMirror (case-insensitive stream tokenizer).
import { StreamLanguage } from '@codemirror/language'
import { FLEX_COORDINATES, FLEX_FUNCTIONS, FLEX_KEYWORDS, FLEX_PLOTS, FLEX_SECTIONS, FLEX_SELECT } from './flex_docs.js'

// Multi-word section names first so "INITIAL VALUES" wins over a lone word.
const SECTION_RE = new RegExp('^(' + FLEX_SECTIONS.map(([s]) => s).sort((a, b) => b.length - a.length)
  .map((s) => s.replace(' ', '\\s+')).join('|') + '|INITIAL\\s+EQUATIONS)\\b(?!\\s*\\()', 'i')
const KEYWORDS = new Set(FLEX_KEYWORDS.map((k) => k.toLowerCase()))
const FUNCS = new Set(FLEX_FUNCTIONS.map(([n]) => n))
const PLOTS = new Set(FLEX_PLOTS.map(([n]) => n))
const SELECTS = new Set(FLEX_SELECT.map(([n]) => n))
const COORDS = new Set(FLEX_COORDINATES)

export const flexStreamParser = {
  name: 'flexpde',
  startState: () => ({ comment: 0, section: '' }),
  token(stream, state) {
    if (state.comment) {
      while (!stream.eol()) {
        const c = stream.next()
        if (c === '{') state.comment++
        else if (c === '}' && --state.comment === 0) break
      }
      return 'blockComment'
    }
    if (stream.eatSpace()) return null
    if (stream.eat('{')) { state.comment = 1; return 'blockComment' }
    if (stream.eat('!')) { stream.skipToEnd(); return 'lineComment' }
    const ch = stream.peek()
    if (ch === "'" || ch === '"') {
      stream.next()
      stream.skipTo(ch) ? stream.next() : stream.skipToEnd()
      return 'string'
    }
    if (!stream.string.slice(0, stream.pos).trim() && stream.match(SECTION_RE)) {
      state.section = stream.current().toUpperCase().replace(/\s+/g, ' ')
      return 'heading'
    }
    if (stream.match(/^(\d+\.?\d*|\.\d+)([eE][-+]?\d+)?/)) return 'number'
    if (stream.match(/^(<=|>=|<>|\*\*|[-+*\/^=<>])/)) return 'operator'
    if (stream.match(/^[()[\]]/)) return 'bracket'
    if (stream.match(/^[,;:]/)) return 'punctuation'
    if (stream.match(/^[A-Za-z_][A-Za-z0-9_]*/)) {
      const w = stream.current().toLowerCase()
      if (state.section === 'EQUATIONS' && stream.match(/^\s*:/, false)) return 'labelName'
      if (state.section === 'SELECT' && SELECTS.has(w)) return 'propertyName'
      if (COORDS.has(w)) return 'atom'
      if (w === 'on' || w === 'off' || w === 'pi' || w === 'endtime') return 'atom'
      if (PLOTS.has(w) && /^(PLOTS|MONITORS|HISTORIES|SUMMARY)/.test(state.section)) return 'keyword'
      if (KEYWORDS.has(w)) return 'keyword'
      if (FUNCS.has(w) || PLOTS.has(w)) return 'variableName.standard'
      if (stream.match(/^\s*=/, false) && /^(DEFINITIONS|VARIABLES|INITIAL)/.test(state.section)) return 'variableName.definition'
      return 'variableName'
    }
    stream.next()
    return null
  },
  languageData: {
    commentTokens: { line: '!', block: { open: '{', close: '}' } },
    closeBrackets: { brackets: ['(', '[', "'", '"'] },
  },
  indent(state, textAfter) {
    return SECTION_RE.test(textAfter.trim()) ? 0 : 2
  },
}

export const flexLanguage = StreamLanguage.define(flexStreamParser)

/** Name of the section enclosing `pos` in a FlexPDE source text. */
export function flexSectionAt(text, pos) {
  let section = ''
  const re = new RegExp(SECTION_RE.source.slice(1), 'gim')
  const head = text.slice(0, pos).replace(/\{[^}]*\}|![^\n]*/g, (m) => ' '.repeat(m.length))
  for (const m of head.matchAll(re)) {
    const before = head.slice(head.lastIndexOf('\n', m.index) + 1, m.index)
    if (!before.trim()) section = m[1].toUpperCase().replace(/\s+/g, ' ')
  }
  return section
}
