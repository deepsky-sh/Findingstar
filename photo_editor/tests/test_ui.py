"""End-to-end smoke test of the window, run headless."""

import os
import sys
import time

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

QtWidgets = pytest.importorskip("PySide6.QtWidgets")

from starlab.document import Document  # noqa: E402
from starlab.imageio import load_image  # noqa: E402
from starlab.sample import make_sample_sky  # noqa: E402


@pytest.fixture(scope="module")
def app():
    from starlab.ui.theme import apply_theme

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    app.setOrganizationName("StarLabTests")
    app.setApplicationName("StarLabTests")
    apply_theme(app)
    return app


def wait_until(app, cond, timeout=60.0):
    end = time.time() + timeout
    while time.time() < end:
        app.processEvents()
        if cond():
            return True
        time.sleep(0.01)
    return False


def test_edit_undo_crop_and_export(app, tmp_path):
    from starlab.ui.main_window import MainWindow, _export

    win = MainWindow()
    win.show()
    doc = Document(make_sample_sky(600, 400, seed=1), "sample.jpg", preview_side=500)
    win.set_document(doc)
    assert wait_until(app, lambda: win._last_result is not None and not win._busy)
    assert win.canvas.has_image()

    win._apply_preset("auto_astro")
    assert wait_until(app, lambda: not win._busy and win._last_result.params == win.params)
    assert win.params["stretch_mode"] == "auto"

    win.adjust.rows["saturation"].set_value(40, emit=True)
    win._commit()
    assert win.params["saturation"] == 40
    win.undo()
    assert win.params["saturation"] == 25  # back to the preset value
    win.redo()
    assert win.params["saturation"] == 40

    win.toggle_crop(True)
    assert wait_until(app, lambda: win._crop_ready)
    from PySide6.QtCore import QRectF

    win.canvas.set_crop_rect(QRectF(60, 40, 300, 200))
    win._apply_crop()
    assert win.params["crop"] == pytest.approx((0.1, 0.1, 0.6, 0.6))
    assert wait_until(app, lambda: not win._busy and win._last_result.world_size == (300, 200))

    win.transform("cw")
    assert win.params["rotation"] == 3
    assert wait_until(app, lambda: not win._busy and win._last_result.world_size == (200, 300))

    out = str(tmp_path / "result.png")
    assert _export(doc, dict(win.params), out) == out
    saved = load_image(out).data
    assert saved.shape == (300, 200, 3)
    # the export matches what the window shows (the preview is 500/600 of full size)
    shown = win._last_result.proc
    w, h = shown.width(), shown.height()
    rows = np.frombuffer(shown.constBits(), np.uint8).reshape(h, shown.bytesPerLine())
    shown_rgb = rows[:, : w * 3].reshape(h, w, 3) / 255.0
    assert abs(float(saved.mean()) - float(shown_rgb.mean())) < 0.02
    assert np.abs(np.median(saved, axis=(0, 1)) - np.median(shown_rgb, axis=(0, 1))).max() < 0.03
    win.close()
