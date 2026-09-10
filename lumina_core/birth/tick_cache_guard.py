"""Fail-closed tick-cache depth and coherence guards (no silent shrink / split-brain)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from lumina_core.birth.tick_cache_persist import (
    cache_manifest_path,
    jsonl_row_count,
    load_cache_manifest,
    save_cache_manifest,
    save_ticks_cache,
    split_cache_path,
    ticks_cache_path,
)
from lumina_core.io.atomic_fs import legacy_tmp_path, tmp_siblings
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.tick_cache_guard")


class TickCacheDepthRegressionError(OSError):
    """Refuse to clobber a deeper certified tape with a shallower one."""


def _norm_symbol(raw: Any) -> str:
    return " ".join(str(raw or "").strip().upper().split())


def _instrument_overlap(existing: Any, incoming: Any) -> bool:
    old = {_norm_symbol(item) for item in (existing or []) if _norm_symbol(item)}
    new = {_norm_symbol(item) for item in (incoming or []) if _norm_symbol(item)}
    if not old or not new:
        return True
    return bool(old & new)


def refuse_shallower_certified_overwrite(
    workspace_root: Path | str,
    *,
    tick_count: int,
    requested_days: int,
    actual_calendar_days: int,
    instruments: list[str] | tuple[str, ...] | None,
) -> None:
    """Raise if this write would shrink an already-certified history tape."""
    from lumina_core.birth.tick_cache_persist import certified_tick_cache_present

    root = Path(workspace_root)
    if not certified_tick_cache_present(root):
        return
    existing = load_cache_manifest(root)
    if not isinstance(existing, dict):
        return
    try:
        old_ticks = int(existing.get("tick_count") or 0)
        old_requested = int(existing.get("requested_days") or 0)
        old_actual = int(existing.get("actual_calendar_days") or 0)
    except (TypeError, ValueError):
        return
    if not _instrument_overlap(existing.get("instruments"), instruments):
        return
    shallower = (
        int(tick_count) < old_ticks
        or int(actual_calendar_days) < old_actual
        or int(requested_days) < old_requested
    )
    if not shallower:
        return
    raise TickCacheDepthRegressionError(
        "certified tick-cache depth regression: "
        f"existing ticks={old_ticks} days={old_actual}/{old_requested} "
        f"incoming ticks={int(tick_count)} days={int(actual_calendar_days)}/{int(requested_days)}"
    )


def discard_shallower_legacy_tmp(dest: Path) -> bool:
    """Drop a leftover ``name.tmp`` that is smaller than dest (failed replace)."""
    tmp = legacy_tmp_path(dest)
    if not tmp.is_file() or not dest.is_file():
        return False
    try:
        if tmp.stat().st_size < dest.stat().st_size:
            tmp.unlink(missing_ok=True)
            logger.warning(
                "birth.cache.discarded_shallower_tmp dest=%s tmp=%s",
                dest,
                tmp,
            )
            return True
    except OSError as exc:
        logger.warning("birth.cache.tmp_discard_failed path=%s err=%s", tmp, exc)
    return False


def _merge_v1_split_ticks(payload: dict[str, Any]) -> list[dict[str, Any]]:
    train = payload.get("train")
    holdout = payload.get("holdout")
    if not isinstance(train, list) or not isinstance(holdout, list):
        return []
    merged: list[dict[str, Any]] = []
    for item in (*train, *holdout):
        if isinstance(item, dict):
            merged.append(item)
    merged.sort(key=lambda row: (str(row.get("timestamp") or ""), int(row.get("bar_index") or 0)))
    return merged


def heal_tick_cache_coherence(workspace_root: Path | str) -> str:
    """Restore jsonl from a deeper v1 split after a partial Windows replace.

    Returns ``ok`` / ``healed`` / ``noop`` / ``incoherent``. Never applies a
    shallower leftover ``.tmp`` over a deeper dest.
    """
    root = Path(workspace_root)
    ticks_path = ticks_cache_path(root)
    split_path = split_cache_path(root)
    discard_shallower_legacy_tmp(split_path)
    discard_shallower_legacy_tmp(ticks_path)
    discard_shallower_legacy_tmp(cache_manifest_path(root))

    manifest = load_cache_manifest(root)
    if not isinstance(manifest, dict):
        return "noop"
    try:
        expected = int(manifest.get("tick_count") or 0)
    except (TypeError, ValueError):
        return "incoherent"
    if expected <= 0:
        return "noop"
    actual = jsonl_row_count(ticks_path)
    if actual == expected:
        return "ok"
    if actual > expected:
        logger.warning(
            "birth.cache.jsonl_ahead_of_manifest actual=%s expected=%s",
            actual,
            expected,
        )
        return "incoherent"
    if not split_path.is_file():
        return "incoherent"
    try:
        payload = json.loads(split_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, MemoryError) as exc:
        logger.warning("birth.cache.split_heal_read_failed err=%s", exc)
        return "incoherent"
    if not isinstance(payload, dict):
        return "incoherent"
    if int(payload.get("schema_version") or 1) >= 2:
        return "incoherent"
    recovered = _merge_v1_split_ticks(payload)
    if len(recovered) < actual:
        return "incoherent"
    save_ticks_cache(root, recovered)
    try:
        from lumina_core.birth.purged_split import PurgedSplit
        from lumina_core.birth.tick_cache_persist import save_split_cache

        healed_split = PurgedSplit(
            train=[item for item in (payload.get("train") or []) if isinstance(item, dict)],
            holdout=[item for item in (payload.get("holdout") or []) if isinstance(item, dict)],
            holdout_days=int(payload.get("holdout_days") or 0),
            train_days=int(payload.get("train_days") or 0),
        )
        save_split_cache(
            root,
            split=healed_split,
            holdout_pct=float(payload.get("holdout_pct") or 0.2),
            ticks=recovered,
        )
    except OSError as exc:
        logger.warning("birth.cache.v2_split_persist_deferred err=%s", exc)
    patched = dict(manifest)
    patched["tick_count"] = len(recovered)
    patched["tick_count_healed_from_split"] = True
    save_cache_manifest(
        root,
        raw_ticks_hash=str(patched.get("raw_ticks_hash") or ""),
        train_hash=str(patched.get("train_hash") or ""),
        holdout_pct=float(patched.get("holdout_pct") or 0.2),
        enrich_version=str(patched.get("enrich_version") or ""),
        tick_count=len(recovered),
        train_tick_count=int(patched.get("train_tick_count") or 0),
        holdout_tick_count=int(patched.get("holdout_tick_count") or 0),
        requested_days=int(patched.get("requested_days") or 0),
        actual_calendar_days=int(patched.get("actual_calendar_days") or 0),
        instruments=list(patched.get("instruments") or []),
        stitched=bool(patched.get("stitched")),
        stitched_from=list(patched.get("stitched_from") or []),
        source=str(patched.get("source") or ""),
        real_data_pct=float(patched.get("real_data_pct") or 0.0),
        extra={"tick_count_healed_from_split": True},
    )
    logger.warning(
        "birth.cache.healed_ticks_from_split recovered=%s manifest_was=%s jsonl_was=%s",
        len(recovered),
        expected,
        actual,
    )
    return "healed"


def cache_files_coherent(workspace_root: Path | str, manifest: dict[str, Any]) -> bool:
    """True when jsonl row count matches the manifest and no leftover tmp remains."""
    root = Path(workspace_root)
    ticks_path = ticks_cache_path(root)
    split_path = split_cache_path(root)
    manifest_path = cache_manifest_path(root)
    if tmp_siblings(ticks_path) or tmp_siblings(split_path) or tmp_siblings(manifest_path):
        return False
    try:
        expected = int(manifest.get("tick_count") or 0)
    except (TypeError, ValueError):
        return False
    if expected <= 0:
        return False
    return jsonl_row_count(ticks_path) == expected
