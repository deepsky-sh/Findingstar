"""Dialog for stacking several exposures into one image."""

from __future__ import annotations

import os

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

from ..imageio import is_readable, load_image, open_dialog_filter
from ..processing.stacking import StackCancelled, stack_images
from .qtutil import NoWheelComboBox, Task

METHOD_ITEMS = [
    ("mean", "평균 — 노이즈 감소 (추천)",
     "모든 사진의 평균을 냅니다. 장수가 많을수록 노이즈가 매끄럽게 줄어듭니다."),
    ("median", "중앙값 — 비행기·위성 궤적 제거",
     "한두 장에만 찍힌 비행기·위성 줄무늬를 지웁니다. (사진 3장 이상 권장)"),
    ("sigma", "시그마 클리핑 — 노이즈 감소 + 궤적 제거",
     "튀는 값을 빼고 평균을 냅니다. 품질이 가장 좋지만 느립니다. (5장 이상 권장)"),
    ("max", "최대값 — 별 궤적 만들기",
     "각 위치의 가장 밝은 값을 남겨 별의 움직임을 궤적으로 이어 붙입니다.\n(정렬은 끄세요)"),
]


def _load_for_stack(path: str):
    return load_image(path).data


class DropList(QListWidget):
    """File list that accepts files dragged in from the desktop."""

    files_dropped = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.viewport().setAcceptDrops(True)
        self.setDragDropMode(QListWidget.DragDropMode.DropOnly)

    def dragEnterEvent(self, event):  # noqa: N802
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dragMoveEvent(self, event):  # noqa: N802
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):  # noqa: N802
        paths = [u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()]
        if paths:
            self.files_dropped.emit(paths)
            event.acceptProposedAction()


class StackDialog(QDialog):
    stacked = Signal(object, str)  # (float32 image, name)

    def __init__(self, parent=None, start_dir: str = ""):
        super().__init__(parent)
        self.setWindowTitle("여러 장 합성 (스태킹)")
        self.setMinimumSize(560, 520)
        self._start_dir = start_dir
        self._task: Task | None = None

        lay = QVBoxLayout(self)
        lay.setSpacing(10)
        intro = QLabel("같은 하늘을 연속으로 찍은 사진 여러 장을 합쳐 노이즈가 적은 한 장을 만듭니다.\n"
                       "사진을 목록에 끌어다 놓거나 [사진 추가]를 누르세요.")
        intro.setObjectName("Muted")
        intro.setWordWrap(True)
        lay.addWidget(intro)

        self.files = DropList()
        self.files.setObjectName("FileList")
        self.files.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.files.files_dropped.connect(self.add_paths)
        lay.addWidget(self.files, 1)

        row = QHBoxLayout()
        add = QPushButton("＋ 사진 추가")
        add.clicked.connect(self._add_files)
        remove = QPushButton("선택 삭제")
        remove.clicked.connect(self._remove_selected)
        clear = QPushButton("모두 비우기")
        clear.clicked.connect(self.files.clear)
        self.count = QLabel("0장")
        self.count.setObjectName("Muted")
        row.addWidget(add)
        row.addWidget(remove)
        row.addWidget(clear)
        row.addStretch(1)
        row.addWidget(self.count)
        lay.addLayout(row)
        self.files.model().rowsInserted.connect(self._update_count)
        self.files.model().rowsRemoved.connect(self._update_count)
        self.files.model().modelReset.connect(self._update_count)

        self.method = NoWheelComboBox()
        for key, text, _tip in METHOD_ITEMS:
            self.method.addItem(text, key)
        self.method.currentIndexChanged.connect(self._method_changed)
        self.method_help = QLabel()
        self.method_help.setObjectName("Dim")
        self.method_help.setWordWrap(True)
        lay.addWidget(QLabel("합성 방식"))
        lay.addWidget(self.method)
        lay.addWidget(self.method_help)

        self.align = QCheckBox("별 위치 자동 정렬 (사진끼리 조금씩 어긋난 경우)")
        self.align.setChecked(True)
        self.align.setToolTip("별을 기준으로 사진을 위아래·좌우로 맞춥니다.\n"
                              "적도의(추적 장비)나 짧은 연속 촬영에 적합하며, 회전은 보정하지 않습니다.")
        lay.addWidget(self.align)

        self.progress = QProgressBar()
        self.progress.setRange(0, 1000)
        self.progress.setVisible(False)
        self.status = QLabel("")
        self.status.setObjectName("Muted")
        lay.addWidget(self.progress)
        lay.addWidget(self.status)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self.cancel_btn = QPushButton("닫기")
        self.cancel_btn.clicked.connect(self._cancel_or_close)
        self.run_btn = QPushButton("합성 시작")
        self.run_btn.setProperty("primary", True)
        self.run_btn.clicked.connect(self._run)
        buttons.addWidget(self.cancel_btn)
        buttons.addWidget(self.run_btn)
        lay.addLayout(buttons)
        self._method_changed(0)
        self._update_count()

    # file list ----------------------------------------------------------

    def add_paths(self, paths: list[str]) -> None:
        existing = {self.files.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.files.count())}
        for path in sorted(paths):
            if is_readable(path) and path not in existing:
                item = QListWidgetItem(os.path.basename(path))
                item.setData(Qt.ItemDataRole.UserRole, path)
                item.setToolTip(path)
                self.files.addItem(item)

    def _add_files(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(self, "합성할 사진 선택", self._start_dir, open_dialog_filter())
        if paths:
            self._start_dir = os.path.dirname(paths[0])
            self.add_paths(paths)

    def _remove_selected(self) -> None:
        for item in self.files.selectedItems():
            self.files.takeItem(self.files.row(item))

    def _update_count(self, *args) -> None:
        n = self.files.count()
        self.count.setText(f"{n}장")
        self.run_btn.setEnabled(n >= 2 and self._task is None)

    def _method_changed(self, index: int) -> None:
        key, _text, tip = METHOD_ITEMS[index]
        self.method_help.setText(tip)
        self.align.setChecked(key != "max")

    # running ------------------------------------------------------------

    def _run(self) -> None:
        paths = [self.files.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.files.count())]
        method = self.method.currentData()
        self.progress.setValue(0)
        self.progress.setVisible(True)
        self.run_btn.setEnabled(False)
        self.cancel_btn.setText("취소")
        task = Task(stack_images, _load_for_stack, paths, method, self.align.isChecked(), progress=True)
        task.signals.progress.connect(self._on_progress)
        task.signals.done.connect(self._on_done)
        task.signals.failed.connect(self._on_failed)
        self._task = task.start()
        self._n = len(paths)

    @Slot(float, str)
    def _on_progress(self, frac: float, text: str) -> None:
        self.progress.setValue(int(frac * 1000))
        self.status.setText(text)

    @Slot(object)
    def _on_done(self, image) -> None:
        self._task = None
        self.stacked.emit(image, f"스태킹 결과 ({self._n}장)")
        self.accept()

    @Slot(str)
    def _on_failed(self, message: str) -> None:
        self._task = None
        self.progress.setVisible(False)
        self.cancel_btn.setText("닫기")
        self._update_count()
        if StackCancelled.__name__ in message:
            self.status.setText("취소했습니다.")
            return
        self.status.setText("")
        QMessageBox.warning(self, "합성 실패", message.split(":", 1)[-1].strip() or message)

    def _cancel_or_close(self) -> None:
        if self._task is not None:
            self._task.cancel()
            self.status.setText("취소하는 중…")
        else:
            self.reject()

    def closeEvent(self, event):  # noqa: N802
        if self._task is not None:
            self._task.cancel()
        super().closeEvent(event)
