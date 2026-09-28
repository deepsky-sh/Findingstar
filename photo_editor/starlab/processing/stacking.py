"""Combine several exposures of the same sky into one cleaner picture.

Frames are aligned by translation using phase correlation, which suits
tracked mounts and short tripod sequences. Field rotation is not corrected.
"""

from __future__ import annotations

from typing import Callable, Sequence

import numpy as np

from .core import blur, luminance

METHODS = {
    "mean": "평균",
    "median": "중앙값",
    "sigma": "시그마 클리핑 평균",
    "max": "최대값 (별 궤적)",
}

# Median and sigma clipping keep every frame in memory as 16-bit.
MEMORY_LIMIT_BYTES = 6 * 1024**3


class StackCancelled(Exception):
    pass


def _alignment_spectrum(img: np.ndarray, size: int = 1024) -> np.ndarray:
    lum = luminance(img)
    h, w = lum.shape
    ch, cw = min(size, h), min(size, w)
    top, left = (h - ch) // 2, (w - cw) // 2
    crop = lum[top : top + ch, left : left + cw].astype(np.float64)
    crop = blur(crop, 1.0) - blur(crop, 20.0)  # keep stars, drop gradients
    crop -= crop.mean()
    window = np.outer(np.hanning(ch), np.hanning(cw))
    return np.fft.fft2(crop * window)


def phase_shift(ref_spectrum: np.ndarray, img: np.ndarray) -> tuple[int, int]:
    """Integer (dy, dx) such that img(y, x) ≈ ref(y - dy, x - dx)."""
    spec = _alignment_spectrum(img, max(ref_spectrum.shape))
    if spec.shape != ref_spectrum.shape:
        return 0, 0
    cross = spec * np.conj(ref_spectrum)
    cross /= np.abs(cross) + 1e-12
    corr = np.fft.ifft2(cross).real
    dy, dx = np.unravel_index(int(np.argmax(corr)), corr.shape)
    h, w = corr.shape
    if dy > h // 2:
        dy -= h
    if dx > w // 2:
        dx -= w
    return int(dy), int(dx)


def _common_box(shifts: Sequence[tuple[int, int]], h: int, w: int) -> tuple[int, int, int, int]:
    y0 = max(0, max(-dy for dy, _ in shifts))
    y1 = min(h, min(h - dy for dy, _ in shifts))
    x0 = max(0, max(-dx for _, dx in shifts))
    x1 = min(w, min(w - dx for _, dx in shifts))
    if y1 - y0 < 16 or x1 - x0 < 16:
        raise ValueError("사진들이 너무 많이 어긋나 있어 정렬할 수 없습니다.")
    return y0, y1, x0, x1


def stack_images(
    loader: Callable[[str], np.ndarray],
    paths: Sequence[str],
    method: str = "mean",
    align: bool = True,
    progress: Callable[[float, str], None] | None = None,
    cancelled: Callable[[], bool] | None = None,
) -> np.ndarray:
    if len(paths) < 2:
        raise ValueError("스태킹하려면 사진이 2장 이상 필요합니다.")
    if method not in METHODS:
        raise ValueError(f"알 수 없는 방식: {method}")

    def report(frac: float, text: str) -> None:
        if cancelled and cancelled():
            raise StackCancelled()
        if progress:
            progress(frac, text)

    keep_frames = method in ("median", "sigma")
    n = len(paths)
    load_share = 0.8 if keep_frames else 1.0
    ref_spec = None
    shape = None
    shifts: list[tuple[int, int]] = []
    frames: list[np.ndarray] = []
    acc = None

    for i, path in enumerate(paths):
        report(i / n * load_share, f"{i + 1}/{n} 불러오는 중…")
        img = loader(path)
        if shape is None:
            shape = img.shape
            if keep_frames and n * img.size * 2 > MEMORY_LIMIT_BYTES:
                raise ValueError("사진이 너무 많거나 커서 메모리가 부족합니다.\n'평균' 방식을 사용해 주세요.")
            if align:
                ref_spec = _alignment_spectrum(img)
        elif img.shape != shape:
            raise ValueError(f"사진 크기가 다릅니다: {path}\n모든 사진은 같은 크기여야 합니다.")

        dy, dx = phase_shift(ref_spec, img) if (align and i > 0) else (0, 0)
        shifts.append((dy, dx))
        h, w = shape[:2]

        if keep_frames:
            frames.append((np.clip(img, 0, 1) * 65535 + 0.5).astype(np.uint16))
            continue
        # Accumulate in reference coordinates: ref(y, x) = img(y + dy, x + dx).
        ys, ye = max(0, -dy), min(h, h - dy)
        xs, xe = max(0, -dx), min(w, w - dx)
        src = img[ys + dy : ye + dy, xs + dx : xe + dx]
        if acc is None:
            acc = np.zeros(shape, dtype=np.float64 if method == "mean" else np.float32)
        if method == "mean":
            acc[ys:ye, xs:xe] += src
        else:
            np.maximum(acc[ys:ye, xs:xe], src, out=acc[ys:ye, xs:xe])
        del img

    h, w = shape[:2]
    y0, y1, x0, x1 = _common_box(shifts, h, w)

    if not keep_frames:
        result = acc[y0:y1, x0:x1]
        if method == "mean":
            result = result / n
        report(1.0, "완료")
        return np.ascontiguousarray(result, dtype=np.float32)

    out = np.empty((y1 - y0, x1 - x0, 3), dtype=np.float32)
    rows = 128
    for r in range(y0, y1, rows):
        re = min(r + rows, y1)
        report(load_share + (r - y0) / (y1 - y0) * (1 - load_share), "합성하는 중…")
        chunk = np.stack(
            [f[r + dy : re + dy, x0 + dx : x1 + dx] for f, (dy, dx) in zip(frames, shifts)], axis=0
        ).astype(np.float32) / 65535.0
        if method == "median":
            out[r - y0 : re - y0] = np.median(chunk, axis=0)
        else:
            out[r - y0 : re - y0] = _sigma_clipped_mean(chunk)
    report(1.0, "완료")
    return out


def _sigma_clipped_mean(chunk: np.ndarray, kappa: float = 2.5, iterations: int = 3) -> np.ndarray:
    mask = np.ones(chunk.shape, dtype=bool)
    for _ in range(iterations):
        count = np.maximum(mask.sum(axis=0), 1)
        mean = np.where(mask, chunk, 0).sum(axis=0) / count
        var = np.where(mask, (chunk - mean) ** 2, 0).sum(axis=0) / count
        std = np.sqrt(var)
        new_mask = np.abs(chunk - mean) <= kappa * std + 1e-6
        if np.array_equal(new_mask, mask):
            break
        mask = new_mask
    count = np.maximum(mask.sum(axis=0), 1)
    return (np.where(mask, chunk, 0).sum(axis=0) / count).astype(np.float32)
