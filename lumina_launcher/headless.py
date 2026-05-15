"""Headless launcher entry: delegates to :mod:`lumina_core.engine.runtime_entrypoint`."""

from __future__ import annotations

import sys
from pathlib import Path


def repo_root() -> Path:
    """Repository root (parent of the ``lumina_launcher`` package directory)."""
    return Path(__file__).resolve().parents[1]


def run_headless(argv: list[str] | None = None) -> int:
    """Run one-shot / stability-check headless runtime. Returns process exit code."""
    from dotenv import load_dotenv
    from lumina_core.engine.runtime_entrypoint import run_with_mode

    root = repo_root()
    load_dotenv(root / ".env")
    args = list(argv if argv is not None else sys.argv[1:])
    return int(run_with_mode("sim", argv=args))
