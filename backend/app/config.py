from __future__ import annotations

import os
import stat
from pathlib import Path


def read_secret(name: str, default: str = "") -> str:
    """Read a setting from NAME or a securely mounted NAME_FILE, never both."""
    direct = os.getenv(name)
    file_name = os.getenv(f"{name}_FILE")
    if direct is not None and file_name:
        raise RuntimeError(f"{name} and {name}_FILE cannot both be configured")
    if not file_name:
        return direct if direct is not None else default

    path = Path(file_name)
    if path.is_symlink() or not path.is_file():
        raise RuntimeError(f"{name}_FILE must reference a regular non-symlink file")
    mode = stat.S_IMODE(path.stat().st_mode)
    if mode & 0o077:
        raise RuntimeError(f"{name}_FILE permissions must not allow group or other access")
    value = path.read_text(encoding="utf-8").strip()
    if not value:
        raise RuntimeError(f"{name}_FILE is empty")
    return value
