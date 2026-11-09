"""Start with Windows: one value in the current user's Run key (no admin password needed). Off by default."""
from __future__ import annotations

import sys

KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
NAME = "StyleVault"


def available() -> bool:
    """Only the installed program (the .exe) can start with Windows."""
    return sys.platform == "win32" and bool(getattr(sys, "frozen", False))


def command() -> str:
    return f'"{sys.executable}" --tray'


def is_enabled() -> bool:
    if sys.platform != "win32":
        return False
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, KEY) as k:
            winreg.QueryValueEx(k, NAME)
            return True
    except OSError:
        return False


def set_enabled(on: bool) -> bool:
    """True when it worked."""
    if not available():
        return False
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, KEY, 0, winreg.KEY_SET_VALUE) as k:
            if on:
                winreg.SetValueEx(k, NAME, 0, winreg.REG_SZ, command())
            else:
                try:
                    winreg.DeleteValue(k, NAME)
                except FileNotFoundError:
                    pass
        return True
    except OSError:
        return False
