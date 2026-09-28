import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from starlab.document import Document  # noqa: E402
from starlab.processing import core  # noqa: E402
from starlab.processing import filters as F  # noqa: E402
from starlab.processing.filters import Geo  # noqa: E402
from starlab.processing.params import DEFAULTS, PARAM_SPECS, default_params  # noqa: E402
from starlab.processing.pipeline import apply_geometry, process, render_frame, render_region, render_tiled  # noqa: E402
from starlab.processing.presets import PRESETS, apply_preset  # noqa: E402
from starlab.sample import make_sample_sky  # noqa: E402


@pytest.fixture(scope="module")
def sky():
    return make_sample_sky(480, 320, seed=3)


@pytest.fixture(scope="module")
def linear_sky():
    return make_sample_sky(480, 320, seed=3, linear=True)


def everything_on() -> dict:
    p = default_params()
    p.update(hotpixel=40, vignette=20, bg_remove=90, bg_neutral=80, color_calib=50, temperature=10, tint=-5,
             exposure=0.3, stretch_mode="auto", stretch=50, black_point=5, brightness=10, contrast=15,
             highlights=-10, shadows=10, scnr=60, ha_boost=40, local_contrast=40, star_reduce=50,
             chroma_denoise=40, denoise=40, saturation=20, vibrance=20, sharpen=30)
    return p


def test_every_preset_keeps_shape_type_and_range(sky):
    for preset in PRESETS:
        out, _ = render_frame(sky, apply_preset(preset, default_params()), 1.0)
        assert out.shape == sky.shape
        assert out.dtype == np.float32
        assert np.isfinite(out).all()
        assert out.min() >= 0.0 and out.max() <= 1.0


def test_default_params_are_identity(sky):
    out, _ = render_frame(sky, default_params(), 1.0)
    np.testing.assert_allclose(out, sky, atol=1e-6)


def test_every_slider_extreme_is_safe(sky):
    for spec in PARAM_SPECS:
        values = [c[0] for c in spec.choices] if spec.is_choice else [spec.minimum, spec.maximum]
        for v in values:
            p = default_params()
            p[spec.key] = v
            p["bg_remove"] = p["bg_remove"] or (50 if spec.key == "bg_degree" else 0)
            out, _ = render_frame(sky, p, 1.0)
            assert np.isfinite(out).all(), (spec.key, v)
            assert out.min() >= 0 and out.max() <= 1, (spec.key, v)


def test_banded_processing_matches_single_thread(sky, monkeypatch):
    p = everything_on()
    h, w = sky.shape[:2]
    ctx: dict = {}
    banded = process(sky, p, Geo(w, h), ctx)
    monkeypatch.setattr(core, "WORKERS", 1)
    single = process(sky, p, Geo(w, h), dict(ctx))
    np.testing.assert_allclose(banded, single, atol=2e-5)


def test_tiled_export_matches_whole_frame(sky):
    p = everything_on()
    whole, ctx = render_frame(sky, p, 1.0)
    tiled = render_tiled(sky, p, ctx, bits=16, tile=128)
    np.testing.assert_allclose(tiled / 65535.0, whole, atol=2e-4)


def test_detail_region_matches_whole_frame(sky):
    p = everything_on()
    whole, ctx = render_frame(sky, p, 1.0)
    box = (100, 60, 300, 220)
    region = render_region(sky, p, 1.0, dict(ctx), box)
    np.testing.assert_allclose(region, whole[60:220, 100:300], atol=2e-5)


def test_background_removal_flattens_gradient():
    h, w = 240, 360
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    grad = 0.05 + 0.2 * (yy / h) + 0.05 * (xx / w)
    img = np.stack([grad * 1.2, grad, grad * 0.6], axis=2).astype(np.float32)
    model = F.measure_background(img, 2)
    out = F.remove_background(img, 100, model, Geo(w, h))
    lum = core.luminance(out)
    assert np.ptp(lum) < 0.01
    # the orange cast is gone as well
    assert np.ptp(np.median(out.reshape(-1, 3), axis=0)) < 0.01


def test_background_removal_keeps_a_bright_object():
    h, w = 240, 360
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    sky = 0.05 + 0.1 * (yy / h)
    blob = 0.3 * np.exp(-(((xx - 180) / 30) ** 2 + ((yy - 120) / 30) ** 2))
    img = np.repeat((sky + blob)[..., None], 3, axis=2).astype(np.float32)
    model = F.measure_background(img, 2)
    out = F.remove_background(img, 100, model, Geo(w, h))
    assert out[120, 180, 0] - out[10, 10, 0] > 0.25


def test_hot_pixels_removed_but_stars_kept():
    rng = np.random.default_rng(1)
    img = (0.05 + rng.normal(0, 0.002, (100, 100, 3))).astype(np.float32)
    yy, xx = np.mgrid[0:100, 0:100]
    star = 0.8 * np.exp(-((xx - 30) ** 2 + (yy - 30) ** 2) / (2 * 1.2**2))
    img += star[..., None].astype(np.float32)
    img[70, 70, 0] = 0.9  # a hot red pixel
    out = F.hot_pixels(img, 50, Geo(100, 100))
    assert out[70, 70, 0] < 0.1
    assert out[30, 30, 1] > 0.7


def test_scnr_removes_green_cast():
    img = np.full((20, 20, 3), (0.2, 0.4, 0.2), dtype=np.float32)
    out = F.scnr(img, 100)
    assert abs(out[..., 1].mean() - 0.2) < 1e-6


def test_auto_stretch_puts_sky_at_target(linear_sky):
    stats = F.measure_stretch(linear_sky)
    for mode in ("auto", "asinh"):
        out = F.stretch(linear_sky, mode, 50, stats)
        sky_level = float(np.median(core.luminance(out)))
        assert 0.12 < sky_level < 0.24, (mode, sky_level)


def test_star_reduce_shrinks_stars_not_sky(linear_sky):
    stats = F.measure_stretch(linear_sky)
    img = F.stretch(linear_sky, "auto", 50, stats)
    noise = F.measure_noise(img, 1.0)
    out = F.star_reduce(img, 80, noise, Geo(img.shape[1], img.shape[0]))
    lum_in, lum_out = core.luminance(img), core.luminance(out)
    assert abs(np.median(lum_out) - np.median(lum_in)) < 0.01  # sky untouched
    bright = lum_in > np.percentile(lum_in, 99.8)
    assert lum_out[bright].mean() < lum_in[bright].mean() * 0.95


def test_contrast_curve_is_monotonic_and_fixed_at_ends():
    x = np.linspace(0, 1, 101, dtype=np.float32).reshape(1, -1, 1).repeat(3, axis=2)
    for amount in (-100, -30, 30, 100):
        y = F.contrast(x, amount)[0, :, 0]
        assert np.all(np.diff(y) >= -1e-6)
        assert y[0] < 1e-4 and y[-1] > 1 - 1e-4


def test_geometry_rotation_and_crop():
    img = np.zeros((10, 20, 3), dtype=np.float32)
    img[0, 19] = 1.0  # top-right corner
    p = dict(DEFAULTS, rotation=1)  # 90° counter-clockwise
    out = apply_geometry(img, p)
    assert out.shape == (20, 10, 3)
    assert out[0, 0, 0] == 1.0  # top-right becomes top-left
    p = dict(DEFAULTS, crop=(0.5, 0.0, 1.0, 0.5))
    assert apply_geometry(img, p).shape == (5, 10, 3)


def test_preview_draft_and_thumbnail_agree_on_brightness():
    doc = Document(make_sample_sky(1200, 800, seed=5), "t", preview_side=900)
    p = apply_preset(PRESETS[1], default_params())  # auto astro
    levels = []
    for which in ("preview", "draft", "thumb"):
        out, _ = render_frame(doc.frame(which, p), p, doc.scale_of(which), {"noise_gain": doc.noise_gain(which)})
        levels.append(float(np.median(core.luminance(out))))
    assert max(levels) - min(levels) < 0.03, levels
