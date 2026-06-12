"""Weekly veto registry summaries (headless, testable)."""

from __future__ import annotations

import json
import sqlite3
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


def _parse_iso(raw: Any) -> datetime | None:
    text = str(raw or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _load_jsonl(path: Path, *, limit: int | None = None) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    try:
        for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                rows.append(row)
    except Exception:
        return []
    if limit is not None and limit > 0:
        return rows[-limit:]
    return rows


def weekly_veto_summary(state_dir: Path) -> tuple[int, list[tuple[str, int]]]:
    """Count veto records in the last 7 days; prefers JSONL when present."""
    veto_jsonl = state_dir / "veto_registry.jsonl"
    veto_db = state_dir / "veto_registry.db"
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=7)
    reasons: Counter[str] = Counter()
    count = 0

    if veto_jsonl.exists():
        for row in _load_jsonl(veto_jsonl):
            ts = _parse_iso(row.get("veto_timestamp") or row.get("timestamp"))
            if ts is None or ts < cutoff:
                continue
            count += 1
            reasons[str(row.get("reason", "unknown"))] += 1
        return count, reasons.most_common(5)

    if veto_db.exists():
        try:
            with sqlite3.connect(veto_db) as conn:
                q = """
                SELECT reason, COUNT(*) as c
                FROM veto_records
                WHERE veto_timestamp >= ?
                GROUP BY reason
                ORDER BY c DESC
                LIMIT 5
                """
                rows = conn.execute(q, (cutoff.isoformat(),)).fetchall()
                total_q = "SELECT COUNT(*) FROM veto_records WHERE veto_timestamp >= ?"
                total = conn.execute(total_q, (cutoff.isoformat(),)).fetchone()
                count = int(total[0]) if total else 0
                return count, [(str(r[0]), int(r[1])) for r in rows]
        except Exception:
            return 0, []

    return 0, []
