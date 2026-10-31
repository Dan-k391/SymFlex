"""Semantic comparison of Maple outputs: golden cmaple text vs the SymFlex engine.

compare_statement(golden_outputs, our_outputs) -> {'verdict': 'pass'|'fail', 'subtype', 'reason', 'notes'}
compare_math(golden_text, our_text) / compare_print(...) / compare_plot(golden_plot, our_spec)
    -> None when equal, else a Diff(subtype, reason) instance.

Math texts are parsed with symflex_maple.parser and compared structurally (assignments, sets in any
order, lists/sequences in order, relations by sides, Vector/Matrix as element arrays, piecewise,
calls by name + args); algebraic leaves are converted to SymPy by a dedicated converter (no engine
state involved) and compared numerically: numbers to 1e-6 relative (1e-9 absolute), expressions at
random points. A numeric match with floats on one side only is the 'float-vs-exact' failure.
"""
from __future__ import annotations

import bisect
import difflib
import itertools
import math
import random
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import sympy as sp

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "py"))
from symflex_maple import nodes as N  # noqa: E402
from symflex_maple.parser import parse  # noqa: E402
from symflex_maple.printer import unparse  # noqa: E402

REL_TOL, ABS_TOL = 1e-6, 1e-9
PLOT_TOL = 0.01
OUTLIERS = 0.05


class Diff(Exception):
    def __init__(self, subtype: str, reason: str):
        super().__init__(f"[{subtype}] {reason}")
        self.subtype, self.reason = subtype, reason


class NotAlgebraic(Exception):
    pass


def _snip(x, n=100) -> str:
    s = x if isinstance(x, str) else unparse(x) if isinstance(x, N.Node) else str(x)
    return s if len(s) <= n else s[:n - 3] + "..."


_scale = 0.0   # magnitude of the enclosing Vector/Matrix: round-off in a ~0 entry is relative to it


def close(a: complex, b: complex) -> bool:
    return abs(a - b) <= REL_TOL * max(abs(a), abs(b), _scale) + ABS_TOL


# ---------------------------------------------------------------- AST -> SymPy
_CONST = {"Pi": sp.pi, "I": sp.I, "infinity": sp.oo}
_FUNCS = {
    "sin": sp.sin, "cos": sp.cos, "tan": sp.tan, "sec": sp.sec, "csc": sp.csc, "cot": sp.cot,
    "sinh": sp.sinh, "cosh": sp.cosh, "tanh": sp.tanh, "sech": sp.sech, "csch": sp.csch,
    "coth": sp.coth, "arcsin": sp.asin, "arccos": sp.acos, "arcsinh": sp.asinh,
    "arccosh": sp.acosh, "arctanh": sp.atanh, "arccot": sp.acot, "arcsec": sp.asec,
    "arccsc": sp.acsc, "exp": sp.exp, "ln": sp.log, "log": sp.log, "sqrt": sp.sqrt,
    "abs": sp.Abs, "signum": sp.sign, "Heaviside": sp.Heaviside, "Dirac": sp.DiracDelta,
    "floor": sp.floor, "ceil": sp.ceiling, "max": sp.Max, "min": sp.Min, "erf": sp.erf,
    "GAMMA": sp.gamma, "factorial": sp.factorial, "binomial": sp.binomial, "Re": sp.re,
    "Im": sp.im, "conjugate": sp.conjugate, "argument": sp.arg, "log10": lambda x: sp.log(x, 10),
    "arctan": lambda y, x=None: sp.atan(y) if x is None else sp.atan2(y, x),
}
_CONST_NAME = re.compile(r"^(?:_C|c__)(\d+)$")


def canon_name(name: str) -> str:
    """Maple's dsolve constants c__1 / _C1 compare equal; assumption tildes are dropped."""
    name = name.rstrip("~")
    m = _CONST_NAME.match(name)
    return f"_C{m.group(1)}" if m else name


def to_sympy(node):
    """Convert an algebraic AST node to SymPy; raises NotAlgebraic for anything else."""
    t = to_sympy
    if isinstance(node, N.Num):
        return sp.Integer(node.text)
    if isinstance(node, N.FloatLit):
        digits = len(re.sub(r"[^0-9]", "", node.text.split("e")[0].split("E")[0]))
        return sp.Float(node.text, max(15, digits))
    if isinstance(node, N.Name):
        return _CONST.get(node.name) or sp.Symbol(canon_name(node.name))
    if isinstance(node, N.Uneval):
        return t(node.expr)
    if isinstance(node, N.UnOp) and node.op in "+-":
        return -t(node.operand) if node.op == "-" else t(node.operand)
    if isinstance(node, N.BinOp):
        a, b = t(node.left), t(node.right)
        match node.op:
            case "+": return a + b
            case "-": return a - b
            case "*" | ".": return a * b
            case "/": return a / b
            case "^": return a ** b
            case "mod": return sp.Mod(a, b)
        raise NotAlgebraic(node.op)
    if isinstance(node, (N.Index, N.Member)):
        return sp.Symbol(canon_name(unparse(node)))
    if isinstance(node, N.Call):
        return _call_to_sympy(node)
    raise NotAlgebraic(type(node).__name__)


def _call_to_sympy(node: N.Call):
    name = node.func.name if isinstance(node.func, N.Name) else None
    args = node.args
    if name == "diff" and len(args) >= 2:
        vars_ = []
        for a in args[1:]:
            if isinstance(a, N.SeqOp) and a.left is not None:
                vars_.append((to_sympy(a.left), int(to_sympy(a.right))))
            else:
                vars_.append(to_sympy(a))
        return sp.Derivative(to_sympy(args[0]), *vars_)
    if name in ("int", "Int", "sum", "Sum") and len(args) == 2:
        cls = sp.Integral if name.lower() == "int" else sp.Sum
        v = args[1]
        if isinstance(v, N.Rel) and v.op == "=" and isinstance(v.right, N.Range):
            return cls(to_sympy(args[0]), (to_sympy(v.left), to_sympy(v.right.lo), to_sympy(v.right.hi)))
        return cls(to_sympy(args[0]), to_sympy(v))
    if isinstance(node.func, N.Call):
        d = _d_operator(node.func, args)
        if d is not None:
            return d
    if name in ("PIECEWISE", "piecewise"):
        return _piecewise(_canon(node).args)
    conv = [to_sympy(a) for a in args]
    if name in _FUNCS:
        return _FUNCS[name](*conv)
    return sp.Function(canon_name(unparse(node.func)))(*conv)


_REL = {"<": sp.Lt, "<=": sp.Le, "=": sp.Eq, "<>": sp.Ne}


def _condition(node):
    if isinstance(node, N.Name) and node.name == "otherwise":
        return sp.true
    node = _canon(node)
    if isinstance(node, N.Rel) and node.op in _REL:
        return _REL[node.op](to_sympy(node.left), to_sympy(node.right))
    raise NotAlgebraic("condition")


def _piecewise(pieces):
    """PIECEWISE([v1, c1], [v2, c2], ...) -> sympy Piecewise."""
    if not all(isinstance(p, N.ListN) and len(p.items) == 2 for p in pieces):
        raise NotAlgebraic("PIECEWISE")
    return sp.Piecewise(*[(to_sympy(v), _condition(c)) for v, c in (p.items for p in pieces)])


def _d_operator(dcall: N.Call, args):
    """D(f)(x) / D[1, 2](g)(x, y) -> the same Derivative (or Subs at a point) that diff gives."""
    d, fs = dcall.func, dcall.args
    if isinstance(d, N.Name) and d.name == "D":
        idx = [1]
    elif isinstance(d, N.Index) and getattr(d.base, "name", None) == "D" and all(_int(i) for i in d.indices):
        idx = [_int(i) for i in d.indices]
    else:
        return None
    if len(fs) != 1 or not isinstance(fs[0], N.Name) or max(idx) > len(args):
        return None
    xs = [sp.Symbol(f"_x{i + 1}") for i in range(len(args))]
    deriv = sp.Derivative(sp.Function(fs[0].name)(*xs), *[xs[i - 1] for i in idx])
    return sp.Subs(deriv, xs, [to_sympy(a) for a in args]).doit()


def has_float(e) -> bool:
    return bool(e.atoms(sp.Float))


def _opaque_map(*exprs):
    """Replace unknown functions, derivatives, integrals ... by symbols so they can be sampled."""
    rep = {}
    for e in exprs:
        for a in e.atoms(sp.Derivative, sp.Subs, sp.Integral, sp.Sum):
            rep.setdefault(a, sp.Dummy(str(a)))
    out = [e.xreplace(rep) for e in exprs]
    rep2 = {}
    for e in out:
        for a in e.atoms(sp.core.function.AppliedUndef):
            rep2.setdefault(a, sp.Dummy(str(a)))
    return [e.xreplace(rep2) for e in out]


def _value(e, pt):
    try:
        v = complex(e.xreplace(pt).evalf(20))
    except (TypeError, ValueError, ZeroDivisionError, OverflowError):
        return None
    return v if math.isfinite(v.real) and math.isfinite(v.imag) else None


def numeric_equal(a, b) -> bool | None:
    """True/False by evaluation at sample points; None when no point could be evaluated."""
    A, B = _opaque_map(a, b)
    syms = sorted(A.free_symbols | B.free_symbols, key=str)
    rng = random.Random(20240531)
    rand = lambda: {s: sp.Float(rng.uniform(0.3, 1.7), 20) for s in syms}  # noqa: E731
    # every piecewise branch must be sampled: also try both sides of each breakpoint
    extra = [{**rand(), s: sp.Float(c + d, 20)}
             for s, c in _breakpoints(A, B) for d in (-0.1 * max(1, abs(c)), 0.1 * max(1, abs(c)))]
    good, need = 0, 3 + len(extra)
    for pt in extra + [rand() for _ in range(12 if syms else 1)]:
        va, vb = _value(A, pt), _value(B, pt)
        if va is None or vb is None:
            continue
        if not close(va, vb):
            return False
        good += 1
        if good == need:
            break
    return True if good else None


def _breakpoints(*exprs):
    out = set()
    for e in exprs:
        for pw in e.atoms(sp.Piecewise):
            for _, c in pw.args:
                if isinstance(c, sp.core.relational.Relational) and len(c.free_symbols) == 1:
                    (s,) = c.free_symbols
                    num = [x for x in (c.lhs, c.rhs) if x.is_number]
                    if num and num[0].is_real:
                        out.add((s, float(num[0])))
    return sorted(out, key=str)


def _equal_up_to_constants(a, b) -> bool:
    """dsolve's arbitrary constants may be numbered differently (_C1 <-> _C2)."""
    consts = sorted((s for s in b.free_symbols if re.fullmatch(r"_C\d+", s.name)), key=str)
    if not 1 < len(consts) <= 4:
        return False
    return any(numeric_equal(a, b.xreplace(dict(zip(consts, perm))))
               for perm in itertools.permutations(consts) if list(perm) != consts)


def compare_algebraic(a, b, gnode=None, onode=None):
    if a == b:
        return
    if a.has(sp.Piecewise) != b.has(sp.Piecewise):
        raise Diff("structure", f"{'piecewise' if a.has(sp.Piecewise) else 'plain'} expression "
                                f"{_snip(gnode if gnode is not None else str(a), 60)} vs "
                                f"{_snip(onode if onode is not None else str(b), 60)}")
    eq = numeric_equal(a, b)
    if eq is None:
        try:
            eq = sp.simplify(a - b) == 0
        except Exception:  # noqa: BLE001 - simplify failing just means "not proven equal"
            eq = False
    if not eq:
        eq = _equal_up_to_constants(a, b)
    snip = f"{_snip(gnode if gnode is not None else str(a))} vs {_snip(onode if onode is not None else str(b))}"
    if not eq:
        raise Diff("value", snip)
    if has_float(a) != has_float(b):
        raise Diff("float-vs-exact", snip)


# ---------------------------------------------------------------- structural comparison
@dataclass
class RTable:
    kind: str            # 'column', 'row' (Vector) or 'matrix'
    rows: int
    cols: int
    elems: list          # row-major element nodes


def _number(node):
    try:
        return complex(to_sympy(node))
    except (NotAlgebraic, TypeError, ValueError):
        return None


def _int(node):
    return int(node.text) if isinstance(node, N.Num) else None


def _rtable(node):
    """Vector[column](n,{i = v},...) / Matrix(r,c,{(i, j) = v},...) / <a, b> -> RTable."""
    if isinstance(node, N.Angle):
        if node.sep == "," and not any(isinstance(x, (N.Angle, N.ExprSeqN)) for x in node.items):
            return RTable("column", len(node.items), 1, list(node.items))
        return None
    if not isinstance(node, N.Call):
        return None
    f = node.func
    if isinstance(f, N.Index) and isinstance(f.base, N.Name) and f.base.name == "Vector" and len(f.indices) == 1:
        kind = getattr(f.indices[0], "name", "column")
    elif isinstance(f, N.Name) and f.name in ("Vector", "Matrix"):
        kind = "column" if f.name == "Vector" else "matrix"
    else:
        return None
    dims = []
    for a in node.args:
        if _int(a) is None:
            break
        dims.append(_int(a))
    if kind == "matrix":
        if len(dims) != 2:
            return None
        rows, cols = dims
    else:
        if len(dims) != 1:
            return None
        rows, cols = (1, dims[0]) if kind == "row" else (dims[0], 1)
    elems = [N.Num("0")] * (rows * cols)
    for a in node.args[len(dims):]:
        if not isinstance(a, N.SetN):
            continue
        for r in a.items:
            if not (isinstance(r, N.Rel) and r.op == "="):
                return None
            idx = [_int(x) for x in (r.left.items if isinstance(r.left, N.ExprSeqN) else [r.left])]
            if None in idx:
                return None
            i, j = (idx + [1])[:2] if kind != "row" else (1, idx[0])
            if not (1 <= i <= rows and 1 <= j <= cols):
                return None
            elems[(i - 1) * cols + (j - 1)] = r.right
    return RTable(kind, rows, cols, elems)


def _canon(node):
    rt = _rtable(node)
    if rt is not None:
        return rt
    if isinstance(node, N.Call) and isinstance(node.func, N.Name) and node.func.name == "piecewise":
        a = node.args
        pieces = [N.ListN([a[i + 1], a[i]]) for i in range(0, len(a) - 1, 2)]
        if len(a) % 2:
            pieces.append(N.ListN([a[-1], N.Name("otherwise")]))
        return N.Call(N.Name("PIECEWISE"), pieces)
    if isinstance(node, N.Rel) and node.op in (">", ">="):
        return N.Rel("<" if node.op == ">" else "<=", node.right, node.left)
    if isinstance(node, N.Uneval):
        return _canon(node.expr)
    return node


def _kind(x) -> str:
    return type(x).__name__.removesuffix("N")


def _match_unordered(gs, os_, what):
    left = list(os_)
    for g in gs:
        diffs = []
        for i, o in enumerate(left):
            try:
                cmp_node(g, o)
            except Diff as d:
                diffs.append(d)
                continue
            del left[i]
            break
        else:
            fve = next((d for d in diffs if d.subtype == "float-vs-exact"), None)
            if fve:
                raise Diff(fve.subtype, f"{what}: {fve.reason}")
            raise Diff("value", f"{what}: no match for {_snip(g)} among {_snip(', '.join(map(_snip, left)))}")


def _cmp_items(gs, os_, what, ordered=True, collection=False):
    if len(gs) != len(os_):
        raise Diff("structure", f"{what} of {len(gs)} vs {len(os_)} items")
    if not ordered:
        return _match_unordered(gs, os_, what)
    for i, (g, o) in enumerate(zip(gs, os_)):
        try:
            cmp_node(g, o)
        except Diff as d:
            if collection:   # tell a mere ordering difference (e.g. solve's roots) apart
                try:
                    _match_unordered(gs, os_, what)
                except Diff:
                    pass
                else:
                    raise Diff("order", f"{what} items match but in another order") from None
            raise Diff(d.subtype, f"{what}[{i + 1}]: {d.reason}") from None


def cmp_node(g, o):
    g, o = _canon(g), _canon(o)
    try:
        ga = to_sympy(g) if isinstance(g, N.Node) else None
    except (NotAlgebraic, TypeError, ValueError):
        ga = None
    try:
        oa = to_sympy(o) if isinstance(o, N.Node) else None
    except (NotAlgebraic, TypeError, ValueError):
        oa = None
    if ga is not None and oa is not None:
        return compare_algebraic(ga, oa, g, o)
    if type(g) is not type(o):
        raise Diff("structure", f"{_kind(g)} {_snip(g, 60)} vs {_kind(o)} {_snip(o, 60)}")
    if isinstance(g, N.Assign):
        _cmp_items(g.targets, o.targets, "assignment target")
        return cmp_node(g.values, o.values)
    if isinstance(g, N.ExprStmt):
        return cmp_node(g.expr, o.expr)
    if isinstance(g, N.ExprSeqN):
        # a sequence of solutions (sets/lists) may come in any order
        any_order = g.items and all(isinstance(_canon(x), (N.SetN, N.ListN, RTable)) for x in g.items)
        return _cmp_items(g.items, o.items, "sequence", ordered=not any_order, collection=True)
    if isinstance(g, N.ListN):
        return _cmp_items(g.items, o.items, "list", collection=True)
    if isinstance(g, N.SetN):
        return _cmp_items(g.items, o.items, "set", ordered=False)
    if isinstance(g, N.Rel):
        if g.op != o.op:
            raise Diff("structure", f"relation {g.op} vs {o.op}")
        return _cmp_items([g.left, g.right], [o.left, o.right], f"'{g.op}' side")
    if isinstance(g, N.Range):
        return _cmp_items([g.lo, g.hi], [o.lo, o.hi], "range end")
    if isinstance(g, N.Str):
        if g.value != o.value:
            raise Diff("value", f"{_snip(g)} vs {_snip(o)}")
        return
    if isinstance(g, RTable):
        if (g.kind, g.rows, g.cols) != (o.kind, o.rows, o.cols):
            raise Diff("structure", f"rtable {g.kind} {g.rows}x{g.cols} vs {o.kind} {o.rows}x{o.cols}")
        global _scale
        outer = _scale
        _scale = max([outer] + [abs(v) for v in map(_number, g.elems) if v is not None])
        try:
            return _cmp_items(g.elems, o.elems, "element")
        finally:
            _scale = outer
    if isinstance(g, N.ProcN):
        if [p.name for p in g.params] != [p.name for p in o.params]:
            raise Diff("structure", f"procedure parameters {_snip(g, 40)} vs {_snip(o, 40)}")
        if g.arrow and o.arrow and len(g.body) == len(o.body) == 1:
            return cmp_node(g.body[0], o.body[0])
        return   # procedure bodies (dsolve/numeric internals) are not compared
    if isinstance(g, N.Call):
        if canon_name(unparse(g.func)) != canon_name(unparse(o.func)):
            raise Diff("structure", f"call {_snip(g.func)} vs {_snip(o.func)}")
        return _cmp_items(g.args, o.args, f"{_snip(g.func, 30)} argument")
    if isinstance(g, (N.BinOp, N.UnOp)):
        if g.op != o.op:
            raise Diff("structure", f"operator {g.op} vs {o.op}")
        if isinstance(g, N.UnOp):
            return cmp_node(g.operand, o.operand)
        return _cmp_items([g.left, g.right], [o.left, o.right], f"'{g.op}' operand")
    if re.sub(r"\s+", "", unparse(g)) != re.sub(r"\s+", "", unparse(o)):
        raise Diff("value", f"{_snip(g)} vs {_snip(o)}")


def parse_math(text: str):
    """Text -> statement node (Assign / ExprStmt), or None if it does not parse as one."""
    text = re.sub(r"([A-Za-z0-9_])~", r"\1", text)
    try:
        tops = parse(text)
    except Exception:  # noqa: BLE001 - unparsable text falls back to a textual comparison
        return None
    if len(tops) != 1 or not isinstance(tops[0].stmt, (N.Assign, N.ExprStmt)):
        return None
    return tops[0].stmt


def compare_math(gtext: str, otext: str):
    if gtext == otext:
        return None
    g, o = parse_math(gtext), parse_math(otext)
    if g is None or o is None:
        d = compare_print(gtext, otext)
        return d and Diff("unparsed-" + d.subtype, d.reason)
    try:
        cmp_node(g, o)
    except Diff as d:
        return d
    except RecursionError:
        return Diff("compare-error", "expression too deep")
    return None


# ---------------------------------------------------------------- print / text
_NUM_RE = re.compile(r"((?<![\w.])[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?)")


def compare_print(gtext: str, otext: str):
    gp, op = _NUM_RE.split(gtext), _NUM_RE.split(otext)
    norm = lambda s: re.sub(r"\s+", " ", s).strip()  # noqa: E731
    if len(gp) == len(op):
        for i, (a, b) in enumerate(zip(gp, op)):
            if i % 2 == 0 and norm(a) != norm(b):
                break
            if i % 2 == 1 and not close(float(a), float(b)):
                return Diff("print", f"number {a} vs {b}")
        else:
            return None
    if norm(gtext) == norm(otext):
        return None
    return Diff("print", f"{_snip(norm(gtext))!r} vs {_snip(norm(otext))!r}")


# ---------------------------------------------------------------- plots
def _seg_dist(p, a, b):
    (px, py), (ax, ay), (bx, by) = p, a, b
    dx, dy = bx - ax, by - ay
    L = dx * dx + dy * dy
    t = 0.0 if L == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L))
    return math.hypot(px - ax - t * dx, py - ay - t * dy)


def _dist_to_polyline(p, P, xs):
    """Distance from p to the polyline P; xs is P's x list when it is sorted (fast window), else None."""
    if len(P) == 1:
        return math.hypot(p[0] - P[0][0], p[1] - P[0][1])
    best = math.inf
    if xs is not None:
        i = bisect.bisect_left(xs, p[0])
        for j in range(max(0, i - 3), min(len(P) - 1, i + 3)):
            best = min(best, _seg_dist(p, P[j], P[j + 1]))
        if best <= PLOT_TOL:
            return best
    return min(best, min(_seg_dist(p, P[j], P[j + 1]) for j in range(len(P) - 1)))


def _points(xs, ys, tx, ty):
    out = []
    for x, y in zip(xs, ys):
        if x is None or y is None:
            continue
        x, y = tx(x), ty(y)
        if x is not None and y is not None and math.isfinite(x) and math.isfinite(y):
            out.append((x, y))
    return out


def _log10(v):
    return math.log10(v) if v > 0 else None


def _sorted_x(P):
    xs = [p[0] for p in P]
    return xs if all(a <= b for a, b in zip(xs, xs[1:])) else None


def _function_like(P):
    """x mostly increasing (Maple's adaptive sampling inserts a few points out of order)."""
    return len(P) > 1 and P[-1][0] > P[0][0] and sum(a[0] > b[0] for a, b in zip(P, P[1:])) <= 0.05 * len(P)


def _deviation(A, B):
    """Distance from the points of A to the polyline B, ignoring the worst points that cover an
    OUTLIERS share of A (singularities, Maple's round-off spikes); returns (distance, point).
    Points of a function plot are weighted by the x interval they stand for, since Maple's
    adaptive sampling crowds points into spikes."""
    A = A[::max(1, len(A) // 300)]
    xs = _sorted_x(B)
    if _function_like(A):
        A = sorted(A)
        w = [(A[min(i + 1, len(A) - 1)][0] - A[max(i - 1, 0)][0]) / 2 for i in range(len(A))]
    else:
        w = [1.0] * len(A)
    devs = sorted(((_dist_to_polyline(p, B, xs), wi, p) for p, wi in zip(A, w)), reverse=True)
    budget = OUTLIERS * sum(w)
    for d, wi, p in devs:
        budget -= wi
        if budget < 0:
            return d, p
    return 0.0, None


def _view_y(options):
    """The numeric y range of the golden VIEW(x, y) option, if any."""
    for o in options:
        parts = o[5:-1].split(",") if o.startswith("VIEW(") else []
        if len(parts) == 2 and ".." in parts[1]:
            try:
                lo, hi = (float(v) for v in parts[1].split(".."))
            except ValueError:
                return None
            return (lo, hi) if hi > lo else None
    return None


def compare_plot(gp: dict, spec: dict):
    """Golden plot record (gen_golden_maple) vs our PlotSpec; returns None or Diff.
    Points are compared in coordinates normalised by the golden x range and y range (the VIEW
    y range when Maple has one, else the 2nd..98th percentile, so spikes do not swamp the scale)."""
    if gp.get("error") or gp.get("type") != "2d" or gp.get("frames"):
        return None   # only static 2-D plots are compared
    if spec.get("type") != "2d":
        return Diff("plot-type", f"2d vs {spec.get('type')}")
    for ax in ("xlog", "ylog"):
        if bool(gp.get(ax)) != bool(spec.get(ax)):
            return Diff("plot-axes", f"{ax} {bool(gp.get(ax))} vs {bool(spec.get(ax))}")
    gcurves = [ob for ob in gp.get("objects", []) if ob.get("points")]
    ocurves = [c for c in spec.get("curves", []) if c.get("x")]
    if len(gcurves) != len(ocurves):
        return Diff("plot-curves", f"{len(gcurves)} curves vs {len(ocurves)}")
    view = None if gp.get("ylog") else _view_y(gp.get("options", []))
    tx = _log10 if gp.get("xlog") else float
    ty = _log10 if gp.get("ylog") else float
    if view:
        ty = lambda y: min(max(float(y), view[0]), view[1])  # noqa: E731
    G = [_points([p[0] for p in ob["points"]], [p[1] for p in ob["points"]], tx, ty) for ob in gcurves]
    allx = [p[0] for c in G for p in c]
    ally = sorted(p[1] for c in G for p in c)
    if not allx:
        return None
    x0 = min(allx)
    xr = (max(allx) - x0) or 1.0
    if view:
        y0, yr = view[0], view[1] - view[0]
    else:
        y0, y1 = ally[int(0.02 * (len(ally) - 1))], ally[int(0.98 * (len(ally) - 1))]
        yr = (y1 - y0) or (ally[-1] - ally[0]) or max(abs(y0), 1.0)
    norm = lambda c: [((x - x0) / xr, (y - y0) / yr) for x, y in c]  # noqa: E731
    at_ = lambda p: f"({p[0] * xr + x0:.4g}, {p[1] * yr + y0:.4g})"  # noqa: E731
    for i, (gc, oc) in enumerate(zip(G, ocurves)):
        g = norm(gc)
        o = norm(_points(oc["x"], oc["y"], tx, ty))
        if not g:
            continue
        if not o:
            return Diff("plot-data", f"curve {i + 1}: no finite points")
        dev, at = _deviation(g, o)
        if dev > PLOT_TOL:
            return Diff("plot-data", f"curve {i + 1}: golden point {at_(at)} is {dev:.3g} of the range from ours")
        if _function_like(g):   # Maple's samples need not reach the interval ends
            lo, hi = min(p[0] for p in g), max(p[0] for p in g)
            o = [p for p in o if lo <= p[0] <= hi]
        dev, at = _deviation(o, g)
        if dev > 2 * PLOT_TOL:
            return Diff("plot-data", f"curve {i + 1}: our point {at_(at)} is {dev:.3g} of the range off the golden curve")
    return None


# ---------------------------------------------------------------- statements
def output_text(o: dict) -> str:
    if o["kind"] == "plot":
        spec = o.get("spec") or o.get("plot") or {}
        n = len(spec.get("curves", spec.get("objects", [])))
        return f"<plot {spec.get('type')} {n} curves>"
    return o.get("text", "")


def compare_output(g: dict, o: dict):
    gk, ok = g["kind"], o["kind"]
    if gk == "error" or ok == "error":
        if gk != ok:
            return Diff("error" if gk == "error" else "unexpected-error",
                        f"{gk} {_snip(output_text(g))!r} vs {ok} {_snip(output_text(o))!r}")
        return None
    if gk == "plot" or ok == "plot":
        if gk != ok:
            return Diff("kind", f"{gk} vs {ok} {_snip(output_text(o))!r}")
        return compare_plot(g["plot"], o["spec"])
    # golden marks every line printed by a natively-run ';' statement as math, so math ~ print
    if gk == "math" or ok == "math":
        return compare_math(g["text"], o["text"])
    return compare_print(g["text"], o["text"])


def compare_statement(golden: list[dict], ours: list[dict]) -> dict:
    notes = []
    gw = [o for o in golden if o["kind"] == "warning"]
    ow = [o for o in ours if o["kind"] == "warning"]
    if len(gw) != len(ow):
        notes.append(f"warnings: golden {len(gw)}, ours {len(ow)}")
    G = [o for o in golden if o["kind"] != "warning"]
    O = [o for o in ours if o["kind"] != "warning"]
    if G and G[-1].get("truncated"):
        O = O[:len(G)]
    res = {"verdict": "pass", "subtype": None, "reason": None, "notes": notes}
    if len(G) != len(O):
        res.update(verdict="fail", subtype="count",
                   reason=f"{len(G)} outputs [{' '.join(o['kind'] for o in G)}] vs "
                          f"{len(O)} [{' '.join(o['kind'] for o in O)}]")
        return res
    for i, (g, o) in enumerate(zip(G, O)):
        try:
            d = compare_output(g, o)
        except Exception as e:  # noqa: BLE001 - a comparator bug must not hide the other cases
            d = Diff("compare-error", f"{type(e).__name__}: {e}")
        if d is not None:
            res.update(verdict="fail", subtype=d.subtype,
                       reason=(f"output {i + 1}: " if len(G) > 1 else "") + d.reason)
            return res
        if g["kind"] == "error":
            ratio = difflib.SequenceMatcher(None, g["text"], o["text"]).ratio()
            if ratio < 0.9:
                notes.append(f"error message similarity {ratio:.2f}")
    return res
