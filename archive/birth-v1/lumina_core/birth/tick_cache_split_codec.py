"""Split-cache JSON codec: v1 embedded ticks, v2 indices into the jsonl tape."""

from __future__ import annotations

import json
from typing import Any

from lumina_core.birth.purged_split import PurgedSplit

SPLIT_CACHE_SCHEMA_VERSION = 2


def tick_index_key(tick: dict[str, Any], fallback: int) -> tuple[str, int]:
    ts = str(tick.get("timestamp") or "")
    try:
        bar = int(tick.get("bar_index"))
    except (TypeError, ValueError):
        bar = fallback
    return ts, bar


def split_indices(
    ticks: list[dict[str, Any]],
    split: PurgedSplit,
) -> tuple[list[int], list[int]] | None:
    id_map = {id(row): i for i, row in enumerate(ticks)}
    key_map: dict[tuple[str, int], int] = {}
    for i, row in enumerate(ticks):
        key_map.setdefault(tick_index_key(row, i), i)

    def _lookup(row: dict[str, Any], fallback: int) -> int | None:
        by_id = id_map.get(id(row))
        if by_id is not None:
            return by_id
        return key_map.get(tick_index_key(row, fallback))

    train_idx: list[int] = []
    for i, row in enumerate(split.train):
        found = _lookup(row, i)
        if found is None:
            return None
        train_idx.append(found)
    holdout_idx: list[int] = []
    for i, row in enumerate(split.holdout):
        found = _lookup(row, i)
        if found is None:
            return None
        holdout_idx.append(found)
    n = len(ticks)
    if any(idx < 0 or idx >= n for idx in (*train_idx, *holdout_idx)):
        return None
    return train_idx, holdout_idx


def split_payload(
    split: PurgedSplit,
    holdout_pct: float,
    *,
    ticks: list[dict[str, Any]] | None = None,
    ticks_fingerprint: str = "",
) -> dict[str, Any]:
    indexed = split_indices(ticks, split) if ticks else None
    if indexed is not None and ticks:
        train_idx, holdout_idx = indexed
        return {
            "schema_version": SPLIT_CACHE_SCHEMA_VERSION,
            "holdout_pct": float(holdout_pct),
            "train_indices": train_idx,
            "holdout_indices": holdout_idx,
            "holdout_days": int(split.holdout_days),
            "train_days": int(split.train_days),
            "tick_count": len(ticks),
            "ticks_fingerprint": str(ticks_fingerprint or ""),
        }
    return {
        "schema_version": 1,
        "holdout_pct": float(holdout_pct),
        "train": list(split.train),
        "holdout": list(split.holdout),
        "holdout_days": int(split.holdout_days),
        "train_days": int(split.train_days),
    }


def ticks_jsonl(ticks: list[dict[str, Any]]) -> str:
    lines = [json.dumps(item, ensure_ascii=True) for item in ticks]
    return "\n".join(lines) + ("\n" if lines else "")


def purged_from_v1(payload: dict[str, Any]) -> PurgedSplit | None:
    train = payload.get("train")
    holdout = payload.get("holdout")
    if not isinstance(train, list) or not isinstance(holdout, list):
        return None
    return PurgedSplit(
        train=[item for item in train if isinstance(item, dict)],
        holdout=[item for item in holdout if isinstance(item, dict)],
        holdout_days=int(payload.get("holdout_days", 0) or 0),
        train_days=int(payload.get("train_days", 0) or 0),
    )


def purged_from_v2(
    payload: dict[str, Any],
    *,
    ticks: list[dict[str, Any]],
    ticks_fingerprint: str,
) -> PurgedSplit | None:
    train_idx = payload.get("train_indices")
    holdout_idx = payload.get("holdout_indices")
    if not isinstance(train_idx, list) or not isinstance(holdout_idx, list):
        return None
    expected_fp = str(payload.get("ticks_fingerprint") or "")
    if expected_fp and ticks_fingerprint != expected_fp:
        return None
    n = len(ticks)
    try:
        train_pos = [int(i) for i in train_idx]
        holdout_pos = [int(i) for i in holdout_idx]
    except (TypeError, ValueError):
        return None
    if any(i < 0 or i >= n for i in (*train_pos, *holdout_pos)):
        return None
    return PurgedSplit(
        train=[ticks[i] for i in train_pos],
        holdout=[ticks[i] for i in holdout_pos],
        holdout_days=int(payload.get("holdout_days", 0) or 0),
        train_days=int(payload.get("train_days", 0) or 0),
    )


def load_purged_split_payload(
    payload: dict[str, Any],
    *,
    holdout_pct: float,
    ticks: list[dict[str, Any]],
    ticks_fingerprint: str,
) -> PurgedSplit | None:
    cached_pct = float(payload.get("holdout_pct", holdout_pct) or holdout_pct)
    if abs(cached_pct - float(holdout_pct)) > 1e-6:
        return None
    schema = int(payload.get("schema_version") or 1)
    if schema >= SPLIT_CACHE_SCHEMA_VERSION and "train_indices" in payload:
        return purged_from_v2(payload, ticks=ticks, ticks_fingerprint=ticks_fingerprint)
    return purged_from_v1(payload)
