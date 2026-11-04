// CodeMirror 6 editor factory for notebook cells.
import { autocompletion, closeBrackets, closeBracketsKeymap, completionKeymap, completionStatus } from '@codemirror/autocomplete'
import { defaultKeymap, history, historyKeymap, indentWithTab, toggleComment } from '@codemirror/commands'
import { bracketMatching, HighlightStyle, indentOnInput, indentUnit, syntaxHighlighting } from '@codemirror/language'
import { linter, lintGutter, lintKeymap } from '@codemirror/lint'
import { highlightSelectionMatches, selectNextOccurrence, selectSelectionMatches } from '@codemirror/search'
import { Compartment, EditorState, Prec, StateEffect, StateField } from '@codemirror/state'
import { Decoration, drawSelection, EditorView, highlightActiveLine, keymap, lineNumbers, placeholder } from '@codemirror/view'
import { tags as t } from '@lezer/highlight'
import { assistTheme, docHover, flexCompletionSource, mapleCompletionSource, mapleLintSource, signatureHelp } from './lang/assist.js'
import { flexLanguage } from './lang/flex.js'
import { mapleLanguage } from './lang/maple.js'

// Colours come from CSS variables so the light/dark switch needs no editor reconfiguration.
const highlight = HighlightStyle.define([
  { tag: [t.keyword, t.controlKeyword, t.operatorKeyword], color: 'var(--syn-keyword)', fontWeight: '600' },
  { tag: t.definitionKeyword, color: 'var(--syn-keyword)', fontWeight: '600' },
  { tag: t.heading, color: 'var(--syn-section)', fontWeight: '700' },
  { tag: [t.lineComment, t.blockComment], color: 'var(--syn-comment)', fontStyle: 'italic' },
  { tag: t.string, color: 'var(--syn-string)' },
  { tag: t.number, color: 'var(--syn-number)' },
  { tag: [t.atom, t.bool], color: 'var(--syn-constant)', fontWeight: '500' },
  { tag: t.namespace, color: 'var(--syn-package)', fontWeight: '500' },
  { tag: t.standard(t.variableName), color: 'var(--syn-builtin)' },
  { tag: t.function(t.variableName), color: 'var(--syn-function)' },
  { tag: t.definition(t.variableName), color: 'var(--syn-def)', fontWeight: '600' },
  { tag: t.special(t.variableName), color: 'var(--syn-string)' },
  { tag: [t.operator, t.definitionOperator], color: 'var(--syn-operator)' },
  { tag: t.labelName, color: 'var(--syn-def)', fontWeight: '600' },
  { tag: t.propertyName, color: 'var(--syn-builtin)' },
  { tag: t.meta, color: 'var(--syn-operator)' },
])

const theme = EditorView.theme({
  '&': { fontSize: 'var(--code-size)', backgroundColor: 'transparent', color: 'var(--fg)' },
  // No ligatures: ":=" and "->" must look exactly as typed.
  '.cm-content': { fontFamily: 'var(--font-mono)', fontVariantLigatures: 'none', padding: '8px 0', caretColor: 'var(--accent)' },
  '.cm-scroller': { fontFamily: 'var(--font-mono)', lineHeight: '1.55' },
  '.cm-gutters': { backgroundColor: 'transparent', border: 'none', color: 'var(--muted)' },
  '.cm-activeLine': { backgroundColor: 'var(--active-line)' },
  '&.cm-focused': { outline: 'none' },
  '&.cm-focused .cm-cursor': { borderLeftColor: 'var(--accent)' },
  '&.cm-focused .cm-selectionBackground, .cm-selectionBackground, ::selection': { backgroundColor: 'var(--selection) !important' },
  '.cm-matchingBracket': { backgroundColor: 'var(--bracket-match)', outline: '1px solid var(--border-strong)' },
  '.cm-tooltip': { backgroundColor: 'var(--panel)', color: 'var(--fg)', border: '1px solid var(--border)', borderRadius: '8px', boxShadow: 'var(--shadow)' },
  '.cm-tooltip-autocomplete > ul': { fontFamily: 'var(--font-mono)', fontSize: '13px' },
  '.cm-tooltip-autocomplete ul li[aria-selected]': { backgroundColor: 'var(--accent)', color: 'var(--accent-fg)' },
  '.cm-completionDetail': { fontStyle: 'normal', opacity: 0.7, marginLeft: '1em' },
  '.cm-placeholder': { color: 'var(--muted)' },
  '.cm-panels': { backgroundColor: 'var(--panel)', color: 'var(--fg)' },
})

export const lineNumbersCompartment = new Compartment()

// Notebook find (find.js) owns the query; each editor only draws the matches it is given.
const setFindMatches = StateEffect.define()
const matchMark = Decoration.mark({ class: 'sf-find-match' })
const currentMark = Decoration.mark({ class: 'sf-find-match sf-find-current' })
const findField = StateField.define({
  create: () => Decoration.none,
  update(deco, tr) {
    for (const e of tr.effects) {
      if (e.is(setFindMatches)) return Decoration.set(e.value.map(([from, to, cur]) => (cur ? currentMark : matchMark).range(from, to)))
    }
    return deco.map(tr.changes)
  },
  provide: (f) => EditorView.decorations.from(f),
})

/** Highlights find matches, given as [from, to, isCurrent] sorted by from ([] clears). */
export const showFindMatches = (view, ranges) => view.dispatch({ effects: setFindMatches.of(ranges) })

/**
 * @param {object} o
 * @param {HTMLElement} o.parent
 * @param {'maple'|'flexpde'|'markdown'} o.type
 * @param {string} o.doc
 * @param {(text: string) => void} o.onChange
 * @param {object} o.keys  {runAdvance, runInPlace, runInsert, escape, up, down} handlers -> boolean
 * @param {object} [o.assist]  {userNames, kernelComplete, flexLint}
 * @param {boolean} [o.lineNumbers]
 */
export function createEditor({ parent, type, doc, onChange, keys, assist = {}, lineNumbers: showNumbers = false }) {
  const langExt = []
  if (type === 'maple') {
    langExt.push(mapleLanguage, autocompletion({ override: [mapleCompletionSource(assist)], icons: true }),
      docHover('maple'), signatureHelp('maple'), linter(mapleLintSource(), { delay: 600 }))
  } else if (type === 'flexpde') {
    langExt.push(flexLanguage, autocompletion({ override: [flexCompletionSource()], icons: true }),
      docHover('flexpde'), signatureHelp('flexpde'))
    if (assist.flexLint) langExt.push(linter((view) => assist.flexLint(view.state.doc), { delay: 900 }))
  } else {
    langExt.push(EditorView.lineWrapping, placeholder('Markdown text, $math$ supported'))
  }

  const atEdge = (view, dir) => {
    const sel = view.state.selection.main
    if (!sel.empty || completionStatus(view.state)) return false
    const line = view.state.doc.lineAt(sel.head)
    return dir < 0 ? line.number === 1 : line.number === view.state.doc.lines
  }
  const cellKeys = Prec.highest(keymap.of([
    { key: 'Shift-Enter', run: () => keys.runAdvance() },
    { key: 'Mod-Enter', run: () => keys.runInPlace() },
    { key: 'Alt-Enter', run: () => keys.runInsert() },
    { key: 'Escape', run: (v) => !completionStatus(v.state) && keys.escape() },
    { key: 'ArrowUp', run: (v) => atEdge(v, -1) && keys.up() },
    { key: 'ArrowDown', run: (v) => atEdge(v, 1) && keys.down() },
    { key: 'Mod-/', run: toggleComment },
  ]))

  const state = EditorState.create({
    doc,
    extensions: [
      cellKeys,
      lineNumbersCompartment.of(showNumbers ? lineNumbers() : []),
      history(), drawSelection(), indentOnInput(), bracketMatching(), closeBrackets(),
      highlightActiveLine(), highlightSelectionMatches(), findField, lintGutter(),
      indentUnit.of('  '), EditorState.tabSize.of(2),
      syntaxHighlighting(highlight), theme, assistTheme,
      ...langExt,
      // Ctrl+F / F3 belong to the notebook find bar, so only the selection commands of searchKeymap are kept.
      keymap.of([...closeBracketsKeymap, ...defaultKeymap, { key: 'Mod-d', run: selectNextOccurrence, preventDefault: true },
        { key: 'Mod-Shift-l', run: selectSelectionMatches }, ...historyKeymap,
        ...completionKeymap, ...lintKeymap, indentWithTab]),
      EditorView.updateListener.of((u) => { if (u.docChanged) onChange(u.state.doc.toString()) }),
      EditorView.contentAttributes.of({ 'aria-label': `${type} cell input` }),
    ],
  })
  return new EditorView({ state, parent })
}

export function setLineNumbers(view, on) {
  view.dispatch({ effects: lineNumbersCompartment.reconfigure(on ? lineNumbers() : []) })
}
