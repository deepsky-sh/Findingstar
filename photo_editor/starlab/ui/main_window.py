"""The main editor window."""

from __future__ import annotations

import json
import os

from PySide6.QtCore import QByteArray, QRectF, QSettings, Qt, QTimer, Slot
from PySide6.QtGui import QAction, QActionGroup, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .. import __version__
from ..document import Document
from ..imageio import bits_for_format, format_for_path, is_readable, load_image, open_dialog_filter, save_image
from ..processing.params import GEOMETRY_DEFAULTS, PARAM_SPECS, default_params, geometry_of
from ..processing.pipeline import render_frame, render_tiled
from ..processing.presets import PRESETS_BY_KEY, apply_preset
from ..sample import make_sample_sky
from .canvas import ImageCanvas
from .controls import AdjustPanel
from .help import GUIDE_HTML, SHORTCUTS_HTML, show_html
from .histogram import HistogramPanel
from .presets_panel import PresetPanel
from .qtutil import NoWheelComboBox, Task
from .render import PreviewResult, RenderController
from .stack_dialog import StackDialog
from .welcome import WelcomePage

APP_TITLE = "StarLab 천체 사진 편집기"
PREVIEW_SIZES = [("빠름 (1200px)", 1200), ("보통 (1800px)", 1800), ("선명 (2600px)", 2600)]
CROP_ASPECTS = [("자유 비율", None), ("원본 비율", "orig"), ("1 : 1", 1.0), ("4 : 3", 4 / 3),
                ("3 : 2", 3 / 2), ("16 : 9", 16 / 9), ("세로 4 : 5", 4 / 5), ("세로 9 : 16", 9 / 16)]


# ─────────────────────────── background jobs ───────────────────────────


def _load_document(path: str, preview_side: int) -> Document:
    loaded = load_image(path)
    doc = Document(loaded.data, os.path.basename(path), path, loaded.exif, loaded.icc, preview_side)
    doc.bit_depth, doc.note = loaded.bit_depth, loaded.note
    return doc


def _sample_document(preview_side: int) -> Document:
    return Document(make_sample_sky(), "예제 - 발광 성운.jpg", None, preview_side=preview_side)


def _array_document(image, name: str, preview_side: int, note: str = "") -> Document:
    doc = Document(image, name, None, preview_side=preview_side)
    doc.note = note
    return doc


def _export(doc: Document, params: dict, path: str, progress=None, cancelled=None) -> str | None:
    # Measure statistics on the preview exactly as the screen did, then render
    # full resolution in tiles with those numbers so the file matches the view.
    ctx: dict = {}
    render_frame(doc.frame("preview", params), params, doc.preview_scale, ctx)
    frame = doc.frame("full", params)
    bits = bits_for_format(format_for_path(path))
    pixels = render_tiled(frame, params, ctx, bits=bits,
                          progress=(lambda f: progress(f * 0.95, "")) if progress else None,
                          cancelled=cancelled)
    if pixels is None:
        return None
    if progress:
        progress(0.97, "")
    save_image(path, pixels, exif=doc.exif, icc=doc.icc)
    return path


# ─────────────────────────── helpers ───────────────────────────


class History:
    """Undo/redo over complete parameter snapshots (edits are non-destructive)."""

    def __init__(self, params: dict, limit: int = 200):
        self.items = [dict(params)]
        self.index = 0
        self.limit = limit

    def push(self, params: dict) -> bool:
        if params == self.items[self.index]:
            return False
        del self.items[self.index + 1:]
        self.items.append(dict(params))
        if len(self.items) > self.limit:
            self.items.pop(0)
        self.index = len(self.items) - 1
        return True

    def can_undo(self) -> bool:
        return self.index > 0

    def can_redo(self) -> bool:
        return self.index < len(self.items) - 1

    def undo(self) -> dict | None:
        if not self.can_undo():
            return None
        self.index -= 1
        return dict(self.items[self.index])

    def redo(self) -> dict | None:
        if not self.can_redo():
            return None
        self.index += 1
        return dict(self.items[self.index])


def _rotate_crop(crop, turn: str):
    """Transform a normalized crop box along with the picture."""
    if not crop:
        return crop
    x0, y0, x1, y1 = crop
    if turn == "ccw":
        box = (y0, 1 - x1, y1, 1 - x0)
    elif turn == "cw":
        box = (1 - y1, x0, 1 - y0, x1)
    elif turn == "flip_h":
        box = (1 - x1, y0, 1 - x0, y1)
    else:  # flip_v
        box = (x0, 1 - y1, x1, 1 - y0)
    return tuple(round(v, 6) for v in box)


class CropBar(QFrame):
    """Floating toolbar shown over the picture while cropping."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("CropBar")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 8, 10, 8)
        lay.setSpacing(8)
        tip = QLabel("✂  드래그해서 남길 영역을 고르세요")
        self.aspect = NoWheelComboBox()
        for text, _ in CROP_ASPECTS:
            self.aspect.addItem(text)
        self.reset = QPushButton("전체 선택")
        self.cancel = QPushButton("취소")
        self.apply = QPushButton("✔ 적용")
        self.apply.setProperty("primary", True)
        for w in (tip, self.aspect, self.reset, self.cancel, self.apply):
            lay.addWidget(w)
        self.adjustSize()


class CanvasHost(QWidget):
    """Holds the canvas and keeps floating overlays positioned on top of it."""

    def __init__(self, canvas: ImageCanvas, crop_bar: CropBar, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(canvas)
        self.crop_bar = crop_bar
        crop_bar.setParent(self)
        crop_bar.hide()

    def resizeEvent(self, event):  # noqa: N802
        super().resizeEvent(event)
        self.place_overlays()

    def place_overlays(self) -> None:
        bar = self.crop_bar
        bar.adjustSize()
        bar.move(max(8, (self.width() - bar.width()) // 2), 12)
        bar.raise_()


# ─────────────────────────── main window ───────────────────────────


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = QSettings("Findingstar", "StarLab")
        self.doc: Document | None = None
        self.params = default_params()
        self.history = History(self.params)
        self.crop_mode = False
        self._crop_ready = False
        self._busy = False
        self._last_result: PreviewResult | None = None
        self._export_task: Task | None = None
        self._loading_task: Task | None = None
        self.preview_side = int(self.settings.value("preview_side", 1800))

        self.render = RenderController(self)
        self.render.preview_ready.connect(self._on_preview_ready)
        self.render.detail_ready.connect(self._on_detail_ready)
        self.render.thumbs_ready.connect(self._on_thumbs_ready)
        self.render.busy_changed.connect(self._on_busy_changed)
        self.render.failed.connect(self._on_render_failed)

        self._commit_timer = QTimer(self, singleShot=True, interval=600)
        self._commit_timer.timeout.connect(self._commit)
        self._detail_timer = QTimer(self, singleShot=True, interval=160)
        self._detail_timer.timeout.connect(self._update_detail)

        self._build_ui()
        self._build_actions()
        self._build_menus()
        self._build_toolbar()
        self._update_enabled()
        self.setWindowTitle(APP_TITLE)
        self.resize(1440, 900)
        geo = self.settings.value("geometry")
        if isinstance(geo, QByteArray) and not geo.isEmpty():
            self.restoreGeometry(geo)

    # ─────────────────────────── construction ───────────────────────────

    def _build_ui(self) -> None:
        self.presets = PresetPanel()
        self.presets.preset_chosen.connect(self._apply_preset)

        self.canvas = ImageCanvas()
        self.canvas.hovered.connect(self._on_hover)
        self.canvas.view_changed.connect(self._on_view_changed)
        self.canvas.files_dropped.connect(self._on_files_dropped)
        self.crop_bar = CropBar()
        self.crop_bar.apply.clicked.connect(self._apply_crop)
        self.crop_bar.cancel.clicked.connect(lambda: self._exit_crop(apply=False))
        self.crop_bar.reset.clicked.connect(self._crop_select_all)
        self.crop_bar.aspect.currentIndexChanged.connect(self._crop_aspect_changed)
        self.canvas_host = CanvasHost(self.canvas, self.crop_bar)

        self.welcome = WelcomePage()
        self.welcome.open_clicked.connect(self.open_file)
        self.welcome.sample_clicked.connect(self.open_sample)
        self.welcome.stack_clicked.connect(self.open_stack_dialog)
        self.welcome.files_dropped.connect(self._on_files_dropped)

        self.center = QStackedWidget()
        self.center.addWidget(self.welcome)
        self.center.addWidget(self.canvas_host)

        right = QWidget()
        right.setObjectName("Panel")
        rl = QVBoxLayout(right)
        rl.setContentsMargins(10, 10, 2, 0)
        rl.setSpacing(6)
        head = QLabel("히스토그램")
        head.setObjectName("PanelTitle")
        rl.addWidget(head)
        self.hist = HistogramPanel()
        rl.addWidget(self.hist)
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("color: #262a40;")
        rl.addWidget(line)
        self.adjust = AdjustPanel()
        self.adjust.param_changed.connect(self._on_param_changed)
        self.adjust.edit_committed.connect(self._commit_soon)
        rl.addWidget(self.adjust, 1)
        right.setMinimumWidth(300)
        right.setMaximumWidth(420)
        self.right_panel = right

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.addWidget(self.presets)
        self.splitter.addWidget(self.center)
        self.splitter.addWidget(right)
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setStretchFactor(2, 0)
        self.splitter.setSizes([200, 900, 340])
        self.splitter.setChildrenCollapsible(False)
        state = self.settings.value("splitter")
        if isinstance(state, QByteArray) and not state.isEmpty():
            self.splitter.restoreState(state)
        self.setCentralWidget(self.splitter)

        sb = self.statusBar()
        self.pixel_label = QLabel("")
        self.size_label = QLabel("")
        self.zoom_label = QLabel("")
        self.state_label = QLabel("")
        for w in (self.pixel_label, self.size_label, self.zoom_label, self.state_label):
            sb.addPermanentWidget(w)
        sb.showMessage("사진을 열거나 끌어다 놓으세요.")

    def _act(self, text: str, slot, shortcut=None, tip: str = "", checkable: bool = False) -> QAction:
        act = QAction(text, self)
        if shortcut:
            seqs = shortcut if isinstance(shortcut, list) else [shortcut]
            act.setShortcuts([QKeySequence(s) for s in seqs])
        keys = act.shortcut().toString(QKeySequence.SequenceFormat.NativeText)
        act.setToolTip(f"{tip or text}" + (f"  ({keys})" if keys else ""))
        act.setStatusTip(tip)
        act.setCheckable(checkable)
        act.triggered.connect(slot)
        self.addAction(act)
        return act

    def _build_actions(self) -> None:
        a = self._act
        self.act_open = a("📂 열기", self.open_file, QKeySequence.StandardKey.Open, "사진 파일을 엽니다")
        self.act_sample = a("✨ 예제 사진", self.open_sample, tip="연습용 성운 사진을 엽니다")
        self.act_export = a("💾 저장", self.export_image, ["Ctrl+S", "Ctrl+Shift+S"],
                            "보정한 사진을 새 파일로 저장합니다")
        self.act_stack = a("🗂 스태킹", self.open_stack_dialog, tip="여러 장을 합쳐 노이즈를 줄입니다")
        self.act_undo = a("↶ 실행 취소", self.undo, QKeySequence.StandardKey.Undo, "마지막 변경을 되돌립니다")
        self.act_redo = a("↷ 다시 실행", self.redo, ["Ctrl+Shift+Z", "Ctrl+Y"], "되돌린 변경을 다시 적용합니다")
        self.act_reset = a("⟲ 모두 초기화", self.reset_all, tip="모든 보정·회전·자르기를 없애고 원본으로 돌아갑니다")
        self.act_compare = a("◧ 비교", self.toggle_compare, "C", "원본과 보정본을 나란히 비교합니다", checkable=True)
        self.act_fit = a("⤢ 맞춤", self.canvas.fit, "Ctrl+0", "사진 전체를 화면에 맞춥니다")
        self.act_100 = a("1:1", lambda: self.canvas.zoom_to(1.0), "Ctrl+1", "원본 크기(100%)로 봅니다")
        self.act_zoom_in = a("확대", lambda: self.canvas.zoom_by(1.25), ["Ctrl+=", "Ctrl++"], "확대")
        self.act_zoom_out = a("축소", lambda: self.canvas.zoom_by(0.8), "Ctrl+-", "축소")
        self.act_rot_l = a("↺ 왼쪽 회전", lambda: self.transform("ccw"), "Ctrl+[", "왼쪽으로 90° 회전")
        self.act_rot_r = a("↻ 오른쪽 회전", lambda: self.transform("cw"), "Ctrl+]", "오른쪽으로 90° 회전")
        self.act_flip_h = a("⇋ 좌우 반전", lambda: self.transform("flip_h"), tip="좌우로 뒤집습니다")
        self.act_flip_v = a("⇅ 상하 반전", lambda: self.transform("flip_v"), tip="위아래로 뒤집습니다")
        self.act_crop = a("✂ 자르기", self.toggle_crop, "R", "필요한 부분만 남기고 잘라냅니다", checkable=True)
        self.act_crop_apply = a("자르기 적용", self._apply_crop, ["Return", "Enter"])
        self.act_crop_cancel = a("자르기 취소", lambda: self._exit_crop(apply=False), "Esc")
        self.act_save_settings = a("편집 설정 내보내기…", self.save_settings_file,
                                   tip="현재 슬라이더 값을 파일로 저장해 다른 사진에 쓸 수 있습니다")
        self.act_load_settings = a("편집 설정 불러오기…", self.load_settings_file, tip="저장해 둔 편집 설정을 적용합니다")
        self.act_guide = a("❔ 가이드", lambda: show_html(self, "천체 사진 보정 가이드", GUIDE_HTML), "F1",
                           "천체 사진 보정 순서를 알려드려요")
        self.act_shortcuts = a("단축키", lambda: show_html(self, "단축키", SHORTCUTS_HTML), tip="단축키 목록")
        self.act_about = a("정보", self.show_about, tip="프로그램 정보")
        self.act_quit = a("종료", self.close, QKeySequence.StandardKey.Quit)

        self.preview_group = QActionGroup(self)
        self.preview_actions = []
        for text, side in PREVIEW_SIZES:
            act = QAction(text, self, checkable=True)
            act.setData(side)
            act.setChecked(side == self.preview_side)
            act.triggered.connect(self._preview_size_chosen)
            self.preview_group.addAction(act)
            self.preview_actions.append(act)

    def _build_menus(self) -> None:
        mb = self.menuBar()
        m = mb.addMenu("파일")
        for act in (self.act_open, self.act_sample, self.act_stack, None, self.act_export, None,
                    self.act_save_settings, self.act_load_settings, None, self.act_quit):
            m.addSeparator() if act is None else m.addAction(act)
        m = mb.addMenu("편집")
        for act in (self.act_undo, self.act_redo, None, self.act_reset, None, self.act_rot_l, self.act_rot_r,
                    self.act_flip_h, self.act_flip_v, self.act_crop):
            m.addSeparator() if act is None else m.addAction(act)
        m = mb.addMenu("보기")
        for act in (self.act_compare, None, self.act_fit, self.act_100, self.act_zoom_in, self.act_zoom_out):
            m.addSeparator() if act is None else m.addAction(act)
        m.addSeparator()
        pm = m.addMenu("미리보기 품질")
        for act in self.preview_actions:
            pm.addAction(act)
        m = mb.addMenu("도움말")
        for act in (self.act_guide, self.act_shortcuts, None, self.act_about):
            m.addSeparator() if act is None else m.addAction(act)

    def _build_toolbar(self) -> None:
        tb = self.addToolBar("도구")
        tb.setMovable(False)
        tb.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        for act in (self.act_open, self.act_export):
            tb.addAction(act)
        tb.addSeparator()
        tb.addAction(self.act_undo)
        tb.addAction(self.act_redo)
        tb.addSeparator()
        self.original_btn = QToolButton()
        self.original_btn.setText("👁 원본")
        self.original_btn.setToolTip("누르고 있는 동안 원본을 보여줍니다  (\\ 키)")
        self.original_btn.pressed.connect(lambda: self.canvas.set_show_original(True))
        self.original_btn.released.connect(lambda: self.canvas.set_show_original(False))
        tb.addWidget(self.original_btn)
        tb.addAction(self.act_compare)
        tb.addSeparator()
        tb.addAction(self.act_fit)
        tb.addAction(self.act_100)
        tb.addSeparator()
        for act in (self.act_rot_l, self.act_rot_r, self.act_flip_h, self.act_crop):
            tb.addAction(act)
        tb.addSeparator()
        tb.addAction(self.act_stack)
        tb.addAction(self.act_reset)
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        tb.addWidget(spacer)
        tb.addAction(self.act_guide)

    # ─────────────────────────── state helpers ───────────────────────────

    def _update_enabled(self) -> None:
        has = self.doc is not None
        editing = has and not self.crop_mode
        for act in (self.act_export, self.act_reset, self.act_compare, self.act_fit, self.act_100,
                    self.act_zoom_in, self.act_zoom_out, self.act_rot_l, self.act_rot_r, self.act_flip_h,
                    self.act_flip_v, self.act_save_settings, self.act_load_settings):
            act.setEnabled(editing)
        self.act_crop.setEnabled(has)
        self.act_crop_apply.setEnabled(self.crop_mode)
        self.act_crop_cancel.setEnabled(self.crop_mode)
        self.original_btn.setEnabled(editing)
        self.act_undo.setEnabled(editing and self.history.can_undo())
        self.act_redo.setEnabled(editing and self.history.can_redo())
        self.presets.setEnabled(editing)
        self.adjust.setEnabled(has)

    def _request_render(self) -> None:
        if self.doc is None:
            return
        self.canvas.clear_detail()
        self.render.request_preview(self.params, use_crop=not self.crop_mode)

    def _commit_soon(self) -> None:
        self._commit_timer.start(150)

    def _commit(self) -> None:
        self._commit_timer.stop()
        if self.history.push(self.params):
            self._update_enabled()

    def _set_params(self, params: dict, commit: bool = True) -> None:
        geometry_changed = geometry_of(params) != geometry_of(self.params)
        self.params = dict(params)
        self.adjust.set_params(self.params)
        self._request_render()
        if geometry_changed:
            self.render.request_thumbnails(self.params)
        if commit:
            self._commit()
        self._update_enabled()

    # ─────────────────────────── opening ───────────────────────────

    def open_file(self) -> None:
        start = self.settings.value("last_dir", os.path.expanduser("~"))
        path, _ = QFileDialog.getOpenFileName(self, "사진 열기", start, open_dialog_filter())
        if path:
            self.open_path(path)

    def open_path(self, path: str) -> None:
        if not os.path.isfile(path):
            QMessageBox.warning(self, "열 수 없음", f"파일을 찾을 수 없습니다:\n{path}")
            return
        if not is_readable(path):
            QMessageBox.warning(self, "지원하지 않는 형식",
                                f"이 형식은 열 수 없습니다:\n{os.path.basename(path)}\n\n"
                                "JPG, PNG, TIFF 등의 이미지를 사용해 주세요.")
            return
        self.settings.setValue("last_dir", os.path.dirname(path))
        self._start_loading(Task(_load_document, path, self.preview_side), os.path.basename(path))

    def open_sample(self) -> None:
        self._start_loading(Task(_sample_document, self.preview_side), "예제 사진")

    def _start_loading(self, task: Task, label: str) -> None:
        if self.crop_mode:
            self._exit_crop(apply=False)
        self.statusBar().showMessage(f"⏳ {label} 불러오는 중…")
        QApplication.setOverrideCursor(Qt.CursorShape.BusyCursor)
        task.signals.done.connect(self._on_loaded)
        task.signals.failed.connect(self._on_load_failed)
        self._loading_task = task.start()

    @Slot(object)
    def _on_loaded(self, doc: Document) -> None:
        QApplication.restoreOverrideCursor()
        self._loading_task = None
        self.set_document(doc)

    @Slot(str)
    def _on_load_failed(self, message: str) -> None:
        QApplication.restoreOverrideCursor()
        self._loading_task = None
        self.statusBar().showMessage("불러오기 실패", 5000)
        QMessageBox.warning(self, "사진을 열 수 없습니다", message)

    def set_document(self, doc: Document) -> None:
        self.doc = doc
        self._detail_params = None
        self._last_result = None
        self.render.set_document(doc)
        self.params = default_params()
        self.history = History(self.params)
        self.adjust.set_params(self.params)
        self.presets.set_current("original")
        self.presets.reset_thumbnails()
        self.canvas.clear()
        self.hist.set_data(None)
        self.adjust.verticalScrollBar().setValue(0)
        self.center.setCurrentWidget(self.canvas_host)
        self.setWindowTitle(f"{doc.name} — {APP_TITLE}")
        self.size_label.setText(f"{doc.width} × {doc.height} px")
        depth = f" ({doc.bit_depth}비트)" if doc.bit_depth > 8 else ""
        self.statusBar().showMessage(
            doc.note or f"불러옴: {doc.name}{depth}  ·  왼쪽 원클릭 필터나 오른쪽 슬라이더로 보정해 보세요", 10000)
        self._request_render()
        self.render.request_thumbnails(self.params)
        self._update_enabled()

    def _on_files_dropped(self, paths: list) -> None:
        images = [p for p in paths if is_readable(p)]
        if not images:
            QMessageBox.information(self, "열 수 없는 파일", "이미지 파일(JPG, PNG, TIFF 등)을 끌어다 놓아 주세요.")
            return
        if len(images) > 1:
            answer = QMessageBox.question(
                self, "여러 장을 놓으셨네요",
                f"{len(images)}장의 사진을 하나로 합성(스태킹)할까요?\n\n"
                "[예] 스태킹 창 열기   ·   [아니요] 첫 번째 사진만 열기")
            if answer == QMessageBox.StandardButton.Yes:
                self.open_stack_dialog(images)
                return
        self.open_path(images[0])

    def open_stack_dialog(self, paths: list | None = None) -> None:
        dlg = StackDialog(self, self.settings.value("last_dir", os.path.expanduser("~")))
        dlg.stacked.connect(self._on_stacked)
        if paths:
            dlg.add_paths(list(paths))
        dlg.exec()

    @Slot(object, str)
    def _on_stacked(self, image, name: str) -> None:
        hint = f"{name} 완료! 결과가 어둡다면 왼쪽의 ✨ 자동 천체 보정을 눌러보세요."
        self._start_loading(Task(_array_document, image, name, self.preview_side, hint), name)

    # ─────────────────────────── editing ───────────────────────────

    def _on_param_changed(self, key: str, value) -> None:
        self.params[key] = value
        self._request_render()
        self._commit_timer.start()
        self._update_enabled()

    def _apply_preset(self, key: str) -> None:
        if self.doc is None:
            return
        preset = PRESETS_BY_KEY[key]
        self._set_params(apply_preset(preset, self.params))
        self.presets.set_current(key)
        self.statusBar().showMessage(f"{preset.name} 적용 — {preset.description}", 6000)

    def reset_all(self) -> None:
        self._set_params(default_params())
        self.presets.set_current("original")
        self.statusBar().showMessage("원본 상태로 되돌렸습니다. (실행 취소로 복구할 수 있어요)", 5000)

    def undo(self) -> None:
        params = self.history.undo()
        if params is not None:
            self._set_params(params, commit=False)
            self.statusBar().showMessage("실행 취소", 2000)

    def redo(self) -> None:
        params = self.history.redo()
        if params is not None:
            self._set_params(params, commit=False)
            self.statusBar().showMessage("다시 실행", 2000)

    def transform(self, turn: str) -> None:
        if self.doc is None or self.crop_mode:
            return
        p = dict(self.params)
        flipped = bool(p["flip_h"])
        # The pipeline rotates first, then mirrors; a rotation applied after a
        # mirror equals the mirror after the opposite rotation.
        if turn == "ccw":
            p["rotation"] = (p["rotation"] + (-1 if flipped else 1)) % 4
        elif turn == "cw":
            p["rotation"] = (p["rotation"] + (1 if flipped else -1)) % 4
        elif turn == "flip_h":
            p["flip_h"] = not flipped
        else:
            p["flip_h"] = not flipped
            p["rotation"] = (p["rotation"] + 2) % 4
        p["crop"] = _rotate_crop(p["crop"], turn)
        self._set_params(p)

    def toggle_compare(self, on: bool) -> None:
        self.canvas.set_compare(on)

    # ─────────────────────────── crop ───────────────────────────

    def toggle_crop(self, on: bool) -> None:
        if on:
            self._enter_crop()
        else:
            self._apply_crop()

    def _enter_crop(self) -> None:
        if self.doc is None or self.crop_mode:
            return
        self.crop_mode = True
        self._crop_ready = False
        self.act_crop.setChecked(True)
        self.act_compare.setChecked(False)
        self.canvas.set_compare(False)
        self.crop_bar.aspect.blockSignals(True)
        self.crop_bar.aspect.setCurrentIndex(0)
        self.crop_bar.aspect.blockSignals(False)
        self.crop_bar.show()
        self.canvas_host.place_overlays()
        self._request_render()
        self._update_enabled()

    def _begin_crop_editing(self, result: PreviewResult) -> None:
        w, h = result.world_size
        crop = self.params["crop"]
        rect = QRectF(crop[0] * w, crop[1] * h, (crop[2] - crop[0]) * w, (crop[3] - crop[1]) * h) \
            if crop else QRectF(0, 0, w, h)
        self.canvas.set_crop_aspect(None)
        self.canvas.set_crop_mode(True, rect)
        self._crop_ready = True

    def _crop_aspect_changed(self, index: int) -> None:
        aspect = CROP_ASPECTS[index][1]
        if aspect == "orig" and self.doc is not None:
            w, h = self.doc.frame_size(self.params, use_crop=False)
            aspect = w / h
        self.canvas.set_crop_aspect(aspect)

    def _crop_select_all(self) -> None:
        if self._last_result is not None:
            w, h = self._last_result.world_size
            self.crop_bar.aspect.setCurrentIndex(0)
            self.canvas.set_crop_rect(QRectF(0, 0, w, h))

    def _apply_crop(self) -> None:
        self._exit_crop(apply=True)

    def _exit_crop(self, apply: bool) -> None:
        if not self.crop_mode:
            return
        new_crop = self.params["crop"]
        if apply and self._crop_ready and self.doc is not None:
            w, h = self.doc.frame_size(self.params, use_crop=False)
            r = self.canvas.crop_rect().normalized()
            box = (r.left() / w, r.top() / h, r.right() / w, r.bottom() / h)
            box = tuple(round(min(max(v, 0.0), 1.0), 6) for v in box)
            full = box[0] <= 0.002 and box[1] <= 0.002 and box[2] >= 0.998 and box[3] >= 0.998
            new_crop = None if full else box
        self.crop_mode = False
        self._crop_ready = False
        self.canvas.set_crop_mode(False)
        self.crop_bar.hide()
        self.act_crop.setChecked(False)
        p = dict(self.params)
        p["crop"] = new_crop
        if p != self.params:
            self._set_params(p)
        else:
            self._request_render()
        self._update_enabled()

    # ─────────────────────────── render results ───────────────────────────

    @Slot(object)
    def _on_preview_ready(self, result: PreviewResult) -> None:
        self._last_result = result
        self.canvas.set_images(result.proc, result.orig, *result.world_size)
        self.hist.set_data(result.hist)
        if self.crop_mode and not self._crop_ready and not result.use_crop:
            self._begin_crop_editing(result)
        w, h = result.world_size
        self.size_label.setText(f"{w} × {h} px")
        self._update_zoom_label()
        if not result.draft:
            self.state_label.setText(f"✓ 준비됨 · {result.elapsed * 1000:.0f} ms")
            self._detail_timer.start()

    @Slot(bool)
    def _on_busy_changed(self, busy: bool) -> None:
        self._busy = busy
        if busy:
            self.state_label.setText("⏳ 처리 중…")

    @Slot(str)
    def _on_render_failed(self, message: str) -> None:
        self.statusBar().showMessage(f"처리 중 오류: {message}", 8000)

    @Slot(object)
    def _on_thumbs_ready(self, thumbs: dict) -> None:
        self.presets.set_thumbnails(thumbs)

    def _on_view_changed(self) -> None:
        self._update_zoom_label()
        self._detail_timer.start()

    def _update_zoom_label(self) -> None:
        if self.canvas.has_image():
            self.zoom_label.setText(f"🔍 {self.canvas.zoom() * 100:.0f}%")

    def _update_detail(self) -> None:
        """Past the preview's resolution, render what is visible from the full-size source."""
        if self.doc is None or self.crop_mode or not self.canvas.has_image():
            return
        if self.doc.preview_scale >= 0.999 or self.canvas.zoom() <= self.canvas.preview_density() * 1.15:
            # The preview already holds every pixel, or is sharp enough at this zoom.
            self.canvas.clear_detail()
            return
        vis = self.canvas.visible_world_rect()
        if vis.isEmpty():
            return
        current = self.canvas.detail_rect()
        if current is not None and current.contains(vis) and self._detail_params == self.params:
            return
        pad_w, pad_h = vis.width() * 0.1, vis.height() * 0.1
        w, h = self._last_result.world_size if self._last_result else (0, 0)
        x0, y0 = max(0, int(vis.left() - pad_w)), max(0, int(vis.top() - pad_h))
        x1, y1 = min(w, int(vis.right() + pad_w) + 1), min(h, int(vis.bottom() + pad_h) + 1)
        if x1 - x0 < 2 or y1 - y0 < 2 or (x1 - x0) * (y1 - y0) > 16_000_000:
            return
        self.render.request_detail(self.params, True, (x0, y0, x1, y1))

    _detail_params: dict | None = None

    @Slot(object)
    def _on_detail_ready(self, result) -> None:
        if result.params != self.params or self.crop_mode:
            return
        x0, y0, x1, y1 = result.box
        self._detail_params = result.params
        self.canvas.set_detail(QRectF(x0, y0, x1 - x0, y1 - y0), result.proc, result.orig)

    def _on_hover(self, x: float, y: float) -> None:
        res = self._last_result
        if x < 0 or res is None:
            self.pixel_label.setText("")
            return
        w, h = res.world_size
        px = min(int(x * res.proc.width() / w), res.proc.width() - 1)
        py = min(int(y * res.proc.height() / h), res.proc.height() - 1)
        c = res.proc.pixelColor(px, py)
        self.pixel_label.setText(f"X {int(x)}  Y {int(y)}   R {c.red()}  G {c.green()}  B {c.blue()}")

    # ─────────────────────────── saving ───────────────────────────

    def export_image(self) -> None:
        if self.doc is None or self._export_task is not None:
            return
        if self.crop_mode:
            self._exit_crop(apply=True)
        self._commit()
        start_dir = self.settings.value("export_dir") or (
            os.path.dirname(self.doc.path) if self.doc.path else self.settings.value("last_dir", os.path.expanduser("~")))
        stem = os.path.splitext(self.doc.name)[0]
        filters = ["JPEG 이미지 — 공유용 (*.jpg)", "PNG 이미지 — 무손실 (*.png)", "TIFF 16비트 — 추가 보정용 (*.tif)"]
        path, chosen = QFileDialog.getSaveFileName(self, "보정한 사진 저장", os.path.join(start_dir, f"{stem}_starlab.jpg"),
                                                   ";;".join(filters))
        if not path:
            return
        ext = os.path.splitext(path)[1].lower()
        if ext not in (".jpg", ".jpeg", ".png", ".tif", ".tiff"):
            path += {0: ".jpg", 1: ".png", 2: ".tif"}.get(filters.index(chosen) if chosen in filters else 0)
        if self.doc.path and os.path.abspath(path) == os.path.abspath(self.doc.path):
            QMessageBox.warning(self, "원본 보호", "원본 파일은 덮어쓸 수 없어요. 다른 이름으로 저장해 주세요.")
            return
        self.settings.setValue("export_dir", os.path.dirname(path))

        dlg = QProgressDialog("원본 해상도로 보정해서 저장하는 중…", "취소", 0, 1000, self)
        dlg.setWindowTitle("저장")
        dlg.setWindowModality(Qt.WindowModality.WindowModal)
        dlg.setMinimumDuration(0)
        dlg.setValue(0)
        self._export_dialog = dlg
        task = Task(_export, self.doc, dict(self.params), path, progress=True)
        task.signals.progress.connect(self._on_export_progress)
        task.signals.done.connect(self._on_export_done)
        task.signals.failed.connect(self._on_export_failed)
        dlg.canceled.connect(task.cancel)
        self._export_task = task.start()

    @Slot(float, str)
    def _on_export_progress(self, frac: float, _text: str) -> None:
        if self._export_dialog is not None:
            self._export_dialog.setValue(int(frac * 1000))

    def _close_export_dialog(self) -> None:
        self._export_task = None
        if self._export_dialog is not None:
            self._export_dialog.reset()
            self._export_dialog.deleteLater()
            self._export_dialog = None

    @Slot(object)
    def _on_export_done(self, path) -> None:
        self._close_export_dialog()
        if path is None:
            self.statusBar().showMessage("저장을 취소했습니다.", 4000)
            return
        self.statusBar().showMessage(f"💾 저장 완료: {path}", 10000)
        QMessageBox.information(self, "저장 완료", f"보정한 사진을 저장했습니다.\n\n{path}")

    @Slot(str)
    def _on_export_failed(self, message: str) -> None:
        self._close_export_dialog()
        QMessageBox.warning(self, "저장 실패", message)

    _export_dialog: QProgressDialog | None = None

    # ─────────────────────────── settings files ───────────────────────────

    def save_settings_file(self) -> None:
        start = self.settings.value("last_dir", os.path.expanduser("~"))
        path, _ = QFileDialog.getSaveFileName(self, "편집 설정 내보내기", os.path.join(start, "편집설정.starlab.json"),
                                              "StarLab 편집 설정 (*.json)")
        if not path:
            return
        data = {k: v for k, v in self.params.items() if k not in GEOMETRY_DEFAULTS}
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"app": "StarLab", "version": __version__, "params": data}, f, ensure_ascii=False, indent=2)
        self.statusBar().showMessage(f"편집 설정을 저장했습니다: {path}", 6000)

    def load_settings_file(self) -> None:
        start = self.settings.value("last_dir", os.path.expanduser("~"))
        path, _ = QFileDialog.getOpenFileName(self, "편집 설정 불러오기", start, "StarLab 편집 설정 (*.json)")
        if not path:
            return
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f).get("params", {})
        except (OSError, ValueError, AttributeError) as exc:
            QMessageBox.warning(self, "불러오기 실패", f"설정 파일을 읽을 수 없습니다.\n{exc}")
            return
        p = dict(self.params)
        valid = {s.key: s for s in PARAM_SPECS}
        for key, value in data.items():
            spec = valid.get(key)
            if spec is None:
                continue
            if spec.is_choice:
                if value in [c[0] for c in spec.choices]:
                    p[key] = value
            elif isinstance(value, (int, float)) and not isinstance(value, bool):
                value = min(max(value, spec.minimum), spec.maximum)
                p[key] = round(float(value), spec.decimals) if spec.decimals else int(round(value))
        self._set_params(p)
        self.presets.set_current(None)
        self.statusBar().showMessage("편집 설정을 적용했습니다.", 5000)

    # ─────────────────────────── misc ───────────────────────────

    def _preview_size_chosen(self) -> None:
        act = self.preview_group.checkedAction()
        side = int(act.data())
        if side == self.preview_side:
            return
        self.preview_side = side
        self.settings.setValue("preview_side", side)
        if self.doc is not None:
            QApplication.setOverrideCursor(Qt.CursorShape.BusyCursor)
            try:
                self.doc.set_preview_side(side)
            finally:
                QApplication.restoreOverrideCursor()
            self.canvas.clear_detail()
            self._request_render()

    def show_about(self) -> None:
        QMessageBox.about(
            self, "StarLab 정보",
            f"<h3>StarLab 천체 사진 편집기 {__version__}</h3>"
            "<p>Findingstar 프로젝트의 파이썬 사진 편집기입니다.</p>"
            "<p>광해 제거 · 배경 중화 · 스트레치 · SCNR · 별 줄이기 · 스태킹 등<br>"
            "천체 사진을 위한 필터를 제공합니다.</p>"
            "<p style='color:#9da3c7'>PySide6 · NumPy · SciPy · Pillow</p>")

    def keyPressEvent(self, event):  # noqa: N802
        if event.key() == Qt.Key.Key_Backslash and not event.isAutoRepeat() and self.doc is not None:
            self.canvas.set_show_original(True)
            return
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event):  # noqa: N802
        if event.key() == Qt.Key.Key_Backslash and not event.isAutoRepeat():
            self.canvas.set_show_original(False)
            return
        super().keyReleaseEvent(event)

    def closeEvent(self, event):  # noqa: N802
        if self._export_task is not None:
            answer = QMessageBox.question(self, "저장 중", "아직 저장 중입니다. 그래도 종료할까요?")
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            self._export_task.cancel()
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("splitter", self.splitter.saveState())
        super().closeEvent(event)
