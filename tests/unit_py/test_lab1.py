"""End-to-end: run course blocks from corpus/raw/lab1 and check the key numbers."""
import pathlib
import re

import pytest

from symflex_maple import Session

RAW = pathlib.Path(__file__).resolve().parents[2] / "corpus" / "raw" / "lab1"


def block(n: int) -> str:
    return re.sub(r"^> ?", "", (RAW / f"{n:02d}.mpl").read_text(encoding="utf-8"), flags=re.M)


def outputs(*blocks: int):
    s = Session()
    out = []
    for b in blocks:
        out += s.run(block(b))
    return out


def number_after(texts, prefix):
    for t in texts:
        if t.startswith(prefix):
            return float(t[len(prefix):])
    raise AssertionError(f"no output starting with {prefix!r} in {texts}")


def math(out):
    return [o["text"] for o in out if o["kind"] == "math"]


pytestmark = pytest.mark.skipif(not RAW.exists(), reason="corpus not available")


def test_friction_block_ex3():
    t = math(outputs(2))
    assert number_after(t, "W := ") == pytest.approx(392.40)
    assert t[1] == "{N = 179.0292942, ax = 4.778519499}"
    assert number_after(t, "x_at_3s := ") == pytest.approx(21.50333775, rel=1e-8)


def test_static_friction_solve():
    t = math(outputs(3))
    assert t[-1] == "{N = 154.9731936, P = 369.7103497}"


def test_kinetic_distance_roots():
    t = math(outputs(5))
    roots = sorted(float(x) for x in t[-1].split(","))
    assert roots == pytest.approx([-1.759921606, 1.759921606])


def test_elevator_fsolve_and_plot():
    out = outputs(11)
    assert [o["kind"] for o in out].count("plot") == 1     # second plot ends with ':'
    t = math(out)
    assert float(t[-2]) == pytest.approx(1.186730974)
    roots = sorted(float(x) for x in t[-1].split(", "))
    assert roots == pytest.approx([-20.17583481, -1.260896159, 1.186730974])


def test_crane_tension_fsolve():
    out = outputs(14, 15)
    assert float(math(out)[-1]) == pytest.approx(3.657070304)


def test_legend_plot():
    out = outputs(13)
    plots = [o["spec"] for o in out if o["kind"] == "plot"]
    assert [c["legend"] for c in plots[0]["curves"]] == ["sc", "vc", "ac"]


def test_vector_calculus_block():
    t = math(outputs(20, 21))
    assert number_after(t, "v := ") == pytest.approx(201.1342835)
    assert t[0] == "FC := 20.2275"
    rvec = [x for x in t if x.startswith("rvec := ")][0]
    assert rvec.startswith("rvec := Vector[column](2,{1 = 2*cos(100.5671418*t)")
