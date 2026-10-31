"""Printing of values: Maple 1-D text (interface(prettyprint=0) / lprint style), LaTeX for
the UI, and unparsing of AST nodes (used to display procedures)."""
from __future__ import annotations

import re

import mpmath.libmp as mlib
import sympy as sp
from sympy.core.function import AppliedUndef
from sympy.printing.latex import LatexPrinter

from . import nodes as N
from .values import (
    AppliedProc, BuiltinProc, ExprSeq, MList, MLogic, MMatrix, Module, MRange, MRelation, MSet,
    MString, MTable, MUneval, MValue, MVector, PlotValue, RememberProc, UserProc,
)

# SymPy function name -> Maple name
FUNC_NAMES = {
    "asin": "arcsin", "acos": "arccos", "atan": "arctan", "acot": "arccot", "asec": "arcsec",
    "acsc": "arccsc", "asinh": "arcsinh", "acosh": "arccosh", "atanh": "arctanh",
    "acoth": "arccoth", "asech": "arcsech", "acsch": "arccsch", "atan2": "arctan",
    "log": "ln", "Abs": "abs", "sign": "signum", "gamma": "GAMMA", "DiracDelta": "Dirac",
    "ceiling": "ceil", "re": "Re", "im": "Im", "arg": "argument", "Max": "max", "Min": "min",
    "loggamma": "lnGAMMA", "lowergamma": "GAMMA", "uppergamma": "GAMMA", "Heaviside": "Heaviside",
    "LambertW": "LambertW", "polygamma": "Psi", "digamma": "Psi", "zeta": "Zeta",
    "besselj": "BesselJ", "bessely": "BesselY", "besseli": "BesselI", "besselk": "BesselK",
    "factorial": "factorial", "binomial": "binomial", "conjugate": "conjugate",
}

PREC_SEQ, PREC_LOGIC, PREC_REL, PREC_RANGE, PREC_ADD, PREC_MUL, PREC_POW, PREC_ATOM = \
    1, 2, 3, 4, 10, 20, 30, 100

_IDENT = re.compile(r"^[A-Za-z_][A-Za-z_0-9]*$")


def name_str(name: str) -> str:
    """A Maple name, back-quoted when it is not a plain identifier."""
    if _IDENT.match(name):
        return name
    return "`" + name.replace("`", "``") + "`"


# ---------------------------------------------------------------- floats
def float_parts(f: sp.Float, digits: int | None = None):
    """Return (sign, mantissa digit string without trailing zeros, exponent E) with
    |f| = int(mantissa) * 10**E."""
    dps = digits or mlib.prec_to_dps(f._prec)
    s = mlib.to_str(f._mpf_, dps, min_fixed=1, max_fixed=0, strip_zeros=False)
    sign = ""
    if s.startswith("-"):
        sign, s = "-", s[1:]
    mant, _, exp = s.partition("e")
    lead = mant.partition(".")[0]
    ds = mant.replace(".", "").rstrip("0") or "0"
    # mpmath omits the exponent for some values; normalise to d.ddd form
    return sign, ds, int(exp or 0) + len(lead) - 1 - len(ds) + 1


def maple_float(f: sp.Float) -> str:
    """Maple's lprint float format: .3333333333, 1200., .12e-1, .1e21, -.5"""
    if f.is_zero:
        return "0."
    sign, ds, e = float_parts(f)
    dps = mlib.prec_to_dps(f._prec)
    if e >= 0:
        if len(ds) + e <= max(dps, 10):
            return f"{sign}{ds}{'0' * e}."
        return f"{sign}.{ds}e{e + len(ds)}"
    if len(ds) >= -e:
        k = len(ds) + e
        return f"{sign}{ds[:k]}.{ds[k:]}"
    return f"{sign}.{ds}e{e + len(ds)}"


# ---------------------------------------------------------------- 1-D printer
class TextPrinter:
    def __init__(self):
        pass

    def __call__(self, v) -> str:
        return self.p(v, 0)

    def p(self, v, prec: int) -> str:
        if isinstance(v, sp.Basic):
            return self.expr(v, prec)
        if isinstance(v, MString):
            return '"' + v.replace("\\", "\\\\").replace('"', '\\"') + '"'
        if isinstance(v, bool):
            return "true" if v else "false"
        if isinstance(v, int):
            return str(v)
        if isinstance(v, float):
            return maple_float(sp.Float(v))
        if isinstance(v, str):
            return name_str(v)
        if v is None:
            return ""
        m = getattr(self, "v_" + type(v).__name__, None)
        if m:
            return m(v, prec)
        if isinstance(v, MRelation):
            return self.v_MRelation(v, prec)
        if isinstance(v, MValue) and hasattr(v, "lprint"):
            return v.lprint(self)
        return str(v)

    # -- containers
    def v_ExprSeq(self, v, prec):
        s = ", ".join(self.p(x, PREC_SEQ + 1) for x in v.items)
        return f"({s})" if prec > PREC_SEQ and len(v.items) != 1 else s

    def v_MList(self, v, prec):
        return "[" + ", ".join(self.p(x, PREC_SEQ + 1) for x in v.items) + "]"

    def v_MSet(self, v, prec):
        return "{" + ", ".join(self.p(x, PREC_SEQ + 1) for x in v.items) + "}"

    def v_MRelation(self, v, prec):
        s = f"{self.p(v.lhs, PREC_REL + 1)} {v.op} {self.p(v.rhs, PREC_REL + 1)}"
        return f"({s})" if prec > PREC_REL else s

    v_MEquation = v_MRelation

    def v_MRange(self, v, prec):
        s = f"{self.p(v.lo, PREC_RANGE + 1)} .. {self.p(v.hi, PREC_RANGE + 1)}"
        return f"({s})" if prec > PREC_RANGE else s

    def v_MLogic(self, v, prec):
        if v.op == "not":
            s = "not " + self.p(v.args[0], PREC_LOGIC + 1)
        else:
            s = f" {v.op} ".join(self.p(a, PREC_LOGIC + 1) for a in v.args)
        return f"({s})" if prec > PREC_LOGIC else s

    def v_MUneval(self, v, prec):
        return "'" + self.p(v.value, 0) + "'"

    def v_MVector(self, v, prec):
        entries = ", ".join(f"{i} = {self.p(x, PREC_REL + 1)}" for i, x in enumerate(v.m, 1)
                            if x != 0)
        return (f"Vector[{v.orient}]({len(v.m)},{{{entries}}},datatype = anything,"
                f"storage = rectangular,order = Fortran_order,shape = [])")

    def v_MMatrix(self, v, prec):
        r, c = v.m.shape
        return (f"Matrix({r},{c},{{{_row_major(self, v)}}},datatype = anything,"
                f"storage = rectangular,order = Fortran_order,shape = [])")

    def v_MTable(self, v, prec):
        items = ", ".join(f"{self.p(_unkey(k), PREC_REL + 1)} = {self.p(x, PREC_REL + 1)}"
                          for k, x in v.entries.items())
        return f"table([{items}])"

    def v_UserProc(self, v, prec):
        return unparse(v.node)

    def v_BuiltinProc(self, v, prec):
        return name_str(v.name)

    def v_RememberProc(self, v, prec):
        return name_str(v.name)

    def v_AppliedProc(self, v, prec):
        if v.label is not None:
            return self.p(v.label, prec)
        return v.name or "proc () ... end proc"

    def v_Module(self, v, prec):
        return v.name

    def v_PlotValue(self, v, prec):
        return f"PLOT(...)"

    def v_MCall(self, v, prec):
        f = v.func
        head = f.name if isinstance(f, sp.Symbol) and "(" in f.name else self.p(f, PREC_ATOM)
        # named procedures appear by name inside unevaluated calls (last-name evaluation)
        args = ",".join(a.name if isinstance(a, UserProc) and a.name else self.p(a, 0)
                        for a in v.args)
        return f"{head}({args})"

    # -- sympy expressions
    def expr(self, e, prec):
        if e.is_Number:
            return self.number(e, prec)
        if isinstance(e, sp.Dummy):
            return name_str(e.name)
        if e.is_Symbol:
            return name_str(e.name)
        if e is sp.pi:
            return "Pi"
        if e is sp.E:
            return "exp(1)"
        if e is sp.I:
            return "I"
        if e is sp.EulerGamma:
            return "gamma"
        if e is sp.true:
            return "true"
        if e is sp.false:
            return "false"
        if isinstance(e, sp.Add):
            return self.add(e, prec)
        if isinstance(e, sp.Mul):
            return self.mul(e, prec)
        if isinstance(e, sp.Pow):
            return self.pow(e, prec)
        if isinstance(e, sp.Indexed):
            return f"{self.p(e.base.label, PREC_ATOM)}[{','.join(self.p(i, 0) for i in e.indices)}]"
        if isinstance(e, sp.IndexedBase):
            return self.p(e.label, prec)
        if isinstance(e, sp.Derivative):
            return self.derivative(e)
        if isinstance(e, sp.Subs):
            return self.subs(e)
        if isinstance(e, sp.Piecewise):
            parts = []
            for val, cond in e.args:
                if cond is sp.true:
                    parts.append(f"[{self.p(val, PREC_SEQ + 1)}, otherwise]")
                else:
                    parts.append(f"[{self.p(val, PREC_SEQ + 1)}, {self.p(cond, PREC_SEQ + 1)}]")
            return "PIECEWISE(" + ",".join(parts) + ")"
        inert = type(e).__name__ in ("Int", "Sum", "Product", "Limit")
        if isinstance(e, sp.Integral):
            return self.limits_call("Int" if inert else "int", e.function, e.limits)
        if isinstance(e, sp.Sum):
            return self.limits_call("Sum" if inert else "sum", e.function, e.limits)
        if isinstance(e, sp.Product):
            return self.limits_call("Product" if inert else "product", e.function, e.limits)
        if isinstance(e, sp.Limit):
            z, z0, d = e.args[1], e.args[2], str(e.args[3])
            extra = {"+": ",right", "-": ",left"}.get(d, "") if z0 not in (sp.oo, -sp.oo) else ""
            # an inert two-sided Limit is stored with dir '+-'

            return f"{'Limit' if inert else 'limit'}({self.p(e.args[0], 0)},{self.p(z, 0)} = {self.p(z0, PREC_REL + 1)}{extra})"
        if isinstance(e, sp.core.relational.Relational):
            return self.relational(e, prec)
        if isinstance(e, (sp.And, sp.Or, sp.Xor)):
            op = {sp.And: "and", sp.Or: "or", sp.Xor: "xor"}[type(e)]
            s = f" {op} ".join(self.p(a, PREC_LOGIC + 1) for a in e.args)
            return f"({s})" if prec > PREC_LOGIC else s
        if isinstance(e, sp.Not):
            s = "not " + self.p(e.args[0], PREC_LOGIC + 1)
            return f"({s})" if prec > PREC_LOGIC else s
        if isinstance(e, sp.Tuple):
            return "[" + ", ".join(self.p(a, PREC_SEQ + 1) for a in e.args) + "]"
        if isinstance(e, sp.exp):
            return f"exp({self.p(e.args[0], 0)})"
        if isinstance(e, sp.Function) or isinstance(e, AppliedUndef):
            return self.function(e)
        if isinstance(e, sp.Lambda):
            vs = e.variables
            params = name_str(str(vs[0])) if len(vs) == 1 else "(" + ", ".join(map(str, vs)) + ")"
            return f"{params} -> {self.p(e.expr, 0)}"
        if e is sp.S.EmptySet:
            return "{}"
        return str(e)

    def number(self, e, prec):
        if e is sp.oo:
            s = "infinity"
        elif e is sp.S.NegativeInfinity:
            s = "-infinity"
        elif e is sp.zoo or e is sp.nan:
            return "undefined"
        elif e.is_Float:
            s = maple_float(e)
        elif e.is_Integer:
            s = str(e.p)
        else:   # Rational
            s = f"{e.p}/{e.q}"
            return f"({s})" if prec > PREC_MUL else s
        if s.startswith("-") and prec > PREC_ADD:
            return f"({s})"
        return s

    def add(self, e, prec):
        if e.has(sp.Order):
            return self.series(e)
        terms = _ordered_terms(e)
        out = ""
        for i, t in enumerate(terms):
            s = self.p(t, PREC_ADD)
            if i and not s.startswith("-"):
                out += "+"
            out += s
        return f"({out})" if prec > PREC_ADD else out

    def series(self, e):
        order = [t for t in e.args if isinstance(t, sp.Order)]
        rest = sp.Add(*[t for t in e.args if not isinstance(t, sp.Order)])
        o = order[0]
        x = o.variables[0] if o.variables else sp.Symbol("x")
        n = sp.degree(o.expr, x) if o.expr.is_polynomial(x) else 0
        terms = sorted(sp.Add.make_args(rest), key=lambda t: sp.degree(t, x) if t.is_polynomial(x) else 0)
        body = ""
        for i, t in enumerate(terms + [o]):
            s = f"O({self.p(o.expr, 0)})" if t is o else self.p(t, PREC_ADD)
            body += ("+" if i and not s.startswith("-") else "") + s
        return f"series({body},{self.p(x, 0)},{n})"

    def mul(self, e, prec):
        c, rest = e.as_coeff_Mul()
        if c.is_negative:
            s = "-" + self._mul_body(-c, rest)
            return f"({s})" if prec > PREC_ADD else s
        s = self._mul_body(c, rest)
        return f"({s})" if prec > PREC_MUL else s

    def _mul_body(self, c, rest):
        num, den = [], []
        for f in _ordered_factors(rest):
            if f is sp.S.One:
                continue
            if isinstance(f, sp.Pow) and f.exp.is_Number and f.exp.is_negative:
                den.append(sp.Pow(f.base, -f.exp, evaluate=False) if f.exp != -1 else f.base)
            else:
                num.append(f)
        parts = []
        if c != 1 or not num:
            if c.is_Float:
                parts.append(maple_float(c))
            elif c.is_Rational and c.q != 1:
                parts.append(f"{c.p}/{c.q}")
            else:
                parts.append(self.p(c, PREC_MUL))
        parts += [self.p(f, PREC_MUL) for f in num]
        s = "*".join(parts)
        for d in den:
            s += "/" + self.p(d, PREC_MUL + 1)
        return s

    def pow(self, e, prec):
        b, x = e.base, e.exp
        if x.is_Number and x.is_negative:
            inv = sp.Pow(b, -x, evaluate=False) if x != -1 else b
            s = "1/" + self.p(inv, PREC_MUL + 1)
            return f"({s})" if prec > PREC_MUL else s
        bs = self.p(b, PREC_POW + 1)
        if x.is_Integer and x.is_positive or (x.is_Symbol and not x.is_Number):
            xs = self.p(x, PREC_POW + 1)
        elif isinstance(x, (sp.Function, AppliedUndef)) or x in (sp.pi,):
            xs = self.p(x, PREC_POW + 1)
        else:
            xs = "(" + self.p(x, 0) + ")"
        s = f"{bs}^{xs}"
        return f"({s})" if prec > PREC_POW else s

    def function(self, e):
        name = type(e).__name__
        if isinstance(e, AppliedUndef):
            fname = name_str(name)
        else:
            fname = FUNC_NAMES.get(name, name)
        args = ",".join(self.p(a, 0) for a in e.args)
        return f"{fname}({args})"

    def derivative(self, e):
        parts = []
        for v, n in e.variable_count:
            vs = self.p(v, 0)
            parts.append(vs if n == 1 else f"{vs} $ {self.p(n, 0)}")
        return f"diff({self.p(e.expr, 0)},{','.join(parts)})"

    def subs(self, e):
        d = d_operator_form(e)
        if d:
            return d[0].name + "(" + ",".join(self.p(a, 0) for a in d[1]) + ")"
        eqs = ",".join(f"{self.p(a, 0)} = {self.p(b, 0)}" for a, b in zip(e.variables, e.point))
        return f"eval({self.p(e.expr, 0)},{eqs})"

    def limits_call(self, name, f, limits):
        parts = []
        for lim in limits:
            if len(lim) == 1:
                parts.append(self.p(lim[0], 0))
            else:
                parts.append(f"{self.p(lim[0], 0)} = {self.p(lim[1], PREC_RANGE + 1)} .. "
                             f"{self.p(lim[2], PREC_RANGE + 1)}")
        return f"{name}({self.p(f, 0)},{','.join(parts)})"

    def relational(self, e, prec):
        op = {"==": "=", "!=": "<>", "<": "<", "<=": "<=", ">": "<", ">=": "<="}[e.rel_op]
        lhs, rhs = (e.rhs, e.lhs) if e.rel_op in (">", ">=") else (e.lhs, e.rhs)
        s = f"{self.p(lhs, PREC_REL + 1)} {op} {self.p(rhs, PREC_REL + 1)}"
        return f"({s})" if prec > PREC_REL else s


def _unkey(k):
    return k[0] if isinstance(k, tuple) and len(k) == 1 else ExprSeq(k) if isinstance(k, tuple) else k


def _row_major(pr, v):
    r, c = v.m.shape
    return ", ".join(f"({i + 1}, {j + 1}) = {pr.p(v.m[i, j], PREC_REL + 1)}"
                     for i in range(r) for j in range(c) if v.m[i, j] != 0)


def _ordered_factors(e):
    try:
        return [f for f in e.as_ordered_factors()]
    except Exception:  # noqa: BLE001 - ordering is cosmetic
        return list(sp.Mul.make_args(e))


def _ordered_terms(e):
    try:
        terms = e.as_ordered_terms()
    except Exception:  # noqa: BLE001 - ordering is cosmetic
        terms = list(e.args)
    # Maple puts the constant term last more often than first (e.g. 2*x+1)
    if len(terms) > 1 and terms[0].is_Number and not terms[-1].is_Number             and not (len(terms) == 2 and terms[1].is_number):   # keep 2+3*I as is
        terms = terms[1:] + terms[:1]
    elif len(terms) == 2 and terms[1].is_Number and terms[0].is_number:
        terms = [terms[1], terms[0]]
    return terms


def d_operator_form(e: sp.Subs):
    """Subs(Derivative(f(x), x$n), x, a) -> (D-operator label, point) or None."""
    expr = e.expr
    if not isinstance(expr, sp.Derivative) or not isinstance(expr.expr, AppliedUndef):
        return None
    f = expr.expr
    if list(f.args) != list(e.variables):
        return None
    counts = []
    for v, n in expr.variable_count:
        counts += [list(f.args).index(v) + 1] * int(n)
    fname = name_str(type(f).__name__)
    if len(f.args) == 1:
        n = len(counts)
        label = f"D({fname})" if n == 1 else f"(D@@{n})({fname})"
    else:
        label = f"D[{','.join(map(str, sorted(counts)))}]({fname})"
    return sp.Symbol(label), list(e.point)


_text = TextPrinter()


def lprint(v) -> str:
    """Maple 1-D (prettyprint=0) form of a value."""
    return _text(v)


# ---------------------------------------------------------------- LaTeX
GREEK = {
    "alpha", "beta", "gamma", "delta", "epsilon", "zeta", "eta", "theta", "iota", "kappa",
    "lambda", "mu", "nu", "xi", "pi", "rho", "sigma", "tau", "upsilon", "phi", "chi", "psi",
    "omega", "Gamma", "Delta", "Theta", "Lambda", "Xi", "Sigma", "Upsilon", "Phi", "Psi", "Omega",
}


def latex_name(name: str) -> str:
    """Maple GUI look: greek letters (omega0 -> omega 0), c__1 -> c_1, other names italic."""
    base, sep, sub = name.partition("__")

    def one(s):
        if s in GREEK:
            return "\\" + s
        m = re.match(r"^([A-Za-z]+)(\d+)$", s)
        if m and m.group(1) in GREEK:
            return "\\" + m.group(1) + " " + m.group(2)
        if len(s) == 1:
            return s
        return "\\mathit{" + s.replace("_", "\\_") + "}"
    out = one(base)
    if sep:
        out += "_{" + one(sub) + "}"
    return out


class MapleLatexPrinter(LatexPrinter):
    def __init__(self, displayprecision: int = -1):
        super().__init__({"mul_symbol": None, "inv_trig_style": "full", "ln_notation": True})
        self.displayprecision = displayprecision

    def _print_Symbol(self, e, style="plain"):
        return latex_name(e.name)

    _print_Dummy = _print_Symbol

    def _print_Float(self, e):
        return latex_float(e, self.displayprecision)

    def _print_Pi(self, e):
        return "\\pi"

    def _print_Exp1(self, e):
        return "\\mathrm{e}"

    def _print_ImaginaryUnit(self, e):
        return "I"

    def _print_Function(self, e, exp=None):
        if isinstance(e, AppliedUndef):
            name = latex_name(type(e).__name__)
            s = f"{name}\\left({', '.join(self._print(a) for a in e.args)}\\right)"
            return f"{s}^{{{exp}}}" if exp else s
        name = type(e).__name__
        if name == "atan2":
            return f"\\arctan\\left({self._print(e.args[0])}, {self._print(e.args[1])}\\right)"
        return super()._print_Function(e, exp)

    def _print_Derivative(self, e):
        f = self._print(e.expr)
        total = sum(int(n) for _, n in e.variable_count)
        if len(e.variable_count) == 1:
            v, n = e.variable_count[0]
            vs = self._print(v)
            if int(n) == 1:
                return f"\\frac{{d}}{{d{vs}}}{f}"
            return f"\\frac{{d^{{{n}}}}}{{d{vs}^{{{n}}}}}{f}"
        den = "".join(f"\\partial {self._print(v)}" + (f"^{{{n}}}" if n != 1 else "")
                      for v, n in e.variable_count)
        return f"\\frac{{\\partial^{{{total}}}}}{{{den}}}{f}"

    def _print_Subs(self, e):
        d = d_operator_form(e)
        if d:
            pts = ", ".join(self._print(a) for a in d[1])
            return _latex_dop(e) + "\\left(" + pts + "\\right)"
        return super()._print_Subs(e)

    def _print_Piecewise(self, e):
        rows = []
        for val, cond in e.args:
            c = "\\mathit{otherwise}" if cond is sp.true else self._print(cond)
            rows.append(f"{self._print(val)} & {c}")
        return "\\begin{cases} " + " \\\\ ".join(rows) + " \\end{cases}"


def _latex_dop(e):
    expr = e.expr
    f = latex_name(type(expr.expr).__name__)
    n = sum(int(c) for _, c in expr.variable_count)
    if len(expr.expr.args) == 1:
        return f"\\mathrm{{D}}({f})" if n == 1 else f"\\mathrm{{D}}^{{({n})}}({f})"
    idx = []
    for v, c in expr.variable_count:
        idx += [str(list(expr.expr.args).index(v) + 1)] * int(c)
    return f"\\mathrm{{D}}_{{{','.join(idx)}}}({f})"


def latex_float(f: sp.Float, displayprecision: int = -1) -> str:
    s = maple_float(f)
    if displayprecision is not None and displayprecision >= 0 and "e" not in s:
        try:
            s = f"{float(f):.{displayprecision}f}" if displayprecision else f"{float(f):.0f}."
        except (OverflowError, ValueError):
            pass
    if "e" in s:
        sign, ds, e = float_parts(f)
        m = ds[0] + ("." + ds[1:] if len(ds) > 1 else ".")
        return f"{sign}{m}\\times 10^{{{e + len(ds) - 1}}}"
    if s.startswith("."):
        s = "0" + s
    elif s.startswith("-."):
        s = "-0" + s[1:]
    return s


class LatexValuePrinter:
    def __init__(self, displayprecision: int = -1):
        self.sp = MapleLatexPrinter(displayprecision)

    def __call__(self, v) -> str:
        return self.p(v)

    def p(self, v) -> str:
        if isinstance(v, sp.Basic):
            try:
                return self.sp.doprint(v)
            except Exception:  # noqa: BLE001 - fall back to the text form
                return "\\mathtt{" + _tt(lprint(v)) + "}"
        if isinstance(v, MString):
            return "\\text{``" + _tt(str(v)) + "''}"
        if isinstance(v, ExprSeq):
            return ", ".join(self.p(x) for x in v.items)
        if isinstance(v, MList):
            return "\\left[" + ", ".join(self.p(x) for x in v.items) + "\\right]"
        if isinstance(v, MSet):
            return "\\left\\{" + ", ".join(self.p(x) for x in v.items) + "\\right\\}"
        if isinstance(v, MRelation):
            op = {"=": "=", "<>": "\\neq", "<": "<", "<=": "\\leq"}[v.op]
            return f"{self.p(v.lhs)} {op} {self.p(v.rhs)}"
        if isinstance(v, MRange):
            return f"{self.p(v.lo)} .. {self.p(v.hi)}"
        if isinstance(v, MVector):
            if v.orient == "row":
                return "\\left[\\begin{matrix} " + " & ".join(self.p(x) for x in v.m) + \
                    " \\end{matrix}\\right]"
            return "\\left[\\begin{matrix} " + " \\\\ ".join(self.p(x) for x in v.m) + \
                " \\end{matrix}\\right]"
        if isinstance(v, MMatrix):
            r, c = v.m.shape
            rows = [" & ".join(self.p(v.m[i, j]) for j in range(c)) for i in range(r)]
            return "\\left[\\begin{matrix} " + " \\\\ ".join(rows) + " \\end{matrix}\\right]"
        if isinstance(v, MLogic):
            if v.op == "not":
                return "\\neg " + self.p(v.args[0])
            return f" \\mathrm{{ {v.op} }} ".join(self.p(a) for a in v.args)
        return "\\mathtt{" + _tt(lprint(v)) + "}"


def _tt(s: str) -> str:
    out = []
    for ch in s:
        if ch in "\\":
            out.append("\\backslash{}")
        elif ch in "{}_#$%&":
            out.append("\\" + ch)
        elif ch == "^":
            out.append("\\hat{}")
        elif ch == "~":
            out.append("\\sim{}")
        elif ch == " ":
            out.append("\\ ")
        else:
            out.append(ch)
    return "".join(out)


def latex(v, displayprecision: int = -1) -> str:
    return LatexValuePrinter(displayprecision)(v)


# ---------------------------------------------------------------- AST unparser
_BIN_PREC = {
    "implies": 3, "xor": 4, "or": 5, "and": 6, "in": 9, "subset": 11, "mod": 12,
    "+": 13, "-": 13, "union": 13, "minus": 13, "*": 14, "/": 14, ".": 14, "@": 14,
    "intersect": 14, "^": 15, "@@": 15, "||": 19,
}


def unparse(node, prec: int = 0) -> str:
    """Maple source text for an AST node, in Maple's own display style."""
    u = unparse
    if isinstance(node, N.Num):
        return node.text
    if isinstance(node, N.FloatLit):
        return node.text
    if isinstance(node, N.Str):
        return '"' + node.value.replace('"', '\\"') + '"'
    if isinstance(node, N.Name):
        return name_str(node.name)
    if isinstance(node, N.Uneval):
        return "'" + u(node.expr) + "'"
    if isinstance(node, N.Ditto):
        return "%" * node.level
    if isinstance(node, N.BinOp):
        p = _BIN_PREC.get(node.op, 17)   # neutral &-operators bind tightest
        sep = node.op if node.op in ("+", "-", "*", "/", "^", ".", "@", "@@", "||") \
            else f" {node.op} "
        s = f"{u(node.left, p)}{sep}{u(node.right, p + 1)}"
        return f"({s})" if prec > p else s
    if isinstance(node, N.UnOp):
        if node.op == "-":
            s = "-" + u(node.operand, 14)
            return f"({s})" if prec > 13 else s
        if node.op == "not":
            s = "not " + u(node.operand, 7)
            return f"({s})" if prec > 7 else s
        if node.op == "!":
            return u(node.operand, 16) + "!"
        return f"{node.op} {u(node.operand, 17)}"
    if isinstance(node, N.Rel):
        s = f"{u(node.left, 11)} {node.op} {u(node.right, 11)}"
        return f"({s})" if prec > 9 else s
    if isinstance(node, N.Range):
        s = f"{u(node.lo, 11)} .. {u(node.hi, 11)}"
        return f"({s})" if prec > 10 else s
    if isinstance(node, N.SeqOp):
        s = f"{u(node.left, 9)} $ {u(node.right, 9)}" if node.left else f"$ {u(node.right, 9)}"
        return f"({s})" if prec > 8 else s
    if isinstance(node, N.ExprSeqN):
        s = ", ".join(u(x, 2) for x in node.items)
        return f"({s})" if prec > 1 or not node.items else s
    if isinstance(node, N.ListN):
        return "[" + ", ".join(u(x, 2) for x in node.items) + "]"
    if isinstance(node, N.SetN):
        return "{" + ", ".join(u(x, 2) for x in node.items) + "}"
    if isinstance(node, N.Call):
        return f"{u(node.func, 20)}({', '.join(u(x, 2) for x in node.args)})"
    if isinstance(node, N.Index):
        return f"{u(node.base, 20)}[{', '.join(u(x, 2) for x in node.indices)}]"
    if isinstance(node, N.Member):
        return f"{u(node.module, 20)}:-{node.name}"
    if isinstance(node, N.TypeAnn):
        return f"{u(node.expr, 20)}::{u(node.type, 20)}"
    if isinstance(node, N.Angle):
        return "<" + node.sep.join(u(x, 2) for x in node.items) + ">"
    if isinstance(node, N.ProcN):
        return _unparse_proc(node, prec)
    if isinstance(node, N.ModuleN):
        return "module () ... end module"
    if isinstance(node, N.Stmt):
        return unparse_stmt(node)
    return repr(node)


def _param_str(p: N.Param) -> str:
    s = name_str(p.name)
    if p.type is not None:
        s += "::" + unparse(p.type, 20)
    if p.default is not None:
        s += " := " + unparse(p.default, 2)
    return s


def _unparse_proc(node: N.ProcN, prec: int) -> str:
    if node.arrow:
        ps = node.params
        if len(ps) == 1 and ps[0].type is None:
            head = name_str(ps[0].name)
        else:
            head = "(" + ", ".join(_param_str(p) for p in ps) + ")"
        body = node.body[0]
        s = f"{head} -> {unparse(body.expr, 2) if isinstance(body, N.ExprStmt) else unparse_stmt(body)}"
        return f"({s})" if prec > 2 else s
    params = [p for p in node.params if not p.keyword]
    kws = [p for p in node.params if p.keyword]
    head = ", ".join(_param_str(p) for p in params)
    if kws:
        head += (", " if head else "") + "{" + ", ".join(_param_str(p) for p in kws) + "}"
    parts = [f"proc ({head})"]
    if node.locals:
        parts.append("local " + ", ".join(_param_str(p) for p in node.locals) + ";")
    if node.globals:
        parts.append("global " + ", ".join(map(name_str, node.globals)) + ";")
    if node.options:
        parts.append("option " + ", ".join(unparse(o, 2) for o in node.options) + ";")
    if node.description:
        parts.append(f'description "{node.description}";')
    body = "; ".join(unparse_stmt(s) for s in node.body)
    if body:
        parts.append(body)
    parts.append("end proc")
    return " ".join(parts)


def _block(stmts) -> str:
    return "; ".join(unparse_stmt(s) for s in stmts)


def unparse_stmt(s) -> str:
    if isinstance(s, N.ExprStmt):
        return unparse(s.expr)
    if isinstance(s, N.Assign):
        return ", ".join(unparse(t, 2) for t in s.targets) + " := " + unparse(s.values, 1)
    if isinstance(s, N.If):
        out = []
        for i, (c, b) in enumerate(s.branches):
            out.append(("if " if i == 0 else "elif ") + unparse(c) + " then " + _block(b))
        if s.orelse is not None:
            out.append("else " + _block(s.orelse))
        return " ".join(out) + " end if"
    if isinstance(s, N.For):
        head = ""
        if s.var is not None:
            head = "for " + (", ".join(s.var) if isinstance(s.var, tuple) else name_str(s.var)) + " "
        if s.iterable is not None:
            head += "in " + unparse(s.iterable) + " "
        if s.start is not None:
            head += "from " + unparse(s.start) + " "
        if s.step is not None:
            head += "by " + unparse(s.step) + " "
        if s.stop is not None:
            head += "to " + unparse(s.stop) + " "
        if s.cond is not None:
            head += "while " + unparse(s.cond) + " "
        return f"{head}do {_block(s.body)} end do"
    if isinstance(s, N.Break):
        return "break"
    if isinstance(s, N.Next):
        return "next"
    if isinstance(s, N.Return):
        return "return" + ("" if s.value is None else " " + unparse(s.value))
    if isinstance(s, N.ErrorStmt):
        return "error " + ", ".join(unparse(a, 2) for a in s.args)
    if isinstance(s, N.Try):
        out = "try " + _block(s.body)
        for pats, b in s.catches:
            out += " catch " + ", ".join(unparse(p, 2) for p in pats) + ": " + _block(b)
        if s.final is not None:
            out += " finally " + _block(s.final)
        return out + " end try"
    if isinstance(s, N.Use):
        return "use " + ", ".join(unparse(p, 2) for p in s.packages) + " in " + \
            _block(s.body) + " end use"
    if isinstance(s, N.Quit):
        return "quit"
    if isinstance(s, N.Read):
        return "read " + unparse(s.file)
    if isinstance(s, N.Empty):
        return ""
    return repr(s)
