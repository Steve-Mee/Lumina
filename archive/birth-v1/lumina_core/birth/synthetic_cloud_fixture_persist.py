"""Persist certified-schema synthetic NQ fixture (cache jsonl + split + manifest)."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping

from lumina_core.birth.foundation_history import FOUNDATION_HISTORY_START_DAYS
from lumina_core.birth.history_loader import actual_calendar_days_from_ticks
from lumina_core.birth.preflight import regime_labels
from lumina_core.birth.purged_split import purged_train_holdout_split
from lumina_core.birth.synthetic_cloud_fixture import (
    SCHEMA_VERSION,
    SOURCE_LABEL,
    CloudFixtureResult,
    CloudFixtureSpec,
    generate_cloud_fixture_ticks,
)
from lumina_core.birth.tick_cache_persist import (
    compute_ticks_fingerprint,
    save_birth_data_cache,
)
from lumina_core.rl.trend_features import ENRICH_VERSION


def assert_tape_sane(ticks: list[dict[str, Any]]) -> None:
    if len(ticks) < 1_000:
        raise RuntimeError(f"fixture tick_count {len(ticks)} < 1000")
    prev = ""
    for row in ticks:
        ts = str(row.get("timestamp") or "")
        if not ts or ts <= prev:
            raise RuntimeError("fixture timestamps must be strictly monotonic")
        prev = ts
        last = float(row["last"])
        if not math.isfinite(last) or last <= 0:
            raise RuntimeError("fixture has non-finite or non-positive price")
        bid = float(row["bid"])
        ask = float(row["ask"])
        if ask <= bid:
            raise RuntimeError("fixture bid/ask inverted")
        if str(row.get("source")) != SOURCE_LABEL:
            raise RuntimeError("fixture source label must stay synthetic_cloud_fixture")


def persist_cloud_fixture(
    workspace_root: Path | str,
    *,
    spec: CloudFixtureSpec | None = None,
    ticks: list[dict[str, Any]] | None = None,
    enrich: bool = True,
) -> CloudFixtureResult:
    """Purged-split + certified cache. ``enrich=False`` is unit-test only."""
    spec = spec or CloudFixtureSpec()
    root = Path(workspace_root)
    root.mkdir(parents=True, exist_ok=True)
    (root / "state").mkdir(parents=True, exist_ok=True)

    raw = list(ticks) if ticks is not None else generate_cloud_fixture_ticks(spec)
    assert_tape_sane(raw)
    raw_hash = compute_ticks_fingerprint(raw)
    if enrich:
        from lumina_core.birth.tick_enricher import enrich_ticks_for_sim

        enriched = enrich_ticks_for_sim(
            [dict(t) for t in raw],
            workspace_root=root,
            raw_ticks_hash=raw_hash,
            enrich_version=ENRICH_VERSION,
        )
    else:
        enriched = [dict(t) for t in raw]
    for row in enriched:
        row["source"] = SOURCE_LABEL
    split = purged_train_holdout_split(enriched, holdout_pct=spec.holdout_pct)
    holdout_regimes = sorted(regime_labels(split.holdout))
    train_regimes = sorted(regime_labels(split.train))
    if len(holdout_regimes) < 3:
        raise RuntimeError(
            f"holdout has {len(holdout_regimes)} regimes {holdout_regimes}; need ≥3 "
            f"(train={train_regimes})"
        )
    from lumina_core.birth.data_pipeline_types import train_hash as _train_hash

    t_hash = _train_hash(split.train)
    actual_days = actual_calendar_days_from_ticks(enriched)
    paths = save_birth_data_cache(
        root,
        ticks=enriched,
        split=split,
        holdout_pct=spec.holdout_pct,
        raw_ticks_hash=raw_hash,
        train_hash=t_hash,
        enrich_version=ENRICH_VERSION,
        requested_days=max(FOUNDATION_HISTORY_START_DAYS, spec.calendar_days),
        actual_calendar_days=actual_days,
        instruments=[spec.instrument],
        stitched=False,
        stitched_from=[],
    )
    man_path = Path(paths["cache_manifest_path"])
    payload = json.loads(man_path.read_text(encoding="utf-8"))
    payload.update(
        {
            "source": SOURCE_LABEL,
            "schema_version": SCHEMA_VERSION,
            "instrument": spec.instrument,
            "holdout_regimes": holdout_regimes,
            "train_regimes": train_regimes,
            "preflight_ok": len(holdout_regimes) >= 3 and len(split.holdout) >= 500,
            "real_data_pct": 0.0,
        }
    )
    man_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    fixture_manifest = {
        "symbol": spec.instrument,
        "days": actual_days,
        "requested_days": max(FOUNDATION_HISTORY_START_DAYS, spec.calendar_days),
        "tick_count": len(enriched),
        "train_tick_count": len(split.train),
        "holdout_tick_count": len(split.holdout),
        "regime_counts": _count_regimes(enriched),
        "holdout_regimes": holdout_regimes,
        "train_regimes": train_regimes,
        "hash": t_hash,
        "raw_ticks_hash": raw_hash,
        "schema_version": SCHEMA_VERSION,
        "cache_schema_version": 1,
        "enrich_version": ENRICH_VERSION,
        "path": str(man_path),
        "ticks_path": paths["ticks_cache_path"],
        "split_path": paths["split_cache_path"],
        "source": SOURCE_LABEL,
        "holdout_pct": spec.holdout_pct,
    }
    return CloudFixtureResult(
        ticks=enriched,
        split=split,
        manifest_path=paths["cache_manifest_path"],
        ticks_path=paths["ticks_cache_path"],
        split_path=paths["split_cache_path"],
        fixture_manifest=fixture_manifest,
    )


def _count_regimes(ticks: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in ticks:
        key = str(row.get("regime") or "NEUTRAL").upper()
        counts[key] = counts.get(key, 0) + 1
    return counts


def write_fixture_sidecar(path: Path | str, fixture_manifest: Mapping[str, Any]) -> str:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(dict(fixture_manifest), indent=2, sort_keys=True)
    digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
    payload = dict(fixture_manifest)
    payload["manifest_sha256"] = digest
    out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return str(out)


class FixtureMarketDataService:
    """Serves on-disk fixture ticks. Never talks to Fabric/NT."""

    def __init__(self, ticks: list[dict[str, Any]], *, instrument: str) -> None:
        self._ticks = list(ticks)
        self._instrument = str(instrument).strip().upper()

    def _app(self) -> Any:
        from types import SimpleNamespace

        return SimpleNamespace(INSTRUMENT=self._instrument)

    def load_historical_ohlc_extended(self, **kwargs: Any) -> list[dict[str, Any]]:
        _ = kwargs
        return [dict(t) for t in self._ticks]


__all__ = [
    "FixtureMarketDataService",
    "assert_tape_sane",
    "persist_cloud_fixture",
    "write_fixture_sidecar",
]
