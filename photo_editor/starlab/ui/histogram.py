"""Live RGB histogram with clipping warnings."""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from . import theme


class HistogramView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(96)
        self._bins: np.ndarray | None = None
        self.setToolTip("히스토그램: 왼쪽은 어두운 영역, 오른쪽은 밝은 영역입니다.\n"
                        "천체 사진은 산 모양이 왼쪽 1/4 부근에 있으면 보기 좋아요.")

    def set_bins(self, bins: np.ndarray | None) -> None:
        self._bins = bins
        self.update()

    def paintEvent(self, _event):  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        bg = QLinearGradient(r.topLeft(), r.bottomLeft())
        bg.setColorAt(0, QColor("#0a0c16"))
        bg.setColorAt(1, QColor("#05060c"))
        p.setBrush(bg)
        p.setPen(QPen(QColor(theme.BORDER), 1))
        p.drawRoundedRect(r, 8, 8)
        p.setPen(QPen(QColor(255, 255, 255, 18), 1))
        for i in (1, 2, 3):
            x = r.left() + r.width() * i / 4
            p.drawLine(QPointF(x, r.top() + 4), QPointF(x, r.bottom() - 4))
        if self._bins is None:
            return
        # Log scale: astro histograms are one tall, narrow peak.
        data = np.log1p(self._bins)
        top = max(float(data[:, 1:-1].max()), 1e-9)
        inner = r.adjusted(4, 6, -4, -3)

        def path_for(row: np.ndarray) -> QPainterPath:
            path = QPainterPath(QPointF(inner.left(), inner.bottom()))
            n = len(row)
            for i, v in enumerate(row):
                x = inner.left() + inner.width() * i / (n - 1)
                y = inner.bottom() - inner.height() * min(v / top, 1.0)
                path.lineTo(QPointF(x, y))
            path.lineTo(QPointF(inner.right(), inner.bottom()))
            path.closeSubpath()
            return path

        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Plus)
        p.setPen(Qt.PenStyle.NoPen)
        for row, color in zip(data[:3], (QColor(230, 60, 80, 150), QColor(60, 200, 110, 150),
                                         QColor(70, 120, 255, 160))):
            p.setBrush(color)
            p.drawPath(path_for(row))
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor(255, 255, 255, 170), 1.2))
        p.drawPath(path_for(data[3]))


class HistogramPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        self.view = HistogramView()
        self.info = QLabel(" ")
        self.info.setObjectName("Dim")
        lay.addWidget(self.view)
        lay.addWidget(self.info)

    def set_data(self, data: dict | None) -> None:
        if not data:
            self.view.set_bins(None)
            self.info.setText(" ")
            return
        self.view.set_bins(data["bins"])
        low, high = data["low"] * 100, data["high"] * 100
        warn_low = "⚠ " if low > 2 else ""
        warn_high = "⚠ " if high > 0.5 else ""
        self.info.setText(f"{warn_low}검게 뭉개짐 {low:.1f}%   ·   {warn_high}하얗게 날아감 {high:.1f}%")
        self.info.setToolTip("값이 크면 어두운/밝은 부분의 디테일이 사라진 것입니다.\n"
                             "블랙 포인트나 하이라이트를 조절해 보세요.")
