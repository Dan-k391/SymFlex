"""Maple evaluation semantics on top of SymPy values.

Key rules implemented here:
* Global names are fully (recursively) evaluated on every lookup, so `ff := mu*N` picks up a
  later `N := 5`.  Locals evaluate one level (their stored value).
* Assignment stores the evaluated right-hand side; `x := 'x'` unassigns.
* `%`, `%%`, `%%%` track the last three non-NULL top-level results (assignments included).
* Procedures are lexically scoped: a nested procedure closes over its defining frame.
* Builtins (builtins/ registry) receive evaluated arguments unless declared evaluate=False.
"""
from __future__ import annotations

import sympy as sp
from sympy.core.function import AppliedUndef

from . import nodes as N
from .builtins import check_arity, get_registry, split_options
from .errors import BreakSignal, MapleError, NextSignal, QuitSignal, ReturnSignal
from .printer import latex, lprint, name_str
from .values import (
    FAIL, NULL, AppliedProc, BuiltinProc, ExprSeq, MEquation, MList, MLogic, MMatrix, Module,
    MRange, MRelation, MSet, MString, MTable, MUneval, MValue, MVector, PlotValue, Procedure,
    RememberProc, UserProc, deep_map, float_zero, make_seq, seq_items,
)

CONSTANTS = {
    "Pi": sp.pi, "I": sp.I, "infinity": sp.oo, "true": sp.true, "false": sp.false, "FAIL": FAIL,
    "NULL": NULL,
}
PROTECTED_CONSTANTS = set(CONSTANTS) | {"Digits"}


class MCall(MValue):
    """Unevaluated call of an unknown function with non-algebraic arguments, e.g. f([1,2])."""
    __slots__ = ("func", "args")

    def __init__(self, func, args):
        self.func, self.args = func, tuple(args)

    def map_leaves(self, f):
        return MCall(self.func, [f(a) for a in self.args])

    def __eq__(self, other):
        return isinstance(other, MCall) and self.func == other.func and self.args == other.args

    def __hash__(self):
        return hash(("call", str(self.func)))


class MIndexExpr(MValue):
    """Unevaluated selection from a non-indexable value, printed (expr)[i]."""
    __slots__ = ("base", "idx")

    def __init__(self, base, idx):
        self.base, self.idx = base, tuple(idx)

    def lprint(self, pr):
        return f"({pr.p(self.base, 0)})[{','.join(pr.p(i, 0) for i in self.idx)}]"


class _Missing:
    def __init__(self, proc, pos, name):
        self.proc, self.pos, self.name = proc, pos, name


class Frame:
    """Variables of one procedure invocation (params, locals, args/nargs)."""
    __slots__ = ("vars", "parent", "proc", "globals_decl")

    def __init__(self, vars, parent, proc=None, globals_decl=()):
        self.vars = vars
        self.parent = parent
        self.proc = proc
        self.globals_decl = set(globals_decl)


def _is_pi_power(f) -> bool:
    return f is sp.pi or (f.is_Pow and f.base is sp.pi and f.exp.is_Rational)


def _float_pi(r, digits):
    """Maple turns Pi into a float when it meets a float in a product or sum:
    Pi/180. = .1745329252e-1, 2.*Pi*t = 6.283185308*t, Pi+1. = 4.141592654
    (sqrt(2)*1.0 and exp(1)*1.0 stay symbolic)."""
    pi = sp.Float(str(sp.pi.evalf(digits)), digits)    # Maple rounds Pi to Digits first

    def term(e):
        if e.is_Mul:
            c, rest = e.as_coeff_Mul()
            if c.is_Float and any(_is_pi_power(f) for f in sp.Mul.make_args(rest)):
                return e.xreplace({sp.pi: pi})
        return e
    if r.is_Add:
        terms = [term(t) for t in r.args]
        if any(t.is_Float for t in terms):
            terms = [t.xreplace({sp.pi: pi}) if t.has(sp.pi) and all(
                _is_pi_power(f) or f.is_Rational for f in sp.Mul.make_args(t)) else t
                for t in terms]
        return sp.Add(*terms)
    return term(r)


def ordinal(n: int) -> str:
    suf = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suf}"


class Evaluator:
    def __init__(self):
        self.env = get_registry()
        self.outputs: list[dict] = []
        self.settings = {"displayprecision": -1, "printlevel": 1, "imaginaryunit": "I"}
        self.frame = None            # frame of the call site while a builtin runs
        self._printf_open = None     # last printf output still waiting for its newline
        self.reset()

    # ------------------------------------------------------------ state
    def reset(self):
        self.globals: dict = {}
        self.bound: dict = {}          # short names made visible by with()
        self.digits = 10
        self.ditto = [NULL, NULL, NULL]
        self.loaded: list[str] = []
        self.assumptions: dict = {}
        self.quoting = 0
        self.call_depth = 0
        self.pending_name: str | None = None
        self.lasterror = NULL

    def interrupted(self):
        """Clear per-statement state an interrupt (KeyboardInterrupt) may leave behind."""
        self.frame = None
        self.quoting = 0
        self.call_depth = 0
        self.pending_name = None
        self._printf_open = None

    # ------------------------------------------------------------ output helpers (builtin API)
    def emit(self, out: dict):
        self.outputs.append(out)

    def print_text(self, text: str):
        self.emit({"kind": "print", "text": text})

    def warn(self, msg: str):
        self.emit({"kind": "warning", "text": f"Warning, {msg}"})

    def to_text(self, v) -> str:
        return lprint(v)

    def to_latex(self, v) -> str:
        return latex(v, self.settings.get("displayprecision", -1))

    def error(self, msg: str, where: str | None = None):
        raise MapleError(msg, where)

    # ------------------------------------------------------------ numbers
    def mkfloat(self, text: str) -> sp.Float:
        mant = text.lower().split("e")[0].replace(".", "").lstrip("0")
        return sp.Float(text, max(self.digits, len(mant)))

    def evalf(self, v, n: int | None = None):
        n = n or self.digits

        def float_args(z):
            if isinstance(z, sp.Piecewise):
                return sp.Piecewise(*((a.evalf(n), c.xreplace({q: sp.Float(q, n) for q in c.atoms(sp.Rational)}))
                                      for a, c in z.args))
            return z.func(*(a.evalf(n) for a in z.args))

        def f(e):
            if isinstance(e, sp.Basic) and not e.is_Boolean:
                try:
                    r = e.evalf(n)
                except Exception:  # noqa: BLE001 - leave non-numeric parts alone
                    return e
                if r is sp.S.Zero:      # SymPy keeps an exact 0; Maple's evalf(0) is 0.
                    return sp.Float(0, n)
                if not r.is_number:     # SymPy leaves sin(t + 2^(1/2)) and t < 1/3 alone; Maple floats them
                    r = r.replace(lambda z: isinstance(z, sp.Function) and not z.is_number, float_args)
                if r.has(sp.Pow) and not r.is_number:
                    # Maple keeps symbolic powers such as x^(1/2) exact under evalf
                    r = r.replace(lambda z: z.is_Pow and z.exp.is_Float and not z.base.is_number
                                  and abs(float(z.exp) * 12 - round(float(z.exp) * 12)) < 1e-9,
                                  lambda z: sp.Pow(z.base, sp.Rational(round(float(z.exp) * 12), 12)))
                return r
            return e
        return deep_map(f, v)

    # ------------------------------------------------------------ evaluation entry points
    def eval(self, node, frame=None):
        try:
            m = getattr(self, "ev_" + type(node).__name__)
        except AttributeError:
            raise MapleError(f"cannot evaluate {type(node).__name__}")
        return m(node, frame)

    def eval_args(self, nodes, frame):
        out = []
        for n in nodes:
            v = self.eval(n, frame)
            if isinstance(v, ExprSeq):
                out.extend(v.items)
            else:
                out.append(v)
        return out

    # ------------------------------------------------------------ names
    def lookup(self, name: str, frame=None, full: bool = True):
        f = frame
        while f is not None:
            if name in f.vars:
                v = f.vars[name]
                if isinstance(v, _Missing):
                    p = v.proc.name or "anonymous procedure"
                    err = MapleError(f"invalid input: {p} uses a {ordinal(v.pos)} argument, "
                                     f"{v.name}, which is missing")
                    err.bare = True
                    raise err
                return v
            if name in f.globals_decl:
                break
            f = f.parent
        if name in self.globals:
            v = self.globals[name]
            return self.full_eval(v) if full else v
        if name in CONSTANTS:
            return CONSTANTS[name]
        if name == "Digits":
            return sp.Integer(self.digits)
        if name == "lasterror":
            return self.lasterror
        if name in self.bound:
            return self.bound[name]
        b = self.env.functions.get(name)
        if b is not None:
            return b
        pkg = self.package(name)
        if pkg is not None:
            return pkg
        return sp.Symbol(name)

    def package(self, name: str):
        from .builtins.packages_data import PACKAGE_EXPORTS
        if name in self.env.packages or name in PACKAGE_EXPORTS:
            return self.env.package(name)
        return None

    def is_assigned(self, name: str, frame=None) -> bool:
        f = frame
        while f is not None:
            if name in f.vars:
                return not isinstance(f.vars[name], sp.Dummy)
            f = f.parent
        return name in self.globals

    # ------------------------------------------------------------ full evaluation
    def _needs_eval(self, e) -> bool:
        if not self.globals and not isinstance(e, AppliedUndef):
            if not e.has(AppliedUndef):
                return False
        g = self.globals
        for s in e.free_symbols:
            if isinstance(s, sp.Dummy):
                continue
            if s.name in g:
                return True
        if e.has(AppliedUndef):
            for a in e.atoms(AppliedUndef):
                n = type(a).__name__
                if n in g or n in self.env.functions or n in self.bound:
                    return True
        if g and e.has(sp.Indexed):
            for a in e.atoms(sp.Indexed):
                if str(a.base.label) in g:
                    return True
        return False

    def rtable_entries(self, v):
        """Vector/Matrix with its entries evaluated. Maple shows an rtable's entries as stored
        (`v;`, `eval(v)`, `lprint(v)`), but arithmetic, indexing and map see their values."""
        if isinstance(v, MMatrix) and any(isinstance(x, sp.Basic) and self._needs_eval(x)
                                          for x in v.m):
            return v.map_leaves(self.full_eval)
        return v

    def full_eval(self, v, depth: int = 0):
        if isinstance(v, sp.Basic):
            if isinstance(v, sp.Symbol):
                if isinstance(v, sp.Dummy) or v.name not in self.globals:
                    return v
            elif v.is_Atom or not self._needs_eval(v):
                return v
            return self.reeval(v, depth)
        if isinstance(v, (MList, MSet, ExprSeq, MRelation, MRange, MLogic, MCall)):
            return v.map_leaves(lambda x: self.full_eval(x, depth))
        return v

    def reeval(self, e, depth: int = 0):
        """Re-evaluate a SymPy expression whose names/functions have since been assigned."""
        if depth > 100:
            raise MapleError("too many levels of recursion")
        if isinstance(e, sp.Symbol):
            if not isinstance(e, sp.Dummy) and e.name in self.globals:
                return self.full_eval(self.globals[e.name], depth + 1)
            return e
        if e.is_Atom or not self._needs_eval(e):
            return e
        args = [self.reeval(a, depth + 1) if isinstance(a, sp.Basic) else a for a in e.args]
        if isinstance(e, AppliedUndef):
            fname = type(e).__name__
            f = self.lookup(fname)
            return self.apply(f, args)
        if isinstance(e, sp.Indexed):
            base = self.full_eval(self.globals.get(str(e.base.label), e.base.label), depth + 1)
            return self.index_value(base, list(e.indices))
        if isinstance(e, sp.Add):
            return _fold(self, "+", args)
        if isinstance(e, sp.Mul):
            return _fold(self, "*", args)
        if isinstance(e, sp.Pow):
            return self.binop("^", args[0], args[1])
        if isinstance(e, sp.Derivative):
            return sp.diff(args[0], *e.variable_count)
        if isinstance(e, sp.Subs):
            return sp.Subs(*args).doit()
        if all(isinstance(a, sp.Basic) for a in args):
            return e.func(*args)
        return e

    # ------------------------------------------------------------ expression nodes
    def ev_Num(self, node, frame):
        return sp.Integer(int(node.text))

    def ev_FloatLit(self, node, frame):
        return self.mkfloat(node.text)

    def ev_Str(self, node, frame):
        return MString(node.value)

    def ev_Name(self, node, frame):
        if self.quoting:
            return self._quoted_name(node.name, frame)
        return self.lookup(node.name, frame)

    def _quoted_name(self, name, frame):
        f = frame
        while f is not None:
            if name in f.vars:
                v = f.vars[name]
                return v if isinstance(v, sp.Dummy) else sp.Symbol(name)
            f = f.parent
        return CONSTANTS.get(name, sp.Symbol(name))

    def ev_Uneval(self, node, frame):
        if isinstance(node.expr, N.Uneval) or self.quoting:
            self.quoting += 1
            try:
                return MUneval(self.eval(node.expr, frame))
            finally:
                self.quoting -= 1
        self.quoting += 1
        try:
            return self.eval(node.expr, frame)
        finally:
            self.quoting -= 1

    def ev_Ditto(self, node, frame):
        return self.ditto[node.level - 1]

    def ev_ExprSeqN(self, node, frame):
        return make_seq(self.eval_args(node.items, frame)) if node.items else NULL

    def ev_ListN(self, node, frame):
        return MList(self.eval_args(node.items, frame))

    def ev_SetN(self, node, frame):
        return MSet(self.eval_args(node.items, frame))

    def ev_Range(self, node, frame):
        return MRange(self.eval(node.lo, frame), self.eval(node.hi, frame))

    def ev_Rel(self, node, frame):
        return MRelation(node.op, self.eval(node.left, frame), self.eval(node.right, frame)) \
            if node.op != "=" else MEquation(self.eval(node.left, frame), self.eval(node.right, frame))

    def ev_TypeAnn(self, node, frame):
        v = self.eval(node.expr, frame)
        t = self._type_value(node.type, frame)
        return sp.true if self.type_check(v, t) else sp.false

    def _type_value(self, node, frame):
        self.quoting += 1
        try:
            return self.eval(node, frame)
        finally:
            self.quoting -= 1

    def ev_Member(self, node, frame):
        mod = self.eval(node.module, frame)
        return self.member(mod, node.name)

    def member(self, mod, name):
        if isinstance(mod, Module):
            if name in mod.exports:
                return mod.exports[name]
            if name in mod.export_names:
                return _not_implemented(f"{mod.name}:-{name}")
            raise MapleError(f"module does not export `{name}`")
        raise MapleError(f"`{lprint(mod)}` does not evaluate to a module")

    def ev_SeqOp(self, node, frame):
        if node.left is None:      # $a..b
            r = self.eval(node.right, frame)
            if not isinstance(r, MRange):
                raise MapleError("invalid input for $")
            return make_seq(_int_range(r))
        right = self.eval(node.right, frame)
        if isinstance(right, MEquation) and isinstance(node.left, N.Node):
            # f(i) $ i = 1..n : evaluate the body for each i
            var, rng = right.lhs, right.rhs
            vals = _int_range(rng) if isinstance(rng, MRange) else seq_items(rng)
            out = []
            for k in vals:
                out.append(self._with_temp(str(var), k, frame, lambda: self.eval(node.left, frame)))
            return make_seq(out)
        left = self.eval(node.left, frame)
        if isinstance(right, MRange):
            return make_seq(_int_range(right))
        n = right
        if not (isinstance(n, sp.Integer)):
            raise MapleError("invalid input for $: the repeat count must be an integer")
        return make_seq([left] * int(n))

    def _with_temp(self, name, value, frame, thunk):
        """Run thunk with `name` temporarily bound to value (seq/add/$ index variables)."""
        target = frame.vars if frame is not None and name in frame.vars else self.globals
        missing = object()
        old = target.get(name, missing)
        target[name] = value
        try:
            return thunk()
        finally:
            if old is missing:
                target.pop(name, None)
            else:
                target[name] = old

    def ev_Angle(self, node, frame):
        items = self.eval_args(node.items, frame)
        op = "<,>" if node.sep == "," else "<|>"
        fn = self.env.operators.get(op)
        if fn:
            return fn(self, items)
        return _angle_default(node.sep, items)

    def ev_ProcN(self, node, frame):
        _implicit_locals(self, node, frame)
        p = UserProc(node, frame)
        if self.pending_name:
            p.name = self.pending_name
        return p

    def ev_ModuleN(self, node, frame):
        f = Frame({p.name: sp.Dummy(p.name) for p in node.locals + node.exports}, frame)
        self.exec_block(node.body, f, 0)
        mod = Module(self.pending_name or "anonymous module",
                     {p.name: f.vars[p.name] for p in node.exports},
                     [p.name for p in node.exports])
        return mod

    def ev_UnOp(self, node, frame):
        v = self.eval(node.operand, frame)
        op = node.op
        if op == "-":
            return self.neg(v)
        if op == "not":
            t = self.try_truth(v)
            if t is None:
                return MLogic("not", [v])
            return sp.false if t else sp.true
        if op == "!":
            return self.call("factorial", v)
        if op.startswith("&"):
            return self.neutral(op, [v])
        raise MapleError(f"unknown operator {op}")

    def neg(self, v):
        if isinstance(v, sp.Basic):
            return -v
        if isinstance(v, (MList, MRelation, MMatrix, ExprSeq)):
            if isinstance(v, MMatrix) and "-" in self.env.operators:
                return self.binop("*", sp.Integer(-1), v)
            return v.map_leaves(self.neg)
        raise MapleError(f"invalid argument for unary minus: {lprint(v)}")

    def ev_BinOp(self, node, frame):
        op = node.op
        if op in ("and", "or", "xor", "implies"):
            return self.logic(op, node, frame)
        a = self.eval(node.left, frame)
        b = self.eval(node.right, frame)
        if op.startswith("&"):
            return self.neutral(op, [a, b])
        return self.binop(op, a, b)

    def logic(self, op, node, frame):
        a = self.eval(node.left, frame)
        ta = self.try_truth(a)
        if op == "and" and ta is False:
            return sp.false
        if op == "or" and ta is True:
            return sp.true
        if op == "implies" and ta is False:
            return sp.true
        b = self.eval(node.right, frame)
        tb = self.try_truth(b)
        if ta is not None and tb is not None:
            r = {"and": ta and tb, "or": ta or tb, "xor": ta != tb, "implies": (not ta) or tb}[op]
            return sp.true if r else sp.false
        if op == "and" and ta is True:
            return b
        if op == "or" and ta is False:
            return b
        if op == "and" and tb is True:
            return a
        if op == "or" and tb is False:
            return a
        return MLogic(op, [a, b])

    def neutral(self, op, args):
        args = [self.rtable_entries(a) for a in args]
        f = self.globals.get(op) or self.bound.get(op) or self.env.functions.get(op)
        if f is None and op in self.env.operators:
            return self.env.operators[op](self, *args)
        if f is not None:
            return self.apply(f, args)
        return self.unknown_call(op, args)

    # ------------------------------------------------------------ arithmetic
    def binop(self, op, a, b):
        sa, sb = isinstance(a, sp.Basic), isinstance(b, sp.Basic)
        if sa and sb and op in ("+", "-", "*", "/", "^"):
            try:
                if op == "+":
                    r = a + b
                elif op == "-":
                    r = a - b
                elif op == "*":
                    r = a * b
                elif op == "/":
                    if b.is_zero and not (b.is_Float):
                        raise MapleError("numeric exception: division by zero")
                    r = a / b
                else:
                    if b.is_negative and a.is_zero:
                        raise MapleError("numeric exception: division by zero")
                    r = a ** b
            except TypeError as e:
                raise MapleError(f"invalid arguments for {op}: {e}")
            if a.has(sp.Float) or b.has(sp.Float):
                r = _float_pi(r, self.digits)
            return float_zero(r, (a, b), self.digits)
        a, b = self.rtable_entries(a), self.rtable_entries(b)
        fn = self.env.operators.get(op)
        if fn is not None and (isinstance(a, MMatrix) or isinstance(b, MMatrix) or op == "."):
            r = fn(self, a, b)
            if r is not NotImplemented:
                return r
        return _generic_binop(self, op, a, b)

    # ------------------------------------------------------------ truth
    def try_truth(self, v):
        """True/False if v is decidable, else None (Maple evalb semantics, numerically lenient)."""
        if v is sp.true or v is True:
            return True
        if v is sp.false or v is False:
            return False
        if v is FAIL:
            return None
        if isinstance(v, MRelation):
            return self.compare(v)
        if isinstance(v, MLogic):
            ts = [self.try_truth(a) for a in v.args]
            if None in ts:
                return None
            return {"and": all(ts), "or": any(ts), "not": not ts[0],
                    "xor": ts[0] != ts[-1], "implies": (not ts[0]) or ts[-1]}[v.op]
        if isinstance(v, sp.Basic) and isinstance(v, sp.logic.boolalg.Boolean):
            r = v.simplify() if not isinstance(v, sp.Symbol) else v
            if r is sp.true:
                return True
            if r is sp.false:
                return False
        return None

    def truth(self, v) -> bool:
        t = self.try_truth(v)
        if t is None:
            raise MapleError(f"cannot determine if this expression is true or false: {lprint(v)}")
        return t

    def compare(self, r: MRelation):
        a, b = r.lhs, r.rhs
        if r.op in ("=", "<>"):
            eq = _structurally_equal(a, b)
            return eq if r.op == "=" else not eq
        if not (isinstance(a, sp.Basic) and isinstance(b, sp.Basic)):
            return None
        d = a - b
        if d.is_number:
            try:
                d = d.evalf(self.digits + 5) if not d.is_Number else d
                if d.is_real is False or d.has(sp.I):
                    return None
                return bool(d < 0) if r.op == "<" else bool(d <= 0)
            except TypeError:
                return None
        return None

    # ------------------------------------------------------------ calls
    def ev_Call(self, node, frame):
        fnode = node.func
        if self.quoting:
            name = fnode.name if isinstance(fnode, N.Name) else None
            args = self.eval_args(node.args, frame)
            if name is None:
                return MCall(self.eval(fnode, frame), args)
            return self.unknown_call(name, args)
        f = self.eval(fnode, frame)
        if isinstance(f, BuiltinProc) and not f.evaluate:
            return self.call_builtin(f, list(node.args), frame=frame)
        args = self.eval_args(node.args, frame)
        if isinstance(f, sp.Symbol) and not isinstance(f, sp.Dummy) and isinstance(fnode, N.Name):
            return self.unknown_call(fnode.name, args)
        return self.apply(f, args)

    def call(self, name: str, *args, **kw):
        """Call a Maple function by name (builtin API for libraries)."""
        f = self.lookup(name)
        if isinstance(f, BuiltinProc) and kw:
            return self.call_builtin(f, list(args), extra_kw=kw)
        return self.apply(f, list(args))

    def apply(self, f, args):
        args = list(ExprSeq(args).items)
        if isinstance(f, BuiltinProc):
            if not f.evaluate:
                return self.call_builtin(f, [_ValueNode(a) for a in args])
            return self.call_builtin(f, args)
        if isinstance(f, UserProc):
            return self.call_user(f, args)
        if isinstance(f, RememberProc):
            key = tuple(args)
            for k, v in f.table.items():
                if _structurally_equal(MList(k), MList(key)):
                    return v
            return self.unknown_call(f.name, args)
        if isinstance(f, AppliedProc):
            return f.fn(self, args)
        if isinstance(f, sp.Symbol) and not isinstance(f, sp.Dummy):
            return self.unknown_call(f.name, args)
        if isinstance(f, sp.Dummy):
            return self.unknown_call(f.name, args)
        if isinstance(f, MList):
            return MList(self.apply(x, args) for x in f.items)
        if isinstance(f, MEquation):
            return MEquation(self.apply(f.lhs, args), self.apply(f.rhs, args))
        if isinstance(f, AppliedUndef):      # q(t)(x) stays as it is in Maple
            return MCall(f, args)
        if isinstance(f, sp.Basic):
            if f.is_Number or f.is_NumberSymbol or f in (sp.I,):
                return f
            syms = [s for s in f.free_symbols if not isinstance(s, sp.Dummy)]
            return _fold_apply(self, f, {s: self.apply(self.lookup(s.name), args) for s in syms})
        if isinstance(f, Module) and "ModuleApply" in f.exports:
            return self.apply(f.exports["ModuleApply"], args)
        if isinstance(f, MString):
            return self.unknown_call(str(f), args)
        return MCall(f, args)

    def unknown_call(self, name: str, args):
        if all(isinstance(a, sp.Basic) and not isinstance(a, sp.logic.boolalg.BooleanAtom)
               for a in args):
            try:
                return sp.Function(name)(*args)
            except Exception:  # noqa: BLE001
                pass
        return MCall(sp.Symbol(name), args)

    def call_builtin(self, f: BuiltinProc, args, frame=None, index=None, extra_kw=None):
        if f.evaluate:
            pos, kw = split_options(f, args)
        else:
            pos, kw = list(args), {}
        if index is not None:
            kw["index"] = index
        if extra_kw:
            kw.update(extra_kw)
        check_arity(f, pos, kw)
        saved_frame = self.frame
        self.frame = frame
        try:
            r = f.fn(self, *pos, **kw)
        except MapleError as e:
            if e.where is None and not e.msg.startswith("invalid input") and \
                    not e.msg.startswith("numeric exception") and not getattr(e, "bare", False):
                e.where = f.name
            raise
        except (ReturnSignal, BreakSignal, NextSignal, QuitSignal):
            raise
        except RecursionError:
            raise MapleError("too many levels of recursion")
        except Exception as e:  # noqa: BLE001 - surface library failures as Maple errors
            raise MapleError(_py_error_text(e), f.name) from e
        finally:
            self.frame = saved_frame
        return NULL if r is None else r

    def call_user(self, p: UserProc, args):
        node = p.node
        if "remember" in _option_names(node):
            key = tuple(args)
            for k, v in p.remember.items():
                if _structurally_equal(MList(k), MList(key)):
                    return v
        frame = Frame({}, p.closure, p, node.globals)
        pname = p.name or "anonymous procedure"
        positional = [q for q in node.params if not q.keyword]
        keywords = {q.name: q for q in node.params if q.keyword}
        rest = []
        kwvals = {}
        for a in args:
            if keywords and isinstance(a, MEquation) and isinstance(a.lhs, sp.Symbol) \
                    and a.lhs.name in keywords:
                kwvals[a.lhs.name] = a.rhs
            else:
                rest.append(a)
        for i, q in enumerate(positional):
            if i < len(rest):
                v = rest[i]
                if q.type is not None and not self._param_type_ok(v, q.type, frame):
                    raise MapleError(
                        f"invalid input: {pname} expects its {ordinal(i + 1)} argument, {q.name}, "
                        f"to be of type {lprint(self._type_value(q.type, frame))}, but received "
                        f"{lprint(v)}")
                frame.vars[q.name] = v
            elif q.default is not None:
                frame.vars[q.name] = self.eval(q.default, frame)
            else:
                frame.vars[q.name] = _Missing(p, i + 1, q.name)
        for name, q in keywords.items():
            if name in kwvals:
                frame.vars[name] = kwvals[name]
            elif q.default is not None:
                frame.vars[name] = self.eval(q.default, frame)
            else:
                frame.vars[name] = sp.Dummy(name)
        frame.vars["args"] = ExprSeq(args)
        frame.vars["nargs"] = sp.Integer(len(args))
        frame.vars["_rest"] = ExprSeq(rest[len(positional):])
        frame.vars["procname"] = sp.Symbol(pname)
        for loc in node.locals + [N.Param(n) for n in getattr(node, "_implicit", ())]:
            frame.vars[loc.name] = sp.Dummy(loc.name)
        for loc in node.locals:
            if loc.default is not None:
                frame.vars[loc.name] = self.eval(loc.default, frame)
        self.call_depth += 1
        if self.call_depth > 400:
            self.call_depth = 0
            raise MapleError("too many levels of recursion")
        try:
            if node.arrow and len(node.body) == 1 and isinstance(node.body[0], N.ExprStmt):
                result = self.eval(node.body[0].expr, frame)
            else:
                result = self.exec_block(node.body, frame, 0)
        except ReturnSignal as r:
            result = r.value
        except MapleError as e:
            if e.where is None and not getattr(e, "bare", False):
                e.where = pname
            raise
        except RecursionError:
            raise MapleError("too many levels of recursion", pname)
        finally:
            self.call_depth -= 1
        if result is None:
            result = NULL
        if "remember" in _option_names(node):
            p.remember[tuple(args)] = result
        return result

    def _param_type_ok(self, v, tnode, frame) -> bool:
        try:
            return self.type_check(v, self._type_value(tnode, frame))
        except MapleError:
            return True

    def type_check(self, v, t) -> bool:
        """Maple type test; type implementations live in builtins (lib.type)."""
        if isinstance(t, MSet):
            return any(self.type_check(v, x) for x in t.items)
        if isinstance(t, MList):
            return isinstance(v, MList) and len(v.items) == len(t.items) and all(
                self.type_check(a, b) for a, b in zip(v.items, t.items))
        if isinstance(t, MCall):
            name, params = lprint(t.func), list(t.args)
        elif isinstance(t, AppliedUndef):
            name, params = type(t).__name__, list(t.args)
        elif isinstance(t, sp.Symbol):
            name, params = t.name, []
        elif isinstance(t, BuiltinProc):
            name, params = t.name, []
        elif isinstance(t, MString):
            name, params = str(t), []
        else:
            name, params = lprint(t), []
        fn = self.env.types.get(name)
        if fn is None:
            raise MapleError(f"type `{name}` does not exist")
        return bool(fn(self, v, *params))

    # ------------------------------------------------------------ indexing
    def ev_Index(self, node, frame):
        if isinstance(node.base, N.Name):
            key = f"{node.base.name}[{', '.join(_index_text(i) for i in node.indices)}]"
            key = key.replace(", ", ",")
            if self.package(key) is not None and key not in self.globals:
                return self.package(key)
        base = self.eval(node.base, frame)
        idx = self.eval_args(node.indices, frame)
        if self.quoting and isinstance(base, (sp.Symbol, sp.Indexed)):
            return _indexed_name(base, idx)
        name = node.base.name if isinstance(node.base, N.Name) else None
        return self.index_value(base, idx, name)

    def index_value(self, base, idx, name=None):
        if isinstance(base, BuiltinProc):
            if base.indexed:
                f = base
                return AppliedProc(lambda ctx, args: ctx.call_builtin(f, args, index=tuple(idx)),
                                   label=_indexed_name(sp.Symbol(base.name), idx))
            return _indexed_name(sp.Symbol(base.name), idx)
        if isinstance(base, Module):
            if len(idx) == 1 and isinstance(idx[0], sp.Symbol):
                return self.member(base, idx[0].name)
        if isinstance(base, (sp.Symbol, sp.Indexed)) and not isinstance(base, sp.Dummy):
            return _indexed_name(base, idx)
        if isinstance(base, sp.Dummy):
            return _indexed_name(base, idx)
        if isinstance(base, MTable):
            key = tuple(idx)
            if key in base.entries:
                return base.entries[key]
            return _indexed_name(sp.Symbol(name or "table"), idx)
        if isinstance(base, (MList, ExprSeq, MSet)):
            return _select(base.items, idx, MList if isinstance(base, MList) else make_seq)
        if isinstance(base, MString):
            if len(idx) == 1:
                r = idx[0]
                if isinstance(r, MRange):
                    lo, hi = int(r.lo), int(r.hi)
                    return MString(str(base)[lo - 1:hi if hi >= 0 else len(base) + hi + 1])
                k = int(r)
                return MString(base[k - 1] if k > 0 else base[k])
        if isinstance(base, MMatrix):
            fn = self.env.operators.get("index")
            if fn is not None:
                r = fn(self, base, idx)
                if r is not NotImplemented:
                    return self.full_eval(self.rtable_entries(r))
            return self.full_eval(self.rtable_entries(_rtable_index(base, idx)))
        if isinstance(base, (MRelation, MRange, sp.Basic)):
            return MIndexExpr(base, idx)    # Maple leaves e.g. (a = b)[2] unevaluated
        raise MapleError("invalid subscript selector")

    # ------------------------------------------------------------ statements
    def exec_block(self, stmts, frame, disp: int):
        last = NULL
        for s in stmts:
            last = self.exec_stmt(s, frame, disp)
        return last

    def exec_stmt(self, s, frame, disp: int):
        m = getattr(self, "st_" + type(s).__name__)
        return m(s, frame, disp)

    def st_Empty(self, s, frame, disp):
        return NULL

    def st_ExprStmt(self, s, frame, disp):
        e = s.expr
        if isinstance(e, N.Name) and e.name in ("restart",) and frame is None:
            self.restart()
            return NULL
        v = self.eval(e, frame)
        if disp > 0:
            self.display(v, e)
        if frame is None:
            self.push_ditto(v)
        return v

    def push_ditto(self, v):
        if not (isinstance(v, ExprSeq) and not v.items):
            self.ditto = [v, self.ditto[0], self.ditto[1]]

    def display(self, v, node=None):
        if isinstance(v, ExprSeq) and not v.items:
            return
        if isinstance(v, PlotValue):
            self.emit({"kind": "plot", "spec": v.spec})
            return
        if isinstance(node, N.Name) and isinstance(v, (Procedure, MTable, Module)):
            text = name_str(node.name)
            self.emit({"kind": "math", "text": text, "latex": latex(sp.Symbol(node.name))})
            return
        self.emit({"kind": "math", "text": lprint(v), "latex": self.to_latex(v)})

    def restart(self):
        self.reset()

    def st_Assign(self, s, frame, disp):
        single_name = len(s.targets) == 1 and isinstance(s.targets[0], N.Name)
        self.pending_name = s.targets[0].name if single_name else None
        try:
            value = self.eval(s.values, frame)
        finally:
            self.pending_name = None
        if len(s.targets) == 1:
            values = [value]
        else:
            values = list(seq_items(value))
            if len(values) != len(s.targets):
                raise MapleError("ambiguous multiple assignment")
        labels = []
        for t, v in zip(s.targets, values):
            labels.append(self.assign(t, v, frame))
        if disp > 0:
            if isinstance(value, PlotValue):
                self.emit({"kind": "plot", "spec": value.spec})
            else:
                unassign = single_name and isinstance(s.values, N.Uneval) and \
                    isinstance(s.values.expr, N.Name) and s.values.expr.name == s.targets[0].name
                rhs_text = f"'{labels[0]}'" if unassign else lprint(value)
                rhs_latex = rhs_text if unassign else self.to_latex(value)
                lhs_latex = ", ".join(latex(_label_value(t, frame, self)) for t in s.targets)
                self.emit({"kind": "math", "text": f"{', '.join(labels)} := {rhs_text}",
                           "latex": f"{lhs_latex} := {rhs_latex}"})
        if frame is None:
            self.push_ditto(value)
        return value

    def assign(self, target, value, frame) -> str:
        """Assign value to an assignment target node; returns the display label."""
        if isinstance(target, N.TypeAnn):
            target = target.expr
        if isinstance(target, N.Name):
            self.assign_name(target.name, value, frame)
            return name_str(target.name)
        if isinstance(target, N.Uneval):
            return self.assign(target.expr, value, frame)
        if isinstance(target, N.Index):
            idx = self.eval_args(target.indices, frame)
            self.assign_index(target.base, idx, value, frame)
            return f"{_label(target.base, frame, self)}[{','.join(lprint(i) for i in idx)}]"
        if isinstance(target, N.Call) and isinstance(target.func, N.Name):
            args = tuple(self.eval_args(target.args, frame))
            self.assign_call(target.func.name, args, value, frame)
            return f"{name_str(target.func.name)}({','.join(lprint(a) for a in args)})"
        raise MapleError(f"invalid left hand side in assignment")

    def assign_name(self, name: str, value, frame=None):
        f = frame
        while f is not None:
            if name in f.vars:
                f.vars[name] = value
                return
            if name in f.globals_decl:
                break
            f = f.parent
        if name == "Digits":
            if not (isinstance(value, sp.Integer) and value > 0):
                raise MapleError("Digits must be a positive integer")
            self.digits = int(value)
            return
        if name in PROTECTED_CONSTANTS or name in self.env.protected or name == "lasterror":
            raise MapleError(f"attempting to assign to `{name}` which is protected.  "
                             f"Try declaring `local {name}`; see ?protect for details.")
        if isinstance(value, sp.Symbol) and not isinstance(value, sp.Dummy) and value.name == name:
            self.globals.pop(name, None)
            return
        if isinstance(value, sp.Basic) and name not in self.globals and not value.is_Atom:
            if any(s.name == name for s in value.free_symbols if not isinstance(s, sp.Dummy)):
                raise MapleError("recursive assignment")
        if isinstance(value, (UserProc, Module)) and value.name in (None, "anonymous module"):
            value.name = name
        self.globals[name] = value

    def assign_index(self, base_node, idx, value, frame):
        if isinstance(base_node, N.Name):
            name = base_node.name
            cur = self._raw_value(name, frame)
            if cur is None:
                self.assign_name(name, MTable({tuple(idx): value}), frame)
                return
            if isinstance(cur, MTable):
                cur.entries[tuple(idx)] = value
                return
            if isinstance(cur, MList):
                items = list(cur.items)
                k = int(idx[0])
                items[k - 1 if k > 0 else k] = value
                self.assign_name(name, MList(items), frame)
                return
            if isinstance(cur, MMatrix):
                _rtable_set(cur, idx, value)
                return
            raise MapleError(f"cannot assign to an entry of {lprint(cur)}")
        container = self.eval(base_node, frame)
        if isinstance(container, MTable):
            container.entries[tuple(idx)] = value
        elif isinstance(container, MMatrix):
            _rtable_set(container, idx, value)
        else:
            raise MapleError("invalid left hand side in assignment")

    def _raw_value(self, name, frame):
        f = frame
        while f is not None:
            if name in f.vars:
                v = f.vars[name]
                return None if isinstance(v, sp.Dummy) else v
            f = f.parent
        return self.globals.get(name)

    def assign_call(self, name, args, value, frame):
        cur = self._raw_value(name, frame)
        if isinstance(cur, UserProc):
            cur.remember[args] = value
            return
        if not isinstance(cur, RememberProc):
            cur = RememberProc(name)
            self.assign_name(name, cur, frame)
        cur.table[args] = value

    def st_If(self, s, frame, disp):
        for cond, body in s.branches:
            if self.truth(self.eval(cond, frame)):
                return self.exec_block(body, frame, disp - 1)
        if s.orelse is not None:
            return self.exec_block(s.orelse, frame, disp - 1)
        return NULL

    def st_For(self, s, frame, disp):
        inner = disp - 1
        var = s.var
        if isinstance(var, tuple):
            idx_var, var = var
        else:
            idx_var = None
        if s.iterable is not None:
            coll = self.eval(s.iterable, frame)
            items = _iter_items(coll)
            for k, x in enumerate(items, 1):
                if idx_var:
                    self.assign_name(idx_var, sp.Integer(k), frame)
                if var:
                    self.assign_name(var, x, frame)
                if s.cond is not None and not self.truth(self.eval(s.cond, frame)):
                    break
                if self._loop_body(s.body, frame, inner):
                    break
            return NULL
        start = self.eval(s.start, frame) if s.start is not None else sp.Integer(1)
        step = self.eval(s.step, frame) if s.step is not None else sp.Integer(1)
        stop = self.eval(s.stop, frame) if s.stop is not None else None
        counting = var is not None or s.stop is not None
        for v, nm in ((start, "initial"), (step, "increment"), (stop, "final")):
            if v is not None and counting and not (isinstance(v, sp.Basic) and v.is_number):
                raise MapleError(f"{nm} value in for loop must be numeric or character")
        i = start
        while True:
            if counting and stop is not None:
                if (step >= 0 and i > stop) or (step < 0 and i < stop):
                    break
            if var:
                self.assign_name(var, i, frame)
            if s.cond is not None and not self.truth(self.eval(s.cond, frame)):
                break
            if self._loop_body(s.body, frame, inner):
                break
            i = i + step
        if var and counting:
            self.assign_name(var, i, frame)
        return NULL

    def _loop_body(self, body, frame, disp) -> bool:
        """Run one iteration; True means break."""
        try:
            self.exec_block(body, frame, disp)
        except BreakSignal:
            return True
        except NextSignal:
            pass
        return False

    def st_Break(self, s, frame, disp):
        raise BreakSignal()

    def st_Next(self, s, frame, disp):
        raise NextSignal()

    def st_Return(self, s, frame, disp):
        v = NULL if s.value is None else self.eval(s.value, frame)
        if frame is None:
            return v
        raise ReturnSignal(v)

    def st_ErrorStmt(self, s, frame, disp):
        args = self.eval_args(s.args, frame)
        if not args:
            raise MapleError(self.lasterror if isinstance(self.lasterror, str) else "")
        msg = format_error(args)
        where = None
        f = frame
        while f is not None and f.proc is None:
            f = f.parent
        if f is not None:
            where = f.proc.name or "anonymous procedure"
        err = MapleError(msg, where)
        err.value = args
        err.bare = where is None
        raise err

    def st_Try(self, s, frame, disp):
        inner = disp - 1
        try:
            return self.exec_block(s.body, frame, inner)
        except MapleError as e:
            for pats, body in s.catches:
                pv = [self.eval(p, frame) for p in pats]
                if not pv or any(e.msg.startswith(str(p)) for p in pv):
                    self.lasterror = MString(e.msg)
                    return self.exec_block(body, frame, inner)
            raise
        finally:
            if s.final is not None:
                self.exec_block(s.final, frame, inner)

    def st_Use(self, s, frame, disp):
        saved = dict(self.bound)
        try:
            for p in s.packages:
                mod = self.eval(p, frame)
                if isinstance(mod, Module):
                    self.bound.update(mod.exports)
            return self.exec_block(s.body, frame, disp - 1)
        finally:
            self.bound = saved

    def st_Quit(self, s, frame, disp):
        raise QuitSignal()

    def st_Read(self, s, frame, disp):
        raise MapleError("read is not supported in SymFlex")


# ---------------------------------------------------------------- helpers
class _ValueNode(N.Node):
    """Wraps an already-evaluated value so it can be passed where an AST node is expected."""

    def __init__(self, value):
        self.value = value


def _ev_value_node(self, node, frame):
    return node.value


Evaluator.ev__ValueNode = _ev_value_node


def format_error(args) -> str:
    if isinstance(args[0], MString):
        tmpl, rest = str(args[0]), args[1:]
        out, i = [], 0
        while i < len(tmpl):
            c = tmpl[i]
            if c == "%" and i + 1 < len(tmpl):
                j = i + 1
                if tmpl[j] == "-":
                    j += 1
                k = j
                while k < len(tmpl) and tmpl[k].isdigit():
                    k += 1
                if k > j:
                    n = int(tmpl[j:k])
                    if n == 0:
                        out.append(", ".join(_err_arg(a) for a in rest))
                    elif n <= len(rest):
                        a = rest[n - 1]
                        out.append(ordinal(int(a)) if tmpl[i + 1] == "-" else _err_arg(a))
                    i = k
                    continue
            out.append(c)
            i += 1
        return "".join(out)
    return ", ".join(_err_arg(a) for a in args)


def _err_arg(a) -> str:
    return str(a) if isinstance(a, MString) else lprint(a)


def _py_error_text(e: Exception) -> str:
    s = (str(e).strip() or type(e).__name__).splitlines()[0]
    return s if len(s) <= 200 else s[:197] + "..."


def _option_names(node) -> set:
    out = set()
    for o in node.options:
        if isinstance(o, N.Name):
            out.add(o.name)
    return out


def _implicit_locals(ev, node: N.ProcN, frame):
    if hasattr(node, "_implicit"):
        return
    declared = {p.name for p in node.params} | {p.name for p in node.locals} | set(node.globals)
    found: list[str] = []

    def outer_has(name):
        f = frame
        while f is not None:
            if name in f.vars:
                return True
            f = f.parent
        return False

    def visit(stmts):
        for s in stmts:
            if isinstance(s, N.Assign):
                for t in s.targets:
                    if isinstance(t, N.Name):
                        found.append(t.name)
            elif isinstance(s, N.For):
                if isinstance(s.var, tuple):
                    found.extend(s.var)
                elif s.var:
                    found.append(s.var)
                visit(s.body)
            elif isinstance(s, N.If):
                for _, b in s.branches:
                    visit(b)
                if s.orelse:
                    visit(s.orelse)
            elif isinstance(s, N.Try):
                visit(s.body)
                for _, b in s.catches:
                    visit(b)
                if s.final:
                    visit(s.final)
            elif isinstance(s, N.Use):
                visit(s.body)

    visit(node.body)
    implicit = []
    for n in found:
        if n not in declared and n not in implicit and not outer_has(n) and n != "Digits":
            implicit.append(n)
    node._implicit = tuple(implicit)
    for n in implicit:
        where = ev.pending_name or "anonymous procedure"
        ev.warn(f"(in {where}) `{n}` is implicitly declared local")


def _structurally_equal(a, b) -> bool:
    if isinstance(a, sp.Basic) and isinstance(b, sp.Basic):
        if a == b:
            return True
        try:
            d = sp.expand(a - b)
            return d == 0
        except Exception:  # noqa: BLE001
            return False
    try:
        return a == b
    except Exception:  # noqa: BLE001
        return False


def _int_range(r: MRange):
    lo, hi = r.lo, r.hi
    if not (isinstance(lo, sp.Basic) and isinstance(hi, sp.Basic) and lo.is_number and hi.is_number):
        raise MapleError("unable to execute seq: range bounds must be numeric")
    out = []
    k = lo
    while k <= hi:
        out.append(k)
        k = k + 1
    return out


def _iter_items(coll):
    if isinstance(coll, (MList, MSet, ExprSeq)):
        return list(coll.items)
    if isinstance(coll, MVector):
        return list(coll.m)
    if isinstance(coll, MMatrix):
        return list(coll.m.T)
    if isinstance(coll, MString):
        return [MString(c) for c in coll]
    if isinstance(coll, MRange):
        return _int_range(coll)
    if isinstance(coll, MTable):
        return list(coll.entries.values())
    if isinstance(coll, sp.Basic) and (coll.is_Add or coll.is_Mul or coll.is_Pow):
        return list(coll.args)
    return [coll]


def _select(items, idx, wrap):
    if len(idx) != 1:
        if len(idx) == 0:
            return wrap(items)
        first = _select(items, idx[:1], wrap)
        if isinstance(first, MList):
            return _select(first.items, idx[1:], MList)
        raise MapleError("invalid subscript selector")
    k = idx[0]
    n = len(items)
    if isinstance(k, MRange):
        lo = int(k.lo) if k.lo is not None else 1
        hi = int(k.hi)
        lo = lo if lo > 0 else n + lo + 1
        hi = hi if hi > 0 else n + hi + 1
        return wrap(items[lo - 1:hi])
    if not (isinstance(k, sp.Integer)):
        raise MapleError(f"invalid subscript selector")
    k = int(k)
    if k == 0 or abs(k) > n:
        raise MapleError("invalid subscript selector")
    return items[k - 1] if k > 0 else items[k]


def _rtable_index(base: MMatrix, idx):
    def conv(k, n):
        if isinstance(k, MRange):
            lo, hi = int(k.lo), int(k.hi)
            return slice(lo - 1, hi)
        k = int(k)
        if k == 0 or abs(k) > n:
            raise MapleError("index out of range")
        return k - 1 if k > 0 else n + k
    if isinstance(base, MVector):
        if len(idx) != 1:
            raise MapleError("invalid subscript selector")
        s = conv(idx[0], len(base.m))
        if isinstance(s, slice):
            return MVector(list(base.m)[s], base.orient)
        return base.m[s]
    r, c = base.m.shape
    if len(idx) == 1:
        s = conv(idx[0], r)
        if isinstance(s, slice):
            return MMatrix(base.m[s, :])
        return MVector(list(base.m.row(s)), "row")
    i, j = conv(idx[0], r), conv(idx[1], c)
    sub = base.m[i, j]
    if isinstance(i, slice) and isinstance(j, slice):
        return MMatrix(sub)
    if isinstance(i, slice):
        return MVector(list(sub), "column")
    if isinstance(j, slice):
        return MVector(list(sub), "row")
    return sub


def _rtable_set(m: MMatrix, idx, value):
    if isinstance(m, MVector):
        k = int(idx[0])
        m.m[k - 1 if k > 0 else len(m.m) + k] = value
    else:
        m.m[int(idx[0]) - 1, int(idx[1]) - 1] = value


def _indexed_name(base, idx):
    if all(isinstance(i, sp.Basic) and not isinstance(i, sp.logic.boolalg.BooleanAtom)
           for i in idx) and idx:
        label = base.base.label if isinstance(base, sp.Indexed) else base
        if isinstance(base, sp.Indexed):
            # a[i][j] -> a[i, j] is not Maple semantics but is the closest name-like value
            return sp.Indexed(sp.IndexedBase(label), *base.indices, *idx)
        return sp.Indexed(sp.IndexedBase(label), *idx)
    return sp.Symbol(f"{lprint(base)}[{','.join(lprint(i) for i in idx)}]")


def _index_text(node) -> str:
    from .printer import unparse
    return unparse(node)


def _label(node, frame, ev) -> str:
    if isinstance(node, N.Name):
        return name_str(node.name)
    if isinstance(node, N.Index):
        idx = ev.eval_args(node.indices, frame)
        return f"{_label(node.base, frame, ev)}[{','.join(lprint(i) for i in idx)}]"
    from .printer import unparse
    return unparse(node)


def _label_value(node, frame, ev):
    if isinstance(node, N.Name):
        return sp.Symbol(node.name)
    if isinstance(node, N.Index) and isinstance(node.base, N.Name):
        return _indexed_name(sp.Symbol(node.base.name), ev.eval_args(node.indices, frame))
    return sp.Symbol(_label(node, frame, ev))


def _not_implemented(qual: str):
    def fn(ctx, *args, **kw):
        raise MapleError(f"{qual} is not implemented in SymFlex")
    return BuiltinProc(name=qual, fn=fn, doc="not implemented")


def _angle_default(sep, items):
    if sep == ",":
        if items and all(isinstance(x, MVector) and x.orient == "column" for x in items):
            return MVector([e for x in items for e in x.m], "column")
        if items and all(isinstance(x, MMatrix) for x in items):
            return MMatrix(sp.Matrix.vstack(*[x.m for x in items]))
        return MVector(items, "column")
    if items and all(isinstance(x, MMatrix) for x in items):
        if all(isinstance(x, MVector) and x.orient == "row" for x in items):
            return MVector([e for x in items for e in x.m], "row")
        return MMatrix(sp.Matrix.hstack(*[x.m for x in items]))
    return MVector(items, "row")


def _fold_apply(ev, f, mapping):
    """Rebuild f with symbols replaced by (possibly non-algebraic) values."""
    if all(isinstance(v, sp.Basic) for v in mapping.values()):
        return f.xreplace(mapping)
    if isinstance(f, sp.Symbol):
        return mapping.get(f, f)
    if isinstance(f, (sp.Add, sp.Mul, sp.Pow)):
        op = "+" if isinstance(f, sp.Add) else "*" if isinstance(f, sp.Mul) else "^"
        return _fold(ev, op, [_fold_apply(ev, a, mapping) for a in f.args])
    return f


def _fold(ev, op, args):
    acc = args[0]
    for a in args[1:]:
        acc = ev.binop(op, acc, a)
    return acc


def _generic_binop(ev, op, a, b):
    """Operators on non-SymPy operands: lists, sets, equations, ranges, strings."""
    # last-name evaluation: a named procedure takes part in arithmetic as its name
    if op in ("+", "-", "*", "/", "^"):
        a2, b2 = _lne(a), _lne(b)
        if (a2 is not a or b2 is not b) and isinstance(a2, sp.Basic) and isinstance(b2, sp.Basic):
            return ev.binop(op, a2, b2)
    if op in ("+", "-", "*", "/", "^"):
        if isinstance(a, MRelation) or isinstance(b, MRelation):
            if isinstance(a, MRelation) and isinstance(b, MRelation):
                return MRelation._rebuild(a.op, ev.binop(op, a.lhs, b.lhs), ev.binop(op, a.rhs, b.rhs))
            if isinstance(a, MRelation):
                return MRelation._rebuild(a.op, ev.binop(op, a.lhs, b), ev.binop(op, a.rhs, b))
            return MRelation._rebuild(b.op, ev.binop(op, a, b.lhs), ev.binop(op, a, b.rhs))
        if isinstance(a, MList) and isinstance(b, MList):
            if op in ("+", "-") and len(a.items) == len(b.items):
                return MList(ev.binop(op, x, y) for x, y in zip(a.items, b.items))
            if op in ("+", "-"):
                raise MapleError("adding lists of different length")
            raise MapleError("invalid list operation")
        if isinstance(a, MList) and isinstance(b, sp.Basic):
            return MList(ev.binop(op, x, b) for x in a.items)
        if isinstance(b, MList) and isinstance(a, sp.Basic):
            return MList(ev.binop(op, a, x) for x in b.items)
        if isinstance(a, MMatrix) or isinstance(b, MMatrix):
            return _matrix_binop(op, a, b)
        if isinstance(a, sp.Basic) and isinstance(b, sp.Basic):
            return ev.binop(op, a, b)
        if isinstance(a, (Procedure,)) or isinstance(b, Procedure):
            return _proc_arith(ev, op, a, b)
    if op == ".":
        if isinstance(a, sp.Basic) and isinstance(b, sp.Basic):
            return a * b
        if isinstance(a, MMatrix) or isinstance(b, MMatrix):
            return _matrix_binop(".", a, b)
    if op == "mod":
        return ev.call("mod", a, b)
    if op in ("union", "minus", "intersect"):
        if isinstance(a, MSet) and isinstance(b, MSet):
            if op == "union":
                return MSet(a.items + b.items)
            if op == "minus":
                return MSet(x for x in a.items if x not in b.items)
            return MSet(x for x in a.items if x in b.items)
        return ev.unknown_call(op, [a, b])
    if op == "subset":
        if isinstance(a, MSet) and isinstance(b, MSet):
            return sp.true if all(x in b.items for x in a.items) else sp.false
    if op == "in":
        if isinstance(b, (MSet, MList)):
            return sp.true if a in b.items else sp.false
        return MRelation("in", a, b)
    if op == "@":
        return AppliedProc(lambda ctx, args: ctx.apply(a, [ctx.apply(b, args)]),
                           label=f"{lprint(a)}@{lprint(b)}")
    if op == "@@":
        n = int(b)

        def rep(ctx, args):
            v = make_seq(args)
            for _ in range(n):
                v = ctx.apply(a, list(seq_items(v)))
            return v
        return AppliedProc(rep, label=f"({lprint(a)}@@{n})")
    if op == "||":
        return sp.Symbol(_cat_text(a) + _cat_text(b))
    raise MapleError(f"invalid arguments for `{op}`: {lprint(a)}, {lprint(b)}")


def _lne(v):
    if isinstance(v, (UserProc, RememberProc)) and v.name:
        return sp.Symbol(v.name)
    return v


def _cat_text(v):
    return str(v) if isinstance(v, MString) else lprint(v).strip("`")


def _proc_arith(ev, op, a, b):
    """(f + g)(x) = f(x) + g(x), the operator algebra Maple applies to procedures."""
    def fn(ctx, args):
        va = ctx.apply(a, args) if isinstance(a, Procedure) else a
        vb = ctx.apply(b, args) if isinstance(b, Procedure) else b
        return ctx.binop(op, va, vb)
    return AppliedProc(fn, label=f"{lprint(a)}{op}{lprint(b)}")


def _matrix_binop(op, a, b):
    def mat(x):
        return x.m if isinstance(x, MMatrix) else x

    def wrap(m, like):
        if isinstance(like, MVector) and (m.shape[0] == 1 or m.shape[1] == 1):
            return MVector(list(m), "row" if m.shape[0] == 1 else "column")
        if m.shape == (1, 1) and not isinstance(like, MMatrix):
            return m[0, 0]
        return MMatrix(m)
    like = a if isinstance(a, MMatrix) else b
    if op == "+":
        if isinstance(a, MMatrix) and isinstance(b, MMatrix):
            if a.m.shape != b.m.shape:
                raise MapleError("invalid input: dimensions of operands do not match")
            return wrap(a.m + b.m, like)
        s, m = (b, a) if isinstance(a, MMatrix) else (a, b)
        if isinstance(m, MVector):
            raise MapleError("invalid arguments for +: a Vector and a scalar")
        return MMatrix(m.m + s * sp.eye(*m.m.shape))
    if op == "-":
        return _matrix_binop("+", a, _matrix_binop("*", sp.Integer(-1), b) if isinstance(b, MMatrix)
                             else -b)
    if op == "*":
        if isinstance(a, MMatrix) and isinstance(b, MMatrix):
            return _matrix_binop(".", a, b)
        s, m = (b, a) if isinstance(a, MMatrix) else (a, b)
        return wrap(m.m * s, like) if not isinstance(m, MVector) else MVector(
            [s * x for x in m.m], m.orient)
    if op == "/":
        if isinstance(b, MMatrix):
            raise MapleError("invalid arguments for /")
        return _matrix_binop("*", sp.Integer(1) / b, a)
    if op == ".":
        if isinstance(a, MVector) and isinstance(b, MVector):
            if len(a.m) != len(b.m):
                raise MapleError("invalid input: vector dimensions do not match")
            if a.orient == "column" and b.orient == "row":
                return MMatrix(a.m * b.m)
            return sp.Add(*[x * y for x, y in zip(a.m, b.m)])
        if isinstance(a, MMatrix) and isinstance(b, MMatrix):
            ma, mb = mat(a), mat(b)
            if isinstance(b, MVector) and b.orient == "column":
                return MVector(list(ma * mb), "column")
            if isinstance(a, MVector) and a.orient == "row":
                return MVector(list(ma * mb), "row")
            return MMatrix(ma * mb)
        return _matrix_binop("*", a, b)
    if op == "^":
        if isinstance(a, MMatrix) and not isinstance(a, MVector):
            return MMatrix(a.m ** b)
    raise MapleError(f"invalid arguments for {op}")
