"""Left column: one-click looks, each shown as a live thumbnail of the current photo."""

from __future__ import annotations

from PySide6.QtCore import QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QIcon, QImage, QPainter, QPixmap
from PySide6.QtWidgets import QLabel, QListView, QListWidget, QListWidgetItem, QVBoxLayout, QWidget

from ..processing.presets import PRESETS
from . import theme

THUMB_W, THUMB_H = 150, 96


def _placeholder(text: str) -> QPixmap:
    pm = QPixmap(THUMB_W, THUMB_H)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(QColor(theme.PANEL_2))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawRoundedRect(QRectF(0, 0, THUMB_W, THUMB_H), 8, 8)
    f = QFont()
    f.setPointSize(22)
    p.setFont(f)
    p.setPen(QColor(theme.TEXT_3))
    p.drawText(QRectF(0, 0, THUMB_W, THUMB_H), Qt.AlignmentFlag.AlignCenter, text)
    p.end()
    return pm


def _icon(pm: QPixmap) -> QIcon:
    # Register the pixmap for the selected state too, otherwise Qt tints the
    # chosen thumbnail with the accent colour and hides what the look does.
    icon = QIcon(pm)
    icon.addPixmap(pm, QIcon.Mode.Selected)
    return icon


def _thumb_pixmap(img: QImage) -> QPixmap:
    """Fill a rounded card with the thumbnail (cover-cropped to the card shape)."""
    pm = QPixmap(THUMB_W, THUMB_H)
    pm.fill(Qt.GlobalColor.transparent)
    scaled = img.scaled(THUMB_W, THUMB_H, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                        Qt.TransformationMode.SmoothTransformation)
    x = (scaled.width() - THUMB_W) // 2
    y = (scaled.height() - THUMB_H) // 2
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(QColor(0, 0, 0))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawRoundedRect(QRectF(0, 0, THUMB_W, THUMB_H), 8, 8)
    p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
    p.drawImage(0, 0, scaled, x, y, THUMB_W, THUMB_H)
    p.end()
    return pm


class PresetPanel(QWidget):
    preset_chosen = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Panel")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 10, 4, 8)
        lay.setSpacing(2)
        title = QLabel("원클릭 필터")
        title.setObjectName("PanelTitle")
        sub = QLabel("사진에 맞는 스타일을 고르고\n오른쪽에서 세부 조정하세요")
        sub.setObjectName("Dim")
        lay.addWidget(title)
        lay.addWidget(sub)
        self.list = QListWidget()
        self.list.setViewMode(QListView.ViewMode.IconMode)
        self.list.setFlow(QListView.Flow.TopToBottom)
        self.list.setWrapping(False)
        self.list.setMovement(QListView.Movement.Static)
        self.list.setResizeMode(QListView.ResizeMode.Adjust)
        self.list.setIconSize(QSize(THUMB_W, THUMB_H))
        self.list.setGridSize(QSize(THUMB_W + 18, THUMB_H + 36))
        self.list.setSpacing(0)
        self.list.setUniformItemSizes(True)
        self.list.setWordWrap(True)
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list.setVerticalScrollMode(QListView.ScrollMode.ScrollPerPixel)
        self.list.setCursor(Qt.CursorShape.PointingHandCursor)
        self.items: dict[str, QListWidgetItem] = {}
        for preset in PRESETS:
            item = QListWidgetItem(_icon(_placeholder(preset.name.split(" ")[0])), preset.name)
            item.setData(Qt.ItemDataRole.UserRole, preset.key)
            item.setToolTip(f"<b>{preset.name}</b><br>{preset.description}")
            item.setTextAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
            self.list.addItem(item)
            self.items[preset.key] = item
        self.list.itemClicked.connect(self._clicked)
        lay.addWidget(self.list, 1)
        self.setMinimumWidth(THUMB_W + 44)
        self.setMaximumWidth(THUMB_W + 70)

    def _clicked(self, item: QListWidgetItem) -> None:
        self.preset_chosen.emit(item.data(Qt.ItemDataRole.UserRole))

    def set_thumbnails(self, thumbs: dict[str, QImage]) -> None:
        for key, img in thumbs.items():
            if key in self.items:
                self.items[key].setIcon(_icon(_thumb_pixmap(img)))

    def reset_thumbnails(self) -> None:
        for preset in PRESETS:
            self.items[preset.key].setIcon(_icon(_placeholder(preset.name.split(" ")[0])))

    def set_current(self, key: str | None) -> None:
        self.list.blockSignals(True)
        self.list.clearSelection()
        if key in self.items:
            self.items[key].setSelected(True)
        self.list.blockSignals(False)
