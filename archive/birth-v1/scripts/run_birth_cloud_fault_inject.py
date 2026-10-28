#!/usr/bin/env python3
"""Crash/resume Birth cloud shadow — delegates to run_birth_cloud_shadow.py --fault-inject."""

from __future__ import annotations

import sys
from pathlib import Path

from run_birth_cloud_shadow import main as shadow_main


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if "--fault-inject" not in args:
        args = ["--fault-inject", *args]
    return shadow_main(args)


if __name__ == "__main__":
    # Ensure sibling import when invoked as a script.
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    raise SystemExit(main())
