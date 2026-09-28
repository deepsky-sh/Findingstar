"""The editing pipeline: geometry, then every filter in a fixed, astro-friendly order.

Editing is non-destructive: the source pixels never change, and a ``params``
dict fully describes the result. The same function renders the fast preview,
1:1 detail views and the full-resolution export.
"""

from __future__ import annotations

from typing import Callable

import numpy as np

from . import filters as F
from .core import run_banded, to_uint8, to_uint16
from .filters import Geo
from .params import geometry_of


def crop_box(h: int, w: int, crop) -> tuple[int, int, int, int]:
    """Pixel box (top, bottom, left, right) of a normalized crop rectangle."""
    if not crop:
        return 0, h, 0, w
    x0, y0, x1, y1 = crop
    left = int(round(min(x0, x1) * w))
    right = int(round(max(x0, x1) * w))
    top = int(round(min(y0, y1) * h))
    bottom = int(round(max(y0, y1) * h))
    left, top = min(max(left, 0), w - 1), min(max(top, 0), h - 1)
    right, bottom = max(min(right, w), left + 1), max(min(bottom, h), top + 1)
    return top, bottom, left, right


def apply_geometry(img: np.ndarray, params: dict, use_crop: bool = True) -> np.ndarray:
    rotation, flip_h, crop = geometry_of(params)
    out = np.rot90(img, rotation) if rotation else img
    if flip_h:
        out = out[:, ::-1]
    if use_crop and crop:
        t, b, l, r = crop_box(out.shape[0], out.shape[1], crop)
        out = out[t:b, l:r]
    return out


LOCAL_STEPS = ("hotpixel", "chroma_denoise", "ha_boost", "local_contrast", "star_reduce", "denoise", "sharpen")


def total_reach(p: dict, geo: Geo) -> int:
    """Margin needed around a tile so it renders exactly like the whole frame."""
    return sum(F.halo(step, p, geo) for step in LOCAL_STEPS if p[step]) + 2


def process(img: np.ndarray, p: dict, geo: Geo, ctx: dict) -> np.ndarray:
    """Run every active filter. The order mirrors a typical astro workflow:
    fix sensor defects → remove sky gradients and colour casts (while the data
    is still linear) → stretch → tone → colour noise/SCNR → local structure →
    luminance noise → colour → sharpen.

    ``ctx`` caches whole-frame statistics. When it is empty they are measured
    here, so ``img`` must then be the whole frame (see render_frame). An
    optional ``ctx["noise_gain"]`` adapts those measurements for shrunken copies.
    """
    out = np.asarray(img, dtype=np.float32)

    def run(step: str, fn) -> None:
        nonlocal out
        out = run_banded(fn, out, geo, F.halo(step, p, geo))

    def stat(key: str, measure):
        if key not in ctx:
            ctx[key] = measure(out)
        return ctx[key]

    if p["hotpixel"]:
        run("hotpixel", lambda a, g: F.hot_pixels(a, p["hotpixel"], g))
    if p["vignette"]:
        run("vignette", lambda a, g: F.vignette(a, p["vignette"], g))
    if p["bg_remove"]:
        model = stat("background", lambda a: F.measure_background(a, int(p["bg_degree"])))
        run("bg_remove", lambda a, g: F.remove_background(a, p["bg_remove"], model, g))
    if p["bg_neutral"]:
        sky = stat("sky", F.measure_sky_level)
        run("bg_neutral", lambda a, g: F.neutralize_background(a, p["bg_neutral"], sky))
    if p["color_calib"]:
        info = stat("star_color", F.measure_star_color)
        run("color_calib", lambda a, g: F.calibrate_color(a, p["color_calib"], info))
    if p["temperature"] or p["tint"]:
        run("wb", lambda a, g: F.white_balance(a, p["temperature"], p["tint"]))
    if p["exposure"]:
        run("exposure", lambda a, g: F.exposure(a, p["exposure"]))
    if p["stretch_mode"] != "none":
        st = stat("stretch", lambda a: F.measure_stretch(a, ctx.get("noise_gain", 1.0)))
        run("stretch", lambda a, g: F.stretch(a, p["stretch_mode"], p["stretch"], st))
    if p["black_point"] or p["brightness"]:
        run("levels", lambda a, g: F.levels(a, p["black_point"], p["brightness"]))
    if p["contrast"]:
        run("contrast", lambda a, g: F.contrast(a, p["contrast"]))
    if p["highlights"] or p["shadows"]:
        run("tones", lambda a, g: F.highlights_shadows(a, p["highlights"], p["shadows"]))
    # Colour noise goes first: otherwise SCNR clips the noisy green channel
    # and tints a grainy sky magenta.
    if p["chroma_denoise"]:
        run("chroma_denoise", lambda a, g: F.chroma_denoise(a, p["chroma_denoise"], g))
    if p["scnr"]:
        run("scnr", lambda a, g: F.scnr(a, p["scnr"]))
    if p["ha_boost"]:
        run("ha_boost", lambda a, g: F.ha_boost(a, p["ha_boost"], g))
    if p["local_contrast"]:
        run("local_contrast", lambda a, g: F.local_contrast(a, p["local_contrast"], g))
    if p["star_reduce"]:
        star_noise = stat("star_noise", lambda a: F.measure_noise(a, geo.scale))
        run("star_reduce", lambda a, g: F.star_reduce(a, p["star_reduce"], star_noise, g))
    if p["denoise"]:
        noise = stat("noise", lambda a: F.measure_noise(a, geo.scale))
        run("denoise", lambda a, g: F.denoise(a, p["denoise"], noise, g))
    if p["saturation"] or p["vibrance"]:
        run("saturation", lambda a, g: F.saturation(a, p["saturation"], p["vibrance"]))
    if p["sharpen"]:
        run("sharpen", lambda a, g: F.sharpen(a, p["sharpen"], g))

    return np.ascontiguousarray(np.clip(out, 0.0, 1.0), dtype=np.float32)


def render_frame(frame: np.ndarray, params: dict, scale: float, ctx: dict | None = None) -> tuple[np.ndarray, dict]:
    """Process a whole frame, measuring any statistics the filters need."""
    ctx = {} if ctx is None else ctx
    h, w = frame.shape[:2]
    return process(frame, params, Geo(w, h, 0, 0, scale), ctx), ctx


def render_region(
    frame: np.ndarray, params: dict, scale: float, ctx: dict, box: tuple[int, int, int, int]
) -> np.ndarray:
    """Process only box = (x0, y0, x1, y1) of a frame, padded so edges match a full render."""
    fh, fw = frame.shape[:2]
    x0, y0, x1, y1 = box
    margin = total_reach(params, Geo(fw, fh, 0, 0, scale))
    ex0, ey0 = max(0, x0 - margin), max(0, y0 - margin)
    ex1, ey1 = min(fw, x1 + margin), min(fh, y1 + margin)
    patch = frame[ey0:ey1, ex0:ex1]
    out = process(patch, params, Geo(fw, fh, ex0, ey0, scale), ctx)
    return out[y0 - ey0 : y1 - ey0, x0 - ex0 : x1 - ex0]


def render_tiled(
    frame: np.ndarray,
    params: dict,
    ctx: dict,
    bits: int = 8,
    tile: int = 1536,
    progress: Callable[[float], None] | None = None,
    cancelled: Callable[[], bool] | None = None,
) -> np.ndarray | None:
    """Full-resolution render in tiles to keep memory bounded.

    ``ctx`` must hold statistics measured on the preview (see render_frame)
    so every tile uses the same global numbers. Returns None if cancelled.
    """
    fh, fw = frame.shape[:2]
    out = np.empty((fh, fw, 3), dtype=np.uint16 if bits == 16 else np.uint8)
    convert = to_uint16 if bits == 16 else to_uint8
    boxes = [
        (x, y, min(x + tile, fw), min(y + tile, fh))
        for y in range(0, fh, tile)
        for x in range(0, fw, tile)
    ]
    for i, (x0, y0, x1, y1) in enumerate(boxes):
        if cancelled and cancelled():
            return None
        out[y0:y1, x0:x1] = convert(render_region(frame, params, 1.0, dict(ctx), (x0, y0, x1, y1)))
        if progress:
            progress((i + 1) / len(boxes))
    return out
