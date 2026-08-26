"""Persist birth tick cache for manifest-based reuse (BRO v2 PR-T2)."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lumina_core.birth.purged_split import PurgedSplit
from lumina_core.rl.trend_features import ENRICH_VERSION

CACHE_SCHEMA_VERSION = 1


def ticks_cache_path(workspace_root: Path | str) -> Path:
    return Path(workspace_root) / "state" / "lumina_birth_ticks_cache.jsonl"


def split_cache_path(workspace_root: Path | str) -> Path:
    return Path(workspace_root) / "state" / "lumina_birth_split_cache.json"


def cache_manifest_path(workspace_root: Path | str) -> Path:
    return Path(workspace_root) / "state" / "lumina_birth_cache_manifest.json"


def compute_ticks_fingerprint(ticks: list[dict[str, Any]]) -> str:
    """Stable fingerprint: len + first/last timestamp (matches engine train hash logic)."""
    if not ticks:
        return ""
    head = str(ticks[0].get("timestamp", ""))
    tail = str(ticks[-1].get("timestamp", ""))
    payload = f"{len(ticks)}:{head}:{tail}"
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def _atomic_write_text(path: Path, encoded: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f"{path.name}.tmp")
    tmp_path.write_text(encoded, encoding="utf-8")
    os.replace(tmp_path, path)


def save_ticks_cache(workspace_root: Path | str, ticks: list[dict[str, Any]]) -> str:
    path = ticks_cache_path(workspace_root)
    lines = [json.dumps(item, ensure_ascii=True) for item in ticks]
    _atomic_write_text(path, "\n".join(lines) + ("\n" if lines else ""))
    return str(path)


def load_ticks_cache(workspace_root: Path | str) -> list[dict[str, Any]]:
    path = ticks_cache_path(workspace_root)
    if not path.is_file():
        return []
    out: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            out.append(item)
    return out


def save_split_cache(
    workspace_root: Path | str,
    *,
    split: PurgedSplit,
    holdout_pct: float,
) -> str:
    path = split_cache_path(workspace_root)
    payload = {
        "holdout_pct": float(holdout_pct),
        "train": list(split.train),
        "holdout": list(split.holdout),
        "holdout_days": int(split.holdout_days),
        "train_days": int(split.train_days),
    }
    _atomic_write_text(path, json.dumps(payload, ensure_ascii=True))
    return str(path)


def load_split_cache(workspace_root: Path | str, *, holdout_pct: float) -> PurgedSplit | None:
    path = split_cache_path(workspace_root)
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    cached_pct = float(payload.get("holdout_pct", holdout_pct) or holdout_pct)
    if abs(cached_pct - float(holdout_pct)) > 1e-6:
        return None
    train = payload.get("train")
    holdout = payload.get("holdout")
    if not isinstance(train, list) or not isinstance(holdout, list):
        return None
    return PurgedSplit(
        train=[dict(item) for item in train if isinstance(item, dict)],
        holdout=[dict(item) for item in holdout if isinstance(item, dict)],
        holdout_days=int(payload.get("holdout_days", 0) or 0),
        train_days=int(payload.get("train_days", 0) or 0),
    )


def save_cache_manifest(
    workspace_root: Path | str,
    *,
    raw_ticks_hash: str,
    train_hash: str,
    holdout_pct: float,
    enrich_version: str = ENRICH_VERSION,
    tick_count: int = 0,
    train_tick_count: int = 0,
    holdout_tick_count: int = 0,
    requested_days: int = 0,
    actual_calendar_days: int = 0,
    instruments: list[str] | tuple[str, ...] | None = None,
    stitched: bool = False,
    stitched_from: list[str] | tuple[str, ...] | None = None,
) -> str:
    payload = {
        "cache_schema_version": CACHE_SCHEMA_VERSION,
        "cache_written_at": datetime.now(timezone.utc).isoformat(),
        "raw_ticks_hash": str(raw_ticks_hash or ""),
        "train_hash": str(train_hash or ""),
        "holdout_pct": float(holdout_pct),
        "enrich_version": str(enrich_version or ENRICH_VERSION),
        "tick_count": int(tick_count),
        "train_tick_count": int(train_tick_count),
        "holdout_tick_count": int(holdout_tick_count),
        "requested_days": int(requested_days),
        "actual_calendar_days": int(actual_calendar_days),
        "instruments": [str(item) for item in (instruments or ())],
        "stitched": bool(stitched),
        "stitched_from": [str(item) for item in (stitched_from or ())],
        "purged_split_params": {"holdout_pct": float(holdout_pct)},
    }
    path = cache_manifest_path(workspace_root)
    _atomic_write_text(path, json.dumps(payload, ensure_ascii=True, indent=2))
    return str(path)


def load_cache_manifest(workspace_root: Path | str) -> dict[str, Any] | None:
    path = cache_manifest_path(workspace_root)
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def certified_tick_cache_present(workspace_root: Path | str) -> bool:
    """True when ticks + split + SLA-depth manifest are on disk (no Fabric probe needed).

    Cheap existence/metadata check — does not parse the jsonl tape.
    """
    root = Path(workspace_root)
    ticks = ticks_cache_path(root)
    split = split_cache_path(root)
    if not ticks.is_file() or ticks.stat().st_size <= 0:
        return False
    if not split.is_file() or split.stat().st_size <= 0:
        return False
    manifest = load_cache_manifest(root)
    if not isinstance(manifest, dict):
        return False
    train = str(manifest.get("train_hash") or "").strip()
    if not train:
        return False
    try:
        actual_days = int(manifest.get("actual_calendar_days") or 0)
        requested_days = int(manifest.get("requested_days") or 0)
        tick_count = int(manifest.get("tick_count") or 0)
    except (TypeError, ValueError):
        return False
    # Foundation start rung is 90d at 0.95 ratio → 86 calendar days.
    if actual_days < 86 or requested_days < 90 or tick_count < 1_000:
        return False
    return True


def save_birth_data_cache(
    workspace_root: Path | str,
    *,
    ticks: list[dict[str, Any]],
    split: PurgedSplit,
    holdout_pct: float,
    raw_ticks_hash: str,
    train_hash: str,
    enrich_version: str = ENRICH_VERSION,
    requested_days: int = 0,
    actual_calendar_days: int = 0,
    instruments: list[str] | tuple[str, ...] | None = None,
    stitched: bool = False,
    stitched_from: list[str] | tuple[str, ...] | None = None,
) -> dict[str, str]:
    ticks_path = save_ticks_cache(workspace_root, ticks)
    split_path = save_split_cache(workspace_root, split=split, holdout_pct=holdout_pct)
    manifest_path = save_cache_manifest(
        workspace_root,
        raw_ticks_hash=raw_ticks_hash,
        train_hash=train_hash,
        holdout_pct=holdout_pct,
        enrich_version=enrich_version,
        tick_count=len(ticks),
        train_tick_count=len(split.train),
        holdout_tick_count=len(split.holdout),
        requested_days=requested_days,
        actual_calendar_days=actual_calendar_days,
        instruments=instruments,
        stitched=stitched,
        stitched_from=stitched_from,
    )
    return {
        "ticks_cache_path": ticks_path,
        "split_cache_path": split_path,
        "cache_manifest_path": manifest_path,
    }


def clear_ticks_cache(workspace_root: Path | str) -> None:
    for path in (
        ticks_cache_path(workspace_root),
        split_cache_path(workspace_root),
        cache_manifest_path(workspace_root),
    ):
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
    enrich_dir = Path(workspace_root) / "state" / "birth_enrichment_cache"
    if enrich_dir.is_dir():
        for child in enrich_dir.glob("*"):
            try:
                child.unlink(missing_ok=True)
            except OSError:
                pass
