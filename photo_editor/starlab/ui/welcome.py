"""The start screen shown before a photo is opened."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QApplication, QFrame, QLabel, QPushButton, QVBoxLayout, QWidget

from ..imageio import format_summary


class WelcomePage(QWidget):
    open_clicked = Signal()
    sample_clicked = Signal()
    stack_clicked = Signal()
    files_dropped = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        outer = QVBoxLayout(self)
        outer.setAlignment(Qt.AlignmentFlag.AlignCenter)

        card = QFrame()
        card.setObjectName("Card")
        card.setMaximumWidth(520)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(40, 34, 40, 30)
        lay.setSpacing(10)

        icon = QLabel()
        icon.setPixmap(QApplication.windowIcon().pixmap(84, 84))
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title = QLabel("천체 사진 편집기")
        title.setObjectName("Hero")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub = QLabel("StarLab · Findingstar")
        sub.setObjectName("Dim")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint = QLabel("사진을 이 창에 끌어다 놓거나 아래 버튼으로 시작하세요")
        hint.setObjectName("Muted")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        for w in (icon, title, sub):
            lay.addWidget(w)
        lay.addSpacing(8)
        lay.addWidget(hint)
        lay.addSpacing(6)

        open_btn = QPushButton("📂   사진 열기")
        open_btn.setProperty("primary", True)
        open_btn.setMinimumHeight(44)
        open_btn.clicked.connect(self.open_clicked)
        sample_btn = QPushButton("✨   예제 사진으로 체험하기")
        sample_btn.setMinimumHeight(40)
        sample_btn.clicked.connect(self.sample_clicked)
        stack_btn = QPushButton("🗂   여러 장 합성 (스태킹)")
        stack_btn.setMinimumHeight(40)
        stack_btn.clicked.connect(self.stack_clicked)
        for b in (open_btn, sample_btn, stack_btn):
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            lay.addWidget(b)

        lay.addSpacing(10)
        tips = QLabel(
            "<b>처음이신가요?</b><br>"
            "① 예제 사진을 열고 → ② 왼쪽 <b>✨ 자동 천체 보정</b>을 누른 뒤 →<br>"
            "③ 오른쪽 슬라이더로 취향껏 다듬고 → ④ <b>💾 저장</b>!<br><br>"
            f"<span style='color:#5a6088'>지원 형식: {format_summary()}</span>"
        )
        tips.setObjectName("Muted")
        tips.setWordWrap(True)
        tips.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(tips)
        outer.addWidget(card)

    def dragEnterEvent(self, event):  # noqa: N802
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):  # noqa: N802
        paths = [u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()]
        if paths:
            self.files_dropped.emit(paths)
