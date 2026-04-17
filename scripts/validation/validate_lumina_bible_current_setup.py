from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from lumina_bible import BibleEngine  # noqa: E402


def main() -> int:
    bible = BibleEngine()
    sacred_core = bible.bible.get("sacred_core", "") if isinstance(bible.bible, dict) else ""

    print("OK lumina-bible package loaded")
    print(f"Sacred Core length: {len(sacred_core)}")
    print("Community contributions ready for world-wide evolution")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
