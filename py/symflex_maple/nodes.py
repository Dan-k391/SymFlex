"""AST node dataclasses for Maple 1-D input."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class Node:
    pass


# ---------------------------------------------------------------- expressions
@dataclass
class Num(Node):
    text: str            # integer literal text


@dataclass
class FloatLit(Node):
    text: str


@dataclass
class Str(Node):
    value: str


@dataclass
class Name(Node):
    name: str


@dataclass
class Uneval(Node):      # 'expr'
    expr: Node


@dataclass
class Ditto(Node):       # %, %%, %%%
    level: int


@dataclass
class BinOp(Node):
    op: str              # + - * / ^ . mod union minus intersect subset and or xor implies @ @@ || &name in
    left: Node
    right: Node


@dataclass
class UnOp(Node):
    op: str              # '-', '+', 'not', '!', '&name' (prefix neutral)
    operand: Node


@dataclass
class Rel(Node):
    op: str              # = <> < <= > >=
    left: Node
    right: Node


@dataclass
class Range(Node):
    lo: Node
    hi: Node


@dataclass
class SeqOp(Node):       # a $ b
    left: Node
    right: Node | None   # None for prefix form $a..b


@dataclass
class ExprSeqN(Node):    # a, b, c  (also the empty sequence)
    items: list[Node]


@dataclass
class ListN(Node):
    items: list[Node]


@dataclass
class SetN(Node):
    items: list[Node]


@dataclass
class Call(Node):
    func: Node
    args: list[Node]


@dataclass
class Index(Node):
    base: Node
    indices: list[Node]


@dataclass
class Member(Node):      # module:-name
    module: Node
    name: str


@dataclass
class TypeAnn(Node):     # x::type
    expr: Node
    type: Node


@dataclass
class Angle(Node):       # <a, b, c> (sep ',') or <a | b | c> (sep '|')
    sep: str
    items: list[Node]


@dataclass
class Param:
    name: str
    type: Node | None = None
    default: Node | None = None
    keyword: bool = False     # declared inside {...}


@dataclass
class ProcN(Node):
    params: list[Param]
    body: list["Stmt"]
    locals: list[Param] = field(default_factory=list)
    globals: list[str] = field(default_factory=list)
    options: list[Node] = field(default_factory=list)
    description: str | None = None
    arrow: bool = False       # defined with ->
    source: str = ""          # original text (for display)


@dataclass
class ModuleN(Node):
    body: list["Stmt"]
    exports: list[Param] = field(default_factory=list)
    locals: list[Param] = field(default_factory=list)
    options: list[Node] = field(default_factory=list)


# ---------------------------------------------------------------- statements
class Stmt(Node):
    pass


@dataclass
class ExprStmt(Stmt):
    expr: Node


@dataclass
class Assign(Stmt):
    targets: list[Node]
    values: Node             # rhs (possibly an ExprSeqN)


@dataclass
class If(Stmt):
    branches: list[tuple[Node, list[Stmt]]]
    orelse: list[Stmt] | None


@dataclass
class For(Stmt):
    var: str | None
    body: list[Stmt]
    start: Node | None = None
    step: Node | None = None
    stop: Node | None = None
    cond: Node | None = None
    iterable: Node | None = None   # for x in ...


@dataclass
class Break(Stmt):
    pass


@dataclass
class Next(Stmt):
    pass


@dataclass
class Return(Stmt):
    value: Node | None


@dataclass
class ErrorStmt(Stmt):
    args: list[Node]


@dataclass
class Try(Stmt):
    body: list[Stmt]
    catches: list[tuple[list[Node], list[Stmt]]]
    final: list[Stmt] | None


@dataclass
class Use(Stmt):
    packages: list[Node]
    body: list[Stmt]


@dataclass
class Quit(Stmt):
    pass


@dataclass
class Read(Stmt):
    file: Node


@dataclass
class Empty(Stmt):
    pass


@dataclass
class TopStmt:
    """A top-level statement plus how it was terminated."""
    stmt: Stmt
    display: bool            # ended with ';' (or nothing at end of cell)
    source: str = ""
    extra: Any = None
