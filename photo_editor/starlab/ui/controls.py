"""The adjustment panel: collapsible sections of labelled sliders built from PARAM_SPECS."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QStyle,
    QStyleOptionSlider,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ..processing.params import DEFAULTS, PARAM_SPECS, SECTIONS, ParamSpec
from . import theme
from .qtutil import NoWheelComboBox, NoWheelDoubleSpinBox, NoWheelMixin, NoWheelSpinBox


class StarSlider(NoWheelMixin, QSlider):
    """A slim slider whose fill starts at zero, so ± adjustments read at a glance."""

    reset_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(Qt.Orientation.Horizontal, parent)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMinimumHeight(22)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mouseDoubleClickEvent(self, event):  # noqa: N802
        self.reset_requested.emit()

    def _handle_x(self, value: int) -> float:
        opt = QStyleOptionSlider()
        self.initStyleOption(opt)
        handle = self.style().subControlRect(QStyle.ComplexControl.CC_Slider, opt,
                                             QStyle.SubControl.SC_SliderHandle, self)
        span = self.width() - handle.width()
        pos = QStyle.sliderPositionFromValue(self.minimum(), self.maximum(), value, span)
        return pos + handle.width() / 2

    def paintEvent(self, _event):  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        cy = self.height() / 2
        left, right = self._handle_x(self.minimum()), self._handle_x(self.maximum())
        enabled = self.isEnabled()
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(theme.GROOVE))
        p.drawRoundedRect(QRectF(left - 3, cy - 2, right - left + 6, 4), 2, 2)
        origin = self._handle_x(min(max(0, self.minimum()), self.maximum()))
        hx = self._handle_x(self.value())
        accent = QColor(theme.ACCENT if enabled else theme.TEXT_3)
        p.setBrush(accent)
        p.drawRoundedRect(QRectF(min(origin, hx), cy - 2, abs(hx - origin), 4), 2, 2)
        if self.minimum() < 0 < self.maximum():
            p.setBrush(QColor(theme.TEXT_3))
            p.drawRect(QRectF(origin - 0.75, cy - 6, 1.5, 12))
        p.setPen(QPen(QColor(theme.BG), 2))
        p.setBrush(QColor("#ffffff") if enabled else QColor(theme.TEXT_3))
        radius = 8 if (self.hasFocus() or self.isSliderDown()) else 7
        p.drawEllipse(QPointF(hx, cy), radius, radius)
        if self.hasFocus():
            p.setPen(QPen(accent, 1.5))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QPointF(hx, cy), radius + 3, radius + 3)


class ParamRow(QWidget):
    """Label + value box on one line, slider (or combo box) underneath."""

    changed = Signal(str, object)
    committed = Signal()

    def __init__(self, spec: ParamSpec, parent=None):
        super().__init__(parent)
        self.spec = spec
        self._mult = round(1 / spec.step) if spec.step < 1 else 1
        grid = QGridLayout(self)
        grid.setContentsMargins(6, 2, 6, 4)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(0)
        self.label = QLabel(spec.label)
        self.label.setObjectName("ParamLabel")
        self.label.setToolTip(spec.tooltip + "\n\n(더블클릭하면 기본값으로 되돌립니다)")
        self.label.installEventFilter(self)
        grid.addWidget(self.label, 0, 0)
        self.combo = self.slider = self.spin = None
        if spec.is_choice:
            self.combo = NoWheelComboBox()
            for value, text in spec.choices:
                self.combo.addItem(text, value)
            self.combo.setToolTip(spec.tooltip)
            self.combo.currentIndexChanged.connect(self._combo_changed)
            grid.addWidget(self.combo, 1, 0, 1, 2)
        else:
            if spec.decimals:
                self.spin = NoWheelDoubleSpinBox()
                self.spin.setDecimals(spec.decimals)
                self.spin.setSingleStep(spec.step)
            else:
                self.spin = NoWheelSpinBox()
            self.spin.setRange(spec.minimum, spec.maximum)
            self.spin.setButtonSymbols(NoWheelSpinBox.ButtonSymbols.NoButtons)
            self.spin.setAlignment(Qt.AlignmentFlag.AlignRight)
            self.spin.setKeyboardTracking(False)
            self.spin.setSuffix(spec.suffix)
            self.spin.setFixedWidth(64 if not spec.suffix else 76)
            self.spin.valueChanged.connect(self._spin_changed)
            self.spin.editingFinished.connect(self.committed)
            grid.addWidget(self.spin, 0, 1, Qt.AlignmentFlag.AlignRight)
            self.slider = StarSlider()
            self.slider.setRange(round(spec.minimum * self._mult), round(spec.maximum * self._mult))
            self.slider.setToolTip(spec.tooltip)
            self.slider.valueChanged.connect(self._slider_changed)
            self.slider.sliderReleased.connect(self.committed)
            self.slider.reset_requested.connect(self.reset)
            grid.addWidget(self.slider, 1, 0, 1, 2)
        self._value = DEFAULTS[spec.key]
        self._sync_widgets()

    # value plumbing ---------------------------------------------------

    def value(self):
        return self._value

    def set_value(self, value, emit: bool = False) -> None:
        if self.spec.is_choice:
            value = str(value)
        else:
            value = round(float(value), self.spec.decimals) if self.spec.decimals else int(round(float(value)))
        changed = value != self._value
        self._value = value
        self._sync_widgets()
        if emit and changed:
            self.changed.emit(self.spec.key, value)

    def reset(self) -> None:
        self.set_value(DEFAULTS[self.spec.key], emit=True)
        self.committed.emit()

    def _sync_widgets(self) -> None:
        if self.combo is not None:
            self.combo.blockSignals(True)
            self.combo.setCurrentIndex(max(0, self.combo.findData(self._value)))
            self.combo.blockSignals(False)
        else:
            self.spin.blockSignals(True)
            self.spin.setValue(self._value)
            self.spin.blockSignals(False)
            self.slider.blockSignals(True)
            self.slider.setValue(round(self._value * self._mult))
            self.slider.blockSignals(False)
        modified = self._value != DEFAULTS[self.spec.key]
        if self.label.property("modified") != modified:
            self.label.setProperty("modified", modified)
            self.label.style().unpolish(self.label)
            self.label.style().polish(self.label)

    def _slider_changed(self, v: int) -> None:
        self.set_value(v / self._mult, emit=True)
        if not self.slider.isSliderDown():
            self.committed.emit()  # keyboard or click-to-jump

    def _spin_changed(self, v) -> None:
        self.set_value(v, emit=True)

    def _combo_changed(self, _index: int) -> None:
        self.set_value(self.combo.currentData(), emit=True)
        self.committed.emit()

    def eventFilter(self, obj, event):  # noqa: N802
        if obj is self.label and event.type() == QEvent.Type.MouseButtonDblClick:
            self.reset()
            return True
        return super().eventFilter(obj, event)


class Section(QWidget):
    """A collapsible group with a header and a reset button."""

    reset_clicked = Signal(str)

    def __init__(self, key: str, title: str, parent=None):
        super().__init__(parent)
        self.key = key
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 6)
        lay.setSpacing(0)
        head = QHBoxLayout()
        head.setContentsMargins(0, 0, 0, 0)
        self.toggle = QPushButton()
        self.toggle.setObjectName("SectionHeader")
        self.toggle.setCheckable(True)
        self.toggle.setChecked(True)
        self.toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._title = title
        self.toggle.toggled.connect(self._on_toggle)
        self.badge = QLabel("")
        self.badge.setObjectName("Muted")
        reset = QToolButton()
        reset.setObjectName("MiniButton")
        reset.setText("↺ 초기화")
        reset.setToolTip("이 영역의 값을 모두 기본값으로 되돌립니다")
        reset.clicked.connect(lambda: self.reset_clicked.emit(self.key))
        head.addWidget(self.toggle, 1)
        head.addWidget(self.badge)
        head.addWidget(reset)
        lay.addLayout(head)
        self.body = QWidget()
        self.body_lay = QVBoxLayout(self.body)
        self.body_lay.setContentsMargins(0, 0, 0, 0)
        self.body_lay.setSpacing(2)
        lay.addWidget(self.body)
        self._on_toggle(True)

    def _on_toggle(self, open_: bool) -> None:
        self.body.setVisible(open_)
        self.toggle.setText(("▾  " if open_ else "▸  ") + self._title)

    def set_modified_count(self, n: int) -> None:
        self.badge.setText(f"{n}개 적용 " if n else "")


class AdjustPanel(QScrollArea):
    param_changed = Signal(str, object)
    edit_committed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inner = QWidget()
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(4, 0, 8, 12)
        lay.setSpacing(4)
        self.rows: dict[str, ParamRow] = {}
        self.sections: dict[str, Section] = {}
        for key, title in SECTIONS:
            sec = Section(key, title)
            sec.reset_clicked.connect(self._reset_section)
            self.sections[key] = sec
            lay.addWidget(sec)
        for spec in PARAM_SPECS:
            row = ParamRow(spec)
            row.changed.connect(self._row_changed)
            row.committed.connect(self.edit_committed)
            self.rows[spec.key] = row
            self.sections[spec.section].body_lay.addWidget(row)
        lay.addStretch(1)
        self.setWidget(inner)
        self._update_states()

    def set_params(self, params: dict) -> None:
        for key, row in self.rows.items():
            row.set_value(params[key], emit=False)
        self._update_states()

    def _row_changed(self, key: str, value) -> None:
        self._update_states()
        self.param_changed.emit(key, value)

    def _reset_section(self, section: str) -> None:
        for row in self.rows.values():
            if row.spec.section == section:
                row.set_value(DEFAULTS[row.spec.key], emit=True)
        self.edit_committed.emit()

    def _update_states(self) -> None:
        # Sub-options only make sense while their parent filter is on.
        self.rows["bg_degree"].setEnabled(bool(self.rows["bg_remove"].value()))
        self.rows["stretch"].setEnabled(self.rows["stretch_mode"].value() != "none")
        for key, sec in self.sections.items():
            n = sum(1 for r in self.rows.values()
                    if r.spec.section == key and r.value() != DEFAULTS[r.spec.key]
                    and r.spec.key not in ("bg_degree", "stretch"))
            sec.set_modified_count(n)
