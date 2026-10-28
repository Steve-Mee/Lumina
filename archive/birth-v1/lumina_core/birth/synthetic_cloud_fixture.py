"""Certified-schema synthetic NQ tape for headless Birth (Cursor Cloud).

Writes the REAL tick-cache / split / manifest files the engine already consumes
(``tick_cache_persist.save_birth_data_cache``). Not a parallel toy format.

Source label is honest: ``synthetic_cloud_fixture``. This is SIM / shadow data —
never REAL, never Fabric. Certificate ``min_real_data_pct`` will fail; that is
Proving Ground, not Birth exit (ADR-0036).
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping
from zoneinfo import ZoneInfo

import numpy as np

from lumina_core.birth.foundation_history import FOUNDATION_HISTORY_START_DAYS
from lumina_core.birth.history_loader import actual_calendar_days_from_ticks
from lumina_core.birth.preflight import regime_labels
from lumina_core.birth.purged_split import purged_train_holdout_split
from lumina_core.birth.tick_cache_persist import (
    compute_ticks_fingerprint,
    save_birth_data_cache,
)
from lumina_core.birth.tick_enricher import enrich_ticks_for_sim
from lumina_core.rl.trend_features import ENRICH_VERSION

SOURCE_LABEL = "synthetic_cloud_fixture"
DEFAULT_INSTRUMENT = "NQ SEP26"
DEFAULT_START_PRICE = 21_150.0
NQ_TICK_SIZE = 0.25
ET = ZoneInfo("America/New_York")
SCHEMA_VERSION = "cloud_fixture_v1"

# Enricher vocabulary (trend_features_batch.regime_from_strength).
REGIME_TREND_UP = "TREND_UP"
REGIME_TREND_DOWN = "TREND_DOWN"
REGIME_RANGE = "NEUTRAL"


@dataclass(frozen=True, slots=True)
class CloudFixtureSpec:
    instrument: str = DEFAULT_INSTRUMENT
    calendar_days: int = FOUNDATION_HISTORY_START_DAYS
    holdout_pct: float = 0.20
    start_price: float = DEFAULT_START_PRICE
    seed: int = 20260902
    # 10s RTH + 60s ETH → ~200k ticks over 90 CME days.
    rth_bar_seconds: int = 10
    eth_bar_seconds: int = 60
    start_et: datetime | None = None


@dataclass(frozen=True, slots=True)
class CloudFixtureResult:
    ticks: list[dict[str, Any]]
    split: Any
    manifest_path: str
    ticks_path: str
    split_path: str
    fixture_manifest: dict[str, Any]


def _round_tick(price: float) -> float:
    return round(float(price) / NQ_TICK_SIZE) * NQ_TICK_SIZE


def _is_cme_open(ts_et: datetime) -> bool:
    wd = ts_et.weekday()  # Mon=0 … Sun=6
    minutes = ts_et.hour * 60 + ts_et.minute
    halt = 17 * 60 <= minutes < 18 * 60
    if wd == 5:
        return False
    if wd == 6:
        return minutes >= 18 * 60
    if wd == 4:
        return minutes < 17 * 60
    # Mon–Thu
    return not halt


def _is_rth(ts_et: datetime) -> bool:
    if ts_et.weekday() >= 5:
        return False
    minutes = ts_et.hour * 60 + ts_et.minute
    return (9 * 60 + 30) <= minutes < (16 * 60)


def _iter_session_times(
    *,
    start_et: datetime,
    calendar_days: int,
    rth_bar_seconds: int,
    eth_bar_seconds: int,
) -> list[datetime]:
    """CME equity-index Globex: RTH + ETH, daily 17:00–18:00 ET halt, weekend gap."""
    end_et = start_et + timedelta(days=int(calendar_days))
    out: list[datetime] = []
    t = start_et.replace(second=0, microsecond=0)
    # Align to Sunday 18:00 ET if the start is mid-week closed.
    if not _is_cme_open(t):
        while t < end_et and not _is_cme_open(t):
            t += timedelta(minutes=1)
    while t < end_et:
        if _is_cme_open(t):
            out.append(t)
            step = rth_bar_seconds if _is_rth(t) else eth_bar_seconds
            t = t + timedelta(seconds=max(1, int(step)))
        else:
            t = t + timedelta(minutes=1)
    return out


def _regime_for_index(i: int, n: int) -> str:
    """Cycle trend-up / trend-down / range so holdout (last 20%) still has all three."""
    # Six equal phase blocks across the tape, repeating.
    phase = int((i / max(1, n)) * 18.0) % 3
    if phase == 0:
        return REGIME_TREND_UP
    if phase == 1:
        return REGIME_TREND_DOWN
    return REGIME_RANGE


def generate_cloud_fixture_ticks(spec: CloudFixtureSpec | None = None) -> list[dict[str, Any]]:
    spec = spec or CloudFixtureSpec()
    start_et = spec.start_et or datetime(2026, 6, 1, 18, 0, tzinfo=ET)
    stamps = _iter_session_times(
        start_et=start_et,
        calendar_days=spec.calendar_days,
        rth_bar_seconds=spec.rth_bar_seconds,
        eth_bar_seconds=spec.eth_bar_seconds,
    )
    if len(stamps) < 1_000:
        raise RuntimeError(
            f"cloud fixture too thin: {len(stamps)} bars (need ≥1000 for certified cache)"
        )

    rng = np.random.default_rng(spec.seed)
    n = len(stamps)
    price = float(spec.start_price)
    ewma_var = (0.00018) ** 2
    session_anchor = price
    last_et_date = stamps[0].date()
    ticks: list[dict[str, Any]] = []
    prev_ts_utc: datetime | None = None

    for i, ts_et in enumerate(stamps):
        if ts_et.date() != last_et_date:
            # Overnight / weekend gap — fat-tailed jump, then re-anchor.
            gap = float(rng.standard_t(5) * 0.003)
            price = max(1_000.0, price * (1.0 + gap))
            session_anchor = price
            last_et_date = ts_et.date()
            ewma_var = min(ewma_var * 1.4, 4e-7)

        rth = _is_rth(ts_et)
        minutes = ts_et.hour * 60 + ts_et.minute
        near_open = rth and (9 * 60 + 30) <= minutes < (9 * 60 + 40)
        near_close = rth and (15 * 60 + 50) <= minutes < (16 * 60)
        intended = _regime_for_index(i, n)

        shock = float(rng.standard_t(5))
        ewma_var = 0.94 * ewma_var + 0.06 * (shock * 0.00022) ** 2
        sigma = math.sqrt(max(ewma_var, 1e-10))
        if not rth:
            sigma *= 0.55
        if near_open:
            sigma *= 1.8

        if intended == REGIME_TREND_UP:
            drift = 0.000045 if rth else 0.000012
            ret = drift + sigma * shock
        elif intended == REGIME_TREND_DOWN:
            drift = -0.000045 if rth else -0.000012
            ret = drift + sigma * shock
        else:
            # Inventory-like mean reversion around the session anchor.
            kappa = 0.08
            ret = -kappa * math.log(max(price, 1.0) / max(session_anchor, 1.0)) + sigma * shock

        price = max(1_000.0, _round_tick(price * (1.0 + ret)))
        half_range = max(NQ_TICK_SIZE, abs(shock) * sigma * price * 8.0)
        high = _round_tick(price + half_range)
        low = _round_tick(max(NQ_TICK_SIZE, price - half_range))

        vol_burst = near_open or (sigma > 0.0004)
        if rth:
            volume = int(rng.integers(400, 2_400))
            if vol_burst:
                volume = int(rng.integers(4_000, 16_000))
        else:
            volume = int(rng.integers(40, 280))

        spread_ticks = 1.0
        if near_open or near_close:
            spread_ticks = 4.0
        elif vol_burst:
            spread_ticks = 3.0
        elif not rth:
            spread_ticks = 2.0
        spread = spread_ticks * NQ_TICK_SIZE
        bid = _round_tick(price - spread / 2.0)
        ask = _round_tick(price + spread / 2.0)
        if ask <= bid:
            ask = bid + NQ_TICK_SIZE

        ts_utc = ts_et.astimezone(timezone.utc)
        if prev_ts_utc is not None and ts_utc <= prev_ts_utc:
            ts_utc = prev_ts_utc + timedelta(milliseconds=1)
        prev_ts_utc = ts_utc

        ticks.append(
            {
                "timestamp": ts_utc.isoformat(),
                "last": float(price),
                "close": float(price),
                "open": float(price),
                "high": float(high),
                "low": float(low),
                "bid": float(bid),
                "ask": float(ask),
                "volume": int(volume),
                "regime": intended,
                "imbalance": 1.0,
                "source": SOURCE_LABEL,
                "instrument": spec.instrument,
                "session": "RTH" if rth else "ETH",
            }
        )
    return ticks


def _assert_tape_sane(ticks: list[dict[str, Any]]) -> None:
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
) -> CloudFixtureResult:
    """Enrich with the engine enricher, purged-split, write certified cache files."""
    spec = spec or CloudFixtureSpec()
    root = Path(workspace_root)
    root.mkdir(parents=True, exist_ok=True)
    (root / "state").mkdir(parents=True, exist_ok=True)

    raw = list(ticks) if ticks is not None else generate_cloud_fixture_ticks(spec)
    _assert_tape_sane(raw)
    raw_hash = compute_ticks_fingerprint(raw)
    enriched = enrich_ticks_for_sim(
        [dict(t) for t in raw],
        workspace_root=root,
        raw_ticks_hash=raw_hash,
        enrich_version=ENRICH_VERSION,
    )
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
    # Stamp honest source + holdout regimes onto the SSOT manifest (extra keys are kept).
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
    """Serves the on-disk fixture if the engine cold-loads instead of cache-hitting.

    Implements the ``load_historical_ohlc_extended`` surface used by
    ``history_loader.load_historical_ticks``. Never talks to Fabric/NT.
    """

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
    "SOURCE_LABEL",
    "DEFAULT_INSTRUMENT",
    "CloudFixtureSpec",
    "CloudFixtureResult",
    "FixtureMarketDataService",
    "generate_cloud_fixture_ticks",
    "persist_cloud_fixture",
    "write_fixture_sidecar",
]
