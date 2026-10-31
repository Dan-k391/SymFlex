"""Generate golden outputs for Maple test cases by running them through real cmaple.

Usage: python scripts/gen_golden_maple.py [paths or globs...] [--jobs N] [--force] [--out DIR]
  default input: corpus/cases/**/*.mpl ; output: corpus/golden/<source>/<case>.json
  (--out is for development: write goldens somewhere else)

How it works: each case is split into top-level statements (scripts/maple_split.py) and a driver
.mpl is built that sets interface(prettyprint=0, screenwidth=infinity, warnlevel=3, errorbreak=0),
plotsetup(jpeg, plotoutput="nul") and _Env_Plot_StandardInterface=true (so plot structures are the
GUI's: _AXIS[n](_MODE(1)) log axes, _PLOTARRAY, ...), re-applied after every top-level restart.
Before statement k it prints "@@STMT k". Statements are run as follows:
  * expression ending in ';' (or nothing):  _SFv := <expr>:  then _SFshow() prints the value
    between @@VAL/@@ENDVAL, or @@P plot records if it is a plot.  The assignment updates %, %%, %%%
    exactly like the bare statement (NULL results do not update ditto, same as Maple).
  * assignment ending in ';': run natively (Maple prints 'x := ...'); if the LHS is a plain name
    whose value is a plot, the 'p := INTERFACE_PLOT(...)' line is replaced by a plot output with
    "name".
  * restart, loops, if, read, ... and anything ending in ':': run natively.
Output kinds: 'error' (Error, ... and cmaple syntax errors), 'warning', 'plot', 'math' (the value
display), 'print' (everything else printed while the statement ran). For natively-run ';'
statements (assignments, loops, if) every printed line is 'math' since prints cannot be told apart
from displayed values there. Consecutive 'print' lines of one statement are merged into one entry.
A trailing statement with no terminator is run as if it ended in ';' (worksheet behaviour; cmaple
itself would raise a syntax error). warnlevel=3 is the GUI default (4 adds library noise such as
"hfarray is obsolete" from odeplot). Plots shown inside loops/if or via print() are not captured.
More than MAX_OUTPUTS outputs per statement are cut; the last kept one gets "truncated": N.

Plot output: {"kind": "plot", "plot": P} where P is
  {"type": "2d"|"3d", "name", "title"?, "xlabel"?, "ylabel"?, "zlabel"?, "xlog", "ylog",
   "options": [raw Maple option strings, _ATTRIBUTE removed],
   "objects": [{"kind": "curve"|"points"|"polygon"|"grid"|"mesh"..., "options": "[COLOUR(...),...]",
                "legend"?, "ranges": [[lo,hi],...], "points": [[x,y(,z)],...] (<=400, uniform subsample)
                | "z": [[...]] for grids (<=60x60)}],
   "frames": [P...] for animations}
  or {"type": "array", "rows", "cols", "plots": [P|null, ...] row-major, "options"}.
Numbers are %.10g; NaN/Inf become null. Use --selftest to check the toolchain end to end.
"""
import argparse, glob, json, os, re, subprocess, sys, tempfile
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from maple_split import split_statements, is_assignment, first_word

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CMAPLE = 'D:/Maple/Installed/bin.X86_64_WINDOWS/cmaple.exe'
TIMEOUT = 90
MAX_OUTPUTS = 500   # per statement
NATIVE_WORDS = {'for', 'from', 'by', 'to', 'while', 'do', 'if', 'try', 'use', 'local', 'global',
                'export', 'read', 'save', 'restart', 'quit', 'done', 'stop', 'return', 'break',
                'next', 'error'}

SETUP = r'''interface(prettyprint=0, screenwidth=infinity, warnlevel=3, errorbreak=0):
plotsetup(jpeg, plotoutput="nul"):
_Env_Plot_StandardInterface := true:
_SFisplot := v -> type(v, function) and member(op(0, v), {PLOT, PLOT3D, _PLOTARRAY}):
_SFnum := proc(x) local y; y := evalf(x); if type(y, numeric) then sprintf("%.10g", y) else "NaN" end if end proc:
_SFidx := proc(lo, hi, cap) local i; `if`(hi-lo+1 <= cap, [$lo..hi], [seq(lo + round((i-1)*(hi-lo)/(cap-1)), i = 1..cap)]) end proc:
_SFdata := proc(A, kind) local d, I1, I2, I3, i, j, k;
  d := [rtable_dims(A)];
  if nops(d) = 1 then return cat("[", StringTools:-Join([seq(_SFnum(A[i]), i = _SFidx(op(d[1]), 400))], ","), "]") end if;
  if kind = "grid" or nops(d) = 3 then I1 := _SFidx(op(d[1]), 60); I2 := _SFidx(op(d[2]), 60)
  else I1 := _SFidx(op(d[1]), 400); I2 := [$d[2]] end if;
  if nops(d) = 2 then
    cat("[", StringTools:-Join([seq(cat("[", StringTools:-Join([seq(_SFnum(A[i, j]), j = I2)], ","), "]"), i = I1)], ","), "]")
  else I3 := [$d[3]];
    cat("[", StringTools:-Join([seq(cat("[", StringTools:-Join([seq(cat("[", StringTools:-Join([seq(_SFnum(A[i, j, k]), k = I3)], ","), "]"), j = I2)], ","), "]"), i = I1)], ","), "]")
  end if
end proc:
_SFclean := q -> subsindets(q, specfunc(_ATTRIBUTE), () -> NULL):
_SFemit1 := proc(p) local h, q, M, d, e, i, j, r, c, f, rg;
  h := op(0, p);
  if h = _PLOTARRAY then
    M := op(1, p); if type(M, list) then M := Matrix(M) end if;
    d := [rtable_dims(M)];
    if nops(d) = 1 then r := 1; c := op(2, d[1]) - op(1, d[1]) + 1 else r := op(2, d[1]) - op(1, d[1]) + 1; c := op(2, d[2]) - op(1, d[2]) + 1 end if;
    printf("@@P ARRAY %d %d\n", r, c);
    for e in [seq(seq(`if`(nops(d) = 1, M[op(1, d[1]) + j - 1], M[op(1, d[1]) + i - 1, op(1, d[2]) + j - 1]), j = 1..c), i = 1..r)] do
      if _SFisplot(e) then _SFemit1(e) else printf("@@P EMPTY\n") end if
    end do;
    for q in [op(2..-1, p)] do printf("@@P OPT %a\n", _SFclean(q)) end do;
    printf("@@P ENDARRAY\n")
  else
    printf("@@P PLOT %a\n", h);
    for q in [op(p)] do
      if type(q, specfunc(_ATTRIBUTE)) then next
      elif type(q, specfunc(ANIMATE)) then
        printf("@@P ANIM %d\n", nops(q));
        for f in [op(q)] do _SFemit1(h(op(f))) end do;
        printf("@@P ENDANIM\n")
      elif type(q, function) and member(op(0, q), {CURVES, POINTS, POLYGONS, MESH, GRID, ISOSURFACE}) then
        d := [plottools:-getdata(h(q))];
        if d <> [] and type(d[1], string) then d := [d] end if;
        for e in d do
          printf("@@P OBJ %s %a\n", e[1], _SFclean(select(type, [op(q)], function)));
          printf("@@P RANGES [%s]\n", StringTools:-Join([seq(cat("[", _SFnum(lhs(rg)), ",", _SFnum(rhs(rg)), "]"), rg = e[2])], ","));
          printf("@@P DATA %s\n", _SFdata(e[3], e[1]))
        end do
      else printf("@@P OPT %a\n", _SFclean(q))
      end if
    end do;
    printf("@@P ENDPLOT\n")
  end if;
  NULL
end proc:
_SFemit := proc(p, nm) printf("@@P BEGIN %s\n", nm); try _SFemit1(p) catch: printf("@@P FAIL %s\n", StringTools:-SubstituteAll(lastexception[2], "\n", " ")) end try; printf("@@P END\n"); NULL end proc:
_SFshow := proc() local v;
  if not assigned(_SFv) then return NULL end if;
  v := [eval(_SFv, 1)];
  if v = [] then return NULL end if;
  if nops(v) = 1 and _SFisplot(v[1]) then _SFemit(v[1], ""); return NULL end if;
  printf("@@VAL\n");
  # print() would show the body of a name bound to a proc/table; the top level shows just the name
  if andmap(type, v, name) then printf("%s\n", StringTools:-Join(map(x -> sprintf("%a", x), v), ", ")) else print(op(v)) end if;
  printf("@@ENDVAL\n"); NULL
end proc:
_SFchk := proc(nm) local v; v := eval(nm); if _SFisplot(v) then _SFemit(v, convert(nm, string)) end if; NULL end proc:
'''

_SIMPLE_LHS = re.compile(r'^\s*([A-Za-z_~][A-Za-z0-9_~]*)\s*:=')


def build_driver(stmts):
    parts = [SETUP]
    for k, st in enumerate(stmts, 1):
        src, term = st['src'], st['terminator'] or ';'
        parts.append('printf("@@STMT %d\\n", %d): unassign(\'_SFv\'):\n' % (k, k))
        word = first_word(src)
        if src.strip() == 'restart':
            parts.append('restart:\n' + SETUP)
        elif term == ';' and word not in NATIVE_WORDS and src[:1] not in '$?' and not is_assignment(src):
            st['mode'] = 'expr'
            parts.append('_SFv := %s:\n_SFshow():\n' % src)
        else:
            parts.append(src + term + '\n')
            m = _SIMPLE_LHS.match(src)
            if term == ';' and m and is_assignment(src):
                parts.append("_SFchk('%s'):\n" % m.group(1))
    parts.append('printf("@@STMT %d\\n", 0):\n')   # end sentinel
    return ''.join(parts)


def _floats(s):
    return json.loads(re.sub(r'-?\bInf\b|\bNaN\b', 'null', s))


def _split_args(s):
    out, depth, cur, q = [], 0, '', None
    for ch in s:
        if q:
            q = None if ch == q else q
        elif ch in '"`':
            q = ch
        elif ch in '([{':
            depth += 1
        elif ch in ')]}':
            depth -= 1
        elif ch == ',' and depth == 0:
            out.append(cur.strip()); cur = ''; continue
        cur += ch
    return out + [cur.strip()] if cur.strip() else out


def _unq(s):
    s = re.sub(r'Typesetting:-m\w+\("([^"]*)"[^()]*\)', r'\1', s)   # GUI typesets name legends: mi("x") -> x
    return s[1:-1] if len(s) >= 2 and s[0] == s[-1] and s[0] in '"`' else s


def _fn_args(opts, name):
    """Args of the first NAME(...) item in a list of option strings."""
    for o in opts:
        if o.startswith(name + '('):
            return _split_args(o[len(name) + 1:-1])
    return None


def _decorate(node):
    """Add title/labels/log flags/legends parsed from the raw option strings."""
    opts = node['options']
    t = _fn_args(opts, 'TITLE')
    if t:
        node['title'] = _unq(t[0])
    labels = _fn_args(opts, 'AXESLABELS') or []
    for key, v in zip(('xlabel', 'ylabel', 'zlabel'), labels):
        node[key] = _unq(v)
    joined = ' '.join(opts)
    node['xlog'] = '_AXIS[1](_MODE(1))' in joined
    node['ylog'] = '_AXIS[2](_MODE(1))' in joined
    for ob in node['objects']:
        lg = re.search(r'LEGEND\((.*?)\)(,|\]$)', ob['options'])
        if lg:
            ob['legend'] = _unq(lg.group(1))


def parse_plot(lines):
    """Turn the @@P record lines (without the '@@P ' prefix) into a plot dict."""
    name, root, stack = '', None, []
    for ln in lines:
        tag, _, rest = ln.partition(' ')
        top = stack[-1] if stack else None
        if tag in ('ARRAY', 'PLOT'):
            if tag == 'ARRAY':
                r, c = map(int, rest.split())
                node = {'type': 'array', 'rows': r, 'cols': c, 'plots': [], 'options': []}
            else:
                node = {'type': '3d' if rest.strip() == 'PLOT3D' else '2d', 'options': [], 'objects': []}
            if top is None:
                root = node
            else:
                top.setdefault('plots' if top['type'] == 'array' else 'frames', []).append(node)
            stack.append(node)
        elif tag == 'BEGIN':
            name = rest.strip()
        elif tag == 'EMPTY':
            top['plots'].append(None)
        elif tag == 'OPT':
            top['options'].append(rest)
        elif tag == 'OBJ':
            kind, _, o = rest.partition(' ')
            top['objects'].append({'kind': kind, 'options': o})
        elif tag == 'RANGES':
            top['objects'][-1]['ranges'] = _floats(rest)
        elif tag == 'DATA':
            ob = top['objects'][-1]
            ob['z' if ob['kind'] == 'grid' else 'points'] = _floats(rest)
        elif tag in ('ENDPLOT', 'ENDARRAY'):
            if top['type'] != 'array':
                _decorate(top)
            stack.pop()
        elif tag == 'FAIL':
            root = dict(root or {}, error=rest)
    root = root or {'type': None}
    root['name'] = name
    return root


_SYNTAX = re.compile(r'^on line \d+ of "[^"]*", (syntax error.*)$')


def parse_output(out, stmts):
    per = {}
    cur = None
    lines = [l for l in out.replace('\r\n', '\n').rstrip('\n').split('\n')
             if not l.startswith('maple: fatal error')]   # printed when a timed-out kernel is killed
    i = 0
    while i < len(lines):
        ln = lines[i]
        m = re.match(r'^@@STMT (\d+)$', ln)
        if m:
            cur = int(m.group(1)) or None
            i += 1
            continue
        if cur is None:
            i += 1
            continue
        st = stmts[cur - 1]
        outs = per.setdefault(cur, [])
        if ln == '@@VAL':
            j = lines.index('@@ENDVAL', i) if '@@ENDVAL' in lines[i:] else len(lines)
            outs.append({'kind': 'math', 'text': '\n'.join(lines[i + 1:j])})
            i = j + 1
            continue
        if ln.startswith('@@P BEGIN'):
            j = i
            while j < len(lines) and lines[j] != '@@P END':
                j += 1
            plot = parse_plot([l[4:] for l in lines[i:j] if l.startswith('@@P ')])
            if plot['name']:   # replace Maple's own 'p := INTERFACE_PLOT(...)' display
                pre = plot['name'] + ' := '
                outs[:] = [o for o in outs if not (o['kind'] == 'math' and o['text'].startswith(pre))]
            outs.append({'kind': 'plot', 'text': '', 'plot': plot})
            i = j + 1
            continue
        sm = _SYNTAX.match(ln)
        if sm:
            outs.append({'kind': 'error', 'text': 'Error, ' + sm.group(1)})
            i += 3 if i + 2 < len(lines) and lines[i + 2].strip() == '^' else 1   # skip echo + caret
            continue
        if ln.startswith('Error, '):
            outs.append({'kind': 'error', 'text': ln})
        elif ln.startswith('Warning, '):
            outs.append({'kind': 'warning', 'text': ln})
        elif ln == '' and i == len(lines) - 1:
            pass
        else:
            kind = 'print' if st.get('mode') == 'expr' or st['terminator'] == ':' else 'math'
            if kind == 'print' and outs and outs[-1]['kind'] == 'print':
                outs[-1]['text'] += '\n' + ln   # keep multi-line printf output in one entry
            else:
                outs.append({'kind': kind, 'text': ln})
        i += 1
    for outs in per.values():   # runaway loops: keep the first MAX_OUTPUTS, note how many were dropped
        if len(outs) > MAX_OUTPUTS:
            outs[MAX_OUTPUTS - 1]['truncated'] = len(outs) - MAX_OUTPUTS
            del outs[MAX_OUTPUTS:]
    return per


def kill_tree(proc):
    subprocess.run(['taskkill', '/F', '/T', '/PID', str(proc.pid)], capture_output=True)


def run_code(code):
    """Run Maple source through cmaple; returns (statements, {k: outputs}, status, raw stdout)."""
    stmts = split_statements(code)
    with tempfile.TemporaryDirectory(prefix='sfgold_') as tmp:
        drv = os.path.join(tmp, 'driver.mpl')
        open(drv, 'w', encoding='utf-8').write(build_driver(stmts))
        proc = subprocess.Popen([CMAPLE, '-q', drv], cwd=tmp, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
        status = 'ok'
        try:
            raw, _ = proc.communicate(timeout=TIMEOUT)
        except subprocess.TimeoutExpired:
            kill_tree(proc)
            raw, _ = proc.communicate()
            status = 'timeout'
    out = raw.decode('utf-8', 'replace')
    if status == 'ok' and (proc.returncode != 0 or not re.search(r'^@@STMT 0\r?$', out, re.M)):
        status = 'crash'
    return stmts, parse_output(out, stmts), status, out


SELFTEST = r'''x := 3; s := "a;b"; x+1; %*2; f := t -> t^2: f; print(x); printf("a\nb\n"); 1/0;
p := plots:-loglogplot([t, t^2], t=1..10, legend=["a","b"]); restart; x; for i to 2 do i end do;
sol := dsolve({diff(y(t),t)=-y(t), y(0)=1}, numeric): plots:-odeplot(sol, [t, y(t)], 0..1); x^2
'''


def selftest():
    stmts, per, status, out = run_code(SELFTEST)
    got = {k: [(o['kind'], o['text']) for o in per.get(k, [])] for k in range(1, len(stmts) + 1)}
    assert status == 'ok', out
    assert got[1] == [('math', 'x := 3')] and got[2] == [('math', 's := "a;b"')], got
    assert got[3] == [('math', '4')] and got[4] == [('math', '8')] and got[6] == [('math', 'f')], got
    assert got[7] == [('print', '3')] and got[8] == [('print', 'a\nb')], got
    assert got[9][0][0] == 'error' and got[12] == [('math', 'x')], got
    assert got[13] == [('math', '1'), ('math', '2')] and got[16] == [('math', 'x^2')], got
    p = per[10][0]['plot']
    assert p['name'] == 'p' and p['xlog'] and p['ylog'] and len(p['objects']) == 2, p
    assert [o.get('legend') for o in p['objects']] == ['a', 'b'] and len(per[10]) == 1, per[10]
    q = per[15][0]['plot']
    assert q['objects'][0]['kind'] == 'curve' and abs(q['objects'][0]['points'][-1][1] - 0.3678794) < 1e-5, q
    print('selftest ok')


def run_case(path, out_dir, force):
    try:
        rel = os.path.relpath(path, ROOT).replace('\\', '/')
    except ValueError:   # other drive (dev runs on temp copies)
        rel = path.replace('\\', '/')
    source = os.path.basename(os.path.dirname(path))
    name = os.path.splitext(os.path.basename(path))[0]
    dst = os.path.join(out_dir, source, name + '.json')
    if not force and os.path.exists(dst) and os.path.getmtime(dst) > os.path.getmtime(path):
        return '%-28s skipped (golden up to date)' % (source + '/' + name), 'skipped'
    stmts, per, status, out = run_code(open(path, encoding='utf-8').read())
    res = {'case': source + '/' + name, 'file': rel, 'maple': '2024', 'status': status,
           'statements': [{'k': k, 'src': st['src'], 'terminator': st['terminator'], 'line': st['line'],
                           'outputs': per.get(k, [])} for k, st in enumerate(stmts, 1)]}
    if status != 'ok':
        res['tail'] = out[-2000:]
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    with open(dst, 'w', encoding='utf-8') as f:
        json.dump(res, f, indent=1, ensure_ascii=False)
    kinds = {}
    for k in per.values():
        for o in k:
            kinds[o['kind']] = kinds.get(o['kind'], 0) + 1
    summary = ' '.join('%s=%d' % kv for kv in sorted(kinds.items()))
    return '%-28s %-7s %3d stmts  %s' % (res['case'], status, len(stmts), summary), status


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('paths', nargs='*')
    ap.add_argument('--jobs', type=int, default=6)
    ap.add_argument('--force', action='store_true')
    ap.add_argument('--out', default=os.path.join(ROOT, 'corpus', 'golden'))
    ap.add_argument('--selftest', action='store_true', help='run a built-in snippet through cmaple and check the parse')
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    pats = a.paths or [os.path.join(ROOT, 'corpus', 'cases', '**', '*.mpl')]
    files = sorted({os.path.abspath(f) for p in pats
                    for f in (glob.glob(p, recursive=True) if any(c in p for c in '*?[') else [p])})
    if not files:
        sys.exit('no .mpl files matched')
    totals = {}
    with ThreadPoolExecutor(a.jobs) as ex:
        for line, status in ex.map(lambda f: run_case(f, a.out, a.force), files):
            print(line, flush=True)
            totals[status] = totals.get(status, 0) + 1
    print('TOTAL %d cases: %s' % (len(files), ', '.join('%s=%d' % kv for kv in sorted(totals.items()))))


if __name__ == '__main__':
    main()
