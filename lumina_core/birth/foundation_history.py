"""Birth Foundation history depth SSOT (ADR-0046).

Start window, expand ladder, and prior-quarterly stitch. Not sized from
trade-budget / 450-trades-per-day. Replay cap lives in foundation_metrics.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from lumina_core.birth.history_loader import actual_calendar_days_from_ticks
from lumina_core.logging_utils import get_logger
from lumina_core.order_gatekeeper.contract_symbols import (
    MONTH_CODE_BY_NUM,
    QUARTERLY_MONTH_CODES,
    parse_contract_symbol,
)

logger = get_logger("lumina.birth.foundation_history")

FOUNDATION_HISTORY_START_DAYS = 90
FOUNDATION_HISTORY_EXPAND_STEPS: tuple[int, ...] = (90, 180, 365)
FOUNDATION_HISTORY_MAX_DAYS = 365
FOUNDATION_HISTORY_HARD_CAP_DAYS = 3650
FOUNDATION_HISTORY_MIN_RATIO = 0.95
FOUNDATION_HISTORY_MAX_PRIOR_CONTRACTS = 3

LoadTicksFn = Callable[..., list[dict[str, Any]]]


def foundation_history_start_days() -> int:
    return FOUNDATION_HISTORY_START_DAYS


def foundation_history_max_days() -> int:
    return FOUNDATION_HISTORY_MAX_DAYS


def foundation_history_expand_steps() -> tuple[int, ...]:
    return FOUNDATION_HISTORY_EXPAND_STEPS


def clamp_foundation_history_ceiling(raw: int | None) -> int:
    """Operator/yaml ceiling: never below start rung, never above hardware hard cap."""
    fallback = FOUNDATION_HISTORY_MAX_DAYS
    try:
        value = int(raw) if raw is not None else fallback
    except (TypeError, ValueError):
        value = fallback
    return max(
        FOUNDATION_HISTORY_START_DAYS,
        min(FOUNDATION_HISTORY_HARD_CAP_DAYS, value),
    )


def prior_quarterly_contract(symbol: str) -> str | None:
    """Previous CME quarterly (MES SEP26 → MES JUN26). None if unparseable."""
    root, month, year = parse_contract_symbol(symbol)
    if root is None or month is None or year is None:
        return None
    month_code = MONTH_CODE_BY_NUM.get(int(month))
    if month_code not in QUARTERLY_MONTH_CODES:
        return None
    idx = QUARTERLY_MONTH_CODES.index(month_code)
    prev_code = QUARTERLY_MONTH_CODES[(idx - 1) % len(QUARTERLY_MONTH_CODES)]
    prev_year = int(year) - (1 if month_code == "MAR" else 0)
    return f"{root} {prev_code}{prev_year % 100:02d}"


def prior_quarterly_contracts(
    symbol: str,
    *,
    count: int = FOUNDATION_HISTORY_MAX_PRIOR_CONTRACTS,
) -> tuple[str, ...]:
    out: list[str] = []
    current = str(symbol or "").strip().upper()
    seen = {current}
    for _ in range(max(0, int(count))):
        prev = prior_quarterly_contract(current)
        if prev is None or prev in seen:
            break
        out.append(prev)
        seen.add(prev)
        current = prev
    return tuple(out)


def merge_ticks_by_timestamp(
    primary: list[dict[str, Any]],
    extra: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Keep primary rows on timestamp collision; append older-contract bars."""
    seen: set[str] = set()
    merged: list[dict[str, Any]] = []
    for row in list(primary) + list(extra):
        if not isinstance(row, dict):
            continue
        ts = str(row.get("timestamp") or "").strip()
        if not ts or ts in seen:
            continue
        seen.add(ts)
        merged.append(row)
    merged.sort(key=lambda item: str(item.get("timestamp") or ""))
    return merged


def resolve_birth_history_instrument(
    market_data_service: Any,
    runtime: Any,
    explicit: str | None = None,
) -> str:
    text = str(explicit or "").strip().upper()
    if text:
        return text
    getter = getattr(market_data_service, "_app", None)
    if callable(getter):
        try:
            app = getter()
            inst = str(getattr(app, "INSTRUMENT", "") or "").strip().upper()
            if inst:
                return inst
        except Exception:
            pass
    cfg = getattr(runtime, "config", None)
    return str(getattr(cfg, "instrument", "") or "").strip().upper()


@dataclass(frozen=True, slots=True)
class FoundationHistoryLoad:
    ticks: list[dict[str, Any]]
    requested_days: int
    actual_calendar_days: int
    instruments: tuple[str, ...]
    stitched: bool
    stitched_from: tuple[str, ...]


def load_foundation_history_ticks(
    *,
    market_data_service: Any,
    runtime: Any,
    days_back: int,
    instrument: str | None = None,
    min_ratio: float = FOUNDATION_HISTORY_MIN_RATIO,
    limit: int | None = None,
    on_chunk: Callable[..., None] | None = None,
    load_fn: LoadTicksFn | None = None,
) -> FoundationHistoryLoad:
    """Load ``days_back`` calendar days from now; stitch prior quarterlies if the front month is thin.

    Fabric uses an absolute ``now - days_back`` window, so each prior listing is
    fetched for the same calendar span — it fills the missing older part of that
    window, not a separate contract-lifetime slice.
    """
    requested = max(1, int(days_back))
    ratio = max(0.0, min(1.0, float(min_ratio)))
    need = max(1, int(requested * ratio))
    if load_fn is None:
        from lumina_core.birth.history_loader import load_historical_ticks as loader
    else:
        loader = load_fn
    front = resolve_birth_history_instrument(market_data_service, runtime, instrument)

    def _fetch(symbol: str | None) -> list[dict[str, Any]]:
        kwargs: dict[str, Any] = {
            "market_data_service": market_data_service,
            "runtime": runtime,
            "days_back": requested,
            "limit": limit,
            "on_chunk": on_chunk,
        }
        if symbol:
            kwargs["instrument"] = symbol
        return list(loader(**kwargs) or [])

    ticks = _fetch(front or None)
    used: list[str] = [front] if front else []
    stitched_from: list[str] = []
    actual = actual_calendar_days_from_ticks(ticks)
    if actual < need and front:
        for prior in prior_quarterly_contracts(front):
            extra = _fetch(prior)
            if not extra:
                logger.info("birth.history.stitch_empty instrument=%s", prior)
                continue
            ticks = merge_ticks_by_timestamp(ticks, extra)
            used.append(prior)
            stitched_from.append(prior)
            actual = actual_calendar_days_from_ticks(ticks)
            logger.info(
                "birth.history.stitched prior=%s actual_days=%s requested=%s",
                prior,
                actual,
                requested,
            )
            if actual >= need:
                break

    return FoundationHistoryLoad(
        ticks=ticks,
        requested_days=requested,
        actual_calendar_days=actual,
        instruments=tuple(used),
        stitched=bool(stitched_from),
        stitched_from=tuple(stitched_from),
    )


def _valid_history_sport(raw: Any) -> int:
    """Accept only a Foundation sport (≥ start rung). Never a thin actual span."""
    try:
        value = int(raw or 0)
    except (TypeError, ValueError):
        return 0
    if value < FOUNDATION_HISTORY_START_DAYS:
        return 0
    return value


def sla_requested_days(
    manifest: dict[str, Any] | None,
    *,
    loaded_requested: int | None = None,
) -> int:
    """SLA sport = this load's requested days, never the expand ceiling or actual span."""
    raw = dict(manifest or {})
    from_manifest = _valid_history_sport(raw.get("requested_days"))
    if from_manifest:
        return from_manifest
    from_loaded = _valid_history_sport(loaded_requested)
    if from_loaded:
        return from_loaded
    return FOUNDATION_HISTORY_START_DAYS


def resolve_reload_history_days(
    manifest: dict[str, Any] | None,
    *,
    ceiling: int | None = None,
) -> int:
    """Cold-reload sport: keep 180/365 if already there; never shrink below start 90."""
    cap = clamp_foundation_history_ceiling(ceiling)
    requested = sla_requested_days(manifest)
    return max(FOUNDATION_HISTORY_START_DAYS, min(cap, requested))


def history_window_meets_sla(
    *,
    actual_days: int,
    manifest: dict[str, Any] | None = None,
    loaded_requested: int | None = None,
    min_ratio: float = FOUNDATION_HISTORY_MIN_RATIO,
) -> bool:
    """Fail-closed: missing/thin requested_days never compare actual to itself."""
    from lumina_core.birth.training_window_sla import training_window_sla_ok

    requested = sla_requested_days(manifest, loaded_requested=loaded_requested)
    return training_window_sla_ok(
        days_loaded=int(actual_days),
        requested_days=requested,
        min_ratio=float(min_ratio),
    )


def history_depth_fail_message(
    *,
    requested_days: int,
    actual_days: int,
    instruments: Any = None,
    stitched_from: Any = None,
    min_ratio: float = FOUNDATION_HISTORY_MIN_RATIO,
) -> str:
    chain_items = [str(item).strip() for item in (instruments or ()) if str(item).strip()]
    chain = ", ".join(chain_items) if chain_items else "unknown"
    need = max(1, int(round(max(0, int(requested_days)) * float(min_ratio))))
    prior = [str(item).strip() for item in (stitched_from or ()) if str(item).strip()]
    stitch_bit = f" stitched_from={', '.join(prior)}." if prior else ""
    return (
        f"History unavailable: loaded {int(actual_days)}/{int(requested_days)} calendar days "
        f"(need ≥{need}, min ratio {float(min_ratio):.0%}) via {chain}.{stitch_bit} "
        "No silent Stage-1 on a thin front-month tape."
    )


def apply_expansion_history_manifest(
    manifest: dict[str, Any],
    expanded: Any,
    *,
    days_loaded: int,
) -> None:
    manifest["requested_days"] = int(getattr(expanded, "requested_days", 0) or 0)
    manifest["actual_calendar_days"] = int(getattr(expanded, "actual_calendar_days", 0) or 0)
    manifest["days_loaded"] = int(days_loaded)
    manifest["stitched"] = bool(getattr(expanded, "stitched", False))
    manifest["instruments"] = list(getattr(expanded, "instruments", ()) or ())
    manifest["stitched_from"] = list(getattr(expanded, "stitched_from", ()) or ())


def apply_foundation_history_manifest(
    manifest: dict[str, Any],
    loaded: FoundationHistoryLoad,
) -> None:
    manifest["requested_days"] = int(loaded.requested_days)
    manifest["actual_calendar_days"] = int(loaded.actual_calendar_days)
    manifest["instruments"] = list(loaded.instruments)
    manifest["stitched"] = bool(loaded.stitched)
    manifest["stitched_from"] = list(loaded.stitched_from)


__all__ = [
    "FOUNDATION_HISTORY_EXPAND_STEPS",
    "FOUNDATION_HISTORY_HARD_CAP_DAYS",
    "FOUNDATION_HISTORY_MAX_DAYS",
    "FOUNDATION_HISTORY_MAX_PRIOR_CONTRACTS",
    "FOUNDATION_HISTORY_MIN_RATIO",
    "FOUNDATION_HISTORY_START_DAYS",
    "FoundationHistoryLoad",
    "clamp_foundation_history_ceiling",
    "foundation_history_expand_steps",
    "foundation_history_max_days",
    "foundation_history_start_days",
    "apply_expansion_history_manifest",
    "apply_foundation_history_manifest",
    "history_depth_fail_message",
    "history_window_meets_sla",
    "load_foundation_history_ticks",
    "merge_ticks_by_timestamp",
    "sla_requested_days",
    "prior_quarterly_contract",
    "prior_quarterly_contracts",
    "resolve_birth_history_instrument",
    "resolve_reload_history_days",
]
