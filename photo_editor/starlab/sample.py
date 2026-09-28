"""A synthetic deep-sky exposure for trying the editor without your own photo.

It deliberately contains everything the astro filters fix: linear (dark) data,
an orange light-pollution gradient, a green cast, vignetting, sensor noise,
colour noise and hot pixels — plus stars and a red/blue nebula to reveal.
"""

from __future__ import annotations

import numpy as np

from .processing.core import blur, resize
from .processing.filters import mtf


def _fbm(rng: np.random.Generator, h: int, w: int, scales=(80, 40, 20, 10, 5)) -> np.ndarray:
    """Fractal cloud texture in [0, 1], built at quarter size (it is smooth anyway)."""
    sh, sw = max(8, h // 4), max(8, w // 4)
    out = np.zeros((sh, sw), dtype=np.float32)
    amp = 1.0
    for s in scales:
        n = blur(rng.standard_normal((sh, sw), dtype=np.float32), s / 4.0)
        n /= n.std() + 1e-9
        out += amp * n
        amp *= 0.55
    out -= out.min()
    out /= out.max() + 1e-9
    return resize(out, w, h)


def make_sample_sky(width: int = 2400, height: int = 1600, seed: int = 7, linear: bool = False) -> np.ndarray:
    rng = np.random.default_rng(seed)
    h, w = height, width
    nx = (np.arange(w, dtype=np.float32) / w * 2 - 1)[None, :]
    ny = (np.arange(h, dtype=np.float32) / h * 2 - 1)[:, None]

    img = np.zeros((h, w, 3), dtype=np.float32)

    # Emission nebula (Hα red with a bluish OIII/reflection core) shaped by fractal noise.
    env = np.exp(-(((nx + 0.1) / 0.55) ** 2 + ((ny + 0.05) / 0.45) ** 2))
    cloud = _fbm(rng, h, w) ** 2.2 * env
    core = np.exp(-(((nx + 0.05) / 0.18) ** 2 + ((ny + 0.1) / 0.15) ** 2)) * _fbm(rng, h, w, (30, 15, 8))
    dust = 1 - 0.7 * np.clip(_fbm(rng, h, w, (40, 20, 10)) - 0.45, 0, 1) * 2 * env
    img += (cloud * 0.045)[..., None] * np.array([1.0, 0.25, 0.32], np.float32)
    img += (core * 0.02)[..., None] * np.array([0.35, 0.55, 1.0], np.float32)
    img *= dust[..., None]

    # Stars: power-law brightness, blackbody-ish colours, gaussian PSF.
    n_stars = int(w * h / 1600)
    sx = rng.uniform(0, w, n_stars)
    sy = rng.uniform(0, h, n_stars)
    flux = (rng.pareto(1.6, n_stars) + 0.2) * 0.02
    temp = rng.uniform(-1, 1, n_stars)
    hot, cool = np.clip(-temp, 0, 1), np.clip(temp, 0, 1)  # blue-white vs. orange stars
    colors = np.stack([1 - 0.35 * hot + 0.3 * cool,
                       np.ones(n_stars),
                       1 + 0.45 * hot - 0.4 * cool], axis=1)
    # Faint stars: splat onto a point image and blur once. Bright stars get a
    # wider individual profile on top (they bloat in real exposures too).
    points = np.zeros((h, w, 3), dtype=np.float32)
    ix = np.clip(sx.astype(int), 0, w - 1)
    iy = np.clip(sy.astype(int), 0, h - 1)
    np.add.at(points, (iy, ix), (flux[:, None] * colors).astype(np.float32))
    img += blur(points, 1.2) * np.float32(2 * np.pi * 1.2**2)
    for x, y, f, c in zip(sx, sy, flux, colors):
        if f < 0.15:
            continue
        sigma = 1.6 + 0.9 * min(f / 0.4, 1.5)
        r = int(sigma * 4) + 1
        x0, x1 = max(0, int(x) - r), min(w, int(x) + r + 1)
        y0, y1 = max(0, int(y) - r), min(h, int(y) + r + 1)
        if x0 >= x1 or y0 >= y1:
            continue
        gx = np.arange(x0, x1) - x
        gy = np.arange(y0, y1) - y
        psf = np.exp(-(gy[:, None] ** 2 + gx[None, :] ** 2) / (2 * sigma * sigma)) * 0.5
        img[y0:y1, x0:x1] += (psf * f)[..., None] * c.astype(np.float32)

    # Sky: dark background, orange light pollution rising towards the bottom-left, green cast.
    sky = 0.018 + 0.05 * np.clip((ny + 1) / 2, 0, 1) ** 1.3 * (1 - 0.3 * nx)
    img += sky[..., None] * np.array([1.0, 0.72, 0.38], np.float32)
    img[..., 1] += 0.006

    # Vignetting, noise, hot pixels.
    img *= (1 - 0.28 * (nx**2 + ny**2) / 2)[..., None]
    img += rng.standard_normal((h, w, 1), dtype=np.float32) * np.float32(0.0035)
    img += rng.standard_normal((h, w, 3), dtype=np.float32) * np.float32(0.0025)
    n_hot = int(w * h / 12000)
    hy, hx, hc = rng.integers(0, h, n_hot), rng.integers(0, w, n_hot), rng.integers(0, 3, n_hot)
    img[hy, hx, hc] = rng.uniform(0.4, 1.0, n_hot)

    img = np.clip(img, 0, 1).astype(np.float32)
    if linear:
        return img
    # Cameras apply a tone curve; mimic an out-of-camera JPEG of the night sky.
    return np.clip(mtf(np.float32(0.15), img), 0, 1).astype(np.float32)
