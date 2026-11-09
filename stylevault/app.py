"""Glue: start Qt, load fonts, open the main window."""
from __future__ import annotations

import os
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
    app.setQuitOnLastWindowClosed(False)         # the window can hide in the tray; closing it for real quits explicitly
    from . import single
    if not os.environ.get("STYLEVAULT_NO_SINGLE") and single.notify_existing():
        return 0                                 # another copy is already running: it was asked to come to the front
    theme.load_fonts()
    app.setFont(theme.font(14))
    app.setStyleSheet(theme.STYLE)
    app.setWindowIcon(theme.app_icon())
    win = MainWindow(Settings.load())
    listener = single.Listener(win.bring_front)  # noqa: F841  (kept alive for the whole run)
    if "--tray" in argv and win.tray and win.tg_connected():
        pass                                     # started with Windows: stay quietly in the tray
    else:
        win.show()
    return app.exec()
