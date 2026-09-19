"""Append-only Twin watch of THIS Awakening run. Metrics dumps are not proof.

Runner telemetry uses source=runner and does **not** satisfy the pass gate.
Only source=twin counts, and only when Twin is Birth-ready.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

SCHEMA = "awakening_twin_watch_v1"
WATCH_REL = Path("state") / "awakening_twin_watch.jsonl"
WatchKind = Literal["prefer_better", "regime", "recovery"]
WatchSource = Literal["twin", "runner"]
ALLOWED_KINDS = frozenset({"prefer_better", "regime", "recovery"})
TWIN_WATCH_MIN = 1


def watch_path(workspace_root: Path | str) -> Path:
    return Path(workspace_root) / WATCH_REL


def append_watch(
    workspace_root: Path | str,
    *,
    kind: WatchKind,
    note: str = "",
    extra: dict[str, Any] | None = None,
    source: WatchSource = "runner",
) -> None:
    if kind not in ALLOWED_KINDS:
        raise ValueError(f"unknown twin-watch kind: {kind}")
    if source not in {"twin", "runner"}:
        raise ValueError(f"unknown twin-watch source: {source}")
    path = watch_path(workspace_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    row: dict[str, Any] = {
        "schema": SCHEMA,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "kind": kind,
        "source": source,
        "note": str(note)[:300],
    }
    if extra:
        row["extra"] = extra
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=True) + "\n")


def watch_count(workspace_root: Path | str) -> int:
    path = watch_path(workspace_root)
    if not path.is_file():
        return 0
    n = 0
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            raw = line.strip()
            if not raw:
                continue
            try:
                row = json.loads(raw)
            except (ValueError, TypeError):
                continue
            if not isinstance(row, dict):
                continue
            if str(row.get("schema") or "") != SCHEMA:
                continue
            if str(row.get("kind") or "") not in ALLOWED_KINDS:
                continue
            if str(row.get("source") or "") != "twin":
                continue
            n += 1
    except OSError:
        return 0
    return n


def watch_ok(workspace_root: Path | str, *, min_n: int = TWIN_WATCH_MIN) -> bool:
    return watch_count(workspace_root) >= int(min_n)


def twin_is_ready(workspace_root: Path | str) -> bool:
    try:
        from lumina_core.evolution.twin_birth_readiness import is_twin_birth_ready

        path = Path(workspace_root) / "state" / "twin_birth_readiness.json"
        return bool(is_twin_birth_ready(path))
    except Exception:
        return False


def twin_watch_cycle(
    workspace_root: Path | str,
    *,
    kind: WatchKind,
    note: str = "",
    extra: dict[str, Any] | None = None,
) -> bool:
    """Record a Twin-source watch only when Twin is Birth-ready. Else fail-closed."""
    if not twin_is_ready(workspace_root):
        return False
    append_watch(workspace_root, kind=kind, note=note, extra=extra, source="twin")
    return True
