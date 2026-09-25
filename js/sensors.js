/* ==========================================================================
   Sensors — device orientation (gyro + compass) → camera basis in ENU,
   geolocation, and rear camera stream for AR overlay.
   ========================================================================== */
(function (global) {
  'use strict';
  const D2R = Math.PI / 180, R2D = 180 / Math.PI;
  const cross = (a, b) => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
  const norm = a => { const n = Math.hypot(a[0], a[1], a[2]) || 1; return [a[0] / n, a[1] / n, a[2] / n]; };
  const dot = (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
  const rotUp = (v, deg) => { const c = Math.cos(deg * D2R), s = Math.sin(deg * D2R); return [c * v[0] - s * v[1], s * v[0] + c * v[1], v[2]]; };

  /** W3C DeviceOrientation: R = Rz(alpha)·Rx(beta)·Ry(gamma), device frame → earth frame (ENU). */
  function rotationMatrix(alpha, beta, gamma) {
    const ca = Math.cos(alpha * D2R), sa = Math.sin(alpha * D2R);
    const cb = Math.cos(beta * D2R), sb = Math.sin(beta * D2R);
    const cg = Math.cos(gamma * D2R), sg = Math.sin(gamma * D2R);
    return [
      ca * cg - sa * sb * sg, -sa * cb, ca * sg + sa * sb * cg,
      sa * cg + ca * sb * sg, ca * cb, sa * sg - ca * sb * cg,
      -cb * sg, sb, cb * cg];
  }
  const col = (R, j) => [R[j], R[3 + j], R[6 + j]];

  class OrientationSensor {
    constructor() {
      this.listeners = new Set();
      this.active = false;
      this.calibration = 0;     // user azimuth correction (deg, + = rotate view clockwise)
      this.headingOffset = null; // iOS: relative alpha → true north
      this.absolute = false;
      this.smoothF = null; this.smoothU = null;
      this._handler = e => this._onEvent(e);
      this.lastEventAt = 0;
      this.accuracy = null;
    }
    static get supported() { return 'DeviceOrientationEvent' in global; }
    static get needsPermission() { return typeof global.DeviceOrientationEvent?.requestPermission === 'function'; }

    /** Must be called from a user gesture on iOS. Resolves true when events arrive. */
    async start() {
      if (!OrientationSensor.supported) throw new Error('unsupported');
      if (OrientationSensor.needsPermission) {
        const res = await global.DeviceOrientationEvent.requestPermission();
        if (res !== 'granted') throw new Error('denied');
      }
      this.stop();
      this.active = true;
      this.smoothF = this.smoothU = null;
      this._evtName = 'ondeviceorientationabsolute' in global ? 'deviceorientationabsolute' : 'deviceorientation';
      global.addEventListener(this._evtName, this._handler, true);
      return new Promise((resolve, reject) => {
        const t0 = Date.now();
        const check = () => {
          if (!this.active) return reject(new Error('stopped'));
          if (this.lastEventAt > t0) return resolve(true);
          if (Date.now() - t0 > 2000) { this.stop(); return reject(new Error('no-data')); }
          setTimeout(check, 100);
        };
        check();
      });
    }
    stop() {
      this.active = false;
      if (this._evtName) global.removeEventListener(this._evtName, this._handler, true);
    }
    onChange(fn) { this.listeners.add(fn); return () => this.listeners.delete(fn); }

    _screenAngle() {
      const a = global.screen?.orientation?.angle ?? global.orientation ?? 0;
      return ((a % 360) + 360) % 360;
    }

    _onEvent(e) {
      if (e.alpha == null || e.beta == null || e.gamma == null) return;
      this.lastEventAt = Date.now();
      const R = rotationMatrix(e.alpha, e.beta, e.gamma);
      const th = this._screenAngle() * D2R;
      // screen axes expressed in device coordinates, then in world
      const dRight = [Math.cos(th), -Math.sin(th), 0];
      const dUp = [Math.sin(th), Math.cos(th), 0];
      const mulv = v => [R[0] * v[0] + R[1] * v[1] + R[2] * v[2], R[3] * v[0] + R[4] * v[1] + R[5] * v[2], R[6] * v[0] + R[7] * v[1] + R[8] * v[2]];
      let f = col(R, 2).map(x => -x); // rear camera looks along −z
      let u = mulv(dUp);

      const isAbs = e.type === 'deviceorientationabsolute' || e.absolute === true;
      this.absolute = isAbs || typeof e.webkitCompassHeading === 'number';
      if (!isAbs && typeof e.webkitCompassHeading === 'number' && e.webkitCompassHeading >= 0) {
        // iOS: alpha is relative. Compare the heading of a reference axis with the compass.
        this.accuracy = e.webkitCompassAccuracy;
        const ref = Math.hypot(f[0], f[1]) > 0.5 ? f : col(R, 1); // camera if upright, device top if flat
        const hRel = Math.atan2(ref[0], ref[1]) * R2D;
        const off = hRel - e.webkitCompassHeading; // rotate world by +off (CCW) to align north
        if (this.headingOffset == null) this.headingOffset = off;
        else { // circular low-pass
          const d = ((off - this.headingOffset + 540) % 360) - 180;
          this.headingOffset += d * 0.08;
        }
      }
      const rot = (this.headingOffset || 0) - this.calibration;
      if (rot) { f = rotUp(f, rot); u = rotUp(u, rot); }

      // exponential smoothing on the basis vectors (no angle wrap issues)
      const k = 0.28;
      if (!this.smoothF) { this.smoothF = f; this.smoothU = u; }
      else {
        this.smoothF = norm(this.smoothF.map((x, i) => x + (f[i] - x) * k));
        this.smoothU = norm(this.smoothU.map((x, i) => x + (u[i] - x) * k));
      }
      const F = this.smoothF;
      let U = norm(this.smoothU.map((x, i) => x - dot(this.smoothU, F) * F[i]));
      const Rr = cross(F, U);
      const basis = { r: Rr, u: U, f: F };
      for (const fn of this.listeners) fn(basis);
    }
  }

  /* ---------------- geolocation ---------------- */
  function getPosition(opts = {}) {
    return new Promise((resolve, reject) => {
      if (!('geolocation' in navigator)) return reject(new Error('unsupported'));
      navigator.geolocation.getCurrentPosition(
        p => resolve({ lat: p.coords.latitude, lon: p.coords.longitude, acc: p.coords.accuracy }),
        err => reject(err),
        Object.assign({ enableHighAccuracy: false, timeout: 12000, maximumAge: 5 * 60000 }, opts));
    });
  }

  /* ---------------- rear camera ---------------- */
  async function startCamera(video) {
    if (!navigator.mediaDevices?.getUserMedia) throw new Error('unsupported');
    const stream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: { ideal: 'environment' }, width: { ideal: 1920 }, height: { ideal: 1080 } }, audio: false
    });
    video.srcObject = stream;
    video.setAttribute('playsinline', ''); video.muted = true;
    await video.play().catch(() => {});
    return stream;
  }
  function stopCamera(video) {
    const s = video.srcObject;
    if (s) s.getTracks().forEach(t => t.stop());
    video.srcObject = null;
  }

  global.Sensors = { OrientationSensor, rotationMatrix, getPosition, startCamera, stopCamera };
})(window);
