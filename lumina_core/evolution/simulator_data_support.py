"""RL / neuroevolution simulator bar contract, validation, and real-data hydration.

``RLTradingEnvironment`` expects a list of dict rows with ``close`` or ``last`` (see
``lumina_core.rl``). Nightly reports should carry ``simulator_data`` when possible;
this module fetches OHLC from ``MarketDataService`` when missing.
"""

from __future__ import annotations

import hashlib
import json
import logging
import random
from typing import Any

from lumina_core.config_loader import ConfigLoader

logger = logging.getLogger(__name__)

MIN_SIMULATOR_BARS = 80


def validate_simulator_bars(data: Any) -> tuple[bool, str]:
    """Return (ok, reason_code)."""
    if not isinstance(data, list):
        return False, "not_a_list"
    if len(data) < MIN_SIMULATOR_BARS:
        return False, "too_short"
    nonzero = 0
    for i, row in enumerate(data[: min(500, len(data))]):
        if not isinstance(row, dict):
            return False, f"row_{i}_not_dict"
        px = float(row.get("close") or row.get("last") or 0.0)
        if px > 0.0:
            nonzero += 1
    if nonzero < max(20, MIN_SIMULATOR_BARS // 4):
        return False, "insufficient_valid_prices"
    return True, "ok"


def normalize_simulator_bars(data: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Ensure close/last and optional OHLC for each row; drop invalid rows."""
    out: list[dict[str, Any]] = []
    for row in data:
        if not isinstance(row, dict):
            continue
        c = float(row.get("close") or row.get("last") or 0.0)
        if c <= 0.0:
            continue
        r = dict(row)
        r["close"] = c
        r["last"] = float(r.get("last") or c)
        o = float(r.get("open") or c)
        h = float(r.get("high") or max(o, c))
        l_ = float(r.get("low") or min(o, c))
        r["open"], r["high"], r["low"] = o, h, l_
        out.append(r)
    return out


def fallback_synthetic_bars(nightly_report: dict[str, Any], n: int = 600) -> list[dict[str, Any]]:
    """Deterministic OHLC when no real data (must match evolution orchestrator semantics)."""
    payload = json.dumps(nightly_report, sort_keys=True, ensure_ascii=True, default=str)
    seed = int(hashlib.sha256(payload.encode("utf-8")).hexdigest()[:8], 16)
    rng = random.Random(seed)
    price = 5000.0
    bars: list[dict[str, Any]] = []
    for _ in range(max(n, MIN_SIMULATOR_BARS)):
        chg = rng.gauss(0, 0.002) * price
        close = max(1.0, price + chg)
        open_ = price
        high = max(open_, close) * (1.0 + abs(rng.gauss(0, 0.0005)))
        low = min(open_, close) * (1.0 - abs(rng.gauss(0, 0.0005)))
        bars.append({"close": close, "last": close, "open": open_, "high": high, "low": low})
        price = close
    return bars


def _bars_from_ohlc_dataframe(df: Any) -> list[dict[str, Any]]:
    import pandas as pd

    if df is None or not isinstance(df, pd.DataFrame) or len(df) < MIN_SIMULATOR_BARS:
        return []
    out: list[dict[str, Any]] = []
    for _, r in df.iterrows():
        ts = r.get("timestamp")
        if hasattr(ts, "isoformat"):
            ts_s = ts.isoformat()
        else:
            ts_s = str(ts or "")
        c = float(r.get("close") or 0.0)
        if c <= 0.0:
            continue
        o = float(r.get("open") or c)
        h = float(r.get("high") or c)
        l_ = float(r.get("low") or c)
        out.append(
            {
                "timestamp": ts_s,
                "open": o,
                "high": h,
                "low": l_,
                "close": c,
                "last": c,
                "volume": int(r.get("volume") or 0),
            }
        )
    return out


def fetch_market_bars_for_rl(engine: Any, neuro_cfg: dict[str, Any]) -> tuple[list[dict[str, Any]] | None, str]:
    """Load historical OHLC via MarketDataService; returns (rows, reason_tag)."""
    if engine is None:
        return None, "no_engine"
    mds = getattr(engine, "market_data_service", None)
    if mds is None:
        return None, "no_market_data_service"

    days_back = max(7, int(neuro_cfg.get("fetch_days_back", 90) or 90))
    limit = max(MIN_SIMULATOR_BARS, int(neuro_cfg.get("fetch_limit", 20000) or 20000))
    cfg = getattr(engine, "config", None)
    instrument = str(getattr(cfg, "instrument", "MES") or "MES") if cfg is not None else "MES"

    if not hasattr(mds, "load_historical_ohlc_for_symbol"):
        return None, "no_load_historical_ohlc_for_symbol"

    try:
        df = mds.load_historical_ohlc_for_symbol(instrument, days_back=days_back, limit=limit)
    except Exception as exc:
        logger.warning("[NEURO_DATA] market fetch failed: %s", exc)
        return None, f"fetch_error:{type(exc).__name__}"

    rows = _bars_from_ohlc_dataframe(df)
    ok, code = validate_simulator_bars(rows)
    if not ok:
        return None, f"fetch_invalid:{code}"
    return rows, "market_historical"


def _neuro_section() -> dict[str, Any]:
    raw = ConfigLoader.section("evolution", "neuroevolution", default={})
    return raw if isinstance(raw, dict) else {}


def require_real_simulator_data_strict() -> bool:
    """When True: no synthetic OHLC for RL training or neuro rollouts; use historical fetch only."""
    return bool(_neuro_section().get("require_real_simulator_data", False))


def filter_non_synthetic_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Drop rows explicitly tagged as synthetic (e.g. InfiniteSimulator tick stream)."""
    out: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        if str(row.get("source", "")).strip().lower() == "synthetic":
            continue
        out.append(row)
    return out


def coerce_rl_training_bars(
    engine: Any,
    simulator_data: list[dict[str, Any]] | None,
    *,
    nightly_context: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Normalize and validate bars for PPO / RLTradingEnvironment.

    If ``require_real_simulator_data`` is true in config, never injects synthetic OHLC;
    raises ``RuntimeError`` if historical bars cannot be obtained.
    """
    neuro_cfg = _neuro_section()
    cap = max(MIN_SIMULATOR_BARS, int(neuro_cfg.get("max_bars_in_report", 12000) or 12000))
    strict = bool(neuro_cfg.get("require_real_simulator_data", False))

    data = filter_non_synthetic_rows(list(simulator_data or []))
    ok, reason = validate_simulator_bars(data)

    if not ok and engine is not None:
        rows, tag = fetch_market_bars_for_rl(engine, neuro_cfg)
        if rows:
            data = rows
            ok, reason = validate_simulator_bars(data)
            logger.info("[RL_TRAIN] loaded %d bars from market (%s)", len(data), tag)

    if not ok:
        if strict:
            raise RuntimeError(
                "RL training requires historical OHLC (evolution.neuroevolution.require_real_simulator_data=true). "
                f"Validation/fetch failed: {reason}"
            )
        ctx = nightly_context if isinstance(nightly_context, dict) else {}
        data = fallback_synthetic_bars(ctx, n=max(600, cap))
        logger.warning("[RL_TRAIN] using synthetic OHLC fallback (require_real_simulator_data=false)")

    norm = normalize_simulator_bars(data)
    return norm[-cap:]


def enrich_nightly_report_simulator_data(report: dict[str, Any], engine: Any) -> None:
    """Mutate ``report`` to add validated ``simulator_data`` when possible; set ``neuro_simulator_data_source``."""
    neuro_cfg = _neuro_section()
    cap = max(MIN_SIMULATOR_BARS, int(neuro_cfg.get("max_bars_in_report", 12000) or 12000))

    ok, _ = validate_simulator_bars(report.get("simulator_data"))
    if ok:
        norm = normalize_simulator_bars(report["simulator_data"])  # type: ignore[arg-type]
        report["simulator_data"] = norm[-cap:]
        report["neuro_simulator_data_source"] = str(report.get("neuro_simulator_data_source") or "simulator_data")
        return

    ok_samples, _ = validate_simulator_bars(report.get("samples"))
    if ok_samples:
        norm = normalize_simulator_bars(report["samples"])  # type: ignore[arg-type]
        report["simulator_data"] = norm[-cap:]
        report["neuro_simulator_data_source"] = "samples"
        return

    rows, tag = fetch_market_bars_for_rl(engine, neuro_cfg)
    if rows:
        report["simulator_data"] = rows[-cap:]
        report["neuro_simulator_data_source"] = tag
        logger.info("[NEURO_DATA] hydrated simulator_data from %s (%d bars)", tag, len(report["simulator_data"]))
        return

    if bool(neuro_cfg.get("require_real_simulator_data", False)):
        report["neuro_simulator_data_source"] = "unavailable"
        logger.warning(
            "[NEURO_DATA] strict mode: no historical OHLC in report and market fetch failed (%s); "
            "neuro/RL must not use synthetic",
            tag,
        )
        return

    report["neuro_simulator_data_source"] = "pending_synthetic"
    logger.warning(
        "[NEURO_DATA] no real simulator_data in report and market fetch unavailable (%s); "
        "neuro may use synthetic fallback if require_real_simulator_data is false",
        tag,
    )


def resolve_neuro_simulator_rows_for_neuro_cycle(
    nightly_report: dict[str, Any],
    *,
    engine: Any | None,
    neuro_cfg: dict[str, Any],
) -> tuple[list[dict[str, Any]], str, str | None]:
    """Resolve bars for PPO rollouts: (rows, source_label, strict_skip_reason)."""
    cap = max(MIN_SIMULATOR_BARS, int(neuro_cfg.get("max_bars_in_report", 12000) or 12000))
    strict = bool(neuro_cfg.get("require_real_simulator_data", False))

    src_meta = str(nightly_report.get("neuro_simulator_data_source") or "")

    ok, code = validate_simulator_bars(nightly_report.get("simulator_data"))
    if ok:
        rows = normalize_simulator_bars(nightly_report["simulator_data"])  # type: ignore[arg-type]
        label = (
            src_meta
            if src_meta in {"simulator_data", "samples", "market_historical", "simulator_real_ticks"}
            else "simulator_data"
        )
        return rows[-cap:], label, None

    ok_s, _ = validate_simulator_bars(nightly_report.get("samples"))
    if ok_s:
        rows = normalize_simulator_bars(nightly_report["samples"])  # type: ignore[arg-type]
        return rows[-cap:], "samples", None

    if engine is not None:
        rows, tag = fetch_market_bars_for_rl(engine, neuro_cfg)
        if rows:
            return rows[-cap:], tag, None
        if strict:
            return [], "none", f"strict_missing_real_data:{tag}"

    if strict:
        return [], "none", f"strict_missing_real_data:{code}"

    syn = fallback_synthetic_bars(nightly_report, n=max(600, cap))
    logger.warning("[NEURO_DATA] using synthetic fallback (%d bars)", len(syn))
    return syn, "synthetic", None
