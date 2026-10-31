from symflex_maple import Session


def texts(session: Session, code: str) -> list[str]:
    """Run code and return the text of every non-plot output."""
    return [o["text"] for o in session.run(code) if "text" in o]


def run1(code: str) -> list[str]:
    return texts(Session(), code)
