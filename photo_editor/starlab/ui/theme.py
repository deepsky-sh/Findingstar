"""Dark night-sky theme shared with the Findingstar web app (pink accent on deep navy)."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPainterPath, QPalette, QPixmap, QRadialGradient
from PySide6.QtWidgets import QApplication, QProxyStyle, QStyle, QStyleFactory

BG = "#0d0f1a"
PANEL = "#141726"
PANEL_2 = "#1b1f33"
BORDER = "#262a40"
CANVAS = "#07080e"
TEXT = "#e8eaff"
TEXT_2 = "#9da3c7"
TEXT_3 = "#5a6088"
ACCENT = "#ff7eb3"
ACCENT_2 = "#8ea2ff"
GROOVE = "#2a2f4a"

FONT_FAMILIES = ["Pretendard", "Malgun Gothic", "Apple SD Gothic Neo", "Noto Sans KR",
                 "Noto Sans CJK KR", "NanumGothic", "Segoe UI", "sans-serif"]

QSS = f"""
* {{ color: {TEXT}; }}
QMainWindow, QDialog {{ background: {BG}; }}
QWidget#Panel {{ background: {PANEL}; }}
QLabel#Muted {{ color: {TEXT_2}; }}
QLabel#Dim {{ color: {TEXT_3}; }}
QLabel#PanelTitle {{ font-weight: 700; font-size: 11pt; padding: 2px 0; }}
QLabel#Hero {{ font-size: 22pt; font-weight: 800; }}
QLabel#ParamLabel[modified="true"] {{ color: {ACCENT}; font-weight: 600; }}
QLabel#ParamLabel:disabled {{ color: {TEXT_3}; }}

QToolTip {{ background: {PANEL_2}; color: {TEXT}; border: 1px solid {BORDER}; padding: 6px 8px;
            border-radius: 6px; }}

QMenuBar {{ background: {BG}; border-bottom: 1px solid {BORDER}; }}
QMenuBar::item {{ padding: 5px 10px; background: transparent; border-radius: 4px; }}
QMenuBar::item:selected {{ background: {PANEL_2}; }}
QMenu {{ background: {PANEL}; border: 1px solid {BORDER}; padding: 4px; }}
QMenu::item {{ padding: 6px 28px 6px 14px; border-radius: 4px; }}
QMenu::item:selected {{ background: {PANEL_2}; color: #fff; }}
QMenu::item:disabled {{ color: {TEXT_3}; }}
QMenu::separator {{ height: 1px; background: {BORDER}; margin: 4px 6px; }}

QToolBar {{ background: {BG}; border: none; border-bottom: 1px solid {BORDER}; spacing: 2px; padding: 4px 6px; }}
QToolBar::separator {{ background: {BORDER}; width: 1px; margin: 6px 6px; }}
QToolButton {{ background: transparent; border: 1px solid transparent; border-radius: 8px; padding: 5px 9px; }}
QToolButton:hover {{ background: {PANEL_2}; border-color: {BORDER}; }}
QToolButton:pressed {{ background: {GROOVE}; }}
QToolButton:checked {{ background: rgba(255,126,179,0.18); border-color: {ACCENT}; color: #fff; }}
QToolButton:disabled {{ color: {TEXT_3}; }}

QPushButton {{ background: {PANEL_2}; border: 1px solid {BORDER}; border-radius: 9px; padding: 8px 16px; }}
QPushButton:hover {{ border-color: {ACCENT_2}; }}
QPushButton:pressed {{ background: {GROOVE}; }}
QPushButton:disabled {{ color: {TEXT_3}; }}
QPushButton[primary="true"] {{ background: {ACCENT}; color: #1a0b14; border: none; font-weight: 700; }}
QPushButton[primary="true"]:hover {{ background: #ff9ec6; }}
QPushButton[primary="true"]:disabled {{ background: {GROOVE}; color: {TEXT_3}; }}

QPushButton#SectionHeader {{ font-weight: 700; font-size: 10.5pt; text-align: left; padding: 8px 6px;
                             border: none; border-radius: 6px; background: transparent; }}
QPushButton#SectionHeader:hover {{ background: {PANEL_2}; }}
QToolButton#MiniButton {{ color: {TEXT_2}; padding: 2px 6px; border-radius: 6px; }}
QToolButton#MiniButton:hover {{ color: {TEXT}; }}

QScrollArea {{ background: transparent; border: none; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {GROOVE}; border-radius: 4px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: {TEXT_3}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: {GROOVE}; border-radius: 4px; min-width: 30px; }}

QAbstractSpinBox {{ background: {BG}; border: 1px solid {BORDER}; border-radius: 6px; padding: 2px 6px;
                    selection-background-color: {ACCENT}; min-width: 52px; }}
QAbstractSpinBox:focus {{ border-color: {ACCENT}; }}
QAbstractSpinBox:disabled {{ color: {TEXT_3}; }}

QComboBox {{ background: {BG}; border: 1px solid {BORDER}; border-radius: 6px; padding: 4px 8px; }}
QComboBox:hover {{ border-color: {ACCENT_2}; }}
QComboBox::drop-down {{ border: none; width: 18px; }}
QComboBox QAbstractItemView {{ background: {PANEL}; border: 1px solid {BORDER}; selection-background-color: {PANEL_2}; }}

QListWidget {{ background: transparent; border: none; outline: none; }}
QListWidget::item {{ border: 1px solid transparent; border-radius: 10px; padding: 4px; margin: 2px 4px; color: {TEXT}; }}
QListWidget::item:hover {{ background: {PANEL_2}; border-color: {BORDER}; }}
QListWidget::item:selected {{ background: rgba(255,126,179,0.16); border-color: {ACCENT}; color: #fff; }}
QListWidget#FileList {{ background: {BG}; border: 1px solid {BORDER}; border-radius: 8px; }}
QListWidget#FileList::item {{ margin: 0; padding: 4px 6px; border-radius: 4px; }}

QCheckBox {{ spacing: 8px; }}
QCheckBox::indicator {{ width: 16px; height: 16px; border-radius: 4px; border: 1px solid {TEXT_3}; background: {BG}; }}
QCheckBox::indicator:checked {{ background: {ACCENT}; border-color: {ACCENT}; }}

QProgressBar {{ background: {BG}; border: 1px solid {BORDER}; border-radius: 6px; text-align: center; height: 16px; }}
QProgressBar::chunk {{ background: {ACCENT}; border-radius: 5px; }}

QStatusBar {{ background: {BG}; border-top: 1px solid {BORDER}; color: {TEXT_2}; }}
QStatusBar QLabel {{ color: {TEXT_2}; padding: 0 8px; }}
QSplitter::handle {{ background: {BORDER}; }}
QSplitter::handle:horizontal {{ width: 1px; }}

QFrame#CropBar {{ background: rgba(20,23,38,0.94); border: 1px solid {BORDER}; border-radius: 12px; }}
QFrame#Card {{ background: {PANEL}; border: 1px solid {BORDER}; border-radius: 16px; }}
QTextBrowser {{ background: {PANEL}; border: 1px solid {BORDER}; border-radius: 10px; padding: 8px; }}
"""


class AppStyle(QProxyStyle):
    """Fusion, but a click on a slider jumps straight to that value (more intuitive)."""

    def styleHint(self, hint, option=None, widget=None, returnData=None):
        if hint == QStyle.StyleHint.SH_Slider_AbsoluteSetButtons:
            return int(Qt.MouseButton.LeftButton.value)
        return super().styleHint(hint, option, widget, returnData)


def make_app_icon() -> QIcon:
    pm = QPixmap(256, 256)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    bg = QRadialGradient(QPointF(128, 110), 150)
    bg.setColorAt(0, QColor("#232a55"))
    bg.setColorAt(1, QColor("#070914"))
    p.setBrush(bg)
    p.setPen(Qt.PenStyle.NoPen)
    p.drawRoundedRect(QRectF(8, 8, 240, 240), 56, 56)
    path = QPainterPath()
    cx, cy, r_out, r_in = 128.0, 128.0, 92.0, 22.0
    import math

    for i in range(8):
        r = r_out if i % 2 == 0 else r_in
        a = math.pi / 4 * i - math.pi / 2
        pt = QPointF(cx + r * math.cos(a), cy + r * math.sin(a))
        path.moveTo(pt) if i == 0 else path.lineTo(pt)
    path.closeSubpath()
    glow = QRadialGradient(QPointF(cx, cy), 70)
    glow.setColorAt(0, QColor(255, 255, 255))
    glow.setColorAt(0.35, QColor(ACCENT))
    glow.setColorAt(1, QColor(255, 126, 179, 120))
    p.setBrush(glow)
    p.drawPath(path)
    p.end()
    return QIcon(pm)


def apply_theme(app: QApplication) -> None:
    app.setStyle(AppStyle(QStyleFactory.create("Fusion")))
    pal = QPalette()
    for role, color in [
        (QPalette.ColorRole.Window, BG), (QPalette.ColorRole.WindowText, TEXT),
        (QPalette.ColorRole.Base, BG), (QPalette.ColorRole.AlternateBase, PANEL),
        (QPalette.ColorRole.Text, TEXT), (QPalette.ColorRole.Button, PANEL_2),
        (QPalette.ColorRole.ButtonText, TEXT), (QPalette.ColorRole.Highlight, ACCENT),
        (QPalette.ColorRole.HighlightedText, "#1a0b14"), (QPalette.ColorRole.ToolTipBase, PANEL_2),
        (QPalette.ColorRole.ToolTipText, TEXT), (QPalette.ColorRole.PlaceholderText, TEXT_3),
    ]:
        pal.setColor(role, QColor(color))
    pal.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor(TEXT_3))
    pal.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, QColor(TEXT_3))
    pal.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, QColor(TEXT_3))
    app.setPalette(pal)
    font = QFont()
    font.setFamilies(FONT_FAMILIES)
    font.setPointSizeF(10)
    app.setFont(font)
    app.setStyleSheet(QSS)
    app.setWindowIcon(make_app_icon())
