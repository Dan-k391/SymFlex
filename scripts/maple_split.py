"""Split Maple 1-D input into top-level statements.

split_statements(code) -> [{'src', 'terminator', 'line'}]
  src        statement text without its terminator, leading/trailing comments and whitespace
  terminator ';' | ':' | ''   ('' = trailing statement with no terminator; real cmaple treats a
             missing final terminator as a syntax error, the worksheet GUI evaluates it like ';')
  line       1-based line of the statement's first token

Also: is_assignment(src), first_word(src), tokens(code).
Self-test: python scripts/maple_split.py --selftest
"""
import re
import sys

OPENERS = {'proc', 'module', 'do', 'if', 'try', 'use'}
CLOSE_PAIR = {')': '(', ']': '[', '}': '{', '>': '<'}
# Tokens after which an expression is complete, so '<' / '>' are comparisons, not vector brackets.
NON_OPERAND_WORDS = {'then', 'else', 'elif', 'do', 'return', 'and', 'or', 'not', 'xor', 'implies',
                     'in', 'to', 'from', 'by', 'while', 'if', 'local', 'global', 'proc', 'use',
                     'error', 'try', 'catch', 'finally', 'union', 'intersect', 'minus', 'mod', 'subset'}
MULTI_OPS = (':=', '::', ':-', '->', '<>', '<=', '>=', '..', '||', '+=', '-=', '*=', '/=')
_IDENT = re.compile(r'[A-Za-z_~][A-Za-z0-9_~]*')
_NUM = re.compile(r'\d+(\.\d*)?([eE][-+]?\d+)?')


def tokens(code):
    """Yield (kind, text, start, end) for significant tokens; comments and whitespace are skipped.
    kind: 'name' (identifier), 'qname' (back-quoted), 'str', 'num', 'op'."""
    i, n = 0, len(code)
    while i < n:
        c = code[i]
        if c.isspace():
            i += 1
        elif c == '#':
            j = code.find('\n', i)
            i = n if j < 0 else j
        elif code.startswith('(*', i):
            j = code.find('*)', i + 2)
            i = n if j < 0 else j + 2
        elif c == '"':
            j = i + 1
            while j < n and code[j] != '"':
                j += 2 if code[j] == '\\' else 1
            yield 'str', code[i:j + 1], i, min(j + 1, n)
            i = j + 1
        elif c == '`':
            j = code.find('`', i + 1)
            j = n - 1 if j < 0 else j
            yield 'qname', code[i:j + 1], i, j + 1
            i = j + 1
        elif _IDENT.match(code, i):
            m = _IDENT.match(code, i)
            yield 'name', m.group(), i, m.end()
            i = m.end()
        elif c.isdigit():
            m = _NUM.match(code, i)
            yield 'num', m.group(), i, m.end()
            i = m.end()
        else:
            op = next((o for o in MULTI_OPS if code.startswith(o, i)), c)
            yield 'op', op, i, i + len(op)
            i += len(op)


def _is_operand(tok):
    if tok is None:
        return False
    kind, text = tok[0], tok[1]
    if kind == 'name':
        return text not in NON_OPERAND_WORDS
    return kind in ('qname', 'str', 'num') or text in (')', ']', '}', '>')


def _scan(code):
    """Yield (tok, depth_before) with block/bracket nesting tracked."""
    stack, prev, skip_next_opener = [], None, False
    for tok in tokens(code):
        kind, text = tok[0], tok[1]
        depth = len(stack)
        if kind == 'name':
            if skip_next_opener and text in OPENERS:   # the 'if' in 'end if'
                skip_next_opener = False
                yield tok, depth
                prev = tok
                continue
            skip_next_opener = False
            if text in OPENERS:
                stack.append(text)
            elif text in ('end', 'od', 'fi'):
                if stack:
                    stack.pop()
                skip_next_opener = text == 'end'
        elif kind == 'op':
            skip_next_opener = False
            if text in '([{':
                stack.append(text)
            elif text == '<' and not _is_operand(prev):
                stack.append('<')
            elif text in CLOSE_PAIR and (text != '>' or (stack and stack[-1] == '<')):
                if stack:
                    stack.pop()
        else:
            skip_next_opener = False
        yield tok, depth
        prev = tok


def split_statements(code):
    code = code.replace('\r\n', '\n')
    out, start, last_end = [], None, None

    def emit(term):
        out.append({'src': code[start:last_end], 'terminator': term,
                    'line': code.count('\n', 0, start) + 1})

    for tok, depth in _scan(code):
        kind, text, s, e = tok
        if depth == 0 and kind == 'op' and text in (';', ':'):
            if start is not None:
                emit(text)
            start = None
            continue
        if start is None:
            start = s
        last_end = e
    if start is not None:
        emit('')
    return out


def first_word(src):
    for kind, text, _, _ in tokens(src):
        return text if kind == 'name' else None
    return None


def is_assignment(src):
    """True if src has a top-level ':=' (or +=, -=, ...) i.e. it is an assignment statement."""
    return any(d == 0 and t[0] == 'op' and t[1] in (':=', '+=', '-=', '*=', '/=') for t, d in _scan(src))


def _selftest():
    def S(code):
        return [(s['src'], s['terminator'], s['line']) for s in split_statements(code)]
    cases = [
        ('a:=1: b:=2;', [('a:=1', ':', 1), ('b:=2', ';', 1)]),
        ('s:="a;b\\"c:d"; t;', [('s:="a;b\\"c:d"', ';', 1), ('t', ';', 1)]),
        ('`x;y` := 5:', [('`x;y` := 5', ':', 1)]),
        ('# c; c\nx;  # tail; tail\n', [('x', ';', 2)]),
        ('(* a; b *) z := 1;', [('z := 1', ';', 1)]),
        ('f := proc(x) local y; y := x; y end proc; g(1);',
         [('f := proc(x) local y; y := x; y end proc', ';', 1), ('g(1)', ';', 1)]),
        ('for i to 3 do if i>1 then print(i); fi; od:\nk;',
         [('for i to 3 do if i>1 then print(i); fi; od', ':', 1), ('k', ';', 2)]),
        ('if a<b then c: elif d then e; else f end if; x;',
         [('if a<b then c: elif d then e; else f end if', ';', 1), ('x', ';', 1)]),
        ('M := <1,2;3,4>; v := <a|b>; a < b; c > d;',
         [('M := <1,2;3,4>', ';', 1), ('v := <a|b>', ';', 1), ('a < b', ';', 1), ('c > d', ';', 1)]),
        ('x::integer := 3: plots:-display(p): y', [('x::integer := 3', ':', 1), ('plots:-display(p)', ':', 1), ('y', '', 1)]),
        ('m := module() export f; f := proc() 1 end; end module: try 1/0; catch: 2; end try;',
         [('m := module() export f; f := proc() 1 end; end module', ':', 1), ('try 1/0; catch: 2; end try', ';', 1)]),
        ('use plots in display(p); end use; while x do x := x-1 end do;',
         [('use plots in display(p); end use', ';', 1), ('while x do x := x-1 end do', ';', 1)]),
        ('x := 3 # no terminator\n', [('x := 3', '', 1)]),
        ('restart;\n\n  f := x -> x^2;;', [('restart', ';', 1), ('f := x -> x^2', ';', 3)]),
        ('L := [seq(i, i=1..3)]: `if`(a, b, c);', [('L := [seq(i, i=1..3)]', ':', 1), ('`if`(a, b, c)', ';', 1)]),
    ]
    bad = 0
    for code, want in cases:
        got = S(code)
        if got != want:
            bad += 1
            print('FAIL', repr(code), '\n  got ', got, '\n  want', want)
    assert is_assignment('x := 3') and is_assignment('a, b := 1, 2') and not is_assignment('f(x := 3)')
    assert not is_assignment('s := "a"'.replace(':=', '=')) and is_assignment('x += 1')
    assert first_word('  for i to 3 do od') == 'for' and first_word('(a)') is None
    print('selftest: %d/%d split cases ok' % (len(cases) - bad, len(cases)))
    return bad == 0


if __name__ == '__main__':
    if '--selftest' in sys.argv:
        sys.exit(0 if _selftest() else 1)
    for st in split_statements(open(sys.argv[1], encoding='utf-8').read()):
        print(st)
