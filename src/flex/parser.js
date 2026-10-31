// Recursive-descent parser: FlexPDE script -> problem description (sections + expression ASTs).
// The grammar is free-form (newlines are not significant): a statement ends where the next token
// cannot continue the current expression, e.g. `q1=5e-3  q2=-20e-6` is two definitions.
import { tokenize, tokenDesc, FlexError, SECTION_WORDS } from './lexer.js';

// Expression AST nodes: {k:'num',v} {k:'name',id,text} {k:'str',v} {k:'call',f,args}
// {k:'neg',a} {k:'not',a} {k:'bin',op,a,b} {k:'if',c,a,b}; every node carries tok (for line/col).

const PLOT_CMDS = new Set(['history', 'histories', 'contour', 'surface', 'elevation', 'vector', 'grid', 'summary',
  'report', 'table', 'tecplot', 'vtk', 'vtklin', 'transfer', 'transfer6', 'cdf', 'print', 'export', 'modes', 'fieldmap']);
const SEGMENT_WORDS = new Set(['line', 'arc', 'spline', 'to', 'close', 'finish', 'curve', 'adapt']);
const BC_WORDS = new Set(['value', 'natural', 'load', 'neumann', 'dirichlet', 'nobc', 'mixed', 'contact', 'velocity']);

export function parseFlex(src) {
  const p = new Parser(src);
  return p.parseProblem();
}

class Parser {
  constructor(src) {
    this.src = src;
    this.toks = tokenize(src);
    this.i = 0;
  }
  get t() { return this.toks[this.i]; }
  peek(k = 1) { return this.toks[Math.min(this.i + k, this.toks.length - 1)]; }
  next() { return this.toks[this.i++]; }
  isOp(v, t = this.t) { return t.type === 'op' && t.value === v; }
  isId(key, t = this.t) { return t.type === 'id' && t.key === key; }
  fail(t = this.t) {
    throw new FlexError(`FlexPDE grammar does not allow '${tokenDesc(t)}' in this location.`, t.line, t.col);
  }
  expectOp(v) { if (!this.isOp(v)) this.fail(); return this.next(); }
  expectId() { if (this.t.type !== 'id') this.fail(); return this.next(); }
  acceptOp(v) { if (this.isOp(v)) { this.i++; return true; } return false; }
  acceptId(key) { if (this.isId(key)) { this.i++; return true; } return false; }
  atSection() { return this.t.type === 'eof' || (this.t.type === 'id' && SECTION_WORDS.has(this.t.key)); }
  textOf(i0, i1) { return this.src.slice(this.toks[i0].pos, this.toks[i1 - 1].end).replace(/\s+/g, ' ').trim(); }

  // ---------------------------------------------------------------- expressions
  // noEq: a bare top-level '=' terminates the expression (definitions, equations).
  expr(noEq = true) {
    if (this.isId('if')) return this.ifExpr(noEq);
    return this.orExpr(noEq);
  }
  ifExpr(noEq) {
    const tok = this.next();
    const c = this.orExpr(false);
    if (!this.acceptId('then')) this.fail();
    const a = this.expr(noEq);
    if (!this.acceptId('else')) this.fail();
    const b = this.expr(noEq);
    return { k: 'if', c, a, b, tok };
  }
  orExpr(noEq) {
    let a = this.andExpr(noEq);
    while (this.isId('or')) { const tok = this.next(); a = { k: 'bin', op: 'or', a, b: this.andExpr(noEq), tok }; }
    return a;
  }
  andExpr(noEq) {
    let a = this.notExpr(noEq);
    while (this.isId('and')) { const tok = this.next(); a = { k: 'bin', op: 'and', a, b: this.notExpr(noEq), tok }; }
    return a;
  }
  notExpr(noEq) {
    if (this.isId('not')) { const tok = this.next(); return { k: 'not', a: this.notExpr(noEq), tok }; }
    return this.relExpr(noEq);
  }
  relExpr(noEq) {
    let a = this.addExpr();
    for (;;) {
      const t = this.t;
      if (t.type === 'op' && ['<', '>', '<=', '>=', '<>'].includes(t.value) || (!noEq && this.isOp('='))) {
        this.next();
        a = { k: 'bin', op: t.value, a, b: this.addExpr(), tok: t };
      } else return a;
    }
  }
  addExpr() {
    let a = this.mulExpr();
    while (this.isOp('+') || this.isOp('-')) {
      const tok = this.next();
      a = { k: 'bin', op: tok.value, a, b: this.mulExpr(), tok };
    }
    return a;
  }
  mulExpr() {
    let a = this.unary();
    while (this.isOp('*') || this.isOp('/') || this.isOp('**') || this.isOp('//')) {
      const tok = this.next();
      a = { k: 'bin', op: tok.value === '**' ? '*' : tok.value === '//' ? '/' : tok.value, a, b: this.powExpr(), tok };
    }
    return a;
  }
  // Leading sign binds looser than '^' (-2^2 = -4) but FlexPDE rejects a sign after '*' ("2*-3").
  unary() {
    if (this.isOp('-')) { const tok = this.next(); return { k: 'neg', a: this.powExpr(), tok }; }
    if (this.isOp('+')) { this.next(); return this.powExpr(); }
    return this.powExpr();
  }
  powExpr() {
    let a = this.postfix();
    while (this.isOp('^')) { // left-associative, as in FlexPDE: 2^3^2 = 64
      const tok = this.next();
      let b;
      if (this.isOp('-')) { const nt = this.next(); b = { k: 'neg', a: this.postfix(), tok: nt }; }
      else b = this.postfix();
      a = { k: 'bin', op: '^', a, b, tok };
    }
    return a;
  }
  postfix() {
    const t = this.t;
    if (t.type === 'num') { this.next(); return { k: 'num', v: t.value, tok: t }; }
    if (t.type === 'str') { this.next(); return { k: 'str', v: t.value, tok: t }; }
    if (this.isOp('(')) {
      this.next();
      const e = this.expr(false);
      if (this.isOp(',')) { // (a, b) point literal -> vector
        const args = [e];
        while (this.acceptOp(',')) args.push(this.expr(false));
        this.expectOp(')');
        return { k: 'call', f: 'vector', args, tok: t };
      }
      this.expectOp(')');
      return e;
    }
    if (t.type === 'id') {
      if (t.key === 'if') return this.ifExpr(true);
      if (SECTION_WORDS.has(t.key) || ['then', 'else', 'and', 'or', 'to', 'by', 'at', 'as', 'vs'].includes(t.key)) this.fail();
      this.next();
      if (this.isOp('(')) {
        this.next();
        const args = [];
        if (!this.isOp(')')) {
          do args.push(this.expr(false)); while (this.acceptOp(','));
        }
        this.expectOp(')');
        return { k: 'call', f: t.key, args, tok: t };
      }
      return { k: 'name', id: t.key, text: t.text, tok: t };
    }
    this.fail();
  }
  // expression plus its source text (report labels, legends)
  labeled(noEq = true) {
    const i0 = this.i;
    const e = this.expr(noEq);
    e.label = this.textOf(i0, this.i);
    return e;
  }
  point() { // (x) | (x, y) | (x, y, z)
    const tok = this.expectOp('(');
    const c = [this.expr(false)];
    while (this.acceptOp(',')) c.push(this.expr(false));
    this.expectOp(')');
    c.tok = tok;
    return c;
  }

  // ---------------------------------------------------------------- sections
  parseProblem() {
    const P = {
      title: '', coords: 'cartesian2', coordArgs: [], select: {}, variables: [], defs: [], initial: [],
      equations: [], regions: [], time: null, plots: [], hasEnd: false, src: this.src,
    };
    while (this.t.type !== 'eof') {
      const t = this.t;
      if (t.type !== 'id' || !SECTION_WORDS.has(t.key)) this.fail();
      this.next();
      switch (t.key) {
        case 'title':
          P.title = this.t.type === 'str' ? this.next().value : '';
          while (this.t.type === 'str') P.title += ' ' + this.next().value;
          break;
        case 'coordinates': {
          const c = this.expectId();
          P.coords = c.key;
          if (this.isOp('(')) {
            this.next();
            while (!this.isOp(')')) this.next();
            this.next();
          }
          break;
        }
        case 'select': this.selectSection(P); break;
        case 'global': this.acceptId('variables'); this.variablesSection(P, true); break;
        case 'variables': this.variablesSection(P, false); break;
        case 'definitions': this.definitions(P.defs); break;
        case 'initial':
          if (this.acceptId('equations')) { this.equationsSection(P, true); break; }
          this.acceptId('values');
          this.initialSection(P);
          break;
        case 'equations': this.equationsSection(P, false); break;
        case 'constraints': case 'extrusion': case 'materials': case 'resolve': case 'mesh': case 'staged':
          this.skipSection(); break;
        case 'boundaries': this.boundaries(P); break;
        case 'time': this.timeSection(P, t); break;
        case 'monitors': case 'plots': case 'histories': this.plotsSection(P, t.key); break;
        case 'end': P.hasEnd = true; return P; // anything after END is ignored
      }
    }
    return P;
  }
  skipSection() { while (!this.atSection()) this.next(); }

  selectSection(P) {
    while (!this.atSection()) {
      const name = this.expectId();
      let val = { k: 'name', id: 'on', tok: name };
      if (this.acceptOp('=')) {
        if (this.t.type === 'id' && ['on', 'off', 'true', 'false'].includes(this.t.key)) {
          const v = this.next();
          val = { k: 'num', v: v.key === 'on' || v.key === 'true' ? 1 : 0, tok: v };
        } else val = this.expr();
      }
      P.select[name.key] = val;
    }
  }

  variablesSection(P, global) {
    while (!this.atSection()) {
      const name = this.expectId();
      const v = { name: name.text, key: name.key, thr: null, comps: null, line: name.line, col: name.col, global };
      const thresh = () => {
        if (this.isOp('(')) {
          this.next();
          if (this.isId('threshold')) { this.next(); this.expectOp('='); }
          v.thr = this.expr();
          this.expectOp(')');
        }
      };
      thresh();
      if (this.acceptOp('=')) {
        const vt = this.expectId();
        if (vt.key !== 'vector') this.fail(vt);
        this.expectOp('(');
        v.comps = [];
        do v.comps.push(this.expectId()); while (this.acceptOp(','));
        this.expectOp(')');
        v.comps = v.comps.map(c => ({ name: c.text, key: c.key }));
        thresh();
      }
      this.acceptOp(',');
      P.variables.push(v);
    }
  }

  definitions(list, stopAt = null) {
    while (!this.atSection() && !(stopAt && stopAt())) {
      const name = this.expectId();
      let params = null;
      if (this.isOp('(')) {
        this.next();
        params = [];
        if (!this.isOp(')')) do params.push(this.expectId().key); while (this.acceptOp(','));
        this.expectOp(')');
      }
      if (!this.acceptOp('=')) { // declared without value
        list.push({ key: name.key, name: name.text, params, expr: null, line: name.line, col: name.col });
        continue;
      }
      const expr = this.labeled();
      list.push({ key: name.key, name: name.text, params, expr, line: name.line, col: name.col });
    }
  }

  initialSection(P) {
    while (!this.atSection()) {
      const name = this.expectId();
      this.expectOp('=');
      P.initial.push({ key: name.key, name: name.text, expr: this.expr(), line: name.line, col: name.col });
    }
  }

  equationsSection(P, initial) {
    while (!this.atSection()) {
      let label = null;
      const t0 = this.t;
      if (this.t.type === 'id' && this.isOp(':', this.peek())) { label = this.next().key; this.next(); }
      const lhs = this.expr();
      let rhs = { k: 'num', v: 0, tok: t0 };
      if (this.acceptOp('=')) rhs = this.expr();
      (initial ? (P.initialEquations ||= []) : P.equations).push({ label, lhs, rhs, line: t0.line, col: t0.col });
    }
  }

  timeSection(P, tok) {
    const T = { from: null, to: null, by: null, halt: [], limit: null, critical: [], line: tok.line };
    this.acceptId('from');
    T.from = this.expr();
    for (;;) {
      if (this.acceptId('to')) T.to = this.expr();
      else if (this.acceptId('by')) T.by = this.expr();
      else break;
    }
    for (;;) {
      if (this.acceptId('halt')) { this.acceptOp('='); T.halt.push(this.expr(false)); }
      else if (this.acceptId('limit')) { this.acceptOp('='); T.limit = this.expr(); }
      else if (this.acceptId('critical')) {
        do T.critical.push(this.expr()); while (this.acceptOp(',') || (this.t.type === 'num'));
      } else break;
    }
    if (!this.atSection()) this.fail();
    if (!T.to) throw new FlexError('No Time Range Has been Specified', tok.line, tok.col);
    P.time = T;
  }

  // BOUNDARIES: regions made of paths; BC statements apply to the segments that follow them.
  boundaries(P) {
    let region = null;
    while (!this.atSection()) {
      const t = this.t;
      if (this.isId('region') || this.isId('feature') || this.isId('exclude') || this.isId('limited')) {
        const kind = this.next().key;
        if (kind === 'limited') this.acceptId('region');
        region = { kind: kind === 'limited' ? 'region' : kind, label: null, number: null, defs: [], paths: [], line: t.line };
        if (this.t.type === 'num') region.number = this.next().value;
        if (this.t.type === 'str') region.label = this.next().value;
        P.regions.push(region);
        // region-local parameter redefinitions: `k = 5` before START
        while (this.t.type === 'id' && !BC_WORDS.has(this.t.key) && this.isOp('=', this.peek())) {
          const name = this.next();
          this.next();
          region.defs.push({ key: name.key, name: name.text, params: null, expr: this.labeled(), line: name.line, col: name.col });
        }
        continue;
      }
      if (!region) { region = { kind: 'region', label: null, number: 1, defs: [], paths: [], line: t.line }; P.regions.push(region); }
      if (this.isId('start')) { region.paths.push(this.path()); continue; }
      if (t.type === 'id' && ['mesh_spacing', 'mesh_density', 'use', 'layer'].includes(t.key)) { this.skipAssignment(); continue; }
      this.fail();
    }
  }
  skipAssignment() {
    this.next();
    if (this.isOp('(')) this.skipParens();
    if (this.acceptOp('=')) this.expr();
  }
  skipParens() {
    let d = 0;
    do {
      if (this.isOp('(')) d++;
      else if (this.isOp(')')) d--;
      this.next();
    } while (d > 0 && this.t.type !== 'eof');
  }
  path() {
    const tok = this.next(); // START
    const path = { name: null, start: null, segs: [], startBcs: [], line: tok.line, closed: false };
    if (this.t.type === 'str') path.name = this.next().value;
    path.start = this.point();
    let bcs = []; // active segment BCs
    let pointBcs = path.startBcs;
    let segType = null;
    for (;;) {
      const t = this.t;
      if (t.type !== 'id') break;
      if (t.key === 'point' && BC_WORDS.has(this.peek().key)) {
        this.next();
        pointBcs.push(this.bc());
        continue;
      }
      if (BC_WORDS.has(t.key)) { // replaces any BC for the same variable
        const bc = this.bc();
        bcs = bcs.filter(b => b.var !== bc.var).concat([bc]);
        continue;
      }
      if (t.key === 'label' || t.key === 'endlabel') { this.next(); if (this.t.type === 'str') this.next(); continue; }
      if (t.key === 'line' || t.key === 'spline') { this.next(); segType = 'line'; continue; }
      if (t.key === 'arc') {
        this.next();
        segType = { type: 'arc' };
        if (this.isOp('(')) {
          this.next();
          while (!this.isOp(')')) {
            const w = this.expectId().key;
            this.acceptOp('=');
            if (w === 'center') { segType.center = [this.expr(false)]; this.expectOp(','); segType.center.push(this.expr(false)); }
            else if (w === 'radius') segType.radius = this.expr(false);
            else this.expr(false);
            this.acceptOp(',');
          }
          this.next();
        }
        if (this.acceptId('angle')) {
          this.acceptOp('=');
          const angle = this.expr();
          const radians = this.acceptId('radians');
          if (!radians) this.acceptId('degrees');
          path.segs.push({ type: 'arc', center: segType.center, angle, radians, bcs, end: null });
          pointBcs = path.segs[path.segs.length - 1].endBcs = [];
        }
        continue;
      }
      if (t.key === 'to') {
        this.next();
        if (this.acceptId('close') || this.acceptId('finish')) {
          path.segs.push({ ...(segType && segType.type === 'arc' ? segType : { type: 'line' }), to: null, bcs, close: true });
          path.closed = true;
          pointBcs = path.segs[path.segs.length - 1].endBcs = [];
          continue;
        }
        if (!segType) this.fail(t);
        const to = this.point();
        if (segType.type === 'arc' && !segType.center && !segType.radius && this.isId('to')) {
          // 3-point arc: ARC TO (mid) TO (end)
          this.next();
          const end = this.point();
          path.segs.push({ type: 'arc', through: to, to: end, bcs });
        } else path.segs.push({ ...(segType.type === 'arc' ? segType : { type: 'line' }), to, bcs });
        pointBcs = path.segs[path.segs.length - 1].endBcs = [];
        continue;
      }
      if (t.key === 'close' || t.key === 'finish') {
        this.next();
        path.segs.push({ type: 'line', to: null, bcs, close: true });
        path.closed = true;
        continue;
      }
      break;
    }
    return path;
  }
  bc() {
    const t = this.next();
    let type = t.key;
    if (type === 'neumann' || type === 'load') type = 'natural';
    if (type === 'dirichlet') type = 'value';
    this.expectOp('(');
    const v = this.expectId();
    this.expectOp(')');
    let expr = { k: 'num', v: 0, tok: t };
    if (this.acceptOp('=')) expr = this.expr();
    return { type, var: v.key, expr, line: t.line };
  }

  // PLOTS / MONITORS: `for` clauses, display commands with modifiers, reports.
  plotsSection(P, section) {
    const block = { section, times: null, cycle: null, items: [], line: this.toks[this.i - 1].line };
    P.plots.push(block);
    let last = null;
    while (!this.atSection()) {
      const t = this.t;
      if (t.type !== 'id') this.fail();
      if (t.key === 'for') {
        this.next();
        const v = this.expectId();
        this.expectOp('=');
        if (v.key === 'cycle') { block.cycle = this.expr(); continue; }
        const spec = [{ at: this.expr() }];
        for (;;) {
          if (this.acceptId('by')) { const by = this.expr(); if (!this.acceptId('to')) this.fail(); spec.push({ by, to: this.expr() }); }
          else if (this.acceptOp(',')) spec.push({ at: this.expr() });
          else break;
        }
        block.times = spec;
        continue;
      }
      if (t.key === 'report') {
        this.next();
        const r = this.report(t);
        block.items.push(r);
        if (last) (last.reports ||= []).push(r);
        continue;
      }
      if (!PLOT_CMDS.has(t.key)) this.fail();
      last = this.plotItem();
      block.items.push(last);
    }
  }
  report(tok) {
    const items = [];
    if (this.isOp('(')) { // REPORT (e1, e2, ...) or a parenthesised expression like (a)+b
      const i0 = this.i;
      this.next();
      const list = [];
      do {
        const j0 = this.i;
        const e = this.expr(false);
        e.label = this.textOf(j0, this.i);
        list.push(e);
      } while (this.acceptOp(','));
      this.expectOp(')');
      if (list.length === 1 && this.t.type === 'op' && ['+', '-', '*', '/', '^', '<', '>'].includes(this.t.value)) {
        this.i = i0;
        items.push(this.labeled());
      } else items.push(...list);
    } else items.push(this.labeled());
    let as = null;
    if (this.acceptId('as')) as = this.next().value;
    const first = this.firstTok(items[0]);
    return { type: 'report', exprs: items, expr: items[0], as, label: as ?? items[0].label, line: first.line, col: first.col };
  }
  firstTok(e) {
    let best = e.tok;
    const walk = n => {
      if (!n || typeof n !== 'object') return;
      if (n.tok && (n.tok.pos < best.pos)) best = n.tok;
      for (const k of ['a', 'b', 'c']) walk(n[k]);
      if (n.args) n.args.forEach(walk);
    };
    walk(e);
    return best;
  }
  plotItem() {
    const t = this.next();
    const item = { type: t.key === 'histories' ? 'history' : t.key, args: [], line: t.line, col: t.col, mods: {} };
    if (this.isOp('(')) {
      this.next();
      if (!this.isOp(')')) {
        do {
          const j0 = this.i;
          const e = this.expr(false);
          e.label = this.textOf(j0, this.i);
          item.args.push(e);
        } while (this.acceptOp(','));
      }
      this.expectOp(')');
    }
    // modifiers
    for (;;) {
      const m = this.t;
      if (m.type !== 'id' || SECTION_WORDS.has(m.key) || PLOT_CMDS.has(m.key) || m.key === 'for') {
        if (m.type === 'id' && m.key === 'export' || m.type === 'id' && m.key === 'print') { this.next(); this.skipOptParens(); continue; }
        break;
      }
      this.next();
      switch (m.key) {
        case 'at': item.at = []; while (this.isOp('(')) item.at.push(this.point()); break;
        case 'from': item.from = this.point(); break;
        case 'to': item.to = this.point(); break;
        case 'vs': case 'versus': { const j0 = this.i; item.vs = this.expr(); item.vs.label = this.textOf(j0, this.i); break; }
        case 'as': item.as = this.next().value; break;
        case 'window':
          if (this.acceptOp('=')) item.window = [this.expr()];
          else { this.expectOp('('); item.window = [this.expr(false)]; this.expectOp(','); item.window.push(this.expr(false)); this.expectOp(')'); }
          break;
        case 'norm': item.norm = true; break;
        case 'file': this.acceptOp('='); this.next(); break;
        case 'format': this.acceptOp('='); this.next(); break;
        case 'points': this.acceptOp('='); if (this.isOp('(')) this.skipParens(); else item.points = this.expr(); break;
        case 'fixed': this.acceptId('range'); this.skipOptParens(); break;
        case 'range': this.skipOptParens(); break;
        case 'on': // ON REGION n | ON 'name' | ON GRID(...)
          if (this.t.type === 'str') this.next();
          else if (this.t.type === 'id') { this.next(); if (this.t.type === 'num' || this.t.type === 'str') this.next(); else this.skipOptParens(); }
          break;
        default:
          if (this.acceptOp('=')) { if (this.isOp('(')) this.skipParens(); else this.expr(); }
          else this.skipOptParens();
      }
    }
    return item;
  }
  skipOptParens() { if (this.isOp('(')) this.skipParens(); }
}
