"""Recursive-descent parser for Maple 1-D input.

Operator precedence, lowest first (from Maple's ?operators,precedence):
  , < -> < implies < xor < or < and < not < $ < relations (= <> < <= > >= in) < .. <
  subset < mod < + - union minus < * / . @ intersect < ^ @@ (non-assoc) < ! < &-operators <
  :: < :- / function application / indexing / ||
"""
from __future__ import annotations

from .errors import MapleSyntaxError
from .lexer import Token, tokenize
from .nodes import (
    Angle, Assign, BinOp, Break, Call, Ditto, Empty, ErrorStmt, ExprSeqN, ExprStmt, FloatLit,
    For, If, Index, ListN, Member, ModuleN, Name, Next, Num, Param, ProcN, Quit, Range, Read,
    Rel, Return, SeqOp, SetN, Str, TopStmt, Try, TypeAnn, UnOp, Uneval, Use,
)

TERMINATORS = (";", ":")
RELOPS = ("=", "<>", "<", "<=", ">", ">=")
BLOCK_END = {"end", "fi", "od", "else", "elif", "catch", "finally"}
END_WORDS = {"if", "do", "proc", "module", "try", "use"}


class Parser:
    def __init__(self, src: str):
        self.src = src
        self.toks = tokenize(src)
        self.i = 0
        self.no_gt = False   # inside <...>: '>' closes the constructor instead of comparing

    # ------------------------------------------------------------ token helpers
    def peek(self, k: int = 0) -> Token:
        return self.toks[min(self.i + k, len(self.toks) - 1)]

    def at(self, value: str, kind: str | None = None) -> bool:
        t = self.peek()
        return t.value == value and t.kind in ((kind,) if kind else ("op", "kw"))

    def at_kw(self, *words: str) -> bool:
        t = self.peek()
        return t.kind == "kw" and t.value in words

    def advance(self) -> Token:
        t = self.peek()
        self.i += 1
        return t

    def accept(self, value: str) -> bool:
        if self.at(value):
            self.i += 1
            return True
        return False

    def expect(self, value: str) -> Token:
        if not self.at(value):
            self.fail_unexpected()
        return self.advance()

    def fail_unexpected(self):
        t = self.peek()
        if t.kind == "eof":
            raise MapleSyntaxError("unexpected end of statement", t.pos)
        raise MapleSyntaxError(f"`{t.value}` unexpected", t.pos)

    # ------------------------------------------------------------ top level
    def top_statements(self):
        """Yield TopStmt one at a time so earlier statements run before a later syntax error."""
        while True:
            while self.at(";") or self.at(":"):
                self.advance()
            if self.peek().kind == "eof":
                return
            start = self.peek().pos
            stmt = self.statement()
            end = self.peek().pos
            if self.at(";"):
                display = True
                self.advance()
            elif self.at(":"):
                display = False
                self.advance()
            elif self.peek().kind == "eof":
                display = True
            else:
                raise MapleSyntaxError("missing operator or `;`", self.peek().pos)
            yield TopStmt(stmt, display, self.src[start:end].strip())

    def parse_all(self) -> list[TopStmt]:
        return list(self.top_statements())

    def block(self) -> list:
        """Statements up to (not including) a block-ending keyword."""
        out = []
        while True:
            while self.at(";") or self.at(":"):
                self.advance()
            t = self.peek()
            if t.kind == "eof" or (t.kind == "kw" and t.value in BLOCK_END):
                return out
            out.append(self.statement())
            if not (self.at(";") or self.at(":")):
                t = self.peek()
                if not (t.kind == "kw" and t.value in BLOCK_END):
                    if t.kind == "eof":
                        return out
                    raise MapleSyntaxError("missing operator or `;`", t.pos)

    def end_block(self, *words: str):
        """Accept 'end [word]' or one of the short forms (fi/od)."""
        t = self.peek()
        if t.kind == "kw" and t.value in ("fi", "od") and t.value in words:
            self.advance()
            return
        if not self.at_kw("end"):
            if t.kind == "eof":
                raise MapleSyntaxError(f"unterminated {words[-1]}", t.pos)
            self.fail_unexpected()
        self.advance()
        if self.peek().kind == "kw" and self.peek().value in END_WORDS:
            if self.peek().value not in words:
                raise MapleSyntaxError(f"reserved word `{self.peek().value}` unexpected",
                                       self.peek().pos)
            self.advance()

    # ------------------------------------------------------------ statements
    def statement(self):
        t = self.peek()
        if t.kind == "kw":
            w = t.value
            if w == "if":
                return self.if_stmt()
            if w in ("for", "while", "do"):
                return self.loop_stmt()
            if w == "return":
                self.advance()
                if self._at_stmt_end():
                    return Return(None)
                return Return(self.expr_seq())
            if w == "break":
                self.advance()
                return Break()
            if w == "next":
                self.advance()
                return Next()
            if w == "error":
                self.advance()
                args = [] if self._at_stmt_end() else self._seq_items(self.expr_seq())
                return ErrorStmt(args)
            if w == "try":
                return self.try_stmt()
            if w == "use":
                return self.use_stmt()
            if w in ("quit", "done", "stop"):
                self.advance()
                return Quit()
            if w == "read":
                self.advance()
                return Read(self.expr())
        if t.kind == "op" and t.value in TERMINATORS:
            return Empty()
        lhs = self.expr_seq()
        if self.accept(":="):
            return Assign(self._seq_items(lhs), self.expr_seq())
        return ExprStmt(lhs)

    def _at_stmt_end(self) -> bool:
        t = self.peek()
        return t.kind == "eof" or (t.kind == "op" and t.value in TERMINATORS) or (
            t.kind == "kw" and t.value in BLOCK_END)

    @staticmethod
    def _seq_items(node):
        return list(node.items) if isinstance(node, ExprSeqN) else [node]

    def if_stmt(self):
        self.expect("if")
        branches = []
        cond = self.expr()
        self.expect("then")
        branches.append((cond, self.block()))
        orelse = None
        while True:
            if self.accept("elif"):
                cond = self.expr()
                self.expect("then")
                branches.append((cond, self.block()))
            elif self.accept("else"):
                orelse = self.block()
            else:
                break
        self.end_block("fi", "if")
        return If(branches, orelse)

    def loop_stmt(self):
        loop = For(None, [])
        if self.accept("for"):
            name = self.advance()
            if name.kind != "name":
                raise MapleSyntaxError(f"`{name.value}` unexpected", name.pos)
            loop.var = name.value
            if self.accept(","):    # for i, x in L  (index, value)
                second = self.advance()
                loop.var = (name.value, second.value)
        while True:
            if self.accept("from"):
                loop.start = self.expr()
            elif self.accept("by"):
                loop.step = self.expr()
            elif self.accept("to"):
                loop.stop = self.expr()
            elif self.accept("while"):
                loop.cond = self.expr()
            elif self.accept("in"):
                loop.iterable = self.expr()
            else:
                break
        self.expect("do")
        loop.body = self.block()
        self.end_block("od", "do")
        return loop

    def try_stmt(self):
        self.expect("try")
        body = self.block()
        catches = []
        final = None
        while self.accept("catch"):
            pats = []
            if not self.accept(":"):
                pats = self._seq_items(self.expr_seq())
                self.expect(":")
            catches.append((pats, self.block()))
        if self.accept("finally"):
            final = self.block()
        self.end_block("try")
        return Try(body, catches, final)

    def use_stmt(self):
        self.expect("use")
        pk = [self.range_expr()]        # not expr(): `in` here is the keyword, not membership
        while self.accept(","):
            pk.append(self.range_expr())
        self.expect("in")
        body = self.block()
        self.end_block("use")
        return Use(pk, body)

    # ------------------------------------------------------------ expressions
    def expr_seq(self):
        if self._at_seq_end():
            return ExprSeqN([])
        items = [self.expr()]
        while self.accept(","):
            items.append(self.expr())      # f(a, , b) and f(a,) are syntax errors
        return items[0] if len(items) == 1 else ExprSeqN(items)

    def _at_seq_end(self) -> bool:
        t = self.peek()
        return t.kind == "eof" or (t.kind == "op" and t.value in (")", "]", "}", ";", ":", ":=")) \
            or (t.kind == "kw" and t.value in BLOCK_END)

    def expr(self):
        """One expression (no top-level commas)."""
        left = self.implies_expr()
        if self.accept("->"):
            return self._make_arrow(left, self.expr())
        return left

    def _make_arrow(self, lhs, body):
        items = lhs.items if isinstance(lhs, ExprSeqN) else [lhs]
        params = []
        for it in items:
            if isinstance(it, Name):
                params.append(Param(it.name))
            elif isinstance(it, TypeAnn) and isinstance(it.expr, Name):
                params.append(Param(it.expr.name, it.type))
            else:
                raise MapleSyntaxError("invalid arrow procedure parameters")
        return ProcN(params, [ExprStmt(body)], arrow=True)

    def _left_assoc(self, sub, ops):
        left = sub()
        while self.peek().kind == "kw" and self.peek().value in ops:
            op = self.advance().value
            left = BinOp(op, left, sub())
        return left

    def implies_expr(self):
        return self._left_assoc(self.xor_expr, ("implies",))

    def xor_expr(self):
        return self._left_assoc(self.or_expr, ("xor",))

    def or_expr(self):
        return self._left_assoc(self.and_expr, ("or",))

    def and_expr(self):
        return self._left_assoc(self.not_expr, ("and",))

    def not_expr(self):
        if self.accept("not"):
            return UnOp("not", self.not_expr())
        return self.dollar_expr()

    def dollar_expr(self):
        left = self.rel_expr()
        while self.accept("$"):
            left = SeqOp(left, self.rel_expr())
        return left

    def rel_expr(self):
        left = self.range_expr()
        t = self.peek()
        if t.kind == "op" and t.value in RELOPS and not (self.no_gt and t.value == ">"):
            self.advance()
            right = self.range_expr()
            nt = self.peek()
            if nt.kind == "op" and nt.value in RELOPS and not (self.no_gt and nt.value == ">"):
                raise MapleSyntaxError(f"`{nt.value}` unexpected", nt.pos)
            return Rel(t.value, left, right)
        if self.at_kw("in"):
            self.advance()
            return BinOp("in", left, self.range_expr())
        return left

    def range_expr(self):
        left = self.subset_expr()
        if self.accept(".."):
            right = self.subset_expr()
            return Range(left, right)
        return left

    def subset_expr(self):
        left = self.mod_expr()
        if self.accept("subset"):
            return BinOp("subset", left, self.mod_expr())
        return left

    def mod_expr(self):
        return self._left_assoc(self.add_expr, ("mod",))

    def add_expr(self):
        if self.at("-") or self.at("+"):
            op = self.advance().value
            left = self.mul_expr()
            if op == "-":
                left = UnOp("-", left)
        else:
            left = self.mul_expr()
        while True:
            t = self.peek()
            if t.kind == "op" and t.value in ("+", "-"):
                self.advance()
                left = BinOp(t.value, left, self.mul_expr())
            elif t.kind == "kw" and t.value in ("union", "minus"):
                self.advance()
                left = BinOp(t.value, left, self.mul_expr())
            else:
                return left

    def mul_expr(self):
        left = self._mul_operand()
        while True:
            t = self.peek()
            if t.kind == "op" and t.value in ("*", "/", ".", "@"):
                self.advance()
                left = BinOp(t.value, left, self._mul_operand())
            elif t.kind == "kw" and t.value == "intersect":
                self.advance()
                left = BinOp("intersect", left, self._mul_operand())
            else:
                return left

    def _mul_operand(self):
        # Maple accepts a*-b; the minus applies to the following power-level operand
        if self.at("-"):
            self.advance()
            return UnOp("-", self.pow_expr())
        return self.pow_expr()

    def pow_expr(self):
        left = self.fact_expr()
        t = self.peek()
        if t.kind == "op" and t.value in ("^", "**", "@@"):
            self.advance()
            op = "^" if t.value == "**" else t.value
            if self.at("-") or self.at("+"):
                sign = self.advance().value
                right = self.fact_expr()
                if sign == "-":
                    right = UnOp("-", right)
            else:
                right = self.fact_expr()
            nt = self.peek()
            if nt.kind == "op" and nt.value in ("^", "**", "@@"):
                raise MapleSyntaxError(f"ambiguous use of `{nt.value}`, please use parentheses",
                                       nt.pos)
            return BinOp(op, left, right)
        return left

    def fact_expr(self):
        left = self.neutral_expr()
        while self.accept("!"):
            left = UnOp("!", left)
        return left

    def neutral_expr(self):
        if self.peek().kind == "neutral":
            op = self.advance().value
            return UnOp(op, self.neutral_expr())
        left = self.postfix_expr()
        while self.peek().kind == "neutral":
            op = self.advance().value
            left = BinOp(op, left, self.postfix_expr())
        return left

    def postfix_expr(self):
        node = self.primary()
        while True:
            if self.at("("):
                node = Call(node, self._bracketed_items("(", ")"))
            elif self.at("["):
                node = Index(node, self._bracketed_items("[", "]"))
            elif self.accept(":-"):
                t = self.advance()
                if t.kind not in ("name", "kw"):
                    raise MapleSyntaxError(f"`{t.value}` unexpected", t.pos)
                node = Member(node, t.value)
            elif self.accept("::"):
                node = TypeAnn(node, self.primary_type())
            elif self.accept("||"):
                node = BinOp("||", node, self.primary())
            else:
                return node

    def primary_type(self):
        # a type after '::' is an ordinary expression without relations/commas
        return self.postfix_expr()

    def _bracketed_items(self, open_, close):
        self.expect(open_)
        saved, self.no_gt = self.no_gt, False
        seq = self.expr_seq()
        self.no_gt = saved
        self.expect(close)
        return self._seq_items(seq)

    def primary(self):
        t = self.peek()
        k, v = t.kind, t.value
        if k == "int":
            self.advance()
            return Num(v)
        if k == "float":
            self.advance()
            return FloatLit(v)
        if k == "string":
            self.advance()
            return Str(v)
        if k == "name":
            self.advance()
            return Name(v)
        if k == "op":
            if v == "(":
                self.advance()
                saved, self.no_gt = self.no_gt, False
                inner = self.expr_seq()
                self.no_gt = saved
                self.expect(")")
                return inner
            if v == "[":
                return ListN(self._bracketed_items("[", "]"))
            if v == "{":
                return SetN(self._bracketed_items("{", "}"))
            if v == "'":
                self.advance()
                saved, self.no_gt = self.no_gt, False
                inner = self.expr_seq()
                self.no_gt = saved
                self.expect("'")
                return Uneval(inner)
            if v in ("%", "%%", "%%%"):
                self.advance()
                return Ditto(len(v))
            if v == "<":
                return self.angle()
            if v == "$":
                self.advance()
                return SeqOp(None, self.rel_expr())
            if v == "-":       # e.g. f(-x) handled by add_expr; this catches x = -1 .. etc.
                self.advance()
                return UnOp("-", self.mul_expr())
        if k == "kw":
            if v == "proc":
                return self.proc_expr()
            if v == "module":
                return self.module_expr()
            if v in ("not",):
                return self.not_expr()
        self.fail_unexpected()

    def angle(self):
        self.expect("<")
        saved, self.no_gt = self.no_gt, True
        items, sep = [], None
        if not self.at(">"):
            items.append(self.expr())
            while self.at(",") or self.at("|"):
                s = self.advance().value
                if sep and s != sep:
                    raise MapleSyntaxError("mixed separators in <...> constructor")
                sep = s
                items.append(self.expr())
        self.no_gt = saved
        self.expect(">")
        return Angle(sep or ",", items)

    # ------------------------------------------------------------ procedures
    def proc_expr(self):
        start = self.peek().pos
        self.expect("proc")
        self.expect("(")
        params = self._params(")")
        self.expect(")")
        if self.accept("::"):        # return type annotation
            self.postfix_expr()
            self.accept(";")
        p = ProcN(params, [])
        self._declarations(p, allow_exports=False)
        p.body = self.block()
        self.end_block("proc")
        p.source = self.src[start:self.toks[self.i - 1].pos + len(self.toks[self.i - 1].value)]
        return p

    def module_expr(self):
        self.expect("module")
        self.expect("(")
        self.expect(")")
        m = ModuleN([])
        self._declarations(m, allow_exports=True)
        m.body = self.block()
        self.end_block("module")
        return m

    def _params(self, close):
        params = []
        if self.at(close):
            return params
        while True:
            if self.accept("{"):
                for p in self._params("}"):
                    p.keyword = True
                    params.append(p)
                self.expect("}")
            elif self.accept("$"):
                pass
            else:
                params.append(self._param())
            if not self.accept(","):
                return params

    def _param(self):
        t = self.advance()
        if t.kind != "name":
            raise MapleSyntaxError(f"`{t.value}` unexpected", t.pos)
        p = Param(t.value)
        if self.accept("::"):
            saved, self.no_gt = self.no_gt, False
            p.type = self.range_expr()
            self.no_gt = saved
        if self.accept(":="):
            p.default = self.expr()
        return p

    def _declarations(self, p, allow_exports):
        while True:
            if self.at_kw("local") or (allow_exports and self.at_kw("export")):
                kind = self.advance().value
                decl = self._params_until_term()
                if kind == "local":
                    p.locals.extend(decl)
                else:
                    p.exports.extend(decl)
            elif self.at_kw("global"):
                self.advance()
                p.globals.extend(x.name for x in self._params_until_term())
            elif self.at_kw("option", "options"):
                self.advance()
                p.options.extend(self._seq_items(self.expr_seq()))
                self._term()
            elif self.at_kw("description"):
                self.advance()
                d = self.expr_seq()
                if isinstance(p, ProcN):
                    p.description = getattr(d, "value", None)
                self._term()
            elif self.at_kw("uses"):
                self.advance()
                self.expr_seq()
                self._term()
            else:
                return

    def _params_until_term(self):
        out = [self._param()]
        while self.accept(","):
            out.append(self._param())
        self._term()
        return out

    def _term(self):
        if not (self.accept(";") or self.accept(":")):
            self.fail_unexpected()


def parse(src: str) -> list[TopStmt]:
    return Parser(src).parse_all()


def parse_expr(src: str):
    p = Parser(src)
    e = p.expr_seq()
    if p.peek().kind != "eof":
        p.fail_unexpected()
    return e
