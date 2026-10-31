// Domain geometry and triangulation for the BOUNDARIES section.
// 2D: boundary paths -> polygons (arcs discretised); mesh = boundary nodes spaced ~h plus a
// hexagonal lattice of interior nodes, Delaunay-triangulated (Bowyer-Watson) and clipped to the
// domain. h = (largest domain extent)/ngrid reproduces FlexPDE's initial node counts closely.
// 1D: intervals split uniformly. Later regions overlay earlier ones (elements are tagged with the
// last region containing their centroid), as in FlexPDE.
import { FlexError } from './lexer.js';

const ARC_STEP = Math.PI / 24;

// -------------------------------------------------------------------------- geometry
export function buildGeometry(model) {
  const P = model.P, k = model.constant;
  const dim = model.dim;
  const regions = [];
  P.regions.forEach((r, ri) => {
    if (r.kind === 'feature') return;
    const number = r.number ?? ri + 1;
    for (const path of r.paths) {
      const start = path.start.map(k);
      if (dim === 1) {
        const pts = [{ x: start[0], bcs: path.startBcs }];
        for (const s of path.segs) if (s.to) pts.push({ x: k(s.to[0]), bcs: s.endBcs || [] });
        regions.push({ number, kind: r.kind, pts, label: path.name || r.label });
        continue;
      }
      const verts = [[start[0], start[1] ?? 0]];
      const segBcs = []; // bcs of the edge starting at verts[i]
      const pointBcs = [{ at: 0, bcs: path.startBcs }];
      let cur = verts[0];
      for (const s of path.segs) {
        const to = s.close ? verts[0] : s.to ? [k(s.to[0]), k(s.to[1] ?? { k: 'num', v: 0 })] : null;
        if (s.close && verts.length > 1 && Math.hypot(cur[0] - to[0], cur[1] - to[1]) < 1e-9 * (1 + Math.hypot(...to))) continue; // e.g. ANGLE=360 TO CLOSE
        let pts;
        if (s.type === 'arc') pts = arcPoints(cur, to, s, k);
        else pts = [to];
        for (const p of pts) { segBcs.push(s.bcs || []); verts.push(p); }
        cur = verts[verts.length - 1];
        if (s.endBcs) pointBcs.push({ at: verts.length - 1, bcs: s.endBcs });
      }
      // closed path: drop the duplicate final vertex
      const last = verts[verts.length - 1];
      if (verts.length > 1 && Math.hypot(last[0] - verts[0][0], last[1] - verts[0][1]) < 1e-12 * (1 + Math.abs(last[0]) + Math.abs(last[1]))) verts.pop();
      else if (r.kind !== 'feature') segBcs.push([]); // implicit closing edge
      regions.push({ number, kind: r.kind, verts, segBcs, pointBcs, label: path.name || r.label });
    }
  });
  if (!regions.length) throw new FlexError('No BOUNDARIES specified');
  return { dim, regions, ...measure(dim, regions) };
}

function arcPoints(cur, to, s, k) {
  let c, r, a0, a1;
  if (s.through) { // three-point arc
    const m = s.through.map(k);
    c = circumcenter(cur, m, to);
    r = Math.hypot(cur[0] - c[0], cur[1] - c[1]);
    a0 = Math.atan2(cur[1] - c[1], cur[0] - c[0]);
    const am = Math.atan2(m[1] - c[1], m[0] - c[0]);
    a1 = Math.atan2(to[1] - c[1], to[0] - c[0]);
    const ccw = norm2pi(am - a0) < norm2pi(a1 - a0);
    a1 = a0 + (ccw ? norm2pi(a1 - a0) : -norm2pi(a0 - a1));
  } else if (s.center) {
    c = s.center.map(k);
    r = Math.hypot(cur[0] - c[0], cur[1] - c[1]);
    a0 = Math.atan2(cur[1] - c[1], cur[0] - c[0]);
    if (s.angle) {
      const ang = k(s.angle) * (s.radians ? 1 : Math.PI / 180);
      a1 = a0 + ang;
    } else {
      a1 = Math.atan2(to[1] - c[1], to[0] - c[0]);
      let d = norm2pi(a1 - a0); // counter-clockwise from start to end
      if (d === 0) d = 2 * Math.PI;
      a1 = a0 + d;
    }
  } else if (s.radius) {
    r = Math.abs(k(s.radius));
    const mx = (cur[0] + to[0]) / 2, my = (cur[1] + to[1]) / 2;
    const dx = to[0] - cur[0], dy = to[1] - cur[1], d = Math.hypot(dx, dy);
    const hgt = Math.sqrt(Math.max(r * r - d * d / 4, 0));
    const sgn = k(s.radius) > 0 ? 1 : -1;
    c = [mx - sgn * hgt * dy / d, my + sgn * hgt * dx / d];
    a0 = Math.atan2(cur[1] - c[1], cur[0] - c[0]);
    a1 = a0 + sgn * norm2pi(sgn * (Math.atan2(to[1] - c[1], to[0] - c[0]) - a0));
  } else return [to];
  const n = Math.max(2, Math.ceil(Math.abs(a1 - a0) / ARC_STEP));
  const pts = [];
  for (let i = 1; i <= n; i++) {
    const a = a0 + (a1 - a0) * i / n;
    pts.push([c[0] + r * Math.cos(a), c[1] + r * Math.sin(a)]);
  }
  if (to && !s.angle) pts[pts.length - 1] = to;
  return pts;
}
const norm2pi = a => ((a % (2 * Math.PI)) + 2 * Math.PI) % (2 * Math.PI);
function circumcenter(a, b, c) {
  const d = 2 * (a[0] * (b[1] - c[1]) + b[0] * (c[1] - a[1]) + c[0] * (a[1] - b[1]));
  const A = a[0] ** 2 + a[1] ** 2, B = b[0] ** 2 + b[1] ** 2, C = c[0] ** 2 + c[1] ** 2;
  return [(A * (b[1] - c[1]) + B * (c[1] - a[1]) + C * (a[1] - b[1])) / d, (A * (c[0] - b[0]) + B * (a[0] - c[0]) + C * (b[0] - a[0])) / d];
}

function polyArea(v) {
  let a = 0, cx = 0, cy = 0;
  for (let i = 0; i < v.length; i++) {
    const p = v[i], q = v[(i + 1) % v.length];
    const cr = p[0] * q[1] - q[0] * p[1];
    a += cr; cx += (p[0] + q[0]) * cr; cy += (p[1] + q[1]) * cr;
  }
  a /= 2;
  return { area: a, centroid: a ? [cx / (6 * a), cy / (6 * a)] : v[0] };
}

export function pointInPoly(p, v) {
  let inside = false;
  for (let i = 0, j = v.length - 1; i < v.length; j = i++) {
    const a = v[i], b = v[j];
    if ((a[1] > p[1]) !== (b[1] > p[1]) && p[0] < ((b[0] - a[0]) * (p[1] - a[1])) / (b[1] - a[1]) + a[0]) inside = !inside;
  }
  return inside;
}

// outer regions (those not contained in an earlier region) define the domain
function measure(dim, regions) {
  if (dim === 1) {
    let lo = Infinity, hi = -Infinity;
    for (const r of regions) for (const p of r.pts) { lo = Math.min(lo, p.x); hi = Math.max(hi, p.x); }
    return { measure: hi - lo, centroid: [(lo + hi) / 2, 0], bbox: [lo, hi, 0, 0] };
  }
  const outer = [];
  for (const r of regions) {
    if (r.kind === 'exclude') continue;
    const inside = outer.some(o => r.verts.every(p => pointInPoly(p, o.verts) || onPolyBoundary(p, o.verts)));
    if (!inside) outer.push(r);
  }
  let A = 0, cx = 0, cy = 0;
  let x0 = Infinity, x1 = -Infinity, y0 = Infinity, y1 = -Infinity;
  for (const r of outer) {
    const { area, centroid } = polyArea(r.verts);
    A += Math.abs(area); cx += Math.abs(area) * centroid[0]; cy += Math.abs(area) * centroid[1];
    for (const p of r.verts) { x0 = Math.min(x0, p[0]); x1 = Math.max(x1, p[0]); y0 = Math.min(y0, p[1]); y1 = Math.max(y1, p[1]); }
  }
  return { measure: A, centroid: A ? [cx / A, cy / A] : [0, 0], outer, bbox: [x0, x1, y0, y1] };
}

function onPolyBoundary(p, v) {
  const tol = 1e-9 * (1 + Math.abs(p[0]) + Math.abs(p[1]));
  for (let i = 0; i < v.length; i++) if (segDist(p, v[i], v[(i + 1) % v.length]) < tol) return true;
  return false;
}
function segDist(p, a, b) {
  const dx = b[0] - a[0], dy = b[1] - a[1];
  const L2 = dx * dx + dy * dy;
  let s = L2 ? ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L2 : 0;
  s = Math.max(0, Math.min(1, s));
  return Math.hypot(p[0] - a[0] - s * dx, p[1] - a[1] - s * dy);
}

// -------------------------------------------------------------------------- meshing
export function buildMesh(geom, ngrid = 10) {
  return geom.dim === 1 ? mesh1d(geom, ngrid) : mesh2d(geom, ngrid);
}

function mesh1d(geom, ngrid) {
  const xs = new Set(), pointBcs = [];
  const ivals = [];
  for (const r of geom.regions) {
    for (let i = 0; i + 1 < r.pts.length; i++) ivals.push([Math.min(r.pts[i].x, r.pts[i + 1].x), Math.max(r.pts[i].x, r.pts[i + 1].x), r.number]);
    for (const p of r.pts) if (p.bcs && p.bcs.length) pointBcs.push({ x: p.x, bcs: p.bcs });
  }
  const [lo, hi] = geom.bbox;
  const h = (hi - lo) / Math.max(4 * ngrid, 8);
  for (const [a, b] of ivals) {
    const n = Math.max(1, Math.round((b - a) / h));
    for (let i = 0; i <= n; i++) xs.add(+(a + (b - a) * i / n).toPrecision(15));
  }
  const x = Float64Array.from([...xs].sort((a, b) => a - b));
  const tri = [], triRegion = [];
  for (let i = 0; i + 1 < x.length; i++) {
    const c = (x[i] + x[i + 1]) / 2;
    let reg = 0;
    for (const [a, b, num] of ivals) if (c >= a && c <= b) reg = num;
    if (!reg) continue;
    tri.push([i, i + 1]); triRegion.push(reg);
  }
  const nodeBcs = new Map();
  for (const pb of pointBcs) {
    let best = 0;
    for (let i = 1; i < x.length; i++) if (Math.abs(x[i] - pb.x) < Math.abs(x[best] - pb.x)) best = i;
    nodeBcs.set(best, [...(nodeBcs.get(best) || []), ...pb.bcs]);
  }
  const m = {
    dim: 1, x, y: new Float64Array(x.length), tri, triRegion, bedges: [], nodeBcs, bbox: [lo, hi, 0, 0],
    contains: p => tri.some(([a, b]) => p[0] >= x[a] - 1e-12 && p[0] <= x[b] + 1e-12),
    locate(p) {
      for (let e = 0; e < tri.length; e++) {
        const [a, b] = tri[e];
        if (p[0] >= x[a] - 1e-12 * (1 + Math.abs(x[a])) && p[0] <= x[b] + 1e-12 * (1 + Math.abs(x[b]))) {
          const s = (p[0] - x[a]) / (x[b] - x[a]);
          return { e, l: [1 - s, s] };
        }
      }
      return null;
    },
  };
  return m;
}

function mesh2d(geom, ngrid) {
  const [x0, x1, y0, y1] = geom.bbox;
  // P1 elements: twice FlexPDE's initial density to approach its (cubic, adaptive) accuracy
  const h = Math.max(x1 - x0, y1 - y0) / Math.max(2 * ngrid, 1);
  const polys = geom.regions.filter(r => r.kind !== 'exclude');
  const excl = geom.regions.filter(r => r.kind === 'exclude');
  const pts = [];
  const key = p => `${Math.round(p[0] / h * 1e6)},${Math.round(p[1] / h * 1e6)}`;
  const seen = new Map();
  const add = p => { const k = key(p); if (seen.has(k)) return seen.get(k); seen.set(k, pts.length); pts.push(p); return pts.length - 1; };
  const bsegs = []; // boundary polyline pieces with their BCs
  for (const r of geom.regions) {
    const v = r.verts;
    for (let i = 0; i < v.length; i++) {
      const a = v[i], b = v[(i + 1) % v.length];
      const L = Math.hypot(b[0] - a[0], b[1] - a[1]);
      const n = Math.max(1, Math.ceil(L / h - 0.2));
      for (let j = 0; j < n; j++) add([a[0] + (b[0] - a[0]) * j / n, a[1] + (b[1] - a[1]) * j / n]);
      bsegs.push({ a, b, bcs: r.segBcs[i] || [], region: r.number });
    }
    for (const pb of r.pointBcs || []) if (pb.bcs.length) bsegs.push({ a: v[pb.at % v.length], b: v[pb.at % v.length], bcs: pb.bcs, point: true });
  }
  const nb = pts.length;
  const inDomain = p => geom.outer.some(o => pointInPoly(p, o.verts)) && !excl.some(e => pointInPoly(p, e.verts));
  // hexagonal interior lattice, kept away from the boundary
  const dy = h * Math.sqrt(3) / 2;
  for (let j = 0, yy = y0 + dy / 2; yy < y1; j++, yy += dy) {
    for (let xx = x0 + (j % 2 ? h / 2 : h / 4); xx < x1; xx += h) {
      const p = [xx, yy];
      if (!inDomain(p)) continue;
      let dmin = Infinity;
      for (const s of bsegs) if (!s.point) dmin = Math.min(dmin, segDist(p, s.a, s.b));
      if (dmin > 0.55 * h) add(p);
    }
  }
  let tri = delaunay(pts);
  tri = tri.filter(t => {
    const c = [(pts[t[0]][0] + pts[t[1]][0] + pts[t[2]][0]) / 3, (pts[t[0]][1] + pts[t[1]][1] + pts[t[2]][1]) / 3];
    return inDomain(c);
  });
  // drop isolated nodes
  const used = new Int32Array(pts.length).fill(-1);
  const keep = [];
  for (const t of tri) for (const i of t) if (used[i] < 0) { used[i] = keep.length; keep.push(i); }
  tri = tri.map(t => t.map(i => used[i]));
  const X = Float64Array.from(keep.map(i => pts[i][0])), Y = Float64Array.from(keep.map(i => pts[i][1]));
  const triRegion = tri.map(t => {
    const c = [(X[t[0]] + X[t[1]] + X[t[2]]) / 3, (Y[t[0]] + Y[t[1]] + Y[t[2]]) / 3];
    let reg = polys[0].number;
    for (const r of polys) if (pointInPoly(c, r.verts)) reg = r.number;
    return reg;
  });
  // boundary edges (one adjacent triangle) and their BCs
  const ecount = new Map();
  for (const t of tri) for (let k = 0; k < 3; k++) {
    const a = t[k], b = t[(k + 1) % 3];
    const kk = a < b ? `${a},${b}` : `${b},${a}`;
    ecount.set(kk, (ecount.get(kk) || 0) + 1);
  }
  const tol = 1e-6 * h;
  const bedges = [];
  for (const [kk, c] of ecount) {
    if (c !== 1) continue;
    const [a, b] = kk.split(',').map(Number);
    const mid = [(X[a] + X[b]) / 2, (Y[a] + Y[b]) / 2];
    let bcs = [];
    let best = Infinity;
    for (const s of bsegs) {
      if (s.point) continue;
      const d = segDist(mid, s.a, s.b);
      if (d < best - tol) { best = d; bcs = s.bcs; }
      else if (Math.abs(d - best) <= tol) bcs = s.bcs; // overlapping later segment wins
    }
    bedges.push({ a, b, bcs });
  }
  const nodeBcs = new Map(); // point BCs
  for (const s of bsegs) if (s.point) {
    let best = 0;
    for (let i = 1; i < X.length; i++) if (Math.hypot(X[i] - s.a[0], Y[i] - s.a[1]) < Math.hypot(X[best] - s.a[0], Y[best] - s.a[1])) best = i;
    nodeBcs.set(best, [...(nodeBcs.get(best) || []), ...s.bcs]);
  }
  let lastE = 0;
  const m = {
    dim: 2, x: X, y: Y, tri, triRegion, bedges, nodeBcs, bbox: geom.bbox, h, nBoundaryNodes: nb,
    contains: p => inDomain(p),
    locate(p) {
      const test = e => {
        const [a, b, c] = tri[e];
        const det = (Y[b] - Y[c]) * (X[a] - X[c]) + (X[c] - X[b]) * (Y[a] - Y[c]);
        const l0 = ((Y[b] - Y[c]) * (p[0] - X[c]) + (X[c] - X[b]) * (p[1] - Y[c])) / det;
        const l1 = ((Y[c] - Y[a]) * (p[0] - X[c]) + (X[a] - X[c]) * (p[1] - Y[c])) / det;
        const l2 = 1 - l0 - l1;
        return Math.min(l0, l1, l2) >= -1e-9 ? [l0, l1, l2] : null;
      };
      let l = test(lastE);
      if (l) return { e: lastE, l };
      for (let e = 0; e < tri.length; e++) if ((l = test(e))) { lastE = e; return { e, l }; }
      // outside (e.g. on a curved boundary between nodes): nearest element by centroid
      let best = -1, bd = Infinity;
      for (let e = 0; e < tri.length; e++) {
        const [a, b, c] = tri[e];
        const d = Math.hypot((X[a] + X[b] + X[c]) / 3 - p[0], (Y[a] + Y[b] + Y[c]) / 3 - p[1]);
        if (d < bd) { bd = d; best = e; }
      }
      if (best < 0) return null;
      const [a, b, c] = tri[best];
      const det = (Y[b] - Y[c]) * (X[a] - X[c]) + (X[c] - X[b]) * (Y[a] - Y[c]);
      const l0 = ((Y[b] - Y[c]) * (p[0] - X[c]) + (X[c] - X[b]) * (p[1] - Y[c])) / det;
      const l1 = ((Y[c] - Y[a]) * (p[0] - X[c]) + (X[a] - X[c]) * (p[1] - Y[c])) / det;
      return { e: best, l: [l0, l1, 1 - l0 - l1] };
    },
  };
  return m;
}

// Bowyer-Watson Delaunay triangulation; returns [[i,j,k]] counter-clockwise.
export function delaunay(pts) {
  const n = pts.length;
  let x0 = Infinity, x1 = -Infinity, y0 = Infinity, y1 = -Infinity;
  for (const p of pts) { x0 = Math.min(x0, p[0]); x1 = Math.max(x1, p[0]); y0 = Math.min(y0, p[1]); y1 = Math.max(y1, p[1]); }
  const d = Math.max(x1 - x0, y1 - y0) || 1, mx = (x0 + x1) / 2, my = (y0 + y1) / 2;
  const P = pts.concat([[mx - 20 * d, my - 10 * d], [mx + 20 * d, my - 10 * d], [mx, my + 20 * d]]);
  const tris = [];
  const mk = (a, b, c) => {
    const [ax, ay] = P[a], [bx, by] = P[b], [cx, cy] = P[c];
    const D = 2 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by));
    const A = ax * ax + ay * ay, B = bx * bx + by * by, C = cx * cx + cy * cy;
    const ux = (A * (by - cy) + B * (cy - ay) + C * (ay - by)) / D, uy = (A * (cx - bx) + B * (ax - cx) + C * (bx - ax)) / D;
    return { v: D > 0 ? [a, b, c] : [a, c, b], ux, uy, r2: (ax - ux) ** 2 + (ay - uy) ** 2, alive: true };
  };
  tris.push(mk(n, n + 1, n + 2));
  // insert in a spatially coherent order (rows) to keep cavities local
  const order = [...pts.keys()].sort((i, j) => Math.round((pts[i][1] - y0) / d * 30) - Math.round((pts[j][1] - y0) / d * 30) || pts[i][0] - pts[j][0]);
  for (const i of order) {
    const [px, py] = P[i];
    const bad = [];
    for (let t = 0; t < tris.length; t++) {
      const T = tris[t];
      if (!T.alive) continue;
      const dx = px - T.ux, dy = py - T.uy;
      if (dx * dx + dy * dy < T.r2 * (1 + 1e-12)) bad.push(t);
    }
    const edges = new Map();
    for (const t of bad) {
      const v = tris[t].v;
      tris[t].alive = false;
      for (let k = 0; k < 3; k++) {
        const a = v[k], b = v[(k + 1) % 3];
        const kk = a < b ? a * 4194304 + b : b * 4194304 + a;
        if (edges.has(kk)) edges.delete(kk); else edges.set(kk, [a, b]);
      }
    }
    for (const [a, b] of edges.values()) tris.push(mk(a, b, i));
    if (tris.length > 4 * (n + 3) * 2) { // compact dead triangles
      const live = tris.filter(T => T.alive);
      tris.length = 0;
      tris.push(...live);
    }
  }
  return tris.filter(T => T.alive && T.v.every(v => v < n)).map(T => T.v);
}
