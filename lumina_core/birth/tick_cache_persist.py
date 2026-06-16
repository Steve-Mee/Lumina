"""Persist birth tick cache for manifest-based reuse (BRO v2 PR-T2)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from lumina_core.birth.purged_split import PurgedSplit


def ticks_cache_path(workspace_root: Path | str) -> Path:
    return Path(workspace_root) / "state" / "lumina_birth_ticks_cache.jsonl"


def split_cache_path(workspace_root: Path | str) -> Path:
    return Path(workspace_root) / "state" / "lumina_birth_split_cache.json"


def save_ticks_cache(workspace_root: Path | str, ticks: list[dict[str, Any]]) -> str:
    path = ticks_cache_path(workspace_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(item, ensure_ascii=True) for item in ticks]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
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
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "holdout_pct": float(holdout_pct),
        "train": list(split.train),
        "holdout": list(split.holdout),
        "holdout_days": int(split.holdout_days),
        "train_days": int(split.train_days),
    }
    path.write_text(json.dumps(payload, ensure_ascii=True), encoding="utf-8")
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


def clear_ticks_cache(workspace_root: Path | str) -> None:
    for path in (ticks_cache_path(workspace_root), split_cache_path(workspace_root)):
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
