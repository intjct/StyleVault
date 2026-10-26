"""Design A1: clean white + electric blue, Prompt font (300/400/500 only), thin borders, no shadows."""
from __future__ import annotations

import os

from PySide6.QtGui import QColor, QFont, QFontDatabase, QIcon

BG = QColor("#FFFFFF")
SURFACE = QColor("#F4F5F7")
LINE = QColor("#E6E8EC")
CARD_LINE = QColor("#ECEEF1")
TEXT = QColor("#14171C")
TEXT_SOFT = QColor("#8A8F98")
TEXT_MID = QColor("#4A505B")
ACCENT = QColor("#2F5BFF")
ACCENT_SOFT = QColor("#EAF0FF")
ACCENT_DARK = QColor("#2549D6")
SFX = QColor("#FF5A1F")
RED = QColor("#D93025")
RED_SOFT = QColor("#FDECEA")

LIGHT, NORMAL, MEDIUM = QFont.Weight.Light, QFont.Weight.Normal, QFont.Weight.Medium
FAMILIES = ["Prompt", "Leelawadee UI", "Segoe UI", "Noto Sans Thai", "sans-serif"]
_loaded = False


def asset(name: str) -> str:
    from ..tools import resource_dir
    return os.path.join(resource_dir(), "assets", name)


def load_fonts() -> None:
    global _loaded
    if _loaded:
        return
    folder = asset("fonts")
    if os.path.isdir(folder):
        for n in sorted(os.listdir(folder)):
            if n.lower().endswith((".ttf", ".otf")):
                QFontDatabase.addApplicationFont(os.path.join(folder, n))
    _loaded = True


def font(px: float, weight: QFont.Weight = NORMAL) -> QFont:
    f = QFont()
    f.setFamilies(FAMILIES)
    f.setPixelSize(max(1, round(px)))
    f.setWeight(weight)
    return f


def app_icon() -> QIcon:
    for n in ("stylevault.ico", "stylevault.png"):
        p = asset(n)
        if os.path.exists(p):
            return QIcon(p)
    return QIcon()


STYLE = f"""
* {{ color: {TEXT.name()}; font-family: "Prompt", "Leelawadee UI", "Segoe UI"; font-weight: 400; }}
QWidget#Main, QWidget#Page, QScrollArea, QScrollArea > QWidget > QWidget {{ background: {BG.name()}; }}
QScrollArea {{ border: none; }}
QLabel {{ background: transparent; }}
QLabel#Soft {{ color: {TEXT_SOFT.name()}; }}
QLabel#Mid {{ color: {TEXT_MID.name()}; }}
QLabel#Title {{ font-size: 20px; font-weight: 500; }}
QLabel#H2 {{ font-size: 15px; font-weight: 500; }}
QLabel#Warn {{ color: #8A5A00; background: #FFF6E0; border-radius: 10px; padding: 10px 12px; }}
QLabel#Hint {{ color: {TEXT_MID.name()}; background: {SURFACE.name()}; border-radius: 10px; padding: 12px 14px; }}
QLabel#Good {{ color: #137333; background: #E8F5EC; border-radius: 10px; padding: 10px 12px; }}
QLineEdit, QPlainTextEdit, QComboBox {{
    background: {SURFACE.name()}; border: 1px solid {SURFACE.name()}; border-radius: 10px;
    padding: 9px 12px; selection-background-color: {ACCENT_SOFT.name()}; selection-color: {TEXT.name()};
}}
QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus {{ border: 1px solid {ACCENT.name()}; background: {BG.name()}; }}
QPushButton {{
    background: {SURFACE.name()}; border: 1px solid {LINE.name()}; border-radius: 10px; padding: 9px 16px;
    font-weight: 500;
}}
QPushButton:hover {{ background: #ECEEF2; }}
QPushButton:disabled {{ color: {TEXT_SOFT.name()}; }}
QPushButton#Primary {{ background: {ACCENT.name()}; border: 1px solid {ACCENT.name()}; color: white; }}
QPushButton#Primary:hover {{ background: {ACCENT_DARK.name()}; }}
QPushButton#Primary:disabled {{ background: #AFC0FF; border-color: #AFC0FF; color: white; }}
QPushButton#Link {{ background: transparent; border: none; color: {TEXT_MID.name()}; padding: 6px 4px; text-align: left; }}
QPushButton#Link:hover {{ color: {ACCENT.name()}; }}
QPushButton#Chip {{
    background: {BG.name()}; border: 1px solid {LINE.name()}; border-radius: 18px; padding: 6px 14px;
    color: {TEXT_MID.name()}; font-weight: 400;
}}
QPushButton#Chip:hover {{ background: {SURFACE.name()}; }}
QPushButton#Chip:checked {{ background: {TEXT.name()}; border-color: {TEXT.name()}; color: white; }}
QPushButton#ChipBlue {{
    background: {ACCENT_SOFT.name()}; border: 1px solid {ACCENT_SOFT.name()}; border-radius: 18px; padding: 6px 14px;
    color: {ACCENT.name()}; font-weight: 500;
}}
QPushButton#ChipBlue:checked {{ background: {ACCENT.name()}; border-color: {ACCENT.name()}; color: white; }}
QComboBox {{ padding-right: 28px; min-width: 90px; }}
QComboBox::drop-down {{ border: none; width: 28px; }}
QComboBox QAbstractItemView {{ background: {BG.name()}; border: 1px solid {LINE.name()}; selection-background-color: {SURFACE.name()}; selection-color: {TEXT.name()}; outline: 0; }}
QCheckBox {{ spacing: 8px; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: #D5D8DE; border-radius: 4px; min-height: 30px; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
QFrame#Sep {{ background: {LINE.name()}; max-height: 1px; min-height: 1px; }}
QFrame#Panel {{ background: {BG.name()}; border: 1px solid {CARD_LINE.name()}; border-radius: 10px; }}
QMessageBox, QDialog {{ background: {BG.name()}; }}
QMenu {{ background: {BG.name()}; border: 1px solid {LINE.name()}; border-radius: 8px; padding: 4px; }}
QMenu::item {{ padding: 8px 22px; border-radius: 6px; }}
QMenu::item:selected {{ background: {SURFACE.name()}; }}
QSlider::groove:horizontal {{ height: 4px; background: {LINE.name()}; border-radius: 2px; }}
QSlider::sub-page:horizontal {{ background: {ACCENT.name()}; border-radius: 2px; }}
QSlider::handle:horizontal {{ background: {ACCENT.name()}; width: 12px; height: 12px; margin: -4px 0; border-radius: 6px; }}
"""
