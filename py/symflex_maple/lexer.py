"""Tokenizer for Maple 1-D input."""
from __future__ import annotations

from dataclasses import dataclass

from .errors import MapleSyntaxError

KEYWORDS = {
    "and", "or", "xor", "implies", "not", "mod", "in", "subset", "union", "minus", "intersect",
    "if", "then", "elif", "else", "fi", "end", "do", "od", "for", "from", "by", "to", "while",
    "proc", "local", "global", "option", "options", "description", "return", "break", "next",
    "error", "try", "catch", "finally", "use", "module", "export", "quit", "done", "stop",
    "read", "save", "uses",
}

# Longest first so that greedy matching works.
OPERATORS = [
    "%%%", ":=", "::", ":-", "->", "..", "<>", "<=", ">=", "**", "@@", "||", "%%",
    "+", "-", "*", "/", "^", "!", "$", "@", "%", ".", "<", ">", "=", "|", ",", ";", ":", "~",
    "(", ")", "[", "]", "{", "}", "'",
]


@dataclass
class Token:
    kind: str   # 'name', 'int', 'float', 'string', 'op', 'kw', 'neutral', 'eof'
    value: str
    pos: int

    def __repr__(self):
        return f"{self.kind}:{self.value!r}"


def _is_name_start(c: str) -> bool:
    return c.isalpha() or c == "_"


def _is_name_char(c: str) -> bool:
    return c.isalnum() or c == "_"


def tokenize(src: str) -> list[Token]:
    toks: list[Token] = []
    i, n = 0, len(src)
    while i < n:
        c = src[i]
        if c in " \t\r\n\f\xa0":   # \xa0: non-breaking spaces pasted from documents
            i += 1
            continue
        if c == "#":
            while i < n and src[i] != "\n":
                i += 1
            continue
        if src.startswith("(*", i):
            j = src.find("*)", i + 2)
            if j < 0:
                raise MapleSyntaxError("unterminated comment", i)
            i = j + 2
            continue
        if c == "\\" and i + 1 < n and src[i + 1] == "\n":   # explicit line continuation
            i += 2
            continue
        start = i
        if c.isdigit() or (c == "." and i + 1 < n and src[i + 1].isdigit()):
            i = _lex_number(src, i, toks)
            continue
        if _is_name_start(c):
            while i < n and _is_name_char(src[i]):
                i += 1
            word = src[start:i]
            toks.append(Token("kw" if word in KEYWORDS else "name", word, start))
            continue
        if c == "`":
            j = src.find("`", i + 1)
            while j >= 0 and j + 1 < n and src[j + 1] == "`":   # `` escapes a backquote
                j = src.find("`", j + 2)
            if j < 0:
                raise MapleSyntaxError("unterminated name", i)
            toks.append(Token("name", src[i + 1:j].replace("``", "`"), start))
            i = j + 1
            continue
        if c == '"':
            i, s = _lex_string(src, i)
            toks.append(Token("string", s, start))
            continue
        if c == "&":
            # neutral operator: &name or &<symbol chars>
            j = i + 1
            if j < n and _is_name_start(src[j]):
                while j < n and _is_name_char(src[j]):
                    j += 1
            else:
                while j < n and src[j] in "*+-/^.<>=!$@~%|":
                    j += 1
            if j == i + 1:
                raise MapleSyntaxError("invalid neutral operator", i)
            toks.append(Token("neutral", src[i:j], start))
            i = j
            continue
        for op in OPERATORS:
            if src.startswith(op, i):
                toks.append(Token("op", op, start))
                i += len(op)
                break
        else:
            raise MapleSyntaxError(f"unexpected character `{c}`", i)
    toks.append(Token("eof", "", n))
    return toks


def _lex_number(src: str, i: int, toks: list[Token]) -> int:
    n = len(src)
    start = i
    is_float = False
    while i < n and src[i].isdigit():
        i += 1
    # a '.' belongs to the number unless it starts '..' (range operator)
    if i < n and src[i] == "." and not src.startswith("..", i):
        is_float = True
        i += 1
        while i < n and src[i].isdigit():
            i += 1
    if i < n and src[i] in "eE":
        j = i + 1
        if j < n and src[j] in "+-":
            j += 1
        if j < n and src[j].isdigit():
            while j < n and src[j].isdigit():
                j += 1
            is_float = True
            i = j
    toks.append(Token("float" if is_float else "int", src[start:i], start))
    return i


_ESCAPES = {"n": "\n", "t": "\t", '"': '"', "\\": "\\", "r": "\r", "a": "\a", "b": "\b"}


def _lex_string(src: str, i: int) -> tuple[int, str]:
    n = len(src)
    i += 1
    out = []
    while i < n:
        c = src[i]
        if c == "\\" and i + 1 < n:
            out.append(_ESCAPES.get(src[i + 1], src[i + 1]))
            i += 2
            continue
        if c == '"':
            if i + 1 < n and src[i + 1] == '"':   # "" inside a string is a literal quote
                out.append('"')
                i += 2
                continue
            return i + 1, "".join(out)
        out.append(c)
        i += 1
    raise MapleSyntaxError("unterminated string", i)
