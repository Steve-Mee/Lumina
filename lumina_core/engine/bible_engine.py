from __future__ import annotations

import sys
from pathlib import Path

# Local developer compatibility: make ./lumina-bible importable without pip install.
_repo_root = Path(__file__).resolve().parents[2]
_pkg_root = _repo_root / "lumina-bible"
if _pkg_root.exists() and str(_pkg_root) not in sys.path:
    sys.path.insert(0, str(_pkg_root))

from lumina_bible.bible_engine import BibleEngine, DEFAULT_BIBLE  # noqa: E402

__all__ = ["BibleEngine", "DEFAULT_BIBLE"]
