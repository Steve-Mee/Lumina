#!/usr/bin/env python3
"""CLI: genesis first-life cloud ladder (SIM / synthetic only)."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


if __name__ == "__main__":
    sys.path.insert(0, str(REPO_ROOT))
    from lumina_core.birth.genesis_cloud_run import main

    raise SystemExit(main())
