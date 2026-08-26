"""Append-only NinjaTrader lifecycle log (Code Red: never silent kill).

Every intentional taskkill / close of NinjaTrader.exe must call
``log_nt_lifecycle`` so operators can prove whether Lumina killed NT.
"""

from __future__ import annotations

import os
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def nt_lifecycle_log_path() -> Path:
    appdata = os.environ.get("APPDATA") or ""
    if appdata:
        return Path(appdata) / "LUMINA" / "nt-lifecycle.log"
    return Path.home() / ".lumina" / "nt-lifecycle.log"


def log_nt_lifecycle(event: str, *, reason: str = "", detail: dict[str, Any] | None = None) -> None:
    """Best-effort append; never raise into trading paths."""
    try:
        path = nt_lifecycle_log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        stack = "".join(traceback.format_stack(limit=12)).replace("\n", " | ")
        extra = ""
        if detail:
            try:
                import json

                extra = " " + json.dumps(detail, default=str)[:500]
            except Exception:
                extra = f" detail={detail!r}"[:500]
        line = f"{ts} event={event} reason={reason}{extra} stack=[{stack}]\n"
        with path.open("a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass
