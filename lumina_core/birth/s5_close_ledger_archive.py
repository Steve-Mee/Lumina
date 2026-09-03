"""Append-only S5 close_ledger archive. Memory cap ≠ disk book.

SYNTHETIC ≡ LIVE: same persist functions on a later live tape. No second schema.
Checkpoint JSON may keep a tail. This file must still hold the prefix.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from lumina_core.birth.s5_close_ledger_trace import close_ledger_row

ARCHIVE_REL = Path("reports/birth_cloud_run/artifacts/s5_close_ledger.jsonl")
SHA256_NAME = "s5_close_ledger.sha256"
MEMORY_CAP = 2000
REQUIRED_ARCHIVE_KEYS = (
    "pnl",
    "qty",
    "point_value",
    "close_reason",
    "gap",
    "regime",
    "intended_risk_usd",
    "trade_r",
    "reward_on_close",
    "cap_hit",
    "stage",
)


def resolve_archive_path(workspace_root: Path | str | None) -> Path:
    """Durable JSONL under reports/, never gitignored state/.

    Path geometry only: a birth_cloud workspace writes the sibling artifacts/
    directory. Any other workspace writes ``<root>/reports/birth_cloud_run/artifacts/``.
    """
    root = Path(workspace_root) if workspace_root else Path.cwd()
    if root.name == "workspace" and root.parent.name == "birth_cloud_run":
        return root.parent / "artifacts" / ARCHIVE_REL.name
    return root / ARCHIVE_REL


def workspace_from_host(host: Any) -> Path | None:
    for obj in (host, getattr(host, "host", None)):
        if obj is None:
            continue
        root = getattr(obj, "workspace_root", None)
        if root:
            return Path(root)
    return None


def resolve_stage(host: Any) -> str:
    stage = getattr(host, "stage", None)
    if stage is not None:
        return str(getattr(stage, "value", stage) or "")
    return str(getattr(host, "curriculum_stage", "") or "")


def enrich_archive_row(
    row: dict[str, Any],
    *,
    stage: str,
    tr: dict[str, Any] | None = None,
    source: str | None = None,
) -> dict[str, Any]:
    """close_ledger_row keys plus stage / ts_iso / bar_index when the live row has them."""
    out = dict(row)
    out["stage"] = stage
    src = tr or {}
    ts = src.get("ts_iso") or src.get("timestamp") or out.get("ts_iso")
    if ts:
        out["ts_iso"] = str(ts)
    bar = src.get("bar_index", src.get("idx", src.get("tick_index", out.get("bar_index"))))
    if bar is not None:
        out["bar_index"] = bar
    if source:
        out["source"] = source
    return out


def append_archive_rows(path: Path, rows: list[dict[str, Any]]) -> int:
    """Append-only. Never truncate to last 2000."""
    if not rows:
        return 0
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=True, default=str) + "\n")
    return len(rows)


def write_archive_sha256(path: Path) -> Path:
    digest = hashlib.sha256()
    if path.is_file():
        digest.update(path.read_bytes())
    sidecar = path.with_name(SHA256_NAME)
    sidecar.write_text(digest.hexdigest() + "\n", encoding="utf-8")
    return sidecar


def archive_line_count(path: Path) -> int:
    if not path.is_file():
        return 0
    n = 0
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                n += 1
    return n


def _append_to_host_archive(host: Any, rows: list[dict[str, Any]]) -> int:
    root = workspace_from_host(host)
    if root is None:
        raise RuntimeError("close_ledger archive flush requires workspace_root")
    return append_archive_rows(resolve_archive_path(root), rows)


def flush_new_close_rows(host: Any, rows: list[dict[str, Any]]) -> int:
    """Write newly appended closes. Must succeed before the caller caps memory."""
    if not rows:
        return 0
    n = _append_to_host_archive(host, rows)
    host._close_ledger_archived_n = int(getattr(host, "_close_ledger_archived_n", 0) or 0) + n
    return n


def flush_close_ledger_before_wipe(
    host: Any,
    *,
    seal: bool = False,
    clear_memory: bool = False,
    source: str | None = None,
) -> int:
    """Flush in-memory rows not yet archived. Then the caller may clear or cap."""
    ledger = list(getattr(host, "close_ledger", None) or [])
    already = int(getattr(host, "_close_ledger_archived_n", 0) or 0)
    pending = ledger[already:] if already < len(ledger) else []
    n = 0
    if pending:
        stage = resolve_stage(host)
        rows = [
            enrich_archive_row(dict(r), stage=stage, source=source)
            if isinstance(r, dict) and "stage" not in r
            else dict(r)
            for r in pending
            if isinstance(r, dict)
        ]
        n = _append_to_host_archive(host, rows)
        host._close_ledger_archived_n = already + n
    if seal:
        root = workspace_from_host(host)
        if root is not None:
            path = resolve_archive_path(root)
            if path.is_file():
                write_archive_sha256(path)
    if clear_memory:
        host.close_ledger = []
        host._close_ledger_archived_n = 0
    return n


def record_close_rows_from_trajectories(
    host: Any,
    trajectories: list[Any],
) -> list[dict[str, Any]]:
    """Build close_ledger_row list and flush archive rows. Caller then caps memory."""
    stage = resolve_stage(host)
    memory_rows: list[dict[str, Any]] = []
    archive_rows: list[dict[str, Any]] = []
    for tr in trajectories or []:
        if not isinstance(tr, dict) or tr.get("pnl") is None:
            continue
        row = close_ledger_row(tr)
        memory_rows.append(row)
        archive_rows.append(enrich_archive_row(row, stage=stage, tr=tr))
    flush_new_close_rows(host, archive_rows)
    return memory_rows


__all__ = [
    "ARCHIVE_REL",
    "MEMORY_CAP",
    "REQUIRED_ARCHIVE_KEYS",
    "SHA256_NAME",
    "archive_line_count",
    "append_archive_rows",
    "enrich_archive_row",
    "flush_close_ledger_before_wipe",
    "flush_new_close_rows",
    "record_close_rows_from_trajectories",
    "resolve_archive_path",
    "resolve_stage",
    "workspace_from_host",
    "write_archive_sha256",
]
