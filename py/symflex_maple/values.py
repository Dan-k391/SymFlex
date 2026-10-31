"""Non-SymPy Maple values.

Algebraic values are plain SymPy objects (Symbol for unassigned names, Function(name)(...)
for unknown calls, Float/Integer/Rational, Piecewise, ...). Everything that SymPy cannot
represent faithfully (or would auto-evaluate, like Eq) is a wrapper class defined here.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

import sympy as sp

FAIL = sp.Symbol("FAIL")


class MValue:
    """Base class of wrapper values. `map_leaves` rebuilds the value with f applied to its parts."""

    def map_leaves(self, f):
        return self


# ---------------------------------------------------------------- strings
class MString(str):
    """A Maple string ("..."), distinct from a name."""

    def map_leaves(self, f):
        return self


# ---------------------------------------------------------------- sequences
class ExprSeq(MValue):
    __slots__ = ("items",)

    def __init__(self, items=()):
        flat = []
        for x in items:
            if isinstance(x, ExprSeq):
                flat.extend(x.items)
            else:
                flat.append(x)
        self.items = tuple(flat)

    def map_leaves(self, f):
        return ExprSeq(f(x) for x in self.items)

    def __eq__(self, other):
        return isinstance(other, ExprSeq) and self.items == other.items

    def __hash__(self):
        return hash(("seq", self.items))

    def __len__(self):
        return len(self.items)

    def __iter__(self):
        return iter(self.items)

    def __repr__(self):
        return f"ExprSeq{self.items!r}"


NULL = ExprSeq(())


def seq_items(v) -> tuple:
    """Items of a value viewed as an expression sequence."""
    return v.items if isinstance(v, ExprSeq) else (v,)


def make_seq(items):
    items = tuple(items)
    if len(items) == 1 and not isinstance(items[0], ExprSeq):
        return items[0]
    return ExprSeq(items)


# ---------------------------------------------------------------- containers
class MList(MValue):
    __slots__ = ("items",)

    def __init__(self, items=()):
        self.items = ExprSeq(items).items

    def map_leaves(self, f):
        return MList(f(x) for x in self.items)

    def __eq__(self, other):
        return isinstance(other, MList) and self.items == other.items

    def __hash__(self):
        return hash(("list", self.items))

    def __len__(self):
        return len(self.items)

    def __iter__(self):
        return iter(self.items)

    def __repr__(self):
        return f"MList{list(self.items)!r}"


def _set_key(x):
    """Deterministic ordering for sets: numbers numerically, then everything else by text."""
    if isinstance(x, sp.Basic) and x.is_number and x.is_extended_real:
        try:
            return (0, float(x), "")
        except (TypeError, ValueError):
            pass
    from .printer import lprint   # local import: printer depends on values
    return (1, 0.0, lprint(x))


class MSet(MValue):
    __slots__ = ("items",)

    def __init__(self, items=()):
        uniq = []
        for x in ExprSeq(items).items:
            if not any(_same(x, y) for y in uniq):
                uniq.append(x)
        self.items = tuple(sorted(uniq, key=_set_key))

    def map_leaves(self, f):
        return MSet(f(x) for x in self.items)

    def __eq__(self, other):
        return isinstance(other, MSet) and len(self.items) == len(other.items) and all(
            any(_same(a, b) for b in other.items) for a in self.items)

    def __hash__(self):
        return hash(("set", len(self.items)))

    def __len__(self):
        return len(self.items)

    def __iter__(self):
        return iter(self.items)

    def __repr__(self):
        return f"MSet{list(self.items)!r}"


def _same(a, b) -> bool:
    try:
        return a == b
    except Exception:  # noqa: BLE001 - sympy relationals may refuse comparison
        return a is b


# ---------------------------------------------------------------- relations
class MRelation(MValue):
    """lhs op rhs with op in '=', '<>', '<', '<='.  Maple rewrites a > b as b < a."""
    __slots__ = ("op", "lhs", "rhs")

    def __init__(self, op, lhs, rhs):
        if op == ">":
            op, lhs, rhs = "<", rhs, lhs
        elif op == ">=":
            op, lhs, rhs = "<=", rhs, lhs
        self.op, self.lhs, self.rhs = op, lhs, rhs

    def map_leaves(self, f):
        return type(self)._rebuild(self.op, f(self.lhs), f(self.rhs))

    @staticmethod
    def _rebuild(op, lhs, rhs):
        return MEquation(lhs, rhs) if op == "=" else MRelation(op, lhs, rhs)

    def __eq__(self, other):
        return isinstance(other, MRelation) and self.op == other.op and \
            _same(self.lhs, other.lhs) and _same(self.rhs, other.rhs)

    def __hash__(self):
        return hash(("rel", self.op))

    def __repr__(self):
        return f"MRelation({self.lhs!r} {self.op} {self.rhs!r})"


class MEquation(MRelation):
    __slots__ = ()

    def __init__(self, lhs, rhs):
        super().__init__("=", lhs, rhs)


class MRange(MValue):
    __slots__ = ("lo", "hi")

    def __init__(self, lo, hi):
        self.lo, self.hi = lo, hi

    def map_leaves(self, f):
        return MRange(f(self.lo), f(self.hi))

    def __eq__(self, other):
        return isinstance(other, MRange) and _same(self.lo, other.lo) and _same(self.hi, other.hi)

    def __hash__(self):
        return hash("range")

    def __repr__(self):
        return f"MRange({self.lo!r}..{self.hi!r})"


class MLogic(MValue):
    """Unevaluated boolean expression: op in 'and', 'or', 'xor', 'implies', 'not'."""
    __slots__ = ("op", "args")

    def __init__(self, op, args):
        self.op, self.args = op, tuple(args)

    def map_leaves(self, f):
        return MLogic(self.op, [f(a) for a in self.args])

    def __eq__(self, other):
        return isinstance(other, MLogic) and self.op == other.op and self.args == other.args

    def __hash__(self):
        return hash(("logic", self.op))


class MUneval(MValue):
    """A value that must print with quotes: the result of evaluating ''x''."""
    __slots__ = ("value",)

    def __init__(self, value):
        self.value = value


# ---------------------------------------------------------------- tables / rtables
class MTable(MValue):
    def __init__(self, entries=None):
        self.entries: dict = dict(entries or {})

    def map_leaves(self, f):
        return MTable({k: f(v) for k, v in self.entries.items()})


class MMatrix(MValue):
    """Matrix wrapper around a (mutable) SymPy matrix."""

    def __init__(self, m):
        self.m = sp.Matrix(m)

    @property
    def shape(self):
        return self.m.shape

    def map_leaves(self, f):
        return MMatrix(self.m.applyfunc(f))

    def __eq__(self, other):
        return isinstance(other, MMatrix) and not isinstance(other, MVector) and self.m == other.m

    __hash__ = object.__hash__


class MVector(MMatrix):
    """Vector wrapper; `orient` is 'column' or 'row'. Stored as a column/row SymPy matrix."""

    def __init__(self, items, orient="column"):
        items = list(items)
        super().__init__([[x] for x in items] if orient == "column" else [items])
        self.orient = orient

    @property
    def items(self):
        return list(self.m)

    def map_leaves(self, f):
        return MVector([f(x) for x in self.m], self.orient)

    def __len__(self):
        return len(self.m)

    def __eq__(self, other):
        return isinstance(other, MVector) and self.orient == other.orient and self.m == other.m

    __hash__ = object.__hash__


# ---------------------------------------------------------------- procedures
class Procedure(MValue):
    """Base of every callable value (user procs, builtins, remember tables, operators)."""


@dataclass(eq=False)
class UserProc(Procedure):
    node: Any                    # nodes.ProcN
    closure: Any                 # defining Frame (None at top level)
    name: str | None = None
    remember: dict = field(default_factory=dict)

    @property
    def params(self):
        return self.node.params

    @property
    def options(self):
        return self.node.options


@dataclass(eq=False)
class BuiltinProc(Procedure):
    """A Maple function implemented in Python (see builtins/__init__.py)."""
    name: str
    fn: Callable
    sig: str = ""
    doc: str = ""
    evaluate: bool = True        # False: receives unevaluated AST nodes
    options: dict | None = None  # recognised keyword options -> default
    indexed: bool = False        # accepts f[index](...)
    package: str | None = None
    hold_names: bool = False     # args that are bare names are passed unevaluated (like assigned())


@dataclass(eq=False)
class RememberProc(Procedure):
    """What `f(x) := expr` / assign(f(x) = expr) creates: a pure remember table."""
    name: str
    table: dict = field(default_factory=dict)


@dataclass(eq=False)
class AppliedProc(Procedure):
    """A procedure-valued result such as D(f) or f@g; `fn(ctx, args)` computes the application."""
    fn: Callable
    label: Any = None            # value printed for this operator, e.g. D(y)
    name: str | None = None


# ---------------------------------------------------------------- packages / plots
@dataclass(eq=False)
class Module(MValue):
    name: str
    exports: dict = field(default_factory=dict)      # export name -> value
    export_names: list = field(default_factory=list) # order shown by with()


@dataclass(eq=False)
class PlotValue(MValue):
    spec: dict

    def map_leaves(self, f):
        return self


def is_container(v) -> bool:
    return isinstance(v, MValue) and not isinstance(v, (Procedure, Module, PlotValue))


def deep_map(f, v):
    """Apply f to every algebraic leaf of v (through lists, sets, equations, matrices ...)."""
    if isinstance(v, (MList, MSet, ExprSeq, MRelation, MRange, MMatrix, MLogic, MTable)):
        return v.map_leaves(lambda x: deep_map(f, x))
    if isinstance(v, (MValue, MString, str)) or v is None:
        return v
    return f(v)
