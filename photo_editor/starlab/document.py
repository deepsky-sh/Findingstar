"""An open picture: the untouched source pixels plus a smaller copy for previews."""

from __future__ import annotations

import threading

import numpy as np

from .processing.core import blur, downsample, luminance, robust_stats, sample_pixels
from .processing.params import geometry_of
from .processing.pipeline import apply_geometry

THUMB_SIDE = 200
DRAFT_SIDE = 900


class Document:
    def __init__(self, image: np.ndarray, name: str, path: str | None = None,
                 exif: bytes | None = None, icc: bytes | None = None, preview_side: int = 1800):
        self.full = np.ascontiguousarray(image, dtype=np.float32)
        self.name = name
        self.path = path
        self.exif = exif
        self.icc = icc
        self.bit_depth = 8
        self.note = ""
        self._lock = threading.Lock()
        self._frames: dict[str, tuple[tuple, np.ndarray]] = {}
        self.set_preview_side(preview_side)

    @property
    def width(self) -> int:
        return self.full.shape[1]

    @property
    def height(self) -> int:
        return self.full.shape[0]

    def set_preview_side(self, side: int) -> None:
        preview = downsample(self.full, side)
        draft = downsample(preview, DRAFT_SIDE)
        thumb = downsample(preview, THUMB_SIDE)
        gains = {"preview": 1.0, "draft": _noise_gain(preview, draft), "thumb": _noise_gain(preview, thumb)}
        with self._lock:
            self.preview_side = side
            self.preview = preview
            self.draft = draft
            self.thumb = thumb
            self._gains = gains
            self._frames.clear()

    @property
    def preview_scale(self) -> float:
        return self.preview.shape[1] / self.full.shape[1]

    def scale_of(self, which: str) -> float:
        """Working pixels per full-resolution pixel for a source."""
        src = {"full": self.full, "preview": self.preview, "draft": self.draft, "thumb": self.thumb}[which]
        return src.shape[1] / self.full.shape[1]

    def noise_gain(self, which: str) -> float:
        """How much stronger per-pixel noise is in the preview than in a smaller source.

        Shrinking an image averages noise away, which would make the auto
        stretch of drafts and thumbnails look brighter than the real preview.
        """
        return self._gains.get(which, 1.0)

    def frame(self, which: str, params: dict, use_crop: bool = True) -> np.ndarray:
        """The source after rotation/flip/crop, for 'full', 'preview', 'draft' or 'thumb'."""
        key = (geometry_of(params), use_crop)
        cache_key = f"{which}:{use_crop}"
        with self._lock:
            cached = self._frames.get(cache_key)
            if cached and cached[0] == key:
                return cached[1]
            src = {"full": self.full, "preview": self.preview, "draft": self.draft, "thumb": self.thumb}[which]
        out = apply_geometry(src, params, use_crop)
        if which != "full":
            out = np.ascontiguousarray(out)
        with self._lock:
            self._frames[cache_key] = (key, out)
        return out

    def frame_size(self, params: dict, use_crop: bool = True) -> tuple[int, int]:
        """(width, height) of the full-resolution frame after geometry."""
        f = self.frame("full", params, use_crop)
        return f.shape[1], f.shape[0]


def _pixel_noise(img: np.ndarray) -> float:
    lum = luminance(img)
    _, mad = robust_stats(sample_pixels(lum - blur(lum, 1.0)))
    return mad


def _noise_gain(reference: np.ndarray, smaller: np.ndarray) -> float:
    ref, small = _pixel_noise(reference), _pixel_noise(smaller)
    # White noise drops at most in proportion to the size ratio.
    ceiling = max(1.0, reference.shape[1] / smaller.shape[1])
    if ref < 1e-5 or small < 1e-7:
        return 1.0
    return float(min(max(ref / small, 1.0), ceiling))
