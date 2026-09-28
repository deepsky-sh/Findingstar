"""The picture viewer: zoom, pan, before/after split view, 1:1 detail overlay and crop box.

All geometry is in *world* coordinates = pixels of the full-resolution frame,
so the preview, the sharper 1:1 detail patch and the crop box all line up no
matter which resolution each image was rendered at.
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, QSizeF, Qt, Signal
from PySide6.QtGui import QColor, QCursor, QFont, QImage, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget

from . import theme

HANDLE_PX = 10


class ImageCanvas(QWidget):
    hovered = Signal(float, float)  # world coordinates, or (-1, -1) outside the picture
    view_changed = Signal()
    crop_edited = Signal()
    files_dropped = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setAcceptDrops(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMinimumSize(320, 240)
        self._world = QSizeF(0, 0)
        self._proc: QImage | None = None
        self._orig: QImage | None = None
        self._detail: tuple[QRectF, QImage, QImage] | None = None
        self._zoom = 1.0
        self._center = QPointF(0, 0)
        self._fit = True
        self._compare = False
        self._split = 0.5
        self._show_original = False
        self._drag: str | None = None
        self._drag_data = None
        self._last = QPointF()
        self._scaled_cache: dict = {}
        self._crop_mode = False
        self._crop = QRectF()
        self._aspect: float | None = None

    # ─────────────────────────── public API ───────────────────────────

    def has_image(self) -> bool:
        return self._proc is not None

    def set_images(self, proc: QImage, orig: QImage, world_w: int, world_h: int) -> None:
        new_world = QSizeF(world_w, world_h)
        world_changed = new_world != self._world
        self._proc, self._orig = proc, orig
        self._scaled_cache.clear()
        if world_changed:
            self._world = new_world
            self._detail = None
            self._fit = True
        if self._fit:
            self._apply_fit()
        self.update()

    def clear(self) -> None:
        self._proc = self._orig = None
        self._detail = None
        self._world = QSizeF(0, 0)
        self.update()

    def set_detail(self, world_rect: QRectF, proc: QImage, orig: QImage) -> None:
        self._detail = (QRectF(world_rect), proc, orig)
        self.update()

    def clear_detail(self) -> None:
        if self._detail is not None:
            self._detail = None
            self.update()

    def detail_rect(self) -> QRectF | None:
        return self._detail[0] if self._detail else None

    def preview_density(self) -> float:
        """Preview pixels per world pixel."""
        if not self._proc or self._world.width() <= 0:
            return 1.0
        return self._proc.width() / self._world.width()

    def zoom(self) -> float:
        return self._zoom

    def set_compare(self, on: bool) -> None:
        self._compare = on
        self.update()

    def set_show_original(self, on: bool) -> None:
        self._show_original = on
        self.update()

    def fit(self) -> None:
        self._fit = True
        self._apply_fit()
        self.update()
        self.view_changed.emit()

    def zoom_to(self, zoom: float, anchor: QPointF | None = None) -> None:
        if not self.has_image():
            return
        anchor = anchor if anchor is not None else QPointF(self.width() / 2, self.height() / 2)
        world_anchor = self.screen_to_world(anchor)
        lo = min(self._fit_zoom() * 0.5, 0.05)
        self._zoom = max(lo, min(32.0, zoom))
        # Keep the point under the cursor fixed while zooming.
        self._center = world_anchor - (anchor - self._screen_center()) / self._zoom
        self._fit = False
        self._clamp_center()
        self.update()
        self.view_changed.emit()

    def zoom_by(self, factor: float, anchor: QPointF | None = None) -> None:
        self.zoom_to(self._zoom * factor, anchor)

    def visible_world_rect(self) -> QRectF:
        tl = self.screen_to_world(QPointF(0, 0))
        br = self.screen_to_world(QPointF(self.width(), self.height()))
        return QRectF(tl, br).intersected(QRectF(QPointF(0, 0), self._world))

    # crop -----------------------------------------------------------

    def set_crop_mode(self, on: bool, rect: QRectF | None = None) -> None:
        self._crop_mode = on
        self._crop = QRectF(rect) if rect is not None else QRectF(QPointF(0, 0), self._world)
        self.setCursor(Qt.CursorShape.CrossCursor if on else Qt.CursorShape.ArrowCursor)
        self.update()

    def crop_rect(self) -> QRectF:
        return QRectF(self._crop)

    def set_crop_rect(self, rect: QRectF) -> None:
        self._crop = rect.intersected(QRectF(QPointF(0, 0), self._world))
        self.update()

    def set_crop_aspect(self, aspect: float | None) -> None:
        """Width/height ratio to keep while cropping, or None for free."""
        self._aspect = aspect
        if aspect and not self._crop.isEmpty():
            c = self._crop.center()
            w, h = self._crop.width(), self._crop.height()
            if w / h > aspect:
                w = h * aspect
            else:
                h = w / aspect
            self.set_crop_rect(QRectF(c.x() - w / 2, c.y() - h / 2, w, h))
            self.crop_edited.emit()

    # ─────────────────────────── coordinates ───────────────────────────

    def _screen_center(self) -> QPointF:
        return QPointF(self.width() / 2, self.height() / 2)

    def world_to_screen(self, p: QPointF) -> QPointF:
        return (p - self._center) * self._zoom + self._screen_center()

    def screen_to_world(self, p: QPointF) -> QPointF:
        return (p - self._screen_center()) / self._zoom + self._center

    def _world_rect_to_screen(self, r: QRectF) -> QRectF:
        return QRectF(self.world_to_screen(r.topLeft()), self.world_to_screen(r.bottomRight()))

    def _fit_zoom(self) -> float:
        if self._world.width() <= 0:
            return 1.0
        margin = 24
        return max(1e-4, min((self.width() - margin) / self._world.width(),
                             (self.height() - margin) / self._world.height()))

    def _apply_fit(self) -> None:
        self._zoom = self._fit_zoom()
        self._center = QPointF(self._world.width() / 2, self._world.height() / 2)

    def _clamp_center(self) -> None:
        # Never let the picture be dragged completely out of view.
        w, h = self._world.width(), self._world.height()
        half_w, half_h = self.width() / 2 / self._zoom, self.height() / 2 / self._zoom
        x = min(max(self._center.x(), min(half_w, w / 2)), max(w - half_w, w / 2))
        y = min(max(self._center.y(), min(half_h, h / 2)), max(h - half_h, h / 2))
        self._center = QPointF(x, y)

    # ─────────────────────────── painting ───────────────────────────

    def _draw_layer(self, p: QPainter, img: QImage, world_rect: QRectF) -> None:
        """Draw img, which covers world_rect, clipped to what is visible."""
        target = self._world_rect_to_screen(world_rect)
        if target.width() < 1 or target.height() < 1:
            return
        if target.width() < img.width() * 0.999:
            # Shrinking: pre-scale with area averaging so stars don't shimmer.
            size = target.size().toSize()
            key = (img.cacheKey(), size.width(), size.height())
            scaled = self._scaled_cache.get(key)
            if scaled is None:
                if len(self._scaled_cache) > 6:
                    self._scaled_cache.clear()
                scaled = img.scaled(size, Qt.AspectRatioMode.IgnoreAspectRatio,
                                    Qt.TransformationMode.SmoothTransformation)
                self._scaled_cache[key] = scaled
            p.drawImage(target.topLeft(), scaled)
            return
        # Enlarging: draw only the visible part; show real pixels when zoomed far in.
        visible = target.intersected(QRectF(self.rect()))
        if visible.isEmpty():
            return
        sx = img.width() / target.width()
        sy = img.height() / target.height()
        src = QRectF((visible.left() - target.left()) * sx, (visible.top() - target.top()) * sy,
                     visible.width() * sx, visible.height() * sy)
        smooth = target.width() / img.width() < 3.0
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, smooth)
        p.drawImage(visible, img, src)

    def _draw_images(self, p: QPainter, original: bool) -> None:
        base = self._orig if original else self._proc
        if base is None:
            return
        self._draw_layer(p, base, QRectF(QPointF(0, 0), self._world))
        if self._detail and not self._crop_mode:
            rect, proc, orig = self._detail
            self._draw_layer(p, orig if original else proc, rect)

    def paintEvent(self, _event):  # noqa: N802
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(theme.CANVAS))
        if not self.has_image():
            return
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        frame_rect = self._world_rect_to_screen(QRectF(QPointF(0, 0), self._world))
        # soft shadow frame
        p.setPen(QPen(QColor(0, 0, 0, 160), 6))
        p.drawRect(frame_rect.adjusted(-3, -3, 3, 3))

        if self._show_original:
            self._draw_images(p, original=True)
            self._draw_badge(p, QPointF(14, 14), "원본", left=True)
        elif self._compare and not self._crop_mode:
            split_x = self.width() * self._split
            p.save()
            p.setClipRect(QRectF(0, 0, split_x, self.height()))
            self._draw_images(p, original=True)
            p.restore()
            p.save()
            p.setClipRect(QRectF(split_x, 0, self.width() - split_x, self.height()))
            self._draw_images(p, original=False)
            p.restore()
            self._draw_split(p, split_x)
        else:
            self._draw_images(p, original=False)

        if self._crop_mode:
            self._draw_crop(p)

    def _draw_badge(self, p: QPainter, pos: QPointF, text: str, left: bool) -> None:
        f = QFont(self.font())
        f.setBold(True)
        p.setFont(f)
        w = p.fontMetrics().horizontalAdvance(text) + 20
        rect = QRectF(pos.x() if left else pos.x() - w, pos.y(), w, 26)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(10, 12, 24, 200))
        p.drawRoundedRect(rect, 13, 13)
        p.setPen(QColor(theme.TEXT))
        p.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)

    def _draw_split(self, p: QPainter, x: float) -> None:
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setPen(QPen(QColor(255, 255, 255, 220), 2))
        p.drawLine(QPointF(x, 0), QPointF(x, self.height()))
        c = QPointF(x, self.height() / 2)
        p.setBrush(QColor(theme.ACCENT))
        p.setPen(QPen(QColor(255, 255, 255), 2))
        p.drawEllipse(c, 14, 14)
        p.setPen(QPen(QColor("#1a0b14"), 2))
        for sgn in (-1, 1):
            tip = QPointF(c.x() + sgn * 8, c.y())
            p.drawLine(tip, QPointF(c.x() + sgn * 3, c.y() - 5))
            p.drawLine(tip, QPointF(c.x() + sgn * 3, c.y() + 5))
        self._draw_badge(p, QPointF(14, 14), "◀ 원본", left=True)
        self._draw_badge(p, QPointF(self.width() - 14, 14), "보정 ▶", left=False)

    def _draw_crop(self, p: QPainter) -> None:
        r = self._world_rect_to_screen(self._crop).normalized()
        outside = QPainterPath()
        outside.addRect(QRectF(self.rect()))
        inner = QPainterPath()
        inner.addRect(r)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 0, 0, 150))
        p.drawPath(outside.subtracted(inner))
        p.setPen(QPen(QColor(255, 255, 255, 90), 1))
        for i in (1, 2):
            x = r.left() + r.width() * i / 3
            y = r.top() + r.height() * i / 3
            p.drawLine(QPointF(x, r.top()), QPointF(x, r.bottom()))
            p.drawLine(QPointF(r.left(), y), QPointF(r.right(), y))
        p.setPen(QPen(QColor(theme.ACCENT), 2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(r)
        p.setBrush(QColor(255, 255, 255))
        p.setPen(QPen(QColor(theme.ACCENT), 2))
        for c in (r.topLeft(), r.topRight(), r.bottomLeft(), r.bottomRight()):
            p.drawRect(QRectF(c.x() - 5, c.y() - 5, 10, 10))
        w = round(self._crop.width())
        h = round(self._crop.height())
        self._draw_badge(p, QPointF(r.left(), max(4, r.top() - 32)), f"{w} × {h}", left=True)

    # ─────────────────────────── interaction ───────────────────────────

    def resizeEvent(self, event):  # noqa: N802
        if self._fit:
            self._apply_fit()
        else:
            self._clamp_center()
        super().resizeEvent(event)
        self.view_changed.emit()

    def wheelEvent(self, event):  # noqa: N802
        if not self.has_image():
            return
        delta = event.angleDelta().y() or event.pixelDelta().y()
        if delta:
            self.zoom_by(1.0015 ** delta, event.position())

    def mouseDoubleClickEvent(self, event):  # noqa: N802
        if not self.has_image() or self._crop_mode:
            return
        if self._fit or abs(self._zoom - self._fit_zoom()) < 1e-3:
            self.zoom_to(1.0, event.position())
        else:
            self.fit()

    def _corner_hit(self, pos: QPointF) -> int | None:
        r = self._world_rect_to_screen(self._crop).normalized()
        corners = [r.topLeft(), r.topRight(), r.bottomLeft(), r.bottomRight()]
        for i, c in enumerate(corners):
            if abs(c.x() - pos.x()) <= HANDLE_PX and abs(c.y() - pos.y()) <= HANDLE_PX:
                return i
        return None

    def mousePressEvent(self, event):  # noqa: N802
        if not self.has_image():
            return
        pos = event.position()
        self._last = pos
        if event.button() == Qt.MouseButton.MiddleButton:
            self._drag = "pan"
        elif event.button() == Qt.MouseButton.LeftButton:
            if self._crop_mode:
                corner = self._corner_hit(pos)
                if corner is not None:
                    r = self._crop.normalized()
                    opposite = [r.bottomRight(), r.bottomLeft(), r.topRight(), r.topLeft()][corner]
                    self._drag, self._drag_data = "crop-new", opposite
                elif self._world_rect_to_screen(self._crop).normalized().contains(pos):
                    self._drag, self._drag_data = "crop-move", self.screen_to_world(pos) - self._crop.topLeft()
                else:
                    self._drag, self._drag_data = "crop-new", self._clamp_world(self.screen_to_world(pos))
            elif self._compare and abs(pos.x() - self.width() * self._split) <= HANDLE_PX + 4:
                self._drag = "split"
            else:
                self._drag = "pan"
                self.setCursor(Qt.CursorShape.ClosedHandCursor)

    def _clamp_world(self, p: QPointF) -> QPointF:
        return QPointF(min(max(p.x(), 0.0), self._world.width()), min(max(p.y(), 0.0), self._world.height()))

    def _constrained_rect(self, anchor: QPointF, point: QPointF) -> QRectF:
        dx, dy = point.x() - anchor.x(), point.y() - anchor.y()
        if self._aspect:
            sx = 1 if dx >= 0 else -1
            sy = 1 if dy >= 0 else -1
            if abs(dx) / self._aspect > abs(dy):
                dy = sy * abs(dx) / self._aspect
            else:
                dx = sx * abs(dy) * self._aspect
            # Shrink uniformly if the box would leave the picture.
            limit_x = (self._world.width() - anchor.x()) if dx > 0 else anchor.x()
            limit_y = (self._world.height() - anchor.y()) if dy > 0 else anchor.y()
            k = min(1.0, limit_x / max(abs(dx), 1e-9), limit_y / max(abs(dy), 1e-9))
            dx, dy = dx * k, dy * k
        end = self._clamp_world(QPointF(anchor.x() + dx, anchor.y() + dy))
        return QRectF(anchor, end).normalized()

    def mouseMoveEvent(self, event):  # noqa: N802
        pos = event.position()
        if self.has_image():
            w = self.screen_to_world(pos)
            inside = 0 <= w.x() < self._world.width() and 0 <= w.y() < self._world.height()
            self.hovered.emit(w.x() if inside else -1.0, w.y() if inside else -1.0)
        if self._drag == "pan":
            self._center -= (pos - self._last) / self._zoom
            self._fit = False
            self._clamp_center()
            self.update()
            self.view_changed.emit()
        elif self._drag == "split":
            self._split = min(max(pos.x() / max(self.width(), 1), 0.02), 0.98)
            self.update()
        elif self._drag == "crop-new":
            self._crop = self._constrained_rect(self._drag_data, self.screen_to_world(pos))
            self.update()
        elif self._drag == "crop-move":
            tl = self.screen_to_world(pos) - self._drag_data
            w, h = self._crop.width(), self._crop.height()
            x = min(max(tl.x(), 0.0), self._world.width() - w)
            y = min(max(tl.y(), 0.0), self._world.height() - h)
            self._crop = QRectF(x, y, w, h)
            self.update()
        elif self._compare and not self._crop_mode and self.has_image():
            near = abs(pos.x() - self.width() * self._split) <= HANDLE_PX + 4
            self.setCursor(Qt.CursorShape.SplitHCursor if near else Qt.CursorShape.ArrowCursor)
        elif self._crop_mode:
            corner = self._corner_hit(pos)
            if corner in (0, 3):
                self.setCursor(Qt.CursorShape.SizeFDiagCursor)
            elif corner in (1, 2):
                self.setCursor(Qt.CursorShape.SizeBDiagCursor)
            elif self._world_rect_to_screen(self._crop).normalized().contains(pos):
                self.setCursor(Qt.CursorShape.SizeAllCursor)
            else:
                self.setCursor(Qt.CursorShape.CrossCursor)
        self._last = pos

    def mouseReleaseEvent(self, event):  # noqa: N802
        was = self._drag
        self._drag = None
        if was in ("crop-new", "crop-move"):
            if self._crop.width() < 4 or self._crop.height() < 4:
                self._crop = QRectF(QPointF(0, 0), self._world)
                self.update()
            self.crop_edited.emit()
        if not self._crop_mode:
            self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))

    def leaveEvent(self, event):  # noqa: N802
        self.hovered.emit(-1.0, -1.0)
        super().leaveEvent(event)

    # drag & drop files onto the picture
    def dragEnterEvent(self, event):  # noqa: N802
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):  # noqa: N802
        paths = [u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()]
        if paths:
            self.files_dropped.emit(paths)
