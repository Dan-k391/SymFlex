"""Generate golden outputs for FlexPDE cases by running real FlexPDE 8 Lite in batch mode.

Usage: python scripts/gen_golden_flex.py [paths/globs ...] [--jobs N] [--force] [--out DIR]
Default input: corpus/cases/**/*.pde -> corpus/golden/<source>/<case>.json

How it works: each case is copied to .work/flex/<source>/<case>/ and a PLOTS section is appended
(before END, the signature after END is dropped) that writes machine-readable text files:
  * table(t, <every REPORT expr>, val(<var>,P0)...) FORMAT  -> reports at the final time
    (FlexPDE 8 rejects field values without a location in REPORT, so every REPORT expression is
    location free and can be evaluated anywhere; TABLE/history exports carry 11 digits while
    SUMMARY exports only carry 7)
  * history(<args>, <vs expr>) at (P) EXPORT FORMAT "#t#r,#i" per script history plot
  * spatial problems (ngrid != 1): table(vars) on a 21x21 grid (values) + contour(var) export
    DROPOUT (exterior mask)
For time problems the section starts with "for t = endtime", which also fires on a HALT.
Original lines are untouched, so FlexPDE error line numbers refer to the case file.

Golden "history[].plot" is the 0-based index of the history statement among all display
statements (lines starting with a plot keyword) of the PLOTS/HISTORIES sections.
Extra key "vs_values" holds the vs-expression values when vs is set. Exterior field points are
null (JSON has no NaN).
"""
import argparse, glob, json, math, os, re, shutil, subprocess, sys
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FLEX = "D:/Maple/FlexPDE8/FlexPDE8n.exe"
WORK = os.path.join(ROOT, ".work", "flex")
TIMEOUT = 180
GRID = 21
SECTIONS = ("title", "coordinates", "variables", "select", "definitions", "initial", "equations",
            "constraints", "extrusion", "boundaries", "front", "resolve", "time", "monitors",
            "plots", "histories", "end", "global", "parameters", "materials", "limits")
PLOT_KW = {"history", "histories", "elevation", "contour", "surface", "vector", "grid", "summary",
           "table", "cdf", "tecplot", "vtk", "vtklin", "transfer", "fieldmap", "glcontour",
           "glsurface", "glgrid", "mode_summary"}


def strip_comments(src):
    """Blank out {..} /*..*/ (nested) and !.. comments, keeping strings and line structure."""
    out, i, n, stack, quote = [], 0, len(src), [], None
    while i < n:
        c = src[i]
        if stack:
            if src.startswith("/*", i) or c == "{":
                stack.append("*/" if c == "/" else "}")
            elif src.startswith(stack[-1], i):
                k = len(stack.pop())
                out.append(" " * k); i += k; continue
            out.append("\n" if c == "\n" else " "); i += 1; continue
        if quote:
            out.append(c); i += 1
            if c == quote or c == "\n":
                quote = None
            continue
        if c in "'\"":
            quote = c
        elif c == "{" or src.startswith("/*", i):
            stack.append("}" if c == "{" else "*/")
            k = 1 if c == "{" else 2
            out.append(" " * k); i += k; continue
        elif c == "!":
            j = src.find("\n", i)
            j = n if j < 0 else j
            out.append(" " * (j - i)); i = j; continue
        out.append(c); i += 1
    return "".join(out)


def balanced(s, i):
    """s[i] == '(' -> index just past the matching ')'."""
    depth = 0
    for j in range(i, len(s)):
        if s[j] == "(":
            depth += 1
        elif s[j] == ")":
            depth -= 1
            if depth == 0:
                return j + 1
    return len(s)


def split_top(s):
    parts, depth, cur = [], 0, ""
    for c in s:
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
        if c == "," and depth == 0:
            parts.append(cur.strip()); cur = ""
        else:
            cur += c
    if cur.strip():
        parts.append(cur.strip())
    return parts


def cut_at_kw(s, kws):
    """Cut s at the first depth-0 whole word in kws (outside strings)."""
    depth, quote = 0, None
    for m in re.finditer(r"[()'\"]|[A-Za-z_]\w*", s):
        t = m.group()
        if quote:
            if t == quote:
                quote = None
        elif t in "'\"":
            quote = t
        elif t == "(":
            depth += 1
        elif t == ")":
            depth -= 1
        elif depth == 0 and t.lower() in kws:
            return s[:m.start()], s[m.start():]
    return s, ""


def sections(code):
    """[(name, start, end)] over the comment-stripped code."""
    marks = [(m.group(1).lower(), m.start()) for m in
             re.finditer(r"(?im)^[ \t]*([A-Za-z_]+)\b", code) if m.group(1).lower() in SECTIONS]
    # a definition like "time = 3" is not a section header, but "Time = 0 to 3" is
    marks = [(k, p) for k, p in marks if not re.match(r"[ \t]*[A-Za-z_]+[ \t]*=", code[p:p + 200])
             or re.match(r"[ \t]*time[ \t]*=[^\n]*\bto\b", code[p:p + 200], re.I)]
    return [(k, p, marks[i + 1][1] if i + 1 < len(marks) else len(code)) for i, (k, p) in enumerate(marks)]


def parse(src):
    code = strip_comments(src)
    secs = sections(code)
    body = lambda name: "\n".join(code[p:e] for k, p, e in secs if k == name)
    info = {"title": None, "dim": 2, "ngrid": None, "time": False, "vars": [], "p0": None,
            "histories": [], "reports": [], "end": None}
    m = re.search(r"""title\s*(['"])(.*?)\1""", body("title"), re.I | re.S)
    info["title"] = m.group(2) if m else None
    coords = body("coordinates").lower()
    info["dim"] = 1 if re.search(r"cartesian1|cylinder1|sphere1", coords) else 3 if "cartesian3" in coords else 2
    m = re.search(r"ngrid\s*=\s*(\d+)", body("select"), re.I)
    info["ngrid"] = int(m.group(1)) if m else None
    info["time"] = any(k == "time" for k, _, _ in secs)
    v = re.sub(r"(?i)^\s*variables", "", body("variables"))
    i = 0
    while True:
        m = re.compile(r"[A-Za-z_]\w*").search(v, i)
        if not m:
            break
        name, i = m.group(), m.end()
        rest = v[i:]
        k = len(rest) - len(rest.lstrip())
        if rest[k:k + 1] == "(":
            i += balanced(rest, k)
        m2 = re.match(r"\s*=\s*vector\s*\(([^)]*)\)", v[i:], re.I)
        if m2:
            info["vars"] += [c.strip() for c in m2.group(1).split(",") if c.strip()]
            i += m2.end()
        elif name.lower() not in ("steady", "array", "complex", "vector", "group", "global",
                                  "threshold", "range", "order", "integer"):
            info["vars"].append(name)
    m = re.search(r"(?i)\bstart\b\s*(?:(['\"]).*?\1)?\s*\(", body("boundaries"))
    if m:
        b = body("boundaries")
        info["p0"] = b[m.end() - 1:balanced(b, m.end() - 1)]
    # plots / histories: display statements, history plots, reports
    idx = -1
    for k, p, e in secs:
        if k not in ("plots", "histories"):
            continue
        text = code[p:e]
        text = re.sub(r"(?i)^\s*(plots|histories)", lambda mm: " " * len(mm.group()), text)
        for line in text.split("\n"):
            m = re.match(r"\s*([A-Za-z_]\w*)", line)
            if m and m.group(1).lower() in PLOT_KW:
                idx += 1
                if m.group(1).lower() == "history":
                    h = parse_history(line[m.end():])
                    if h:
                        h["plot"] = idx
                        info["histories"].append(h)
            info["reports"] += parse_reports(line)
    m = None
    for m in re.finditer(r"(?im)^[ \t]*end\b", code):
        pass
    info["end"] = m.start() if m else len(src)
    return info


def parse_history(s):
    s0 = s.lstrip()
    if not s0.startswith("("):
        return None
    j = balanced(s0, 0)
    args = split_top(s0[1:j - 1])
    rest = s0[j:]
    pts = []
    m = re.match(r"\s*at\s*", rest, re.I)
    if m:
        rest = rest[m.end():]
        while rest.lstrip().startswith("("):
            r = rest.lstrip()
            q = balanced(r, 0)
            pts.append(r[:q]); rest = r[q:]
    vs = None
    m = re.match(r"\s*vs\b", rest, re.I)
    if m:
        vs = cut_at_kw(rest[m.end():], {"as", "report", "export", "print", "file", "format",
                                         "range", "fixed", "log", "points", "printonly"})[0].strip() or None
    # shortcut: only the first AT point is exported; multi-point histories lose the other points
    return {"args": args, "at": pts[0] if pts else None, "vs": vs}


def parse_reports(line):
    out = []
    pieces = re.split(r"(?i)\breport\b", line)
    for piece in pieces[1:]:
        expr, tail = cut_at_kw(piece, {"as", "report"} | PLOT_KW)
        expr = expr.strip()
        label = None
        m = re.match(r"""\s*as\s*(['"])(.*?)\1""", tail, re.I)
        if m:
            label = m.group(2)
        if not expr or expr[0] in "'\"" or (expr.startswith("(") and expr[1:].lstrip()[:1] in "'\""):
            continue  # REPORT 'string'
        exprs = [expr]
        if expr.startswith("(") and balanced(expr, 0) == len(expr):
            exprs = split_top(expr[1:-1])
        for e in exprs:
            out.append({"label": label if label and len(exprs) == 1 else e, "expr": e})
    return out


def inject(src, info):
    p0 = info["p0"] or ("(0)" if info["dim"] == 1 else "(0,0)")
    loc = p0[1:-1]
    fmt = '"#x#r,#i"' if info["dim"] == 1 else '"#x,#y#r,#i"'
    lines = ["", "PLOTS { symflex golden exports }"]
    if info["time"]:
        lines.append("for t = endtime")
    rep = (["t"] if info["time"] else []) + [r["expr"] for r in info["reports"]] + \
          ["val(%s,%s)" % (v, loc) for v in info["vars"]]
    if rep:
        lines.append("table(%s) points=2 format %s file 'sx_rep.txt'" % (", ".join(rep), fmt))
    if info["time"]:
        for i, h in enumerate(info["histories"]):
            args = h["args"] + ([h["vs"]] if h["vs"] else [])
            at = " at " + h["at"] if h["at"] else ""
            lines.append("history(%s)%s export format \"#t#r,#i\" file 'sx_hist_%d.txt'"
                         % (", ".join(args), at, i))
    if info["ngrid"] != 1 and info["vars"] and info["dim"] in (1, 2):
        vs = ", ".join(info["vars"])
        lines.append("table(%s) points=%d format %s file 'sx_field.txt'" % (vs, GRID, fmt))
        if info["dim"] == 2:
            lines.append("contour(%s) export(%d) dropout format \"#x,#y,#1\" file 'sx_mask.txt'"
                         % (info["vars"][0], GRID))
    lines.append("END")
    return src[:info["end"]].rstrip() + "\n" + "\n".join(lines) + "\n"


def num(s):
    try:
        return float(s)
    except ValueError:
        return float("nan")


def read_rows(path):
    """Data rows of a FORMAT export: list of (exterior, [floats])."""
    rows = []
    with open(path, encoding="latin-1") as f:
        text = f.read()
    hdr = text.find("}")
    for line in text[hdr + 1:].splitlines():
        line = line.strip()
        if not line:
            continue
        ext = line.startswith("{")
        if ext:
            line = line.strip("{} ").split(":", 1)[-1]
        rows.append((ext, [num(x) for x in line.split(",")]))
    return rows


def last_file(outdir, stem):
    """sx_rep.txt or the highest-numbered sx_rep_<n>.txt."""
    best, bn = None, -1
    for f in os.listdir(outdir):
        m = re.fullmatch(re.escape(stem) + r"(?:_(\d+))?\.txt", f)
        if m and int(m.group(1) or 0) > bn:
            best, bn = os.path.join(outdir, f), int(m.group(1) or 0)
    return best


def parse_log(path):
    errors, halted, done, last_t = [], False, False, None
    if not os.path.exists(path):
        return ["no log written"], halted, done, last_t
    with open(path, encoding="latin-1") as f:
        lines = f.read().splitlines()
    started = False
    cur = None
    for ln in lines:
        if ln.startswith("START "):
            started = True; continue
        if not started:
            continue
        if ln.startswith(" +"):
            msg = ln.split("|", 2)[-1].strip()
            m = re.search(r"Time=\s*(\S+)", msg)
            if m:
                last_t = num(m.group(1))
            if "Halt on User Condition" in msg:
                halted = True
            if "--DONE--" in msg:
                done = True
            if "*****" in msg:
                errors.append(msg.strip("* ").strip())
            cur = None
            continue
        if ln.startswith(" Stop Time"):
            break
        if not ln.strip():
            cur = None; continue
        if cur is None:
            errors.append(ln.strip()); cur = len(errors) - 1
        else:
            errors[cur] += " " + ln.strip()
    return errors, halted, done, last_t


def clean(x):
    return None if isinstance(x, float) and (math.isnan(x) or math.isinf(x)) else x


def run_case(path, out_root):
    path = os.path.abspath(path)
    source, name = os.path.basename(os.path.dirname(path)), os.path.splitext(os.path.basename(path))[0]
    wdir = os.path.join(WORK, source, name)
    shutil.rmtree(wdir, ignore_errors=True)
    os.makedirs(wdir)
    with open(path, encoding="latin-1") as f:
        src = f.read()
    res = _run(path, src, source, name, wdir, out_root)
    if res["status"] == "error" and any("no Location Specified" in e for e in res["errors"]):
        # FlexPDE 6 (used by the course) accepted "report rx"; v8 needs val(rx,pt). Golden comes from the patched script.
        p0 = parse(src)["p0"].strip("()")
        patched = re.sub(r"""(?im)^(\s*report\s+)(?!val\s*\()([^!'"\n]+?)(\s*(?:!.*)?)$""", lambda m: "%sval(%s,%s)%s" % (m.group(1), m.group(2), p0, m.group(3))
                         if m.group(2).strip().lower() != "t" else m.group(0), src)
        shutil.rmtree(wdir, ignore_errors=True); os.makedirs(wdir)
        res = _run(path, patched, source, name, wdir, out_root)
        res["patched"] = "bare 'report X' rewritten to 'report val(X,%s)' for FlexPDE 8" % p0
        with open(os.path.join(out_root, source, name + ".json"), "w", encoding="utf-8") as f:
            json.dump(res, f, allow_nan=False)
    return res


def _run(path, src, source, name, wdir, out_root):
    info = parse(src)
    work_pde = os.path.join(wdir, name + ".pde")
    with open(work_pde, "w", encoding="latin-1", newline="") as f:
        f.write(inject(src, info))
    n_orig = src[:info["end"]].count("\n") + 1
    status = "ok"
    try:
        subprocess.run([FLEX, "-S", work_pde], cwd=wdir, timeout=TIMEOUT,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        status = "timeout"
    outdir = os.path.join(wdir, name + "_output")
    errors, halted, done, last_t = parse_log(os.path.join(outdir, name + "_log.txt"))
    errors = ["[injected export] " + e if (m := re.match(r"Line (\d+)", e)) and int(m.group(1)) > n_orig
              else e for e in errors]
    if status == "ok" and (errors or not done):
        status = "error"
        if not errors:
            errors = ["FlexPDE did not finish (no --DONE-- in log)"]
    res = {"case": source + "/" + name, "file": os.path.relpath(path, ROOT).replace("\\", "/"),
           "status": status, "errors": errors, "title": info["title"],
           "end_time": last_t if info["time"] else None, "halted": halted,
           "reports": [], "history": [], "fields": {}}
    if os.path.isdir(outdir):
        collect(res, info, outdir)
    os.makedirs(os.path.join(out_root, source), exist_ok=True)
    with open(os.path.join(out_root, source, name + ".json"), "w", encoding="utf-8") as f:
        json.dump(res, f, allow_nan=False)
    return res


def collect(res, info, outdir):
    f = last_file(outdir, "sx_rep")
    if f:
        rows = read_rows(f)
        if rows:
            vals = rows[0][1]
            labels = (["t"] if info["time"] else []) + [r["label"] for r in info["reports"]] + \
                     ["val(%s)" % v for v in info["vars"]]
            vals = vals[len(vals) - len(labels):]
            if info["time"]:
                res["end_time"] = clean(vals[0]); vals, labels = vals[1:], labels[1:]
            res["reports"] = [{"label": l, "value": clean(v)} for l, v in zip(labels, vals)]
    for i, h in enumerate(info["histories"]):
        f = os.path.join(outdir, "sx_hist_%d.txt" % i)
        if not os.path.exists(f):
            continue
        rows = [r for _, r in read_rows(f)]
        col = lambda k: [clean(r[k]) if k < len(r) else None for r in rows]
        entry = {"plot": h["plot"], "vs": h["vs"], "t": col(0),
                 "series": [{"label": a, "values": col(1 + k)} for k, a in enumerate(h["args"])]}
        if h["vs"]:
            entry["vs_values"] = col(1 + len(h["args"]))
        res["history"].append(entry)
    f = last_file(outdir, "sx_field")
    if f:
        rows = read_rows(f)
        mask = set()
        mf = last_file(outdir, "sx_mask")
        if mf:
            mask = {(round(r[0], 9), round(r[1], 9)) for ext, r in read_rows(mf) if ext}
        nd = 1 if info["dim"] == 1 else 2
        xs = sorted({round(r[0], 9) for _, r in rows})
        ys = sorted({round(r[1], 9) for _, r in rows}) if nd == 2 else []
        for k, v in enumerate(info["vars"]):
            if nd == 1:
                vals = [clean(r[1 + k]) for _, r in rows]
            else:
                grid = {(round(r[0], 9), round(r[1], 9)): r[2 + k] for _, r in rows}
                vals = [[None if (x, y) in mask else clean(grid.get((x, y), float("nan")))
                         for x in xs] for y in ys]
            res["fields"][v] = {"x": xs, "y": ys, "values": vals}


def self_check():
    info = parse("TITLE 'a'\nCOORDINATES cartesian1\nVARIABLES\n r(threshold=1e-2) = vector(rx,ry)\n"
                 " h {c} v ! c\nSELECT ngrid = 1\nBOUNDARIES\n REGION 1 START(0) LINE TO (1)\n"
                 "TIME 0 TO 2 halt(v<0)\nPLOTS\nfor t= 0 by endtime/50 to endtime\n"
                 " history(ry, a/2) at (0) vs rx report val(rx,0) as 'X'\nreport (t, 2*t)\n"
                 "report 'hi'\n!report h\nSUMMARY\nreport KE\nEND 'sig'\n")
    assert info["vars"] == ["rx", "ry", "h", "v"], info["vars"]
    assert info["time"] and info["ngrid"] == 1 and info["dim"] == 1 and info["p0"] == "(0)"
    assert info["histories"] == [{"args": ["ry", "a/2"], "at": "(0)", "vs": "rx", "plot": 0}], info["histories"]
    assert [r["label"] for r in info["reports"]] == ["X", "t", "2*t", "KE"], info["reports"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="*")
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--out", default=os.path.join(ROOT, "corpus", "golden"))
    a = ap.parse_args()
    self_check()
    pats = a.paths or [os.path.join(ROOT, "corpus", "cases", "**", "*.pde")]
    files = sorted({os.path.abspath(f) for p in pats for f in glob.glob(p, recursive=True)
                    if f.lower().endswith(".pde")})
    todo = []
    for f in files:
        g = os.path.join(a.out, os.path.basename(os.path.dirname(f)), os.path.splitext(os.path.basename(f))[0] + ".json")
        if a.force or not os.path.exists(g) or os.path.getmtime(g) < os.path.getmtime(f):
            todo.append(f)
    print("%d cases, %d to run" % (len(files), len(todo)))
    with ThreadPoolExecutor(a.jobs) as ex:
        for r in ex.map(lambda f: run_case(f, a.out), todo):
            print("%-34s %-7s t=%-10s halted=%-5s reports=%d hist=%d fields=%d %s" % (
                r["case"], r["status"], r["end_time"], r["halted"], len(r["reports"]),
                len(r["history"]), len(r["fields"]), "; ".join(r["errors"])[:90]))
            sys.stdout.flush()


if __name__ == "__main__":
    main()
