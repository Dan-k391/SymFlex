"""Exception types used across the engine."""


class MapleError(Exception):
    """A Maple run-time error. `where` is the procedure name shown as "(in where)"."""

    def __init__(self, msg: str, where: str | None = None, value=None):
        super().__init__(msg)
        self.msg = msg
        self.where = where
        self.value = value   # the raw error value (for try/catch lastexception)

    def text(self) -> str:
        if self.where:
            return f"Error, (in {self.where}) {self.msg}"
        return f"Error, {self.msg}"


class MapleSyntaxError(MapleError):
    def __init__(self, msg: str, pos: int = -1):
        super().__init__(msg)
        self.pos = pos


class BreakSignal(Exception):
    pass


class NextSignal(Exception):
    pass


class ReturnSignal(Exception):
    def __init__(self, value):
        self.value = value


class QuitSignal(Exception):
    pass
