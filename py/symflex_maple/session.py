"""Public API: Session.run / complete / reset (see docs/ARCHITECTURE.md)."""
from __future__ import annotations

from .errors import MapleError, MapleSyntaxError, QuitSignal
from .evaluator import Evaluator
from .parser import Parser
from .values import BuiltinProc, Procedure, UserProc


class Session:
    def __init__(self):
        self.ev = Evaluator()

    def reset(self):
        self.ev.reset()

    def run(self, code: str) -> list[dict]:
        """Run one notebook cell. Never raises; an error ends the cell like in Maple."""
        ev = self.ev
        ev.outputs = []
        try:
            parser = Parser(code)
            for top in parser.top_statements():
                ev.exec_stmt(top.stmt, None, (ev.settings.get("printlevel", 1) + 1)
                             if top.display else 0)
        except QuitSignal:
            pass
        except MapleSyntaxError as e:
            ev.emit({"kind": "error", "text": e.text()})
        except MapleError as e:
            ev.emit({"kind": "error", "text": e.text()})
        except RecursionError:
            ev.emit({"kind": "error", "text": "Error, too many levels of recursion"})
        except Exception as e:  # noqa: BLE001 - run must never raise
            ev.emit({"kind": "error", "text": f"Error, (internal) {type(e).__name__}: {e}"})
        out, ev.outputs = ev.outputs, []
        return out

    def complete(self, prefix: str) -> list[dict]:
        """Completion items for names starting with prefix: builtins, loaded exports, user vars."""
        ev = self.ev
        items: dict[str, dict] = {}
        for name, v in ev.globals.items():
            if name.startswith(prefix):
                kind = "function" if isinstance(v, Procedure) else "variable"
                detail = v.node.source[:80] if isinstance(v, UserProc) and v.node.source else ""
                items[name] = {"label": name, "kind": kind, "detail": detail, "doc": "user-defined"}
        for name, v in ev.bound.items():
            if name.startswith(prefix) and name not in items and isinstance(v, BuiltinProc):
                items[name] = _builtin_item(v)
        for name, v in ev.env.functions.items():
            if name.startswith(prefix) and name not in items:
                items[name] = _builtin_item(v)
        for name, pkg in ev.env.packages.items():
            if name.startswith(prefix) and name not in items:
                items[name] = {"label": name, "kind": "module", "detail": "package",
                               "doc": f"{len(pkg.export_names)} exports"}
        for name in ("Pi", "I", "infinity", "true", "false", "FAIL", "NULL", "Digits"):
            if name.startswith(prefix) and name not in items:
                items[name] = {"label": name, "kind": "constant", "detail": "", "doc": ""}
        return sorted(items.values(), key=lambda d: (d["label"].lower(), d["label"]))


def _builtin_item(b: BuiltinProc) -> dict:
    return {"label": b.name, "kind": "function", "detail": b.sig,
            "doc": b.doc + (f" ({b.package})" if b.package else "")}
