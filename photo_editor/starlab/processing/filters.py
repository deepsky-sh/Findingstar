"""Individual image filters.

Every filter has the signature ``f(img, ..., geo) -> img`` where

* ``img`` is float32 (H, W, 3) in [0, 1] — the whole frame or one band/tile of it.
* ``geo`` says where that region sits inside the frame and at what scale we work.

Filters that depend on global image statistics take them as an argument. The
``measure_*`` functions compute those statistics once on the whole preview
frame; the pipeline then reuses them unchanged for 1:1 detail views and
full-resolution export, so what you see is what you save.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .core import (
    LUMA,
    apply_luminance,
    blur,
    blur_reach,
    channel_max,
    downsample,
    fit_gamut,
    luminance,
    max_filter,
    min_filter,
    robust_stats,
    sample_pixels,
    smoothstep,
)


@dataclass(frozen=True)
class Geo:
    """Placement of the pixels being processed.

    frame_w/frame_h: size of the whole (cropped) picture at the working scale.
    x0/y0:           offset of the current region inside that frame.
    scale:           working pixels per full-resolution pixel (preview < 1).
    """

    frame_w: int
    frame_h: int
    x0: int = 0
    y0: int = 0
    scale: float = 1.0

    @property
    def frame_long(self) -> int:
        return max(self.frame_w, self.frame_h)

    def px(self, full_res_pixels: float) -> float:
        """Convert a distance in full-resolution pixels to working pixels."""
        return full_res_pixels * self.scale

    def norm_coords(self, h: int, w: int) -> tuple[np.ndarray, np.ndarray]:
        """Frame coordinates in [-1, 1] for the columns and rows of a region."""
        xs = (self.x0 + np.arange(w, dtype=np.float32) + 0.5) / self.frame_w * 2.0 - 1.0
        ys = (self.y0 + np.arange(h, dtype=np.float32) + 0.5) / self.frame_h * 2.0 - 1.0
        return xs, ys


def _padded_neighbours(a: np.ndarray):
    """The eight 1-pixel-shifted views of an edge-padded array."""
    p = np.pad(a, ((1, 1), (1, 1), (0, 0)), mode="edge")
    h, w = a.shape[:2]
    for dy in (0, 1, 2):
        for dx in (0, 1, 2):
            if dy == 1 and dx == 1:
                continue
            yield p[dy : dy + h, dx : dx + w]


# ─────────────────────────────── 천체 필터 ───────────────────────────────


def hot_pixels(img: np.ndarray, strength: float, geo: Geo) -> np.ndarray:
    """Replace pixels that are far brighter than all eight neighbours."""
    s = strength / 100.0
    # Downscaled previews average a hot pixel with its neighbours, so the
    # threshold shrinks with the pixel area to find the same pixels.
    thr = (0.30 * (1.0 - s) + 0.015) * max(min(geo.scale, 1.0) ** 2, 0.02)
    nmax = nmin = total = None
    for v in _padded_neighbours(img):
        if nmax is None:
            nmax, nmin, total = v.copy(), v.copy(), v.copy()
        else:
            np.maximum(nmax, v, out=nmax)
            np.minimum(nmin, v, out=nmin)
            total += v
    excess = img - nmax
    # A star's neighbours fall off unevenly (edge vs. diagonal); a hot pixel
    # sits on flat background, so demand the spike dwarf the neighbour spread.
    hot = (excess > thr) & (excess > 3.0 * (nmax - nmin))
    return np.where(hot, total * 0.125, img).astype(np.float32)


def vignette(img: np.ndarray, amount: float, geo: Geo) -> np.ndarray:
    k = amount / 100.0 * 0.8
    h, w = img.shape[:2]
    xs, ys = geo.norm_coords(h, w)
    fw, fh = float(geo.frame_w), float(geo.frame_h)
    r2 = ((xs[None, :] * fw) ** 2 + (ys[:, None] * fh) ** 2) / (fw * fw + fh * fh)
    gain = (1.0 + k * r2 * (0.6 + 0.4 * r2)).astype(np.float32)
    return np.clip(img * gain[..., None], 0.0, 1.0)


def _poly_terms(degree: int) -> list[tuple[int, int]]:
    return [(d - j, j) for d in range(degree + 1) for j in range(d + 1)]


def _poly_eval(coef: np.ndarray, degree: int, xs: np.ndarray, ys: np.ndarray) -> np.ndarray:
    out = np.zeros((ys.size, xs.size, coef.shape[1]), dtype=np.float32)
    for (i, j), c in zip(_poly_terms(degree), coef):
        term = np.outer(ys.astype(np.float32) ** j, xs.astype(np.float32) ** i)
        out += term[..., None] * c.astype(np.float32)
    return out


def measure_background(img: np.ndarray, degree: int) -> dict:
    """Fit a smooth 2-D polynomial to the sky background, ignoring stars and nebulae.

    The image is cut into tiles; each tile's median ignores stars, and tiles
    that sit well above the fitted surface (nebulae, galaxies, the Milky Way
    core) are rejected iteratively.
    """
    small = downsample(img, 384)
    h, w = small.shape[:2]
    ts = max(4, max(h, w) // 16)
    ny, nx = max(1, h // ts), max(1, w // ts)
    tiles = small[: ny * ts, : nx * ts].reshape(ny, ts, nx, ts, 3)
    med = np.median(tiles, axis=(1, 3)).reshape(-1, 3).astype(np.float64)
    cy = (np.arange(ny) * ts + ts / 2.0) / h * 2.0 - 1.0
    cx = (np.arange(nx) * ts + ts / 2.0) / w * 2.0 - 1.0
    gx, gy = np.meshgrid(cx, cy)
    gx, gy = gx.ravel(), gy.ravel()

    terms = _poly_terms(degree)
    while len(terms) * 2 > med.shape[0] and degree > 1:
        degree -= 1
        terms = _poly_terms(degree)
    design = np.stack([gx**i * gy**j for i, j in terms], axis=1)

    keep = np.ones(med.shape[0], dtype=bool)
    coef = np.zeros((len(terms), 3))
    for _ in range(6):
        coef, *_ = np.linalg.lstsq(design[keep], med[keep], rcond=None)
        resid = (med - design @ coef) @ LUMA.astype(np.float64)
        sigma = 1.4826 * np.median(np.abs(resid[keep])) + 1e-9
        new_keep = (resid < 2.0 * sigma) & (resid > -4.0 * sigma)
        if new_keep.sum() < len(terms) * 2 or np.array_equal(new_keep, keep):
            break
        keep = new_keep

    grid = _poly_eval(coef, degree, np.linspace(-1, 1, 48), np.linspace(-1, 1, 48))
    # Flatten every channel to one neutral grey at the brightness of the darkest
    # part of the sky: this removes both the glow and the orange/green cast of
    # light pollution without turning an already-bright photo black.
    target = float(np.percentile(grid.reshape(-1, 3) @ LUMA, 10))
    return {"coef": coef, "degree": degree, "target": max(target, 0.0)}


def remove_background(img: np.ndarray, strength: float, model: dict, geo: Geo) -> np.ndarray:
    h, w = img.shape[:2]
    xs, ys = geo.norm_coords(h, w)
    surface = _poly_eval(model["coef"], model["degree"], xs, ys)
    surface -= np.float32(model["target"])
    surface *= np.float32(strength / 100.0)
    return np.clip(img - surface, 0.0, 1.0)


def measure_sky_level(img: np.ndarray) -> np.ndarray:
    """Per-channel sky level: median of the darker half of the picture."""
    px = sample_pixels(img)
    lum = px @ LUMA
    dark = px[lum <= np.median(lum)]
    if dark.shape[0] < 10:
        dark = px
    return np.median(dark, axis=0).astype(np.float32)


def neutralize_background(img: np.ndarray, strength: float, sky: np.ndarray) -> np.ndarray:
    offsets = (sky - sky.min()) * np.float32(strength / 100.0)
    return np.clip(img - offsets, 0.0, 1.0)


def measure_star_color(img: np.ndarray) -> dict:
    """Channel gains that make the average star white (stars are a good white reference)."""
    sky = measure_sky_level(img)
    lum = luminance(img)
    detail = lum - blur(lum, 2.5)
    thr = np.percentile(sample_pixels(detail), 99.5)
    sel = (detail > max(thr, 1e-4)) & (channel_max(img) < 0.97)
    if int(sel.sum()) < 30:
        return {"sky": sky, "gains": np.ones(3, dtype=np.float32)}
    signal = np.maximum((img[sel] - sky).mean(axis=0), 1e-5)
    gains = signal.mean() / signal
    gains = np.clip(gains / gains[1], 0.5, 2.0).astype(np.float32)
    return {"sky": sky, "gains": gains}


def calibrate_color(img: np.ndarray, strength: float, info: dict) -> np.ndarray:
    gains = (1.0 + (strength / 100.0) * (info["gains"] - 1.0)).astype(np.float32)
    sky = info["sky"]
    return np.clip(sky + (img - sky) * gains, 0.0, 1.0)


def mtf(m: float, x):
    """PixInsight's midtones transfer function: maps 0→0, m→0.5, 1→1."""
    return ((m - 1.0) * x) / ((2.0 * m - 1.0) * x - m)


def measure_stretch(img: np.ndarray, noise_gain: float = 1.0) -> dict:
    """Sky median and spread. ``noise_gain`` rescales the spread of a shrunken
    copy (draft, thumbnail) to what the full preview would measure."""
    med, mad = robust_stats(sample_pixels(luminance(img)))
    return {"median": med, "mad": mad * noise_gain}


def _asinh_factor(xm: float, target: float) -> float:
    """k such that asinh(k·xm)/asinh(k) = target (k→0 is the identity curve)."""
    if xm <= 1e-6:
        return 1000.0
    if target <= xm:
        return 1e-3
    lo, hi = -3.0, 7.0
    for _ in range(50):
        mid = (lo + hi) / 2
        k = 10.0**mid
        if np.arcsinh(k * xm) / np.arcsinh(k) < target:
            lo = mid
        else:
            hi = mid
    return 10.0 ** ((lo + hi) / 2)


def stretch(img: np.ndarray, mode: str, strength: float, stats: dict) -> np.ndarray:
    """Non-linear stretch that pulls faint signal out of linear astro data.

    Both modes set the black point 2.8σ below the sky and then bend the curve
    so the sky lands on a target grey chosen by ``strength``, whatever the
    input brightness or noise.
    """
    s = strength / 100.0
    med, mad = stats["median"], stats["mad"]
    c0 = float(np.clip(med - 2.8 * mad, 0.0, 0.99))
    x = np.clip((img - np.float32(c0)) * np.float32(1.0 / (1.0 - c0)), 0.0, 1.0)
    xm = (med - c0) / (1.0 - c0)
    target = 0.04 + 0.26 * s
    if mode == "asinh":
        # Colour-preserving arcsinh on luminance, steep enough to put the sky
        # at the same target brightness the STF would.
        k = _asinh_factor(xm, target)
        lum = luminance(x)
        new_lum = np.arcsinh(np.float32(k) * lum) / np.float32(np.arcsinh(k))
        return apply_luminance(x, lum, new_lum.astype(np.float32))
    if mode == "auto":
        # PixInsight-style screen transfer function.
        m = float(mtf(target, xm)) if xm > 1e-6 else 0.5
        m = float(np.clip(m, 1e-4, 0.9999))
        return np.clip(mtf(np.float32(m), x), 0.0, 1.0).astype(np.float32)
    return img


def scnr(img: np.ndarray, strength: float) -> np.ndarray:
    """Average-neutral SCNR: green may not exceed the mean of red and blue."""
    s = np.float32(strength / 100.0)
    out = img.copy()
    g = img[..., 1]
    neutral = (img[..., 0] + img[..., 2]) * np.float32(0.5)
    out[..., 1] = g + (np.minimum(g, neutral) - g) * s
    return out


def ha_boost(img: np.ndarray, strength: float, geo: Geo) -> np.ndarray:
    s = np.float32(strength / 100.0)
    r, g, b = img[..., 0], img[..., 1], img[..., 2]
    redness = np.clip((r - np.maximum(g, b)) * 4.0, 0.0, 1.0)
    amt = blur(redness, ha_sigma(geo)) * s
    out = np.empty_like(img)
    out[..., 0] = r * (1.0 + amt)
    out[..., 1] = g * (1.0 - 0.15 * amt)
    out[..., 2] = b * (1.0 - 0.05 * amt)
    return fit_gamut(out)


def ha_sigma(geo: Geo) -> float:
    return max(1.0, geo.px(3.0))


def local_contrast_sigmas(geo: Geo) -> tuple[float, float, float]:
    """Large, medium and fine scales, relative to the picture so every resolution agrees."""
    return geo.frame_long * 0.012, geo.frame_long * 0.003, max(0.8, geo.frame_long * 0.0008)


def local_contrast(img: np.ndarray, strength: float, geo: Geo) -> np.ndarray:
    """Two-scale local contrast: large dust lanes and mid-size nebula structure.

    Band-pass rather than high-pass, so pixel-level noise is not amplified.
    """
    s = strength / 100.0
    big, mid, fine = local_contrast_sigmas(geo)
    lum = luminance(img)
    base = blur(lum, fine)
    large = np.clip(base - blur(lum, big), -0.25, 0.25)
    medium = np.clip(base - blur(lum, mid), -0.2, 0.2)
    new_lum = np.clip(lum + np.float32(1.6 * s) * large + np.float32(0.9 * s) * medium, 0.0, 1.0)
    return apply_luminance(img, lum, new_lum)


def star_radii(strength: float, geo: Geo) -> tuple[int, int]:
    s = strength / 100.0
    return max(1, round(geo.px(4.0))), max(1, round(geo.px(1.0 + 2.0 * s)))


def star_reduce(img: np.ndarray, strength: float, noise_full_res: float, geo: Geo) -> np.ndarray:
    """Find stars with a morphological top-hat, then shrink and dim them.

    Only peaks well above the noise count as stars, so a grainy sky is left alone.
    """
    s = strength / 100.0
    r, erode_r = star_radii(strength, geo)
    noise = noise_full_res * min(geo.scale, 1.0)
    lum = luminance(img)
    opened_lum = max_filter(min_filter(lum, r), r)  # the sky with stars removed
    lo = max(0.015, 5.0 * noise)
    mask = smoothstep(lo, lo + max(0.06, 5.0 * noise), lum - opened_lum)
    mask = blur(max_filter(mask, 1), 0.8)
    eroded = min_filter(img, erode_r)
    # Pull star pixels toward their eroded (smaller) version and dim them a bit.
    background = img * (opened_lum / np.maximum(lum, 1e-5)).clip(0, 1)[..., None]
    smaller = np.maximum(background + (eroded - background) * np.float32(1.0 - 0.45 * s), 0.0)
    w = (mask * np.float32(min(1.0, s * 1.5)))[..., None]
    return (img + (np.minimum(smaller, img) - img) * w).astype(np.float32)


# ─────────────────────────────── 톤 · 색 ───────────────────────────────


def white_balance(img: np.ndarray, temperature: float, tint: float) -> np.ndarray:
    t, m = temperature / 100.0, tint / 100.0
    gains = np.array([1.0 + 0.30 * t, 1.0 - 0.25 * m, 1.0 - 0.30 * t], dtype=np.float32)
    gains /= np.float32(gains @ LUMA)
    return np.clip(img * gains, 0.0, 1.0)


def exposure(img: np.ndarray, ev: float) -> np.ndarray:
    return np.clip(img * np.float32(2.0**ev), 0.0, 1.0)


def levels(img: np.ndarray, black_point: float, brightness: float) -> np.ndarray:
    out = img
    if black_point:
        bp = black_point / 100.0 * 0.3
        out = np.clip((out - np.float32(bp)) * np.float32(1.0 / (1.0 - bp)), 0.0, 1.0)
    if brightness:
        gamma = np.float32(2.0 ** (-brightness / 100.0 * 1.2))
        out = np.power(out, gamma)
    return out.astype(np.float32, copy=False)


def contrast(img: np.ndarray, amount: float) -> np.ndarray:
    """Symmetric S-curve through (0.5, 0.5); never clips."""
    p = np.float32(2.0 ** (amount / 100.0 * 1.3))
    xp = np.power(img, p)
    return (xp / (xp + np.power(1.0 - img, p) + np.float32(1e-6))).astype(np.float32)


def highlights_shadows(img: np.ndarray, highlights: float, shadows: float) -> np.ndarray:
    lum = luminance(img)
    sh, hi = np.float32(shadows / 100.0 * 1.5), np.float32(highlights / 100.0 * 1.5)
    inv = 1.0 - lum
    new_lum = lum + sh * lum * inv * inv + hi * lum * lum * inv
    return apply_luminance(img, lum, np.clip(new_lum, 0.0, 1.0))


def saturation(img: np.ndarray, sat: float, vib: float) -> np.ndarray:
    lum = luminance(img)
    factor = np.float32(1.0 + sat / 100.0)
    if vib:
        colourfulness = channel_max(img) - np.minimum(np.minimum(img[..., 0], img[..., 1]), img[..., 2])
        factor = factor * (1.0 + np.float32(vib / 100.0) * (1.0 - np.clip(colourfulness * 2.0, 0.0, 1.0)))
        factor = factor[..., None]
    lum3 = lum[..., None]
    out = lum3 + (img - lum3) * factor
    # Keep luminance while pulling out-of-range colours back toward grey.
    peak = channel_max(out)
    over = peak > 1.0
    if over.any():
        k = np.ones_like(peak)
        np.divide(1.0 - lum, peak - lum, out=k, where=over & (peak - lum > 1e-6))
        out = lum3 + (out - lum3) * k[..., None]
    return np.clip(out, 0.0, 1.0)


# ─────────────────────────────── 디테일 · 노이즈 ───────────────────────────────


def measure_noise(img: np.ndarray, scale: float) -> float:
    """Luminance noise σ expressed at full resolution.

    Downscaling averages ~1/scale² pixels, which lowers white noise by 1/scale,
    so a σ measured on the preview is converted back to full-resolution units.
    """
    lum = luminance(img)
    hp = lum - blur(lum, 1.0)
    _, mad = robust_stats(sample_pixels(hp))
    return mad / max(min(scale, 1.0), 1e-3) * 1.2


def denoise_sigma(strength: float, geo: Geo) -> float:
    return max(0.6, geo.px(0.8 + 2.4 * strength / 100.0))


def denoise(img: np.ndarray, strength: float, noise_full_res: float, geo: Geo) -> np.ndarray:
    """Edge-aware luminance smoothing, strongest on the dark sky background."""
    s = strength / 100.0
    noise = max(noise_full_res * min(geo.scale, 1.0), 0.002)
    sigma = denoise_sigma(strength, geo)
    lum = luminance(img)
    smooth = blur(lum, sigma)
    edges = smoothstep(2.0 * noise, 6.0 * noise, blur(np.abs(lum - smooth), sigma))
    dark = 1.0 - smoothstep(0.3, 0.85, smooth)
    w = np.float32(s) * (1.0 - edges) * (0.4 + 0.6 * dark)
    return apply_luminance(img, lum, lum + (smooth - lum) * w)


def chroma_sigma(strength: float, geo: Geo) -> float:
    return max(0.8, geo.px(1.0 + 5.0 * strength / 100.0))


def chroma_denoise(img: np.ndarray, strength: float, geo: Geo) -> np.ndarray:
    s = np.float32(strength / 100.0)
    lum = luminance(img)[..., None]
    chroma = img - lum
    smooth = blur(chroma, chroma_sigma(strength, geo))
    return np.clip(lum + chroma + (smooth - chroma) * s, 0.0, 1.0)


def sharpen_sigma(geo: Geo) -> float:
    return max(0.6, geo.px(1.2))


def sharpen(img: np.ndarray, strength: float, geo: Geo) -> np.ndarray:
    s = strength / 100.0
    lum = luminance(img)
    detail = lum - blur(lum, sharpen_sigma(geo))
    thr = np.float32(0.004)
    mag = np.abs(detail)
    detail = np.where(mag < thr, detail * mag / thr, detail)
    return apply_luminance(img, lum, np.clip(lum + detail * np.float32(2.2 * s), 0.0, 1.0))


# How far (in working pixels) each local filter looks around a pixel. Bands and
# tiles are padded by this much so they match a whole-image render exactly.
def halo(step: str, p: dict, geo: Geo) -> int:
    if step == "hotpixel":
        return 2
    if step == "ha_boost":
        return blur_reach(ha_sigma(geo)) + 1
    if step == "local_contrast":
        return max(blur_reach(s) for s in local_contrast_sigmas(geo)) + 1
    if step == "star_reduce":
        r, er = star_radii(p["star_reduce"], geo)
        return 2 * r + 1 + blur_reach(0.8) + er + 1
    if step == "chroma_denoise":
        return blur_reach(chroma_sigma(p["chroma_denoise"], geo)) + 1
    if step == "denoise":
        return 2 * blur_reach(denoise_sigma(p["denoise"], geo)) + 1
    if step == "sharpen":
        return blur_reach(sharpen_sigma(geo)) + 1
    return 0
