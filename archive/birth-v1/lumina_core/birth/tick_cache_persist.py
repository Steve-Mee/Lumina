"""Persist birth tick cache for manifest-based reuse (BRO v2 PR-T2)."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lumina_core.birth.data_source_honesty import real_data_percentage, tape_source_label
from lumina_core.birth.purged_split import PurgedSplit
from lumina_core.birth.tick_cache_split_codec import (
    load_purged_split_payload,
    split_payload,
    ticks_jsonl,
)
from lumina_core.io.atomic_fs import atomic_write_text, atomic_write_text_many, tmp_siblings
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


def jsonl_row_count(path: Path | str) -> int:
    target = Path(path)
    if not target.is_file():
        return 0
    count = 0
    with target.open("rb") as handle:
        for raw in handle:
            if raw.strip():
                count += 1
    return count


def _atomic_write_text(path: Path, encoded: str) -> None:
    atomic_write_text(path, encoded)


def save_ticks_cache(workspace_root: Path | str, ticks: list[dict[str, Any]]) -> str:
    path = ticks_cache_path(workspace_root)
    atomic_write_text(path, ticks_jsonl(ticks))
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
    ticks: list[dict[str, Any]] | None = None,
) -> str:
    path = split_cache_path(workspace_root)
    payload = split_payload(
        split,
        holdout_pct,
        ticks=ticks,
        ticks_fingerprint=compute_ticks_fingerprint(ticks) if ticks else "",
    )
    atomic_write_text(path, json.dumps(payload, ensure_ascii=True))
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
    ticks = load_ticks_cache(workspace_root) if "train_indices" in payload else []
    return load_purged_split_payload(
        payload,
        holdout_pct=holdout_pct,
        ticks=ticks,
        ticks_fingerprint=compute_ticks_fingerprint(ticks) if ticks else "",
    )


def _manifest_payload(
    *,
    raw_ticks_hash: str,
    train_hash: str,
    holdout_pct: float,
    enrich_version: str,
    tick_count: int,
    train_tick_count: int,
    holdout_tick_count: int,
    requested_days: int,
    actual_calendar_days: int,
    instruments: list[str] | tuple[str, ...] | None,
    stitched: bool,
    stitched_from: list[str] | tuple[str, ...] | None,
    source: str,
    real_data_pct: float,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
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
        "source": str(source or ""),
        "real_data_pct": float(real_data_pct),
    }
    if extra:
        payload.update(extra)
    return payload


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
    source: str = "",
    real_data_pct: float = 0.0,
    extra: dict[str, Any] | None = None,
) -> str:
    payload = _manifest_payload(
        raw_ticks_hash=raw_ticks_hash,
        train_hash=train_hash,
        holdout_pct=holdout_pct,
        enrich_version=enrich_version,
        tick_count=tick_count,
        train_tick_count=train_tick_count,
        holdout_tick_count=holdout_tick_count,
        requested_days=requested_days,
        actual_calendar_days=actual_calendar_days,
        instruments=instruments,
        stitched=stitched,
        stitched_from=stitched_from,
        source=source,
        real_data_pct=real_data_pct,
        extra=extra,
    )
    path = cache_manifest_path(workspace_root)
    atomic_write_text(path, json.dumps(payload, ensure_ascii=True, indent=2))
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

    Cheap existence/metadata check — does not parse the jsonl tape, but does
    require jsonl row count == manifest tick_count so a partial Windows
    replace cannot look certified.
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
    from lumina_core.birth.tick_cache_guard import cache_files_coherent

    return cache_files_coherent(root, manifest)


def ensure_certified_tick_cache(workspace_root: Path | str) -> bool:
    """Heal split-brain leftovers, then report certified presence honestly."""
    from lumina_core.birth.tick_cache_guard import heal_tick_cache_coherence

    heal_tick_cache_coherence(workspace_root)
    return certified_tick_cache_present(workspace_root)


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
    from lumina_core.birth.tick_cache_guard import (
        heal_tick_cache_coherence,
        refuse_shallower_certified_overwrite,
    )

    heal_tick_cache_coherence(workspace_root)
    honest_pct = real_data_percentage(ticks)
    refuse_shallower_certified_overwrite(
        workspace_root,
        tick_count=len(ticks),
        requested_days=requested_days,
        actual_calendar_days=actual_calendar_days,
        instruments=instruments,
    )
    ticks_path = ticks_cache_path(workspace_root)
    split_path = split_cache_path(workspace_root)
    manifest_path = cache_manifest_path(workspace_root)
    existing = load_cache_manifest(workspace_root)
    skip_ticks = False
    if isinstance(existing, dict) and ticks_path.is_file() and ticks_path.stat().st_size > 0:
        same_hash = str(existing.get("raw_ticks_hash") or "") == str(raw_ticks_hash or "")
        same_enrich = str(existing.get("enrich_version") or "") == str(enrich_version or ENRICH_VERSION)
        try:
            same_n = int(existing.get("tick_count") or 0) == len(ticks)
        except (TypeError, ValueError):
            same_n = False
        skip_ticks = bool(same_hash and same_enrich and same_n)
    manifest = _manifest_payload(
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
        source=tape_source_label(ticks),
        real_data_pct=honest_pct,
    )
    # Split dest first: if that replace fails, ticks+manifest dests stay as they were.
    # Skip rewriting a matching jsonl — a 900MB replace is what killed the runner.
    staged: list[tuple[Path, str]] = [
        (
            split_path,
            json.dumps(
                split_payload(
                    split,
                    holdout_pct,
                    ticks=ticks,
                    ticks_fingerprint=compute_ticks_fingerprint(ticks),
                ),
                ensure_ascii=True,
            ),
        )
    ]
    if not skip_ticks:
        staged.append((ticks_path, ticks_jsonl(ticks)))
    staged.append((manifest_path, json.dumps(manifest, ensure_ascii=True, indent=2)))
    atomic_write_text_many(staged)
    return {
        "ticks_cache_path": str(ticks_path),
        "split_cache_path": str(split_path),
        "cache_manifest_path": str(manifest_path),
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
        for leftover in tmp_siblings(path):
            try:
                leftover.unlink(missing_ok=True)
            except OSError:
                pass
    enrich_dir = Path(workspace_root) / "state" / "birth_enrichment_cache"
    if enrich_dir.is_dir():
        for child in enrich_dir.glob("*"):
            try:
                child.unlink(missing_ok=True)
            except OSError:
                pass
