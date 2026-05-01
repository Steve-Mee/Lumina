"""Pytest wiring for lumina_os: ensure `backend` (and peers) resolve without per-file sys.path hacks."""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_root_str = str(_ROOT)
if _root_str not in sys.path:
    sys.path.insert(0, _root_str)
