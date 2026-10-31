"""Registry of Maple functions implemented in Python.

Each area module (core, algebra, calculus, ode, linalg, plots) creates a `Library`, decorates its
functions with `@lib.builtin(...)` and exposes `register(env)`.  See README.md in this folder.
"""
from __future__ import annotations

import importlib
import inspect
from typing import Callable

import sympy as sp

from ..errors import MapleError
from ..values import BuiltinProc, Module
from .packages_data import PACKAGE_EXPORTS

AREA_MODULES = ["core", "algebra", "calculus", "ode", "linalg", "plots"]


class Registry:
    """Global (session-independent) tables: functions, packages, operators, types."""

    def __init__(self):
        self.functions: dict[str, BuiltinProc] = {}
        self.packages: dict[str, Module] = {}
        self.operators: dict[str, Callable] = {}     # '.', '&x', ... -> fn(ctx, a, b)
        self.types: dict[str, Callable] = {}         # 'numeric' -> fn(ctx, value, *params) -> bool
        self.with_hooks: dict[str, list[Callable]] = {}
        self.protected: set[str] = set()

    def add(self, proc: BuiltinProc):
        if proc.package:
            pkg = self.package(proc.package)
            pkg.exports[proc.name] = proc
            if proc.name not in pkg.export_names:
                pkg.export_names.append(proc.name)
        else:
            self.functions[proc.name] = proc
            self.protected.add(proc.name)

    def package(self, name: str) -> Module:
        if name not in self.packages:
            self.packages[name] = Module(name, {}, list(PACKAGE_EXPORTS.get(name, [])))
        return self.packages[name]

    def lookup(self, name: str):
        return self.functions.get(name)


class Library:
    """Collects the builtins of one module; `register(env)` installs them."""

    def __init__(self):
        self.procs: list[BuiltinProc] = []
        self.operators: dict[str, Callable] = {}
        self.types: dict[str, Callable] = {}
        self.with_hooks: list[tuple[str, Callable]] = []

    def builtin(self, name: str | list[str], *, sig: str = "", doc: str = "",
                options=None, evaluate: bool = True, indexed: bool = False,
                package: str | list[str] | None = None, also_global: bool = False):
        """Decorator registering `fn(ctx, *args, **options)` as Maple function `name`.

        name      -- Maple name, or a list of aliases
        sig, doc  -- shown by Session.complete()
        options   -- iterable (or dict) of option names recognised in the argument list:
                     `name = value` equations become keyword arguments, a bare `name`
                     becomes name=True (e.g. dsolve(..., numeric, output=listprocedure)).
        evaluate  -- False: the function receives the raw AST nodes and must call
                     ctx.eval(node) itself (seq, add, `if`, assigned, ...).
        indexed   -- the function accepts f[i](...) and gets the evaluated indices as
                     the keyword argument `index` (tuple).
        package   -- install as an export of this package (or list of packages) instead of
                     globally; also_global=True installs it globally too.
        """
        names = [name] if isinstance(name, str) else list(name)
        pkgs = [package] if isinstance(package, str) else list(package or [])

        def deco(fn):
            for n in names:
                kw = dict(name=n, fn=fn, sig=sig or f"{n}(...)", doc=doc, evaluate=evaluate,
                          options=_opt_dict(options), indexed=indexed)
                for pk in pkgs:
                    self.procs.append(BuiltinProc(package=pk, **kw))
                if not pkgs or also_global:
                    self.procs.append(BuiltinProc(**kw))
            return fn
        return deco

    def operator(self, op: str):
        """Decorator: implementation of a binary operator ('.', '&x', ...): fn(ctx, a, b)."""
        def deco(fn):
            self.operators[op] = fn
            return fn
        return deco

    def type(self, name: str):
        """Decorator: a Maple type test fn(ctx, value, *type_params) -> bool."""
        def deco(fn):
            self.types[name] = fn
            return fn
        return deco

    def on_with(self, package: str):
        """Decorator: fn(ctx) runs whenever with(package) is executed."""
        def deco(fn):
            self.with_hooks.append((package, fn))
            return fn
        return deco

    def register(self, env: Registry):
        for p in self.procs:
            env.add(p)
        env.operators.update(self.operators)
        env.types.update(self.types)
        for pk, fn in self.with_hooks:
            env.with_hooks.setdefault(pk, []).append(fn)


def _opt_dict(options):
    if options is None:
        return None
    if isinstance(options, dict):
        return dict(options)
    return {o: None for o in options}


# ---------------------------------------------------------------- argument helpers
def split_options(proc: BuiltinProc, args):
    """Separate recognised `name = value` / bare-name options from positional args."""
    from ..values import MEquation
    if not proc.options:
        return list(args), {}
    pos, kw = [], {}
    for a in args:
        if isinstance(a, MEquation) and isinstance(a.lhs, sp.Symbol) and a.lhs.name in proc.options:
            kw[_pyname(a.lhs.name)] = a.rhs
        elif isinstance(a, sp.Symbol) and not isinstance(a, sp.Dummy) and a.name in proc.options \
                and proc.options[a.name] in (None, False, True):
            kw[_pyname(a.name)] = sp.true
        else:
            pos.append(a)
    return pos, kw


def _pyname(n: str) -> str:
    return n + "_" if n in ("lambda", "class", "def", "in", "is", "type_", "from", "global") else n


_sig_cache: dict = {}


def check_arity(proc: BuiltinProc, args, kw):
    fn = proc.fn
    sig = _sig_cache.get(fn)
    if sig is None:
        try:
            sig = inspect.signature(fn)
        except (TypeError, ValueError):
            return
        _sig_cache[fn] = sig
    try:
        sig.bind(None, *args, **kw)
    except TypeError:
        n = len(args)
        params = list(sig.parameters.values())[1:]
        if all(p.kind == p.POSITIONAL_OR_KEYWORD and p.default is p.empty for p in params):
            k = len(params)
            raise MapleError(f"invalid input: {proc.name} expects {k} argument"
                             f"{'s' if k != 1 else ''}, but received {n}")
        raise MapleError(f"invalid input: {proc.name} does not accept {n} argument"
                         f"{'s' if n != 1 else ''} here")


def is_true(v) -> bool:
    """Interpret an option value such as numeric=true."""
    return v is True or v is sp.true or (isinstance(v, sp.Symbol) and v.name == "true")


_ENV: Registry | None = None


def get_registry() -> Registry:
    """Build (once) the registry with every area module installed."""
    global _ENV
    if _ENV is None:
        env = Registry()
        for name in AREA_MODULES:
            mod = importlib.import_module(f"{__name__}.{name}")
            mod.register(env)
        _ENV = env
    return _ENV
