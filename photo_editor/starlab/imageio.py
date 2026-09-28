"""Loading and saving images as float32 RGB arrays in [0, 1].

Pillow covers the common formats. FITS (astropy), camera RAW (rawpy) and
16-bit colour TIFF input (tifffile) are used automatically when installed.
"""

from __future__ import annotations

import os
import struct
from dataclasses import dataclass

import numpy as np
from PIL import Image, ImageOps

from .processing.core import to_uint8, to_uint16

try:  # optional
    from astropy.io import fits as _fits
except Exception:  # pragma: no cover - optional dependency
    _fits = None
try:  # optional
    import rawpy as _rawpy
except Exception:  # pragma: no cover - optional dependency
    _rawpy = None
try:  # optional
    import tifffile as _tifffile
except Exception:  # pragma: no cover - optional dependency
    _tifffile = None

Image.MAX_IMAGE_PIXELS = 400_000_000  # big panoramas and mosaics are normal in astro

COMMON_EXT = [".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp", ".webp"]
FITS_EXT = [".fits", ".fit", ".fts"]
RAW_EXT = [".cr2", ".cr3", ".nef", ".arw", ".dng", ".orf", ".rw2", ".raf", ".pef", ".srw"]


@dataclass
class LoadedImage:
    data: np.ndarray  # float32 (H, W, 3) in [0, 1]
    exif: bytes | None = None
    icc: bytes | None = None
    bit_depth: int = 8
    note: str = ""  # a warning worth showing the user, e.g. reduced precision


def readable_extensions() -> list[str]:
    exts = list(COMMON_EXT)
    if _fits is not None:
        exts += FITS_EXT
    if _rawpy is not None:
        exts += RAW_EXT
    return exts


def open_dialog_filter() -> str:
    patterns = " ".join(f"*{e}" for e in readable_extensions())
    parts = [f"모든 지원 이미지 ({patterns})", "JPEG (*.jpg *.jpeg)", "PNG (*.png)", "TIFF (*.tif *.tiff)"]
    if _fits is not None:
        parts.append("FITS 천체 데이터 (*.fits *.fit *.fts)")
    if _rawpy is not None:
        parts.append("카메라 RAW (" + " ".join(f"*{e}" for e in RAW_EXT) + ")")
    parts.append("모든 파일 (*)")
    return ";;".join(parts)


def format_summary() -> str:
    parts = ["JPG", "PNG", "TIFF", "BMP", "WEBP"]
    if _fits is not None:
        parts.append("FITS")
    if _rawpy is not None:
        parts.append("RAW (CR2 · NEF · ARW 등)")
    return " · ".join(parts)


def is_readable(path: str) -> bool:
    return os.path.splitext(path)[1].lower() in readable_extensions()


def _to_rgb(arr: np.ndarray) -> np.ndarray:
    if arr.ndim == 2:
        arr = np.repeat(arr[..., None], 3, axis=2)
    elif arr.shape[2] == 1:
        arr = np.repeat(arr, 3, axis=2)
    elif arr.shape[2] > 3:
        arr = arr[..., :3]
    return np.ascontiguousarray(arr, dtype=np.float32)


def _normalize_int(arr: np.ndarray) -> tuple[np.ndarray, int]:
    if arr.dtype == np.uint8:
        return arr.astype(np.float32) / 255.0, 8
    if arr.dtype == np.uint16:
        return arr.astype(np.float32) / 65535.0, 16
    arr = arr.astype(np.float32)
    top = float(np.nanmax(arr)) if arr.size else 1.0
    bottom = float(np.nanmin(arr)) if arr.size else 0.0
    if bottom >= 0.0 and top <= 1.0:
        return np.nan_to_num(arr), 32
    if bottom >= 0.0 and top <= 65535.0:
        return np.nan_to_num(arr / 65535.0), 16
    return np.nan_to_num((arr - bottom) / max(top - bottom, 1e-12)), 32


def _load_fits(path: str) -> LoadedImage:
    with _fits.open(path, memmap=False) as hdul:
        hdu = next((h for h in hdul if h.data is not None and h.data.ndim >= 2), None)
        if hdu is None:
            raise ValueError("FITS 파일에 이미지 데이터가 없습니다.")
        data = np.asarray(hdu.data, dtype=np.float32)
    if data.ndim == 3:
        if data.shape[0] in (1, 3, 4):
            data = np.moveaxis(data[:3], 0, -1)
        elif data.shape[2] not in (1, 3, 4):
            data = data[0]
    data = np.nan_to_num(data)
    lo, hi = float(data.min()), float(data.max())
    data = (data - lo) / max(hi - lo, 1e-12)
    data = data[::-1]  # FITS rows start at the bottom
    return LoadedImage(_to_rgb(data), bit_depth=32)


def _load_raw(path: str) -> LoadedImage:
    with _rawpy.imread(path) as raw:
        rgb = raw.postprocess(use_camera_wb=True, output_bps=16)
    return LoadedImage(_to_rgb(rgb.astype(np.float32) / 65535.0), bit_depth=16)


def _load_pillow(path: str) -> LoadedImage:
    with Image.open(path) as im:
        im.load()
        im = ImageOps.exif_transpose(im)  # phone photos store rotation in EXIF
        exif = None
        try:
            ex = im.getexif()
            exif = ex.tobytes() if len(ex) else None
        except Exception:
            exif = None
        icc = im.info.get("icc_profile")
        mode = im.mode
        note = ""
        bits = getattr(im, "tag_v2", {}).get(258) if hasattr(im, "tag_v2") else None
        if mode == "RGB" and bits and max(bits if isinstance(bits, tuple) else (bits,)) > 8:
            note = ("16비트 TIFF를 8비트로 읽었습니다. 정밀하게 읽으려면: "
                    "pip install tifffile imagecodecs")
        if mode in ("I;16", "I;16B", "I;16L", "I;16N"):
            arr = np.asarray(im, dtype=np.float32) / 65535.0
            depth = 16
        elif mode in ("I", "F"):
            arr, depth = _normalize_int(np.asarray(im))
        else:
            if mode not in ("RGB", "L"):
                if "A" in mode or mode == "P":
                    im = im.convert("RGBA")
                    bg = Image.new("RGBA", im.size, (0, 0, 0, 255))
                    im = Image.alpha_composite(bg, im)
                im = im.convert("RGB")
            arr = np.asarray(im, dtype=np.float32) / 255.0
            depth = 8
    return LoadedImage(_to_rgb(arr), exif=exif, icc=icc, bit_depth=depth, note=note)


def load_image(path: str) -> LoadedImage:
    ext = os.path.splitext(path)[1].lower()
    if ext in FITS_EXT:
        if _fits is None:
            raise ValueError("FITS 파일을 열려면 astropy가 필요합니다.\npip install astropy")
        return _load_fits(path)
    if ext in RAW_EXT:
        if _rawpy is None:
            raise ValueError("RAW 파일을 열려면 rawpy가 필요합니다.\npip install rawpy")
        return _load_raw(path)
    if ext in (".tif", ".tiff") and _tifffile is not None:
        # tifffile keeps 16/32-bit colour TIFFs (DSS, Siril, …) at full precision.
        try:
            arr = _tifffile.imread(path)
            if arr.ndim == 3 and arr.shape[0] in (3, 4) and arr.shape[2] not in (3, 4):
                arr = np.moveaxis(arr, 0, -1)
            if arr.ndim in (2, 3):
                norm, depth = _normalize_int(arr)
                return LoadedImage(_to_rgb(norm), bit_depth=depth)
        except Exception:
            pass  # e.g. LZW without imagecodecs: fall back to Pillow
    return _load_pillow(path)


# ───────────────────────────── saving ─────────────────────────────


def _write_tiff16(path: str, rgb16: np.ndarray) -> None:
    """Minimal baseline TIFF writer for 16-bit RGB (uncompressed, one strip)."""
    h, w = rgb16.shape[:2]
    pixels = np.ascontiguousarray(rgb16, dtype="<u2").tobytes()
    entries_n = 13
    ifd_offset = 8
    extra_offset = ifd_offset + 2 + entries_n * 12 + 4
    bps_offset = extra_offset
    xres_offset = bps_offset + 6
    yres_offset = xres_offset + 8
    data_offset = yres_offset + 8
    data_offset += data_offset % 2

    SHORT, LONG, RATIONAL = 3, 4, 5

    def entry(tag, typ, count, value):
        if typ == SHORT and count == 1:
            return struct.pack("<HHIHH", tag, typ, count, value, 0)
        return struct.pack("<HHII", tag, typ, count, value)

    entries = [
        entry(256, LONG, 1, w),
        entry(257, LONG, 1, h),
        entry(258, SHORT, 3, bps_offset),
        entry(259, SHORT, 1, 1),  # no compression
        entry(262, SHORT, 1, 2),  # RGB
        entry(273, LONG, 1, data_offset),
        entry(277, SHORT, 1, 3),
        entry(278, LONG, 1, h),
        entry(279, LONG, 1, len(pixels)),
        entry(282, RATIONAL, 1, xres_offset),
        entry(283, RATIONAL, 1, yres_offset),
        entry(284, SHORT, 1, 1),  # chunky
        entry(296, SHORT, 1, 2),  # inches
    ]
    assert len(entries) == entries_n
    with open(path, "wb") as f:
        f.write(b"II" + struct.pack("<HI", 42, ifd_offset))
        f.write(struct.pack("<H", entries_n) + b"".join(entries) + struct.pack("<I", 0))
        f.write(struct.pack("<HHH", 16, 16, 16))
        f.write(struct.pack("<II", 300, 1) + struct.pack("<II", 300, 1))
        f.write(b"\0" * (data_offset - f.tell()))
        f.write(pixels)


def format_for_path(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    if ext in (".tif", ".tiff"):
        return "tiff16"
    if ext == ".png":
        return "png"
    return "jpeg"


def bits_for_format(fmt: str) -> int:
    return 16 if fmt == "tiff16" else 8


def save_image(path: str, pixels: np.ndarray, exif: bytes | None = None, icc: bytes | None = None,
               quality: int = 95) -> None:
    """Save uint8/uint16 (or float) RGB pixels; the format follows the extension."""
    fmt = format_for_path(path)
    if fmt == "tiff16":
        rgb16 = pixels if pixels.dtype == np.uint16 else to_uint16(pixels)
        _write_tiff16(path, rgb16)
        return
    if pixels.dtype == np.uint16:
        rgb8 = (pixels >> 8).astype(np.uint8)
    elif pixels.dtype == np.uint8:
        rgb8 = pixels
    else:
        rgb8 = to_uint8(pixels)
    im = Image.fromarray(np.ascontiguousarray(rgb8), mode="RGB")
    kwargs = {}
    if icc:
        kwargs["icc_profile"] = icc
    if fmt == "png":
        im.save(path, "PNG", optimize=False, **kwargs)
    else:
        if exif:
            kwargs["exif"] = exif
        # 4:4:4 chroma keeps small coloured stars from turning grey.
        im.save(path, "JPEG", quality=quality, subsampling=0, **kwargs)
