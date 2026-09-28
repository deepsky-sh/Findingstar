"""Background rendering that keeps the window responsive.

* Previews: only one render runs at a time and only the newest request waits.
  While the user drags a slider, quick half-resolution drafts are shown; the
  sharp preview follows as soon as they stop.
* Detail: when zoomed past the preview's resolution, the visible area is
  rendered from the full-resolution source using the preview's statistics.
* Thumbnails: every preset applied to a tiny copy, for the left panel.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import numpy as np
from PySide6.QtCore import QObject, Signal, Slot
from PySide6.QtGui import QImage

from ..document import Document
from ..processing.pipeline import render_frame, render_region
from ..processing.presets import PRESETS, apply_preset
from .qtutil import Task, histogram, to_qimage


@dataclass
class PreviewResult:
    doc: Document
    params: dict
    use_crop: bool
    draft: bool
    proc: QImage
    orig: QImage
    hist: dict
    ctx: dict
    world_size: tuple[int, int]
    elapsed: float


@dataclass
class DetailResult:
    doc: Document
    params: dict
    box: tuple[int, int, int, int]
    proc: QImage
    orig: QImage


def _render_preview(doc: Document, params: dict, use_crop: bool, draft: bool) -> PreviewResult:
    t0 = time.perf_counter()
    which = "draft" if draft else "preview"
    frame = doc.frame(which, params, use_crop)
    out, ctx = render_frame(frame, params, doc.scale_of(which), {"noise_gain": doc.noise_gain(which)})
    world = doc.frame_size(params, use_crop)
    return PreviewResult(doc, dict(params), use_crop, draft, to_qimage(out), to_qimage(frame),
                         histogram(out), ctx, world, time.perf_counter() - t0)


def _render_detail(doc: Document, params: dict, use_crop: bool, ctx: dict,
                   box: tuple[int, int, int, int]) -> DetailResult:
    frame = doc.frame("full", params, use_crop)
    x0, y0, x1, y1 = box
    out = render_region(frame, params, 1.0, dict(ctx), box)
    orig = np.asarray(frame[y0:y1, x0:x1], dtype=np.float32)
    return DetailResult(doc, dict(params), box, to_qimage(out), to_qimage(orig))


def _render_thumbs(doc: Document, params: dict) -> tuple[Document, dict]:
    frame = doc.frame("thumb", params)
    thumbs = {}
    for preset in PRESETS:
        ctx = {"noise_gain": doc.noise_gain("thumb")}
        out, _ = render_frame(frame, apply_preset(preset, params), doc.scale_of("thumb"), ctx)
        thumbs[preset.key] = to_qimage(out)
    return doc, thumbs


class RenderController(QObject):
    preview_ready = Signal(object)
    detail_ready = Signal(object)
    thumbs_ready = Signal(object)
    busy_changed = Signal(bool)
    failed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.doc: Document | None = None
        self._preview_task: Task | None = None
        self._pending: tuple[dict, bool] | None = None
        self._last_final: PreviewResult | None = None
        self._detail_task: Task | None = None
        self._detail_pending: tuple | None = None
        self._thumb_task: Task | None = None
        self._thumb_pending: dict | None = None

    def set_document(self, doc: Document | None) -> None:
        self.doc = doc
        self._pending = None
        self._detail_pending = None
        self._last_final = None

    @property
    def last_final(self) -> PreviewResult | None:
        return self._last_final

    # previews -----------------------------------------------------------

    def request_preview(self, params: dict, use_crop: bool = True) -> None:
        if self.doc is None:
            return
        self._pending = (dict(params), use_crop)
        if self._preview_task is None:
            self._start_pending(draft=False)

    def _start_pending(self, draft: bool) -> None:
        params, use_crop = self._pending
        self._pending = None
        task = Task(_render_preview, self.doc, params, use_crop, draft)
        task.signals.done.connect(self._on_preview_done)
        task.signals.failed.connect(self._on_preview_failed)
        self._preview_task = task.start()
        self.busy_changed.emit(True)

    @Slot(object)
    def _on_preview_done(self, result: PreviewResult) -> None:
        self._preview_task = None
        if result.doc is not self.doc:
            result = None
        if result is not None:
            if not result.draft:
                self._last_final = result
            self.preview_ready.emit(result)
        if self._pending is not None:
            # The user is still moving things: keep up with a quick draft.
            self._start_pending(draft=result is not None)
        elif result is not None and result.draft:
            self._pending = (result.params, result.use_crop)
            self._start_pending(draft=False)
        else:
            self.busy_changed.emit(False)

    @Slot(str)
    def _on_preview_failed(self, message: str) -> None:
        self._preview_task = None
        self.failed.emit(message)
        if self._pending is not None:
            self._start_pending(draft=False)
        else:
            self.busy_changed.emit(False)

    # 1:1 detail ---------------------------------------------------------

    def request_detail(self, params: dict, use_crop: bool, box: tuple[int, int, int, int]) -> None:
        final = self._last_final
        if self.doc is None or final is None or final.params != params or final.use_crop != use_crop:
            return
        self._detail_pending = (dict(params), use_crop, final.ctx, box)
        if self._detail_task is None:
            self._start_detail()

    def _start_detail(self) -> None:
        params, use_crop, ctx, box = self._detail_pending
        self._detail_pending = None
        task = Task(_render_detail, self.doc, params, use_crop, ctx, box)
        task.signals.done.connect(self._on_detail_done)
        task.signals.failed.connect(self._on_detail_failed)
        self._detail_task = task.start()

    @Slot(object)
    def _on_detail_done(self, result: DetailResult) -> None:
        self._detail_task = None
        if self._detail_pending is not None:
            self._start_detail()
        elif result.doc is self.doc:
            self.detail_ready.emit(result)

    @Slot(str)
    def _on_detail_failed(self, message: str) -> None:
        self._detail_task = None
        self.failed.emit(message)

    # thumbnails ---------------------------------------------------------

    def request_thumbnails(self, params: dict) -> None:
        if self.doc is None:
            return
        self._thumb_pending = dict(params)
        if self._thumb_task is None:
            self._start_thumbs()

    def _start_thumbs(self) -> None:
        params = self._thumb_pending
        self._thumb_pending = None
        task = Task(_render_thumbs, self.doc, params)
        task.signals.done.connect(self._on_thumbs_done)
        task.signals.failed.connect(self._on_thumbs_failed)
        self._thumb_task = task.start()

    @Slot(object)
    def _on_thumbs_done(self, result) -> None:
        self._thumb_task = None
        doc, thumbs = result
        if self._thumb_pending is not None:
            self._start_thumbs()
        elif doc is self.doc:
            self.thumbs_ready.emit(thumbs)

    @Slot(str)
    def _on_thumbs_failed(self, message: str) -> None:
        self._thumb_task = None
        self.failed.emit(message)
