"""Glue: start Qt, load fonts, open the main window."""
from __future__ import annotations

import sys


def main(argv=None) -> int:
    argv = list(sys.argv if argv is None else argv)
    if "--selftest" in argv:
        from .selftest import selftest
        return selftest()

    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication

    from .settings import Settings
    from .ui import theme
    from .ui.mainwindow import MainWindow

    app = QApplication(argv)
    app.setApplicationName("StyleVault")
    theme.load_fonts()
    app.setFont(theme.font(14))
    app.setStyleSheet(theme.STYLE)
    app.setWindowIcon(theme.app_icon())
    win = MainWindow(Settings.load())
    win.show()
    return app.exec()
