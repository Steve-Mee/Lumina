"""Disk cache for tick enrichment features (regime map output)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from lumina_core.birth.tick_cache_persist import _atomic_write_text, compute_ticks_fingerprint
from lumina_core.rl.trend_features import ENRICH_VERSION, regime_from_strength

_FEATURE_KEYS = (
    "trend_regime_strength",
    "trend_adx_7",
    "trend_adx_14",
    "trend_adx_21",
    "trend_slope_5",
    "trend_slope_15",
    "trend_slope_30",
    "trend_slope_60",
    "trend_direction",
    "trend_duration_norm",
    "trend_atr_norm",
    "trend_atr_ratio",
)


def _cache_dir(workspace_root: Path | str) -> Path:
    return Path(workspace_root) / "state" / "birth_enrichment_cache"


def _cache_key_path(workspace_root: Path | str, *, raw_ticks_hash: str, enrich_version: str) -> Path:
    safe = f"{raw_ticks_hash}_{enrich_version}".replace("/", "_")
    return _cache_dir(workspace_root) / f"{safe}.npz"


def _meta_path(npz_path: Path) -> Path:
    return npz_path.with_suffix(".meta.json")


def save_enrichment_cache(
    workspace_root: Path | str,
    *,
    ticks: list[dict[str, Any]],
    raw_ticks_hash: str | None = None,
    enrich_version: str = ENRICH_VERSION,
) -> str | None:
    if not ticks:
        return None
    raw_hash = str(raw_ticks_hash or compute_ticks_fingerprint(ticks)).strip()
    if not raw_hash:
        return None
    n = len(ticks)
    arrays: dict[str, np.ndarray] = {}
    for key in _FEATURE_KEYS:
        arrays[key] = np.array([float(t.get(key, 0.0) or 0.0) for t in ticks], dtype=np.float64)
    regimes = np.array(
        [str(t.get("regime", "NEUTRAL") or "NEUTRAL") for t in ticks],
        dtype=object,
    )
    path = _cache_key_path(workspace_root, raw_ticks_hash=raw_hash, enrich_version=enrich_version)
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, regimes=regimes, **arrays)
    _atomic_write_text(
        _meta_path(path),
        json.dumps(
            {
                "raw_ticks_hash": raw_hash,
                "enrich_version": enrich_version,
                "tick_count": n,
            },
            ensure_ascii=True,
        ),
    )
    return str(path)


def load_enrichment_cache(
    workspace_root: Path | str,
    *,
    raw_ticks_hash: str,
    tick_count: int,
    enrich_version: str = ENRICH_VERSION,
) -> dict[str, Any] | None:
    path = _cache_key_path(workspace_root, raw_ticks_hash=raw_ticks_hash, enrich_version=enrich_version)
    if not path.is_file():
        return None
    try:
        data = np.load(path, allow_pickle=True)
    except (OSError, ValueError):
        return None
    if int(data["trend_regime_strength"].shape[0]) != int(tick_count):
        return None
    return {key: data[key] for key in _FEATURE_KEYS} | {"regimes": data["regimes"]}


def apply_enrichment_cache(ticks: list[dict[str, Any]], cached: dict[str, Any]) -> list[dict[str, Any]]:
    for i, tick in enumerate(ticks):
        for key in _FEATURE_KEYS:
            tick[key] = float(cached[key][i])
        tick["regime"] = str(cached["regimes"][i])
    return ticks


def try_apply_enrichment_cache(
    workspace_root: Path | str,
    ticks: list[dict[str, Any]],
    *,
    raw_ticks_hash: str | None = None,
    enrich_version: str = ENRICH_VERSION,
) -> bool:
    raw_hash = str(raw_ticks_hash or compute_ticks_fingerprint(ticks)).strip()
    if not raw_hash:
        return False
    cached = load_enrichment_cache(
        workspace_root,
        raw_ticks_hash=raw_hash,
        tick_count=len(ticks),
        enrich_version=enrich_version,
    )
    if cached is None:
        return False
    apply_enrichment_cache(ticks, cached)
    return True


def strip_trend_enrichment(ticks: list[dict[str, Any]]) -> None:
    for tick in ticks:
        for key in _FEATURE_KEYS:
            tick.pop(key, None)


def finalize_enrichment_cache(
    workspace_root: Path | str,
    ticks: list[dict[str, Any]],
    *,
    raw_ticks_hash: str | None = None,
    enrich_version: str = ENRICH_VERSION,
) -> None:
    for i, tick in enumerate(ticks):
        if "regime" not in tick or not str(tick.get("regime", "")).strip():
            strength = float(tick.get("trend_regime_strength", 0.0) or 0.0)
            tick["regime"] = regime_from_strength(strength)
        tick.setdefault("bar_index", i)
    save_enrichment_cache(
        workspace_root,
        ticks=ticks,
        raw_ticks_hash=raw_ticks_hash,
        enrich_version=enrich_version,
    )
