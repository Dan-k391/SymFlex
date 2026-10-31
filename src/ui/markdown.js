// Markdown cells: marked for the prose, KaTeX for $...$ and $$...$$. Raw HTML is escaped
// and links restricted to safe schemes because notebooks can come from other people.
import katex from 'katex'
import { Marked } from 'marked'
import { escapeHtml } from './io.js'

const marked = new Marked({
  gfm: true,
  breaks: false,
  renderer: {
    html: ({ text }) => escapeHtml(text),
    link({ href, title, tokens }) {
      const safe = /^(https?:|mailto:|#|\.{0,2}\/)/i.test(href) ? href : '#'
      const t = title ? ` title="${escapeHtml(title)}"` : ''
      return `<a href="${escapeHtml(safe)}"${t} target="_blank" rel="noopener">${this.parser.parseInline(tokens)}</a>`
    },
  },
})

export function renderMath(tex, displayMode, output = 'htmlAndMathml') {
  try {
    return katex.renderToString(tex, { displayMode, throwOnError: false, output })
  } catch {
    return `<code>${escapeHtml(tex)}</code>`
  }
}

/** Renders markdown with math to an HTML string. */
export function renderMarkdown(src, mathOutput) {
  const math = []
  // Pull math out first so marked does not mangle underscores and backslashes inside it.
  const stash = (tex, display) => `\u0000${math.push([tex, display]) - 1}\u0000`
  const text = src
    .replace(/\$\$([\s\S]+?)\$\$/g, (_, t) => stash(t, true))
    .replace(/(^|[^\\$])\$([^\s$](?:[^$\n]*?[^\s$])?)\$(?!\d)/g, (_, pre, t) => pre + stash(t, false))
  return marked.parse(text).replace(/\u0000(\d+)\u0000/g, (_, i) => renderMath(math[i][0], math[i][1], mathOutput))
}
