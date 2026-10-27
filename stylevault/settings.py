"""User settings, saved as JSON in %APPDATA%\\StyleVault\\settings.json (survives reinstalling)."""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass

from . import APP_NAME


def config_dir() -> str:
    base = os.environ.get("APPDATA") or os.path.join(os.path.expanduser("~"), ".config")
    d = os.path.join(base, APP_NAME)
    os.makedirs(d, exist_ok=True)
    return d


def default_library_dir() -> str:
    return os.path.join(os.path.expanduser("~"), "Documents", "StyleVault Library")


@dataclass
class Settings:
    library_dir: str = ""
    last_kind: str = "effects"           # effects / viral
    use_browser_login: bool = False      # read the browser's login for Instagram/Facebook
    browser: str = "chrome"              # chrome / edge
    first_run_done: bool = False
    volume: int = 50                     # clip player volume 0-100 (remembered)

    def library_path(self) -> str:
        return self.library_dir or default_library_dir()

    @classmethod
    def load(cls) -> "Settings":
        try:
            with open(os.path.join(config_dir(), "settings.json"), encoding="utf-8") as f:
                raw = json.load(f)
            known = {k: v for k, v in raw.items() if k in cls.__dataclass_fields__}
            return cls(**known)
        except Exception:
            return cls()

    def save(self) -> None:
        try:
            path = os.path.join(config_dir(), "settings.json")
            tmp = path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(asdict(self), f, ensure_ascii=False, indent=2)
            os.replace(tmp, path)
        except Exception:
            pass
