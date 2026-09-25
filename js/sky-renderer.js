/* ==========================================================================
   SkyRenderer — canvas renderer for the celestial sphere
   frame: 'horizon'    → real sky for an observer (alt/az, ground, horizon)
          'equatorial' → star-chart view centred on RA/Dec (constellation charts)
   projection: 'stereo' (wide, pleasant) | 'gnomonic' (true perspective, for AR)
   ========================================================================== */
(function (global) {
  'use strict';
  const A = global.Astro;
  const D2R = Math.PI / 180, R2D = 180 / Math.PI;
  const SKY = global.SKY_DATA;

  /* ---------- shared catalog prep (once) ---------- */
  const NSTAR = SKY.stars.length / 4;
  const STAR_V = new Float32Array(NSTAR * 3);
  const STAR_MAG = new Float32Array(NSTAR);
  const STAR_BV = new Float32Array(NSTAR);
  for (let i = 0; i < NSTAR; i++) {
    const v = A.vec(SKY.stars[i * 4], SKY.stars[i * 4 + 1]);
    STAR_V[i * 3] = v[0]; STAR_V[i * 3 + 1] = v[1]; STAR_V[i * 3 + 2] = v[2];
    STAR_MAG[i] = SKY.stars[i * 4 + 2];
    STAR_BV[i] = SKY.stars[i * 4 + 3];
  }
  const NAME_FIX = { '아크투루스': '아르크투루스', '미르파크': '미르팍' };
  const STAR_NAMES = SKY.names.map(n => ({ hip: n[0], idx: n[1], ko: NAME_FIX[n[2]] || n[2], en: n[3], desig: n[4] }));
  const NAME_BY_IDX = new Map(STAR_NAMES.map(n => [n.idx, n]));
  const NAME_BY_HIP = new Map(STAR_NAMES.map(n => [n.hip, n]));
  const CONS = {};
  for (const [id, c] of Object.entries(SKY.cons)) {
    const lines = c.lines.map(seg => {
      const out = [];
      for (let k = 0; k < seg.length; k += 2) out.push(A.vec(seg[k], seg[k + 1]));
      return out;
    });
    // centroid of the stick figure (better than label point for "find" targets)
    let sx = 0, sy = 0, sz = 0, n = 0;
    for (const l of lines) for (const v of l) { sx += v[0]; sy += v[1]; sz += v[2]; n++; }
    const lbl = A.vec(c.lbl[0], c.lbl[1]);
    const cen = n ? normalize([sx, sy, sz]) : lbl;
    let ext = 5;
    for (const l of lines) for (const v of l) ext = Math.max(ext, Math.acos(Math.min(1, dot(v, cen))) * R2D);
    CONS[id] = { id, ko: c.ko, en: c.en, la: c.la, gen: c.gen, rank: c.rank, lines, lbl, center: cen, extent: ext };
  }
  const MW = [];
  for (let k = 0; k < SKY.mw.length; k += 3) MW.push({ v: A.vec(SKY.mw[k], SKY.mw[k + 1]), w: SKY.mw[k + 2] });

  function dot(a, b) { return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]; }
  function cross(a, b) { return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]; }
  function normalize(a) { const n = Math.hypot(a[0], a[1], a[2]) || 1; return [a[0] / n, a[1] / n, a[2] / n]; }

  function bvColor(bv) {
    if (bv < -0.2) return 0; if (bv < 0.0) return 1; if (bv < 0.3) return 2; if (bv < 0.6) return 3;
    if (bv < 0.9) return 4; if (bv < 1.2) return 5; if (bv < 1.5) return 6; return 7;
  }
  const STAR_COLORS = ['#9bb4ff', '#adc2ff', '#cfdcff', '#f6f6ff', '#fff3e4', '#ffe4c0', '#ffcf9a', '#ffb36b'];
  const STAR_COLOR_IDX = new Uint8Array(NSTAR);
  for (let i = 0; i < NSTAR; i++) STAR_COLOR_IDX[i] = bvColor(STAR_BV[i]);

  function makeSprite(color, red) {
    const c = document.createElement('canvas'); c.width = c.height = 64;
    const x = c.getContext('2d');
    const g = x.createRadialGradient(32, 32, 0, 32, 32, 32);
    g.addColorStop(0, red ? '#ffd0d0' : '#ffffff');
    g.addColorStop(0.18, color);
    g.addColorStop(0.35, color + '66');
    g.addColorStop(1, color + '00');
    x.fillStyle = g; x.fillRect(0, 0, 64, 64);
    return c;
  }
  let SPRITES = null, GLOW = null;
  function sprites() {
    if (!SPRITES) {
      SPRITES = STAR_COLORS.map(c => makeSprite(c));
      GLOW = makeSprite('#b8c8ff');
    }
    return SPRITES;
  }

  const CARDINALS = [['북', 0, true], ['북동', 45], ['동', 90, true], ['남동', 135], ['남', 180, true], ['남서', 225], ['서', 270, true], ['북서', 315]];

  class SkyRenderer {
    constructor(canvas, opts = {}) {
      this.cv = canvas;
      this.cx = canvas.getContext('2d');
      this.frame = opts.frame || 'horizon';
      this.projection = opts.projection || 'stereo';
      this.lat = 37.5665; this.lon = 126.978;
      this.time = new Date();
      this.fov = opts.fov || 90;
      this.minFov = opts.minFov || 8; this.maxFov = opts.maxFov || 150;
      this.layers = Object.assign({ stars: true, lines: true, conNames: true, starNames: true, planets: true,
        milkyway: true, ground: true, cardinals: true, altazGrid: false, eqGrid: false, allConLines: true }, opts.layers || {});
      this.magLimit = opts.magLimit || 5.5; // observing-site limit (light pollution)
      this.fontScale = opts.fontScale || 1;
      this.transparentBg = false;           // true in AR camera mode
      this.highlight = new Map();           // conId → color
      this.guides = [];                     // [{hips:[...], color, label, closed}]
      this.target = null;                   // {kind, id, label, vec: () => J2000 unit vector}
      this.interactive = opts.interactive !== false;
      this.onSelect = opts.onSelect || null;
      this.onTarget = opts.onTarget || null;
      this.onViewChange = opts.onViewChange || null;
      this.sensorBasis = null;              // {r,u,f} in ENU when gyro controls the camera
      this.onCalibrate = null;              // drag in sensor mode → azimuth offset delta
      this.dpr = Math.min(global.devicePixelRatio || 1, 2.5);
      this._dirty = true; this._running = false;
      this._proj = new Float32Array(NSTAR * 3);
      this.view = { lon: opts.lon ?? 180, lat: opts.lat ?? 40 }; // az/alt or ra/dec of view centre
      this._basis();
      if (this.interactive) this._bindInput();
      this._ro = new ResizeObserver(() => { this.resize(); });
      this._ro.observe(canvas);
      this.resize();
    }

    /* ---------------- public API ---------------- */
    setLocation(lat, lon) { this.lat = lat; this.lon = lon; this.invalidate(); }
    setTime(date) { this.time = date; this.invalidate(); }
    setView(lon, lat, fov) {
      this.view.lon = A.norm360(lon); this.view.lat = Math.max(-89.9, Math.min(89.9, lat));
      if (fov) this.fov = Math.max(this.minFov, Math.min(this.maxFov, fov));
      this._basis(); this.invalidate();
    }
    getView() {
      const f = this._cam.f;
      const lat = Math.asin(Math.max(-1, Math.min(1, f[2]))) * R2D;
      const lon = this.frame === 'horizon' ? A.norm360(Math.atan2(f[0], f[1]) * R2D) : A.norm360(Math.atan2(f[1], f[0]) * R2D);
      return { lon, lat, fov: this.fov };
    }
    setSensorBasis(b) { this.sensorBasis = b; if (b) this._cam = b; else this._basis(); this.invalidate(); }
    invalidate() { this._dirty = true; }
    start() { if (this._running) return; this._running = true; const loop = () => { if (!this._running) return; if (this._dirty) { this._dirty = false; this.render(); } requestAnimationFrame(loop); }; requestAnimationFrame(loop); }
    stop() { this._running = false; }
    destroy() { this.stop(); this._ro.disconnect(); }

    /** Smoothly rotate view to centre a J2000 vector. */
    flyTo(vJ2000, fov) {
      const w = this._world(vJ2000);
      const lat = Math.asin(w[2]) * R2D;
      const lon = this.frame === 'horizon' ? Math.atan2(w[0], w[1]) * R2D : Math.atan2(w[1], w[0]) * R2D;
      this.flyToView(lon, lat, fov);
    }

    /** Smoothly rotate view to frame coordinates (az/alt or ra/dec). */
    flyToView(lon, lat, fov) {
      const s = { lon: this.view.lon, lat: this.view.lat, fov: this.fov };
      let dl = A.norm180(lon - s.lon);
      const tf = fov || this.fov, t0 = performance.now();
      const step = t => {
        const p = Math.min(1, (t - t0) / 900), e = p < 0.5 ? 4 * p * p * p : 1 - Math.pow(-2 * p + 2, 3) / 2;
        if (this.sensorBasis) return;
        this.setView(s.lon + dl * e, s.lat + (lat - s.lat) * e, s.fov + (tf - s.fov) * e);
        if (p < 1) requestAnimationFrame(step); else this._emitView();
      };
      requestAnimationFrame(step);
    }

    /** Horizontal coordinates of a J2000 vector for the current observer/time. */
    altAz(vJ2000) { return A.toAltAz(A.apply(this._W(), vJ2000)); }

    resize() {
      const r = this.cv.getBoundingClientRect();
      const w = Math.max(1, Math.round(r.width)), h = Math.max(1, Math.round(r.height));
      if (w === this.w && h === this.h) return;
      this.w = w; this.h = h;
      this.cv.width = Math.round(w * this.dpr); this.cv.height = Math.round(h * this.dpr);
      this.invalidate();
    }

    /* ---------------- geometry ---------------- */
    _W() {
      if (this.frame !== 'horizon') return [1, 0, 0, 0, 1, 0, 0, 0, 1];
      const key = this.time.getTime() + ':' + this.lat + ':' + this.lon;
      if (this._wKey !== key) { this._wKey = key; this._wMat = A.j2000ToHorizon(this.time, this.lat, this.lon); }
      return this._wMat;
    }
    _world(v) { return A.apply(this._W(), v); }
    _basis() {
      const { lon, lat } = this.view;
      const cl = Math.cos(lat * D2R), sl = Math.sin(lat * D2R), co = Math.cos(lon * D2R), so = Math.sin(lon * D2R);
      const f = this.frame === 'horizon' ? [so * cl, co * cl, sl] : [co * cl, so * cl, sl];
      let r = cross(f, [0, 0, 1]);
      r = Math.hypot(...r) < 1e-6 ? (this._cam ? this._cam.r : [1, 0, 0]) : normalize(r);
      const u = cross(r, f);
      this._cam = { r, u, f };
    }
    _scale() {
      return this.projection === 'gnomonic'
        ? (this.h / 2) / Math.tan(this.fov * D2R / 2)
        : (this.h / 2) / (2 * Math.tan(this.fov * D2R / 4));
    }
    /** camera-space → screen; returns false if not drawable */
    _p(cx, cy, cz, out) {
      if (this.projection === 'gnomonic') {
        if (cz < 0.02) return false;
        out[0] = this.w / 2 + cx / cz * this.S; out[1] = this.h / 2 - cy / cz * this.S;
      } else {
        if (cz < -0.6) return false;
        const k = 2 / (1 + cz) * this.S;
        out[0] = this.w / 2 + cx * k; out[1] = this.h / 2 - cy * k;
      }
      return true;
    }
    _cm(M, v) { return [M[0] * v[0] + M[1] * v[1] + M[2] * v[2], M[3] * v[0] + M[4] * v[1] + M[5] * v[2], M[6] * v[0] + M[7] * v[1] + M[8] * v[2]]; }
    projectJ(v, out = [0, 0]) { const c = this._cm(this._M, v); return this._p(c[0], c[1], c[2], out) ? out : null; }
    projectF(v, out = [0, 0]) { const c = this._cm(this._C, v); return this._p(c[0], c[1], c[2], out) ? out : null; }
    _onScreen(p, m = 0) { return p && p[0] > -m && p[0] < this.w + m && p[1] > -m && p[1] < this.h + m; }

    /* ---------------- rendering ---------------- */
    render() {
      const cx = this.cx, w = this.w, h = this.h;
      if (!w || !h) return;
      sprites();
      cx.setTransform(this.dpr, 0, 0, this.dpr, 0, 0);
      const cam = this.sensorBasis || this._cam;
      this._cam = cam;
      this._C = [cam.r[0], cam.r[1], cam.r[2], cam.u[0], cam.u[1], cam.u[2], cam.f[0], cam.f[1], cam.f[2]];
      const W = this._W();
      this._M = A.mul(this._C, W);
      this.S = this._scale();
      this._labels = [];
      this._hits = [];

      // bodies (needed for sky colour)
      let sunAlt = -90;
      const bodies = this._bodies = [];
      if (this.frame === 'horizon' || this.layers.planets) {
        const P = A.planets(this.time);
        const m = A.moon(this.time);
        const mv = this.frame === 'horizon' ? A.topocentric(m.v, m.dist, this.time, this.lat, this.lon) : m.v;
        bodies.push(Object.assign({}, m, { v: mv }));
        for (const k of ['mercury', 'venus', 'mars', 'jupiter', 'saturn', 'sun']) bodies.push(P[k]);
        if (this.frame === 'horizon') sunAlt = A.toAltAz(A.apply(W, P.sun.v)).alt;
      }
      this.sunAlt = sunAlt;

      // background
      cx.clearRect(0, 0, w, h);
      if (!this.transparentBg) {
        cx.fillStyle = this._skyColor(sunAlt);
        cx.fillRect(0, 0, w, h);
      }
      // effective limiting magnitude: sky brightness & zoom
      let lim = this.magLimit + Math.max(0, Math.log2(60 / this.fov)) * 0.6;
      if (this.frame === 'horizon') {
        if (sunAlt > -18) lim = Math.min(lim, sunAlt > -6 ? (sunAlt > 0 ? -1.5 : 1.5) : 1.5 + (-6 - sunAlt) / 12 * 3.5);
      }
      this._lim = lim;
      const dayFade = this.frame === 'horizon' ? Math.max(0, Math.min(1, (-sunAlt - 2) / 10)) : 1;

      if (this.layers.milkyway && dayFade > 0.3) this._drawMilkyWay(dayFade);
      if (this.layers.eqGrid) this._drawEqGrid();
      if (this.frame === 'horizon' && this.layers.altazGrid) this._drawAltAzGrid();
      if (this.layers.lines) this._drawConLines();
      this._drawGuides();
      if (this.layers.stars) this._drawStars(lim);
      if (this.layers.planets) this._drawBodies();
      if (this.frame === 'horizon' && this.layers.ground) this._drawGround(sunAlt);
      if (this.layers.conNames) this._drawConNames();
      if (this.frame === 'horizon' && this.layers.cardinals) this._drawCardinals();
      this._drawTarget();
    }

    _skyColor(sunAlt) {
      if (this.frame !== 'horizon') return '#060816';
      const stops = [[-90, [4, 6, 15]], [-18, [5, 8, 20]], [-12, [10, 18, 42]], [-6, [24, 40, 84]], [0, [60, 96, 150]], [10, [92, 142, 205]], [90, [110, 165, 225]]];
      let i = 0; while (i < stops.length - 2 && sunAlt > stops[i + 1][0]) i++;
      const [a0, c0] = stops[i], [a1, c1] = stops[i + 1];
      const t = Math.max(0, Math.min(1, (sunAlt - a0) / (a1 - a0)));
      const c = c0.map((v, k) => Math.round(v + (c1[k] - v) * t));
      return `rgb(${c[0]},${c[1]},${c[2]})`;
    }

    _drawMilkyWay(fade) {
      const cx = this.cx, p = [0, 0];
      const rad = Math.max(6, 2.6 * D2R * this.S * (this.projection === 'gnomonic' ? 1 : 1));
      cx.save(); cx.globalCompositeOperation = 'lighter';
      for (const m of MW) {
        if (!this.projectJ(m.v, p) || !this._onScreen(p, rad)) continue;
        cx.globalAlpha = Math.min(0.2, 0.035 * m.w) * fade * (this.transparentBg ? 0.6 : 1);
        cx.drawImage(GLOW, p[0] - rad, p[1] - rad, rad * 2, rad * 2);
      }
      cx.restore();
    }

    _polyline(pts, useJ, color, width, dash) {
      const cx = this.cx, p = [0, 0];
      cx.save(); cx.strokeStyle = color; cx.lineWidth = width; if (dash) cx.setLineDash(dash);
      cx.beginPath();
      let pen = false;
      for (const v of pts) {
        const ok = useJ ? this.projectJ(v, p) : this.projectF(v, p);
        if (!ok) { pen = false; continue; }
        if (pen) cx.lineTo(p[0], p[1]); else { cx.moveTo(p[0], p[1]); pen = true; }
      }
      cx.stroke(); cx.restore();
    }

    _drawEqGrid() {
      const col = 'rgba(120,170,255,.16)';
      for (let dec = -60; dec <= 60; dec += 30) {
        const pts = []; for (let ra = 0; ra <= 360; ra += 4) pts.push(A.vec(ra, dec));
        this._polyline(pts, true, col, dec === 0 ? 1.4 : 0.8);
      }
      for (let ra = 0; ra < 360; ra += 30) {
        const pts = []; for (let dec = -88; dec <= 88; dec += 4) pts.push(A.vec(ra, dec));
        this._polyline(pts, true, col, 0.8);
      }
    }
    _drawAltAzGrid() {
      const col = 'rgba(120,255,190,.14)';
      const hv = (az, alt) => [Math.sin(az * D2R) * Math.cos(alt * D2R), Math.cos(az * D2R) * Math.cos(alt * D2R), Math.sin(alt * D2R)];
      for (let alt = 15; alt < 90; alt += 15) {
        const pts = []; for (let az = 0; az <= 360; az += 4) pts.push(hv(az, alt));
        this._polyline(pts, false, col, 0.8);
      }
      for (let az = 0; az < 360; az += 30) {
        const pts = []; for (let alt = -10; alt <= 88; alt += 4) pts.push(hv(az, alt));
        this._polyline(pts, false, col, 0.8);
      }
    }

    _drawConLines() {
      const cx = this.cx, a = [0, 0], b = [0, 0];
      const zoom = Math.max(1, Math.min(2.2, 70 / this.fov));
      for (const id in CONS) {
        const hl = this.highlight.get(id);
        if (!hl && !this.layers.allConLines) continue;
        const c = CONS[id];
        cx.strokeStyle = hl || (this.transparentBg ? 'rgba(150,190,255,.45)' : 'rgba(120,150,230,.32)');
        cx.lineWidth = (hl ? 1.8 : 1) * zoom;
        cx.beginPath();
        for (const l of c.lines) {
          for (let k = 0; k < l.length - 1; k++) {
            if (!this.projectJ(l[k], a) || !this.projectJ(l[k + 1], b)) continue;
            if (!this._onScreen(a, 400) && !this._onScreen(b, 400)) continue;
            // shorten segment near stars for a cleaner look
            const dx = b[0] - a[0], dy = b[1] - a[1], L = Math.hypot(dx, dy); if (L < 8) continue;
            const g = Math.min(5, L / 4) / L;
            cx.moveTo(a[0] + dx * g, a[1] + dy * g); cx.lineTo(b[0] - dx * g, b[1] - dy * g);
          }
        }
        cx.stroke();
      }
    }

    _drawGuides() {
      const cx = this.cx, p = [0, 0];
      for (const g of this.guides) {
        const pts = g.hips.map(h => { const n = NAME_BY_HIP.get(h); return n ? starVec(n.idx) : null; }).filter(Boolean);
        if (g.closed) pts.push(pts[0]);
        this._polyline(pts, true, g.color, 2.2, [10, 7]);
        if (g.label) {
          let sx = 0, sy = 0, n = 0;
          for (const v of pts) if (this.projectJ(v, p) && this._onScreen(p)) { sx += p[0]; sy += p[1]; n++; }
          if (n) this._label(g.label, sx / n, sy / n + (g.closed ? 0 : -14), g.color, 'bold 12px', true);
        }
      }
    }

    _drawStars(lim) {
      const cx = this.cx, M = this._M, S = this.S, w = this.w, h = this.h, P = this._proj, sp = SPRITES;
      const zoom = Math.max(1, Math.min(2.6, Math.pow(70 / this.fov, 0.6)));
      const gnom = this.projection === 'gnomonic';
      const m0 = M[0], m1 = M[1], m2 = M[2], m3 = M[3], m4 = M[4], m5 = M[5], m6 = M[6], m7 = M[7], m8 = M[8];
      const showNames = this.layers.starNames;
      const nameLim = Math.min(lim - 1.5, 1.6 + Math.max(0, Math.log2(60 / this.fov)) * 1.1);
      const boost = this.transparentBg ? 1.25 : 1;
      for (let i = 0; i < NSTAR; i++) {
        const mag = STAR_MAG[i];
        P[i * 3 + 2] = 0;
        if (mag > lim) continue; // sorted by magnitude → could break, but keep projections cleared
        const x = STAR_V[i * 3], y = STAR_V[i * 3 + 1], z = STAR_V[i * 3 + 2];
        const cz = m6 * x + m7 * y + m8 * z;
        let sx, sy;
        const cxv = m0 * x + m1 * y + m2 * z, cyv = m3 * x + m4 * y + m5 * z;
        if (gnom) { if (cz < 0.02) continue; sx = w / 2 + cxv / cz * S; sy = h / 2 - cyv / cz * S; }
        else { if (cz < -0.6) continue; const k = 2 / (1 + cz) * S; sx = w / 2 + cxv * k; sy = h / 2 - cyv * k; }
        if (sx < -10 || sx > w + 10 || sy < -10 || sy > h + 10) continue;
        const r = Math.max(0.55, (lim + 1.2 - mag) * 0.62) * zoom * boost;
        const a = Math.max(0.25, Math.min(1, (lim + 0.4 - mag) / 1.8));
        P[i * 3] = sx; P[i * 3 + 1] = sy; P[i * 3 + 2] = r;
        cx.globalAlpha = a;
        const s = r * 3.2;
        cx.drawImage(sp[STAR_COLOR_IDX[i]], sx - s / 2, sy - s / 2, s, s);
        if (showNames && mag < nameLim) {
          const n = NAME_BY_IDX.get(i);
          if (n) { cx.globalAlpha = 1; this._label(n.ko, sx, sy + r + 12, 'rgba(220,228,255,.78)', '11px'); }
        }
      }
      cx.globalAlpha = 1;
    }

    _drawBodies() {
      const cx = this.cx, p = [0, 0];
      for (const b of this._bodies) {
        if (!this.projectJ(b.v, p) || !this._onScreen(p, 40)) continue;
        const pxPerDeg = this.S * D2R * 2;
        if (b.key === 'sun' || b.key === 'moon') {
          const r = Math.max(b.key === 'sun' ? 9 : 8, 0.26 * pxPerDeg);
          const g = cx.createRadialGradient(p[0], p[1], r * 0.6, p[0], p[1], r * 4);
          g.addColorStop(0, b.key === 'sun' ? 'rgba(255,220,120,.55)' : 'rgba(240,240,255,.28)'); g.addColorStop(1, 'rgba(0,0,0,0)');
          cx.fillStyle = g; cx.beginPath(); cx.arc(p[0], p[1], r * 4, 0, Math.PI * 2); cx.fill();
          if (b.key === 'moon') this._drawMoonDisc(p[0], p[1], r, b);
          else { cx.fillStyle = '#ffe28a'; cx.beginPath(); cx.arc(p[0], p[1], r, 0, Math.PI * 2); cx.fill(); }
          this._label(b.ko, p[0], p[1] - r - 8, b.key === 'sun' ? '#ffd76a' : '#e9e7ff', 'bold 12px', true);
          this._hits.push({ x: p[0], y: p[1], r: Math.max(26, r + 10), obj: { kind: 'body', key: b.key, name: b.ko, data: b, vec: b.v } });
        } else {
          const r = Math.max(2.4, (2.5 - b.mag) * 1.1 + 2);
          cx.globalAlpha = 1;
          cx.drawImage(GLOW, p[0] - r * 3, p[1] - r * 3, r * 6, r * 6);
          cx.fillStyle = b.color; cx.beginPath(); cx.arc(p[0], p[1], r * 0.8, 0, Math.PI * 2); cx.fill();
          this._label(b.ko, p[0], p[1] - r - 7, '#ffd9a0', 'bold 12px', true);
          this._hits.push({ x: p[0], y: p[1], r: 24, obj: { kind: 'body', key: b.key, name: b.ko, data: b, vec: b.v } });
        }
      }
    }

    _drawMoonDisc(x, y, r, m) {
      const cx = this.cx;
      // orientation: bright limb faces the sun
      const sun = this._bodies.find(b => b.key === 'sun');
      const ps = [0, 0];
      let ang = 0;
      const cz = this._cm(this._M, sun.v);
      if (this.projection === 'gnomonic' && cz[2] < 0.02) ang = Math.atan2(-cz[1], cz[0]);
      else if (this.projectJ(sun.v, ps)) ang = Math.atan2(ps[1] - y, ps[0] - x);
      else ang = Math.atan2(-cz[1], cz[0]);
      cx.save(); cx.translate(x, y); cx.rotate(ang);
      cx.fillStyle = '#2b2d3a'; cx.beginPath(); cx.arc(0, 0, r, 0, Math.PI * 2); cx.fill();
      cx.fillStyle = '#f4f1e6';
      const k = 1 - 2 * m.illum; // terminator ellipse x-radius
      cx.beginPath();
      cx.arc(0, 0, r, -Math.PI / 2, Math.PI / 2, false);          // lit half toward +x (sun)
      cx.ellipse(0, 0, Math.abs(k) * r, r, 0, Math.PI / 2, -Math.PI / 2, k > 0);
      cx.fill();
      cx.restore();
    }

    _drawGround(sunAlt) {
      const cx = this.cx, w = this.w, h = this.h, C = this._C;
      const groundCol = this.transparentBg ? 'rgba(6,12,10,.35)' : (sunAlt > -6 ? 'rgba(20,30,24,.93)' : 'rgba(8,12,11,.9)');
      cx.save();
      cx.fillStyle = groundCol;
      if (this.projection === 'gnomonic') {
        // ground is the half-plane nx·X + ny·Y + nz·S < 0 (screen coords relative to centre, Y up)
        const n = [C[2], C[5], C[8]];
        let poly = [[-w / 2, -h / 2], [w / 2, -h / 2], [w / 2, h / 2], [-w / 2, h / 2]];
        const f = q => n[0] * q[0] + n[1] * q[1] + n[2] * this.S;
        const out = [];
        for (let i = 0; i < poly.length; i++) {
          const a = poly[i], b = poly[(i + 1) % poly.length], fa = f(a), fb = f(b);
          if (fa < 0) out.push(a);
          if ((fa < 0) !== (fb < 0)) { const t = fa / (fa - fb); out.push([a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t]); }
        }
        if (out.length > 2) {
          cx.beginPath(); out.forEach((q, i) => { const X = w / 2 + q[0], Y = h / 2 - q[1]; i ? cx.lineTo(X, Y) : cx.moveTo(X, Y); });
          cx.closePath(); cx.fill();
        }
      } else {
        const pts = [], p = [0, 0];
        for (let az = 0; az <= 360; az += 2) {
          const v = [Math.sin(az * D2R), Math.cos(az * D2R), 0];
          const c = this._cm(C, v);
          if (c[2] < -0.985) continue;
          const k = 2 / (1 + c[2]) * this.S; pts.push([w / 2 + c[0] * k, h / 2 - c[1] * k]);
        }
        cx.beginPath();
        pts.forEach((q, i) => i ? cx.lineTo(q[0], q[1]) : cx.moveTo(q[0], q[1]));
        cx.closePath();
        if (C[8] >= 0) { // looking above horizon → ground is outside the horizon circle
          cx.rect(-1e6, -1e6, 2e6, 2e6);
          cx.fill('evenodd');
        } else cx.fill();
      }
      cx.restore();
      // horizon line
      const hz = []; for (let az = 0; az <= 360; az += 2) hz.push([Math.sin(az * D2R), Math.cos(az * D2R), 0]);
      this._polyline(hz, false, this.transparentBg ? 'rgba(120,255,190,.7)' : 'rgba(120,200,160,.55)', 1.4);
    }

    _drawCardinals() {
      const p = [0, 0];
      for (const [name, az, major] of CARDINALS) {
        const v = [Math.sin(az * D2R) * Math.cos(-2 * D2R), Math.cos(az * D2R) * Math.cos(-2 * D2R), Math.sin(-2 * D2R)];
        if (!this.projectF(v, p) || !this._onScreen(p, 20)) continue;
        this._label(name, p[0], p[1] + 16, major ? (az === 0 ? '#ff7a7a' : '#8fe3b5') : 'rgba(143,227,181,.6)', major ? 'bold 15px' : '12px', true);
      }
    }

    _drawConNames() {
      const p = [0, 0];
      for (const id in CONS) {
        const c = CONS[id];
        const hl = this.highlight.get(id);
        if (!hl && this.fov > 100 && c.rank > 2) continue;
        if (!this.projectJ(c.lbl, p) || !this._onScreen(p)) continue;
        if (this.frame === 'horizon' && this.layers.ground && this._world(c.lbl)[2] < -0.01 && !(this.target && this.target.id === id)) continue;
        this._label(c.ko, p[0], p[1], hl || 'rgba(170,190,255,.62)', hl ? 'bold 13px' : '11px', !!hl);
        this._hits.push({ x: p[0], y: p[1], r: 40, obj: { kind: 'con', id, name: c.ko, vec: c.center } });
      }
    }

    _label(text, x, y, color, font, force) {
      const cx = this.cx;
      if (this.fontScale !== 1) font = font.replace(/(\d+)px/, (m, n) => Math.round(n * this.fontScale) + 'px');
      cx.font = font + ' "Noto Sans KR", system-ui, sans-serif';
      const tw = cx.measureText(text).width, rect = [x - tw / 2 - 2, y - 11, tw + 4, 14];
      if (!force) for (const r of this._labels) if (rect[0] < r[0] + r[2] && rect[0] + rect[2] > r[0] && rect[1] < r[1] + r[3] && rect[1] + rect[3] > r[1]) return;
      this._labels.push(rect);
      cx.textAlign = 'center';
      cx.lineWidth = 3; cx.strokeStyle = 'rgba(3,5,14,.75)'; cx.strokeText(text, x, y);
      cx.fillStyle = color; cx.fillText(text, x, y);
    }

    _drawTarget() {
      const t = this.target;
      if (!t) return;
      const cx = this.cx, w = this.w, h = this.h, v = t.vec(), p = [0, 0];
      const c = this._cm(this._M, v);
      const vis = this.projectJ(v, p) && this._onScreen(p, -24);
      const ang = Math.acos(Math.max(-1, Math.min(1, c[2]))) * R2D; // angle from view centre
      const now = performance.now();
      if (vis) {
        const pulse = 1 + 0.12 * Math.sin(now / 220);
        const R = 26 * pulse;
        cx.save(); cx.strokeStyle = '#ffd166'; cx.lineWidth = 2.2;
        cx.beginPath(); cx.arc(p[0], p[1], R, 0, Math.PI * 2); cx.stroke();
        for (let k = 0; k < 4; k++) {
          const a = k * Math.PI / 2; cx.beginPath();
          cx.moveTo(p[0] + Math.cos(a) * (R + 4), p[1] + Math.sin(a) * (R + 4));
          cx.lineTo(p[0] + Math.cos(a) * (R + 14), p[1] + Math.sin(a) * (R + 14)); cx.stroke();
        }
        cx.restore();
        this._label(t.label, p[0], p[1] + R + 20, '#ffd166', 'bold 14px', true);
      } else {
        // edge arrow toward target direction on the image plane
        let dx = c[0], dy = -c[1];
        const L = Math.hypot(dx, dy) || 1; dx /= L; dy /= L;
        const pad = 46, hw = w / 2 - pad, hh = h / 2 - pad;
        const s = Math.min(hw / Math.abs(dx || 1e-6), hh / Math.abs(dy || 1e-6));
        const ex = w / 2 + dx * s, ey = h / 2 + dy * s;
        cx.save(); cx.translate(ex, ey); cx.rotate(Math.atan2(dy, dx));
        const bob = 4 * Math.sin(now / 180);
        cx.translate(bob, 0);
        cx.fillStyle = '#ffd166'; cx.shadowColor = 'rgba(255,209,102,.7)'; cx.shadowBlur = 14;
        cx.beginPath(); cx.moveTo(20, 0); cx.lineTo(-6, -14); cx.lineTo(-1, 0); cx.lineTo(-6, 14); cx.closePath(); cx.fill();
        cx.restore();
        this._label(`${t.label} ${Math.round(ang)}°`, ex - dx * 34, ey - dy * 34 + 4, '#ffd166', 'bold 12px', true);
      }
      if (this.onTarget) {
        const hz = this.frame === 'horizon' ? A.toAltAz(A.apply(this._W(), v)) : null;
        const f = this._cam.f;
        const camAlt = Math.asin(Math.max(-1, Math.min(1, f[2]))) * R2D, camAz = A.norm360(Math.atan2(f[0], f[1]) * R2D);
        // offsets in the camera's own frame: how far to turn the device right / up
        const right = Math.atan2(c[0], c[2]) * R2D, up = Math.atan2(c[1], Math.hypot(c[0], c[2])) * R2D;
        this.onTarget({ visible: vis, angle: ang, target: hz, camAz, camAlt, right, up });
      }
      this.invalidate(); // keep animating the reticle
    }

    /* ---------------- input ---------------- */
    _bindInput() {
      const cv = this.cv;
      const pts = new Map();
      let last = null, pinch0 = 0, fov0 = 0, moved = 0, downT = 0, vel = [0, 0], lastMoveT = 0, inertia = null;
      const degPerPx = () => this.fov / this.h;
      const pan = (dx, dy) => {
        if (this.sensorBasis) { if (this.onCalibrate) this.onCalibrate(-dx * degPerPx()); return; }
        const k = degPerPx() * (this.projection === 'stereo' ? 0.9 : 1);
        if (this.frame === 'horizon') this.setView(this.view.lon - dx * k, this.view.lat + dy * k);
        else this.setView(this.view.lon + dx * k, this.view.lat + dy * k);
      };
      cv.addEventListener('pointerdown', e => {
        cv.setPointerCapture(e.pointerId);
        pts.set(e.pointerId, [e.clientX, e.clientY]);
        if (inertia) { cancelAnimationFrame(inertia); inertia = null; }
        if (pts.size === 1) { last = [e.clientX, e.clientY]; moved = 0; downT = performance.now(); vel = [0, 0]; }
        if (pts.size === 2) { const [a, b] = [...pts.values()]; pinch0 = Math.hypot(a[0] - b[0], a[1] - b[1]); fov0 = this.fov; }
      });
      cv.addEventListener('pointermove', e => {
        if (!pts.has(e.pointerId)) return;
        pts.set(e.pointerId, [e.clientX, e.clientY]);
        if (pts.size === 2) {
          const [a, b] = [...pts.values()]; const d = Math.hypot(a[0] - b[0], a[1] - b[1]);
          if (pinch0 > 0) { this.fov = Math.max(this.minFov, Math.min(this.maxFov, fov0 * pinch0 / d)); this.invalidate(); this._emitView(); }
          moved += 10; return;
        }
        if (pts.size === 1 && last) {
          const dx = e.clientX - last[0], dy = e.clientY - last[1];
          moved += Math.abs(dx) + Math.abs(dy);
          const t = performance.now(), dt = Math.max(1, t - lastMoveT); lastMoveT = t;
          vel = [dx / dt * 16, dy / dt * 16];
          last = [e.clientX, e.clientY];
          pan(dx, dy);
        }
      });
      const up = e => {
        const wasSingle = pts.size === 1;
        pts.delete(e.pointerId);
        if (pts.size < 2) pinch0 = 0;
        if (wasSingle && pts.size === 0) {
          if (moved < 8 && performance.now() - downT < 400) this._tap(e.clientX, e.clientY);
          else if (!this.sensorBasis && performance.now() - lastMoveT < 60) {
            const run = () => {
              vel = [vel[0] * 0.92, vel[1] * 0.92];
              if (Math.abs(vel[0]) + Math.abs(vel[1]) < 0.2) { inertia = null; this._emitView(); return; }
              pan(vel[0], vel[1]); inertia = requestAnimationFrame(run);
            };
            inertia = requestAnimationFrame(run);
          } else this._emitView();
        }
        if (pts.size === 1) last = [...pts.values()][0];
      };
      cv.addEventListener('pointerup', up);
      cv.addEventListener('pointercancel', up);
      cv.addEventListener('wheel', e => {
        e.preventDefault();
        this.fov = Math.max(this.minFov, Math.min(this.maxFov, this.fov * Math.exp(e.deltaY * 0.0012)));
        this.invalidate(); this._emitView();
      }, { passive: false });
    }
    _emitView() { if (this.onViewChange) this.onViewChange(this.getView()); }

    _tap(clientX, clientY) {
      const r = this.cv.getBoundingClientRect(), x = clientX - r.left, y = clientY - r.top;
      let best = null, bd = 1e9;
      for (const hObj of this._hits) {
        const d = Math.hypot(hObj.x - x, hObj.y - y);
        if (d < hObj.r && d - (hObj.obj.kind === 'body' ? 20 : 0) < bd) { bd = d - (hObj.obj.kind === 'body' ? 20 : 0); best = hObj.obj; }
      }
      // stars (projected cache)
      const P = this._proj;
      for (let i = 0; i < NSTAR; i++) {
        if (!P[i * 3 + 2]) continue;
        const d = Math.hypot(P[i * 3] - x, P[i * 3 + 1] - y);
        const rad = Math.max(16, P[i * 3 + 2] * 2.5);
        if (d < rad && d - 6 < bd) {
          const n = NAME_BY_IDX.get(i);
          bd = d - 6;
          best = { kind: 'star', idx: i, name: n ? n.ko : `${STAR_MAG[i].toFixed(1)}등급 별`, en: n && n.en, desig: n && n.desig, mag: STAR_MAG[i], vec: starVec(i) };
        }
      }
      // otherwise: constellation whose figure is nearest
      if (!best && this.layers.lines) {
        const a = [0, 0];
        let bestC = null, bcd = 60;
        for (const id in CONS) for (const l of CONS[id].lines) for (const v of l) {
          if (!this.projectJ(v, a)) continue;
          const d = Math.hypot(a[0] - x, a[1] - y); if (d < bcd) { bcd = d; bestC = id; }
        }
        if (bestC) best = { kind: 'con', id: bestC, name: CONS[bestC].ko, vec: CONS[bestC].center };
      }
      if (best && this.onSelect) this.onSelect(best);
    }
  }

  function starVec(i) { return [STAR_V[i * 3], STAR_V[i * 3 + 1], STAR_V[i * 3 + 2]]; }

  SkyRenderer.CONS = CONS;
  SkyRenderer.STAR_NAMES = STAR_NAMES;
  SkyRenderer.NAME_BY_HIP = NAME_BY_HIP;
  SkyRenderer.starVec = starVec;
  SkyRenderer.starMag = i => STAR_MAG[i];
  SkyRenderer.hipVec = hip => { const n = NAME_BY_HIP.get(hip); return n ? starVec(n.idx) : null; };
  global.SkyRenderer = SkyRenderer;
})(window);
