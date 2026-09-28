"""Application entry point."""

from __future__ import annotations

import os
import sys


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv if argv is None else argv)
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtWidgets import QApplication

    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(argv)
    app.setApplicationName("StarLab")
    app.setApplicationDisplayName("StarLab 천체 사진 편집기")
    app.setOrganizationName("Findingstar")

    from .ui.main_window import MainWindow
    from .ui.theme import apply_theme

    apply_theme(app)
    window = MainWindow()
    window.show()
    files = [a for a in argv[1:] if os.path.isfile(a)]
    if files:
        window.open_path(files[0])
    return app.exec()
