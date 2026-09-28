import os
import struct
import sys

import numpy as np
import pytest
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from starlab.imageio import load_image, save_image  # noqa: E402
from starlab.processing.stacking import _alignment_spectrum, phase_shift, stack_images  # noqa: E402
from starlab.sample import make_sample_sky  # noqa: E402


def test_jpeg_png_roundtrip(tmp_path):
    img = make_sample_sky(160, 120, seed=2)
    for ext in (".jpg", ".png"):
        path = str(tmp_path / f"out{ext}")
        save_image(path, img)
        back = load_image(path).data
        assert back.shape == img.shape
        assert np.abs(back - img).mean() < (0.02 if ext == ".jpg" else 0.003)


def test_tiff16_writer_is_valid(tmp_path):
    img = np.linspace(0, 1, 40 * 30 * 3, dtype=np.float32).reshape(30, 40, 3)
    path = str(tmp_path / "out.tif")
    save_image(path, img)
    with open(path, "rb") as f:
        raw = f.read()
    assert raw[:4] == b"II*\x00"
    (ifd,) = struct.unpack("<I", raw[4:8])
    (count,) = struct.unpack("<H", raw[ifd:ifd + 2])
    tags = {}
    for i in range(count):
        tag, typ, n, value = struct.unpack("<HHII", raw[ifd + 2 + 12 * i: ifd + 14 + 12 * i])
        tags[tag] = value if typ != 3 or n != 1 else value & 0xFFFF
    assert tags[256] == 40 and tags[257] == 30
    offset, nbytes = tags[273], tags[279]
    pixels = np.frombuffer(raw[offset:offset + nbytes], dtype="<u2").reshape(30, 40, 3)
    np.testing.assert_allclose(pixels / 65535.0, img, atol=1 / 65535)
    with Image.open(path) as im:  # other software can open it too
        assert im.size == (40, 30)


def test_exif_orientation_is_applied(tmp_path):
    arr = np.zeros((20, 40, 3), dtype=np.uint8)
    arr[:, :20] = 255  # left half white
    im = Image.fromarray(arr)
    exif = im.getexif()
    exif[0x0112] = 6  # rotate 90° CW on display
    path = str(tmp_path / "rot.jpg")
    im.save(path, exif=exif.tobytes(), quality=95)
    data = load_image(path).data
    assert data.shape[:2] == (40, 20)


def test_grayscale_and_16bit_png_load(tmp_path):
    path = str(tmp_path / "g16.png")
    Image.fromarray((np.arange(64 * 32).reshape(32, 64) * 16).astype(np.uint16)).save(path)
    data = load_image(path).data
    assert data.shape == (32, 64, 3)
    assert 0.0 <= data.min() and data.max() <= 1.0


def _shifted(img, dy, dx):
    return np.roll(np.roll(img, dy, axis=0), dx, axis=1)


def test_phase_correlation_finds_shift():
    ref = make_sample_sky(320, 240, seed=9, linear=True)
    moved = _shifted(ref, 7, -12)
    assert phase_shift(_alignment_spectrum(ref), moved) == (7, -12)


@pytest.mark.parametrize("method", ["mean", "median", "sigma", "max"])
def test_stacking_reduces_noise_and_aligns(method):
    rng = np.random.default_rng(4)
    clean = make_sample_sky(256, 192, seed=11, linear=True)
    frames = {}
    for i, (dy, dx) in enumerate([(0, 0), (3, -2), (-4, 5), (2, 2), (-1, -3)]):
        noisy = np.clip(clean + rng.normal(0, 0.01, clean.shape), 0, 1).astype(np.float32)
        frames[f"f{i}"] = _shifted(noisy, dy, dx)
    out = stack_images(lambda k: frames[k], list(frames), method=method, align=True)
    assert out.ndim == 3 and out.shape[2] == 3
    assert out.shape[0] < clean.shape[0] and out.shape[1] < clean.shape[1]  # cropped to common area
    if method != "max":
        # compare against the clean frame in the reference crop
        y0, x0 = 4, 3
        ref = clean[y0:y0 + out.shape[0], x0:x0 + out.shape[1]]
        single_noise = 0.01
        assert np.std(out - ref) < single_noise * 0.8


def test_stacking_rejects_mismatched_sizes():
    frames = {"a": np.zeros((50, 60, 3), np.float32), "b": np.zeros((40, 60, 3), np.float32)}
    with pytest.raises(ValueError):
        stack_images(lambda k: frames[k], ["a", "b"], align=False)
