"""Small Qt helpers: numpy ↔ QImage, background tasks, and scroll-safe input widgets."""

from __future__ import annotations

import traceback

import numpy as np
from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QComboBox, QDoubleSpinBox, QSpinBox

from ..processing.core import LUMA, sample_pixels, to_uint8


def to_qimage(img: np.ndarray) -> QImage:
    """float32 RGB [0,1] → an independent QImage (safe to create off the GUI thread)."""
    u8 = np.ascontiguousarray(to_uint8(img))
    h, w = u8.shape[:2]
    return QImage(u8.data, w, h, 3 * w, QImage.Format.Format_RGB888).copy()


def histogram(img: np.ndarray) -> dict:
    """256-bin R, G, B and luminance histograms plus clipping percentages."""
    px = sample_pixels(img, 300_000)
    u8 = to_uint8(px)
    lum = to_uint8(px @ LUMA)
    bins = np.stack([np.bincount(u8[:, c], minlength=256) for c in range(3)]
                    + [np.bincount(lum, minlength=256)]).astype(np.float64)
    n = max(len(lum), 1)
    return {"bins": bins, "low": float((lum == 0).sum()) / n, "high": float((u8 >= 255).any(axis=1).sum()) / n}


class TaskSignals(QObject):
    done = Signal(object)
    failed = Signal(str)
    progress = Signal(float, str)


class _Reaper(QObject):
    """Drops a finished task only after its result reached the GUI thread."""

    @Slot(object)
    def on_done(self, _result) -> None:
        self._reap()

    @Slot(str)
    def on_failed(self, _message) -> None:
        self._reap()

    def _reap(self) -> None:
        sender = self.sender()
        for task in list(Task._alive):
            if task.signals is sender:
                Task._alive.discard(task)


class Task(QRunnable):
    """Run fn(*args) on the global thread pool and report back through Qt signals.

    Connect ``signals`` (before calling start) only to methods of QObjects that
    live on the GUI thread, so that delivery is queued onto that thread.
    """

    _alive: set["Task"] = set()
    _reaper: _Reaper | None = None

    def __init__(self, fn, *args, progress: bool = False):
        super().__init__()
        self.setAutoDelete(False)
        self.fn, self.args, self.wants_progress = fn, args, progress
        self.signals = TaskSignals()
        self.cancelled = False

    def start(self) -> "Task":
        if Task._reaper is None:
            Task._reaper = _Reaper()
        # Connected last, so it runs after the caller's own handlers.
        self.signals.done.connect(Task._reaper.on_done)
        self.signals.failed.connect(Task._reaper.on_failed)
        Task._alive.add(self)
        QThreadPool.globalInstance().start(self)
        return self

    def cancel(self) -> None:
        self.cancelled = True

    def _progress(self, frac: float, text: str = "") -> None:
        self.signals.progress.emit(float(frac), text)

    def run(self) -> None:
        try:
            if self.wants_progress:
                result = self.fn(*self.args, progress=self._progress, cancelled=lambda: self.cancelled)
            else:
                result = self.fn(*self.args)
        except Exception as exc:  # report every failure to the GUI instead of dying silently
            detail = "".join(traceback.format_exception_only(type(exc), exc)).strip()
            traceback.print_exc()
            self.signals.failed.emit(detail)
        else:
            self.signals.done.emit(result)


class NoWheelMixin:
    """Ignore the mouse wheel unless focused, so scrolling a panel never nudges values."""

    def wheelEvent(self, event):  # noqa: N802 - Qt naming
        if self.hasFocus():
            super().wheelEvent(event)
        else:
            event.ignore()


class NoWheelSpinBox(NoWheelMixin, QSpinBox):
    pass


class NoWheelDoubleSpinBox(NoWheelMixin, QDoubleSpinBox):
    pass


class NoWheelComboBox(NoWheelMixin, QComboBox):
    pass
