"""Run the Maple corpus through the SymFlex engine and compare with the cmaple golden outputs.

Usage: python tests/run_maple_corpus.py [substring filters...] [--jobs N] [--timeout S] [-v] [--json PATH]

Each case runs in a worker process (a fresh Session per case, one s.run per golden statement, since
cmaple batch mode keeps going after errors); a case that runs longer than --timeout is killed and
reported TIMEOUT. Golden cases that timed out in cmaple only need to finish (PASS-TIMEOUT-OK).
Statements are compared semantically by tests/maple_compare.py. Writes tests/out/maple_report.json;
exits nonzero when any case is FAIL / CRASH / TIMEOUT.
"""
from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import sys
import time
import traceback
from multiprocessing.connection import wait
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CASES, GOLDEN = ROOT / "corpus" / "cases", ROOT / "corpus" / "golden"
BAD = ("FAIL", "CRASH", "TIMEOUT")


def run_case(case: dict):
    """Worker side: yields ('at', k, src) before each statement, 'ran' when the engine is done,
    then ('done', result) after the comparison."""
    from symflex_maple import Session
    import maple_compare as mc
    from maple_split import split_statements

    golden = json.loads(Path(case["golden"]).read_text(encoding="utf-8"))
    stmts = golden["statements"]
    current = [s["src"] for s in split_statements(Path(case["path"]).read_text(encoding="utf-8"))]
    stale = current != [s["src"] for s in stmts]
    s, ours, t0 = Session(), [], time.perf_counter()
    for st in stmts:
        yield "at", st["k"], st["src"]
        ours.append(s.run(st["src"] + (st["terminator"] or ";")))
    elapsed = time.perf_counter() - t0
    yield "ran"
    res = {"case": case["name"], "time": round(elapsed, 2), "stale_golden": stale, "statements": []}
    if golden["status"] == "timeout":
        res["status"] = "PASS-TIMEOUT-OK"
        yield "done", res
        return
    first = None
    for st, outs in zip(stmts, ours):
        v = mc.compare_statement(st["outputs"], outs)
        v.update(k=st["k"], src=st["src"],
                 golden=[mc.output_text(o) for o in st["outputs"]], ours=[mc.output_text(o) for o in outs])
        res["statements"].append(v)
        if first is None and v["verdict"] == "fail":
            first = v
    res["status"] = "FAIL" if first else "PASS"
    if first:
        res.update(k=first["k"], subtype=first["subtype"], reason=first["reason"])
    yield "done", res


def worker(conn):
    sys.path[:0] = [str(ROOT / "py"), str(ROOT / "tests"), str(ROOT / "scripts")]
    while (case := conn.recv()) is not None:
        try:
            for msg in run_case(case):
                conn.send(msg)
        except BaseException:  # noqa: BLE001 - report anything (incl. KeyboardInterrupt) as CRASH
            conn.send(("done", {"case": case["name"], "status": "CRASH",
                                "reason": traceback.format_exc(limit=-3)}))


class Worker:
    def __init__(self):
        self.conn, child = mp.Pipe()
        self.proc = mp.Process(target=worker, args=(child,), daemon=True)
        self.proc.start()
        self.case = None
        self.start = 0.0

    def submit(self, case):
        self.case, self.start, self.phase, self.at = case, time.monotonic(), "run", None
        self.conn.send(case)

    def kill(self):
        self.proc.kill()
        self.proc.join()


def discover(filters):
    cases = []
    for path in sorted(CASES.glob("*/*.mpl")):
        name = f"{path.parent.name}/{path.stem}"
        if filters and not any(f in name for f in filters):
            continue
        cases.append({"name": name, "path": str(path), "golden": str(GOLDEN / path.parent.name / (path.stem + ".json"))})
    return cases


def run_all(cases, jobs, timeout, on_result):
    pending = list(reversed(cases))
    workers = [Worker() for _ in range(max(1, min(jobs, len(cases))))]
    busy = 0
    for w in workers:
        if pending:
            w.submit(pending.pop()); busy += 1
    while busy:
        ready = wait([w.conn for w in workers if w.case], timeout=0.5)
        now = time.monotonic()
        for i, w in enumerate(workers):
            if not w.case:
                continue
            res = None
            if w.conn in ready:
                try:
                    msg = w.conn.recv()
                except EOFError:
                    res = {"case": w.case["name"], "status": "CRASH", "reason": "worker process died"}
                else:
                    if msg == "ran":
                        w.phase, w.start = "compare", now
                        continue
                    if msg[0] == "at":
                        w.at = msg[1:]
                        continue
                    res = msg[1]
            elif now - w.start > timeout:
                what = f"engine at k={w.at[0]} {_short([w.at[1]], 70)}" if w.phase == "run" else "comparator"
                res = {"case": w.case["name"], "status": "TIMEOUT", "reason": f"{what}: over {timeout:g} s",
                       "k": w.at and w.at[0]}
            if res is None:
                continue
            if res["status"] in ("CRASH", "TIMEOUT"):
                w.kill()
                w = workers[i] = Worker()
            on_result(res)
            w.case = None
            busy -= 1
            if pending:
                w.submit(pending.pop()); busy += 1
    for w in workers:
        w.conn.send(None)


def _short(texts, n=90):
    s = " | ".join(t.replace("\n", "\\n") for t in texts) or "(nothing)"
    return s if len(s) <= n else s[:n - 3] + "..."


def line_for(res):
    st = res["status"]
    head = f"{st:<15} {res['case']:<34}"
    if st == "FAIL":
        v = next(s for s in res["statements"] if s["verdict"] == "fail")
        return (f"{head} k={v['k']} [{v['subtype']}] {v['reason']}\n"
                f"{'':16}src:    {_short([v['src']])}\n"
                f"{'':16}golden: {_short(v['golden'])}\n{'':16}ours:   {_short(v['ours'])}")
    if st in ("CRASH", "TIMEOUT"):
        return f"{head} {res['reason'].strip().splitlines()[-1]}"
    return f"{head} {res.get('time', 0):.1f}s" + ("  (golden is stale)" if res.get("stale_golden") else "")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("filters", nargs="*", help="substrings of case names (source/case)")
    ap.add_argument("--jobs", type=int, default=6)
    ap.add_argument("--timeout", type=float, default=60)
    ap.add_argument("-v", "--verbose", action="store_true", help="print every statement diff")
    ap.add_argument("--json", default=str(ROOT / "tests" / "out" / "maple_report.json"))
    a = ap.parse_args()

    cases = discover(a.filters)
    missing = [c for c in cases if not Path(c["golden"]).exists()]
    cases = [c for c in cases if Path(c["golden"]).exists()]
    for c in missing:
        print(f"{'NO-GOLDEN':<15} {c['name']}")
    if not cases:
        sys.exit("no cases matched")
    results, t0 = [], time.monotonic()

    def on_result(res):
        results.append(res)
        print(line_for(res), flush=True)
        if a.verbose:
            for v in res.get("statements", []):
                if v["verdict"] == "fail" or v["notes"]:
                    print(f"{'':6}k={v['k']} {v['verdict']} [{v['subtype']}] {v['reason'] or ''} "
                          f"{'; '.join(v['notes'])}\n{'':10}golden: {_short(v['golden'], 200)}\n"
                          f"{'':10}ours:   {_short(v['ours'], 200)}")

    run_all(cases, a.jobs, a.timeout, on_result)
    results.sort(key=lambda r: r["case"])
    totals = {}
    for r in results:
        totals[r["status"]] = totals.get(r["status"], 0) + 1
    nstmt = sum(len(r.get("statements", [])) for r in results)
    npass = sum(v["verdict"] == "pass" for r in results for v in r.get("statements", []))
    print(f"TOTAL {len(results)} cases: " + ", ".join(f"{k}={v}" for k, v in sorted(totals.items()))
          + f"; statements {npass}/{nstmt} pass; {time.monotonic() - t0:.0f}s")
    out = Path(a.json)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"totals": totals, "statements": {"pass": npass, "total": nstmt},
                               "cases": results}, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
    sys.exit(1 if any(r["status"] in BAD for r in results) else 0)


if __name__ == "__main__":
    main()
