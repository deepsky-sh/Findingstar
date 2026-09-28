"""Low-level numeric helpers shared by all filters.

All images are float32 numpy arrays in the range [0, 1] with shape (H, W, 3).
Single-channel planes are (H, W).
"""

from __future__ import annotations

import math
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

import numpy as np
from PIL import Image
from scipy import ndimage

LUMA = np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
EPS = 1e-6

# scipy.ndimage and large numpy operations release the GIL, so splitting an
# image into bands and filtering them on a few threads scales with CPU cores.
WORKERS = max(1, min(8, os.cpu_count() or 2))
_POOL = ThreadPoolExecutor(max_workers=WORKERS, thread_name_prefix="starlab")


def parallel_map(fn, items) -> list:
    items = list(items)
    # Work already running on the pool stays serial: waiting on the same pool
    # from inside it could deadlock.
    if len(items) <= 1 or threading.current_thread().name.startswith("starlab"):
        return [fn(i) for i in items]
    return list(_POOL.map(fn, items))


def run_banded(fn, img: np.ndarray, geo, halo: int, min_rows: int = 96) -> np.ndarray:
    """Apply fn(region, geo) to horizontal bands in parallel.

    Each band is padded by ``halo`` rows so that filters reaching that far see
    the same neighbourhood as they would on the whole image.
    """
    h = img.shape[0]
    n = min(WORKERS, max(1, h // max(min_rows, 2 * halo)))
    if n <= 1:
        return fn(img, geo)
    bounds = np.linspace(0, h, n + 1).astype(int)
    out = np.empty(img.shape, dtype=np.float32)

    def work(i: int) -> None:
        a, b = int(bounds[i]), int(bounds[i + 1])
        ea, eb = max(0, a - halo), min(h, b + halo)
        res = fn(img[ea:eb], replace(geo, y0=geo.y0 + ea))
        out[a:b] = res[a - ea : b - ea]

    parallel_map(work, range(n))
    return out


def _filter1d(func, a: np.ndarray, axis: int, *args, **kwargs) -> np.ndarray:
    """Run a scipy 1-D filter along a spatial axis, split across threads."""
    out = np.empty(a.shape, dtype=np.float32)
    other = 1 - axis
    n = a.shape[other]
    chunks = min(WORKERS, max(1, n // 64))
    bounds = np.linspace(0, n, chunks + 1).astype(int)

    def work(i: int) -> None:
        sl = [slice(None)] * a.ndim
        sl[other] = slice(int(bounds[i]), int(bounds[i + 1]))
        sl = tuple(sl)
        func(a[sl], *args, axis=axis, output=out[sl], mode="reflect", **kwargs)

    parallel_map(work, range(chunks))
    return out


def luminance(img: np.ndarray) -> np.ndarray:
    """Rec.709 luminance of an RGB image."""
    return np.ascontiguousarray(img @ LUMA, dtype=np.float32)


def channel_max(img: np.ndarray) -> np.ndarray:
    # Much faster than img.max(axis=2) for channel-last data.
    return np.maximum(np.maximum(img[..., 0], img[..., 1]), img[..., 2])


def channel_min(img: np.ndarray) -> np.ndarray:
    return np.minimum(np.minimum(img[..., 0], img[..., 1]), img[..., 2])


def smoothstep(e0: float, e1: float, x: np.ndarray) -> np.ndarray:
    t = np.clip((x - e0) / max(e1 - e0, EPS), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def _boxes_for_gauss(sigma: float, n: int = 3) -> list[int]:
    """Odd box widths whose n-fold convolution approximates a gaussian."""
    w_ideal = math.sqrt(12.0 * sigma * sigma / n + 1.0)
    wl = int(math.floor(w_ideal))
    if wl % 2 == 0:
        wl -= 1
    wu = wl + 2
    m_ideal = (12.0 * sigma * sigma - n * wl * wl - 4 * n * wl - 3 * n) / (-4.0 * wl - 4.0)
    m = int(round(m_ideal))
    return [wl if i < m else wu for i in range(n)]


def blur(a: np.ndarray, sigma: float) -> np.ndarray:
    """Gaussian blur over the two spatial axes.

    Small radii use an exact gaussian; large radii use three box passes, which
    cost the same regardless of radius. Both reach about 3σ, see blur_reach().
    """
    if sigma < 0.3:
        return a
    a = np.asarray(a, dtype=np.float32)
    if sigma < 4.0:
        out = _filter1d(ndimage.gaussian_filter1d, a, 0, sigma, truncate=3.0)
        return _filter1d(ndimage.gaussian_filter1d, out, 1, sigma, truncate=3.0)
    out = a
    for w in _boxes_for_gauss(sigma):
        out = _filter1d(ndimage.uniform_filter1d, out, 0, w)
        out = _filter1d(ndimage.uniform_filter1d, out, 1, w)
    return out


def blur_reach(sigma: float) -> int:
    if sigma < 0.3:
        return 0
    if sigma < 4.0:
        return int(math.ceil(3.0 * sigma)) + 1
    return sum(w // 2 for w in _boxes_for_gauss(sigma)) + 1


def min_filter(a: np.ndarray, radius: int) -> np.ndarray:
    if radius < 1:
        return a
    out = _filter1d(ndimage.minimum_filter1d, a, 0, 2 * radius + 1)
    return _filter1d(ndimage.minimum_filter1d, out, 1, 2 * radius + 1)


def max_filter(a: np.ndarray, radius: int) -> np.ndarray:
    if radius < 1:
        return a
    out = _filter1d(ndimage.maximum_filter1d, a, 0, 2 * radius + 1)
    return _filter1d(ndimage.maximum_filter1d, out, 1, 2 * radius + 1)


def resize(img: np.ndarray, width: int, height: int) -> np.ndarray:
    """Area-averaging resize that keeps float precision (no ringing around stars)."""
    h, w = img.shape[:2]
    if (w, h) == (width, height):
        return img
    method = Image.Resampling.BOX if width < w else Image.Resampling.BILINEAR
    planes = img[..., None] if img.ndim == 2 else img
    out = np.empty((height, width, planes.shape[2]), dtype=np.float32)
    for c in range(planes.shape[2]):
        ch = Image.fromarray(np.ascontiguousarray(planes[..., c], dtype=np.float32), mode="F")
        out[..., c] = np.asarray(ch.resize((width, height), method), dtype=np.float32)
    return out[..., 0] if img.ndim == 2 else out


def fit_size(w: int, h: int, max_side: int) -> tuple[int, int]:
    """Size that fits inside max_side on the long edge (never upscales)."""
    long_side = max(w, h)
    if long_side <= max_side:
        return w, h
    s = max_side / long_side
    return max(1, round(w * s)), max(1, round(h * s))


def downsample(img: np.ndarray, max_side: int) -> np.ndarray:
    h, w = img.shape[:2]
    return resize(img, *fit_size(w, h, max_side))


def sample_pixels(a: np.ndarray, max_count: int = 400_000) -> np.ndarray:
    """Strided subsample flattened to (N,) or (N, C) for fast statistics."""
    h, w = a.shape[:2]
    step = max(1, int(math.sqrt(h * w / max_count)))
    s = a[::step, ::step]
    return s.reshape(-1, *a.shape[2:])


def robust_stats(x: np.ndarray) -> tuple[float, float]:
    """Median and normalized MAD (≈ standard deviation for gaussian noise)."""
    med = float(np.median(x))
    mad = float(np.median(np.abs(x - med))) * 1.4826
    return med, mad


def apply_luminance(img: np.ndarray, lum: np.ndarray, new_lum: np.ndarray) -> np.ndarray:
    """Scale RGB so that luminance becomes new_lum while keeping hue and saturation."""
    ratio = np.divide(new_lum, lum, out=np.ones_like(lum), where=lum > 1e-5)
    out = img * ratio[..., None]
    return fit_gamut(out)


def fit_gamut(out: np.ndarray) -> np.ndarray:
    """Clip to [0, 1], scaling over-bright pixels as a whole so their hue survives."""
    peak = channel_max(out)
    scale = np.ones_like(peak)
    np.divide(1.0, peak, out=scale, where=peak > 1.0)
    out *= scale[..., None]
    return np.clip(out, 0.0, 1.0, out=out)


def to_uint8(img: np.ndarray) -> np.ndarray:
    return (np.clip(img, 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8)


def to_uint16(img: np.ndarray) -> np.ndarray:
    return (np.clip(img, 0.0, 1.0) * 65535.0 + 0.5).astype(np.uint16)
