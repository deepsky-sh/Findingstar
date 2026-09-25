/* ==========================================================================
   Astro — lightweight positional astronomy for the browser
   - Sidereal time (IAU 1982), J2000 → date precession (Lieske 1977)
   - Sun & planets: JPL "Keplerian elements for approximate positions" (1800–2050)
   - Moon: Schlyter series with main perturbations + topocentric parallax
   - Rise / set / transit by sampled altitude root finding
   All angles in degrees unless noted. Frames are right-handed unit vectors:
     equatorial: x → (RA 0, Dec 0), y → (RA 90°), z → north celestial pole
     horizontal (ENU): x → East, y → North, z → Zenith
   ========================================================================== */
(function (global) {
  'use strict';
  const D2R = Math.PI / 180, R2D = 180 / Math.PI;
  const sin = x => Math.sin(x * D2R), cos = x => Math.cos(x * D2R);
  const norm360 = x => ((x % 360) + 360) % 360;
  const norm180 = x => { x = norm360(x); return x > 180 ? x - 360 : x; };

  const jd = date => date.getTime() / 86400000 + 2440587.5;
  const centuries = date => (jd(date) - 2451545.0) / 36525;

  /** Greenwich mean sidereal time in degrees. */
  function gmst(date) {
    const JD = jd(date), T = (JD - 2451545.0) / 36525;
    return norm360(280.46061837 + 360.98564736629 * (JD - 2451545.0) + 0.000387933 * T * T - T * T * T / 38710000);
  }
  /** Local sidereal time in degrees (east longitude positive). */
  const lst = (date, lon) => norm360(gmst(date) + lon);

  /* ---------------- vectors & matrices (row-major 3x3 arrays of 9) ---------------- */
  const vec = (ra, dec) => [cos(dec) * cos(ra), cos(dec) * sin(ra), sin(dec)];
  const mul = (a, b) => {
    const r = new Array(9);
    for (let i = 0; i < 3; i++) for (let j = 0; j < 3; j++)
      r[i * 3 + j] = a[i * 3] * b[j] + a[i * 3 + 1] * b[3 + j] + a[i * 3 + 2] * b[6 + j];
    return r;
  };
  const apply = (m, v) => [
    m[0] * v[0] + m[1] * v[1] + m[2] * v[2],
    m[3] * v[0] + m[4] * v[1] + m[5] * v[2],
    m[6] * v[0] + m[7] * v[1] + m[8] * v[2]];
  const rotZ = a => { const c = cos(a), s = sin(a); return [c, -s, 0, s, c, 0, 0, 0, 1]; };
  const rotY = a => { const c = cos(a), s = sin(a); return [c, 0, s, 0, 1, 0, -s, 0, c]; };
  const rotX = a => { const c = cos(a), s = sin(a); return [1, 0, 0, 0, c, -s, 0, s, c]; };

  /** Precession matrix J2000 → mean equator of date. */
  function precession(date) {
    const T = centuries(date);
    const zeta = (2306.2181 * T + 0.30188 * T * T + 0.017998 * T * T * T) / 3600;
    const z = (2306.2181 * T + 1.09468 * T * T + 0.018203 * T * T * T) / 3600;
    const theta = (2004.3109 * T - 0.42665 * T * T - 0.041833 * T * T * T) / 3600;
    return mul(rotZ(z), mul(rotY(-theta), rotZ(zeta)));
  }

  /** Equatorial-of-date → horizontal (ENU) for a given local sidereal time and latitude. */
  function eqToHorMatrix(lstDeg, lat) {
    // Rotate so the local meridian is at x, then tilt the pole down to the latitude.
    // hour angle H = LST − RA. In (x=towards H=0 on equator, y=towards H=−90 (east)) basis:
    const m1 = rotZ(-lstDeg); // RA → −H frame: x toward meridian
    const sl = sin(lat), cl = cos(lat);
    // meridian-equator point (x) has alt = 90−lat pointing south; pole (z) at alt=lat pointing north.
    // ENU basis: E = y', N = −sl·x' + cl·z', U = cl·x' + sl·z'
    const m2 = [0, 1, 0, -sl, 0, cl, cl, 0, sl];
    return mul(m2, m1);
  }

  /** Full J2000-equatorial → horizontal matrix for an observer. */
  function j2000ToHorizon(date, lat, lon) {
    return mul(eqToHorMatrix(lst(date, lon), lat), precession(date));
  }

  function toAltAz(v) {
    const alt = Math.asin(Math.max(-1, Math.min(1, v[2]))) * R2D;
    const az = norm360(Math.atan2(v[0], v[1]) * R2D);
    return { alt, az };
  }
  function toRaDec(v) {
    return { ra: norm360(Math.atan2(v[1], v[0]) * R2D), dec: Math.asin(Math.max(-1, Math.min(1, v[2]))) * R2D };
  }

  /** Standard atmospheric refraction (Bennett), degrees to add to geometric altitude. */
  function refraction(alt) {
    if (alt < -1.5) return 0;
    return 1.02 / Math.tan((alt + 10.3 / (alt + 5.11)) * D2R) / 60;
  }

  /* ---------------- Sun & planets ---------------- */
  // a, e, I, L, long.peri, long.node  and rates per Julian century (JPL, Standish)
  const ELEMENTS = {
    mercury: [0.38709927, 0.20563593, 7.00497902, 252.25032350, 77.45779628, 48.33076593,
      0.00000037, 0.00001906, -0.00594749, 149472.67411175, 0.16047689, -0.12534081],
    venus: [0.72333566, 0.00677672, 3.39467605, 181.97909950, 131.60246718, 76.67984255,
      0.00000390, -0.00004107, -0.00078890, 58517.81538729, 0.00268329, -0.27769418],
    earth: [1.00000261, 0.01671123, -0.00001531, 100.46457166, 102.93768193, 0.0,
      0.00000562, -0.00004392, -0.01294668, 35999.37244981, 0.32327364, 0.0],
    mars: [1.52371034, 0.09339410, 1.84969142, -4.55343205, -23.94362959, 49.55953891,
      0.00001847, 0.00007882, -0.00813131, 19140.30268499, 0.44441088, -0.29257343],
    jupiter: [5.20288700, 0.04838624, 1.30439695, 34.39644051, 14.72847983, 100.47390909,
      -0.00011607, -0.00013253, -0.00183714, 3034.74612775, 0.21252668, 0.20469106],
    saturn: [9.53667594, 0.05386179, 2.48599187, 49.95424423, 92.59887831, 113.66242448,
      -0.00125060, -0.00050991, 0.00193609, 1222.49362201, -0.41897216, -0.28867794]
  };
  const OBL_J2000 = 23.43928;

  function helio(name, T) {
    const el = ELEMENTS[name];
    const a = el[0] + el[6] * T, e = el[1] + el[7] * T, I = el[2] + el[8] * T;
    const L = el[3] + el[9] * T, wbar = el[4] + el[10] * T, node = el[5] + el[11] * T;
    const w = wbar - node;
    const M = norm180(L - wbar);
    let E = M + R2D * e * sin(M);
    for (let k = 0; k < 8; k++) {
      const dM = M - (E - R2D * e * sin(E));
      E += dM / (1 - e * cos(E));
    }
    const xp = a * (cos(E) - e), yp = a * Math.sqrt(1 - e * e) * sin(E);
    const cw = cos(w), sw = sin(w), cO = cos(node), sO = sin(node), cI = cos(I), sI = sin(I);
    return [
      (cw * cO - sw * sO * cI) * xp + (-sw * cO - cw * sO * cI) * yp,
      (cw * sO + sw * cO * cI) * xp + (-sw * sO + cw * cO * cI) * yp,
      (sw * sI) * xp + (cw * sI) * yp];
  }
  const eclToEq = v => {
    const c = cos(OBL_J2000), s = sin(OBL_J2000);
    return [v[0], c * v[1] - s * v[2], s * v[1] + c * v[2]];
  };

  const PLANET_INFO = {
    mercury: { ko: '수성', color: '#c9b8a6', mag: [-0.36, 0.027, 2.2e-13, 6] },
    venus: { ko: '금성', color: '#fff1c1', mag: [-4.34, 0.013, 4.2e-7, 3] },
    mars: { ko: '화성', color: '#ff8a5c', mag: [-1.51, 0.016, 0, 1] },
    jupiter: { ko: '목성', color: '#ffe0b0', mag: [-9.25, 0.014, 0, 1] },
    saturn: { ko: '토성', color: '#f3dc9b', mag: [-9.0, 0.044, 0, 1] }
  };

  /** Geocentric J2000 equatorial position of sun & planets. */
  function planets(date) {
    const T = centuries(date);
    const earth = helio('earth', T);
    const out = {};
    const sunGeo = eclToEq([-earth[0], -earth[1], -earth[2]]);
    const Rs = Math.hypot(...sunGeo);
    out.sun = { key: 'sun', ko: '태양', v: sunGeo.map(x => x / Rs), dist: Rs, mag: -26.7, color: '#ffd76a' };
    for (const name of Object.keys(PLANET_INFO)) {
      const h = helio(name, T);
      const g = [h[0] - earth[0], h[1] - earth[1], h[2] - earth[2]];
      const r = Math.hypot(...h), R = Math.hypot(...g);
      // phase angle between sun and earth as seen from planet
      const cosFV = (r * r + R * R - Rs * Rs) / (2 * r * R);
      const FV = Math.acos(Math.max(-1, Math.min(1, cosFV))) * R2D;
      const p = PLANET_INFO[name].mag;
      let mag = p[0] + 5 * Math.log10(r * R) + p[1] * FV + p[2] * Math.pow(FV, p[3]);
      if (name === 'saturn') mag += 0.0; // ring tilt ignored
      const eq = eclToEq(g);
      out[name] = { key: name, ko: PLANET_INFO[name].ko, color: PLANET_INFO[name].color,
        v: eq.map(x => x / R), dist: R, mag: Math.round(mag * 10) / 10 };
    }
    return out;
  }

  /* ---------------- Moon ---------------- */
  /** Geocentric moon: J2000 equatorial unit vector, distance in Earth radii, phase info. */
  function moon(date) {
    const d = jd(date) - 2451543.5;
    const N = norm360(125.1228 - 0.0529538083 * d);
    const i = 5.1454, a = 60.2666, e = 0.054900;
    const w = norm360(318.0634 + 0.1643573223 * d);
    const M = norm360(115.3654 + 13.0649929509 * d);
    let E = M + R2D * e * sin(M) * (1 + e * cos(M));
    for (let k = 0; k < 6; k++) E = E - (E - R2D * e * sin(E) - M) / (1 - e * cos(E));
    const xv = a * (cos(E) - e), yv = a * Math.sqrt(1 - e * e) * sin(E);
    const v = Math.atan2(yv, xv) * R2D;
    let r = Math.hypot(xv, yv);
    const xh = r * (cos(N) * cos(v + w) - sin(N) * sin(v + w) * cos(i));
    const yh = r * (sin(N) * cos(v + w) + cos(N) * sin(v + w) * cos(i));
    const zh = r * (sin(v + w) * sin(i));
    let lon = Math.atan2(yh, xh) * R2D, lat = Math.atan2(zh, Math.hypot(xh, yh)) * R2D;

    const Ms = norm360(356.0470 + 0.9856002585 * d);
    const ws = 282.9404 + 4.70935e-5 * d;
    const Ls = Ms + ws, Lm = M + w + N;
    const D = Lm - Ls, F = Lm - N;
    lon += -1.274 * sin(M - 2 * D) + 0.658 * sin(2 * D) - 0.186 * sin(Ms) - 0.059 * sin(2 * M - 2 * D)
      - 0.057 * sin(M - 2 * D + Ms) + 0.053 * sin(M + 2 * D) + 0.046 * sin(2 * D - Ms)
      + 0.041 * sin(M - Ms) - 0.035 * sin(D) - 0.031 * sin(M + Ms) - 0.015 * sin(2 * F - 2 * D)
      + 0.011 * sin(M - 4 * D);
    lat += -0.173 * sin(F - 2 * D) - 0.055 * sin(M - F - 2 * D) - 0.046 * sin(M + F - 2 * D)
      + 0.033 * sin(F + 2 * D) + 0.017 * sin(2 * M + F);
    r += -0.58 * cos(M - 2 * D) - 0.46 * cos(2 * D);

    // ecliptic of date → ecliptic J2000 (remove general precession in longitude)
    const T = centuries(date);
    lon -= 1.396971 * T;
    const ecl = [cos(lat) * cos(lon), cos(lat) * sin(lon), sin(lat)];
    const eq = eclToEq(ecl);

    // phase: elongation from the sun
    const sunLon = norm360(Ls);
    const elong = Math.acos(cos(lat) * cos(lon + 1.396971 * T - sunLon)) * R2D;
    const illum = (1 - cos(elong)) / 2;
    const waxing = norm360(lon + 1.396971 * T - sunLon) < 180;
    const age = norm360(lon + 1.396971 * T - sunLon) / 360 * 29.530589;
    return { key: 'moon', ko: '달', v: eq, dist: r, illum, waxing, age, elong, mag: -12.7 * illum, color: '#f4f1e6' };
  }

  function moonPhaseName(m) {
    const a = m.age;
    if (a < 1.2 || a > 28.3) return '삭 (그믐)';
    if (a < 6.4) return '초승달';
    if (a < 8.4) return '상현달';
    if (a < 13.8) return '차가는 달';
    if (a < 15.8) return '보름달';
    if (a < 21.1) return '기우는 달';
    if (a < 23.1) return '하현달';
    return '그믐달';
  }

  /** Topocentric correction of the moon's J2000 direction (parallax up to ~1°). */
  function topocentric(v, distEarthRadii, date, lat, lon) {
    const H = j2000ToHorizon(date, lat, lon);
    const h = apply(H, v).map(x => x * distEarthRadii);
    h[2] -= 1; // observer is 1 Earth radius "up" from the geocentre (ENU)
    const n = Math.hypot(...h);
    // back to J2000: H is orthonormal → transpose
    const Ht = [H[0], H[3], H[6], H[1], H[4], H[7], H[2], H[5], H[8]];
    return apply(Ht, h.map(x => x / n));
  }

  /* ---------------- rise / set ---------------- */
  /**
   * Find rise, transit and set around a date for a body whose J2000 direction is given by fn(date).
   * h0 = altitude threshold (−0.833 sun, +0.125 moon approx, −0.5667 stars).
   * Searches from `from` over `hours` hours. Returns {rise, set, transit, maxAlt, alwaysUp, neverUp}.
   */
  function riseSet(fn, from, lat, lon, h0 = -0.5667, hours = 24, stepMin = 10) {
    const alt = t => toAltAz(apply(j2000ToHorizon(t, lat, lon), fn(t))).alt;
    const t0 = from.getTime(), step = stepMin * 60000, n = Math.ceil(hours * 60 / stepMin);
    let prevT = t0, prevA = alt(from) - h0, rise = null, set = null, maxAlt = -99, transit = null;
    let anyUp = prevA > 0, anyDown = prevA <= 0;
    const refine = (ta, tb, fa) => {
      let a = ta, b = tb, va = fa;
      for (let k = 0; k < 12; k++) {
        const m = (a + b) / 2, vm = alt(new Date(m)) - h0;
        if ((vm > 0) === (va > 0)) { a = m; va = vm; } else b = m;
      }
      return new Date((a + b) / 2);
    };
    for (let k = 1; k <= n; k++) {
      const t = t0 + k * step, a = alt(new Date(t)) - h0;
      if (a + h0 > maxAlt) { maxAlt = a + h0; transit = new Date(t); }
      if (a > 0) anyUp = true; else anyDown = true;
      if (prevA <= 0 && a > 0 && !rise) rise = refine(prevT, t, prevA);
      if (prevA > 0 && a <= 0 && !set) set = refine(prevT, t, prevA);
      prevT = t; prevA = a;
    }
    return { rise, set, transit, maxAlt, alwaysUp: !anyDown, neverUp: !anyUp };
  }

  /** Twilight / night summary for the evening that starts on `date` (local). */
  function nightInfo(date, lat, lon) {
    const noon = new Date(date); noon.setHours(12, 0, 0, 0);
    const sunFn = t => planets(t).sun.v;
    const sunset = riseSet(sunFn, noon, lat, lon, -0.833, 24, 15);
    const astro = riseSet(sunFn, noon, lat, lon, -18, 24, 15);
    return { sunset: sunset.set, sunrise: sunset.rise, darkStart: astro.set, darkEnd: astro.rise };
  }

  global.Astro = {
    D2R, R2D, sin, cos, norm360, norm180, jd, gmst, lst, vec, mul, apply, rotX, rotY, rotZ,
    precession, eqToHorMatrix, j2000ToHorizon, toAltAz, toRaDec, refraction,
    planets, moon, moonPhaseName, topocentric, riseSet, nightInfo, PLANET_INFO
  };
})(typeof window !== 'undefined' ? window : globalThis);
