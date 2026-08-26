"""Foundation history SSOT: start 90, stitch, SLA vs rung not ceiling."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

from lumina_core.birth.foundation_history import (
    FOUNDATION_HISTORY_EXPAND_STEPS,
    FOUNDATION_HISTORY_MAX_DAYS,
    FOUNDATION_HISTORY_START_DAYS,
    clamp_foundation_history_ceiling,
    history_window_meets_sla,
    load_foundation_history_ticks,
    prior_quarterly_contract,
    prior_quarterly_contracts,
    resolve_reload_history_days,
    sla_requested_days,
)
from lumina_core.birth.training_window_sla import training_window_sla_ok
from lumina_core.first_boot_ui import resolve_default_max_real_days


def _day_ticks(start: datetime, days: int, *, price: float = 5000.0) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for offset in range(max(1, days)):
        ts = start + timedelta(days=offset)
        rows.append(
            {
                "timestamp": ts.isoformat(),
                "last": price,
                "close": price,
                "volume": 1,
            }
        )
    return rows


@pytest.mark.unit
def test_prior_quarterly_mes_sep26_chain() -> None:
    assert prior_quarterly_contract("MES SEP26") == "MES JUN26"
    assert prior_quarterly_contracts("MES SEP26") == ("MES JUN26", "MES MAR26", "MES DEC25")


@pytest.mark.unit
def test_ssot_start_and_ceiling_independent_of_25k_trades() -> None:
    assert FOUNDATION_HISTORY_START_DAYS == 90
    assert FOUNDATION_HISTORY_EXPAND_STEPS == (90, 180, 365)
    assert FOUNDATION_HISTORY_MAX_DAYS == 365
    assert resolve_default_max_real_days(25_000) == 365
    assert clamp_foundation_history_ceiling(56) == 90
    assert clamp_foundation_history_ceiling(365) == 365


@pytest.mark.unit
def test_sla_requested_days_ignores_ceiling() -> None:
    assert sla_requested_days({"requested_days": 90}) == 90
    assert sla_requested_days({}) == 90
    assert sla_requested_days(None, loaded_requested=90) == 90
    assert training_window_sla_ok(days_loaded=90, requested_days=90) is True
    assert training_window_sla_ok(days_loaded=57, requested_days=90) is False
    assert training_window_sla_ok(days_loaded=90, requested_days=365) is False


@pytest.mark.unit
def test_sla_requested_days_never_uses_thin_actual_as_sport() -> None:
    """Fail-closed: 57/57 must not pass because the sport collapsed to actual."""
    assert sla_requested_days({}, loaded_requested=57) == 90
    assert sla_requested_days({"requested_days": 56}) == 90
    assert sla_requested_days({"requested_days": 90}, loaded_requested=57) == 90
    assert sla_requested_days({"requested_days": 180}) == 180
    assert history_window_meets_sla(actual_days=57, manifest={}) is False
    assert history_window_meets_sla(actual_days=57, manifest={"requested_days": 56}) is False
    assert history_window_meets_sla(actual_days=90, manifest={"requested_days": 90}) is True


@pytest.mark.unit
def test_reload_sport_keeps_expand_rung() -> None:
    assert resolve_reload_history_days({}) == 90
    assert resolve_reload_history_days({"requested_days": 56}) == 90
    assert resolve_reload_history_days({"requested_days": 180}) == 180
    assert resolve_reload_history_days({"requested_days": 365}, ceiling=365) == 365
    assert resolve_reload_history_days({"requested_days": 180}, ceiling=90) == 90


@pytest.mark.unit
def test_stitch_two_contracts_reaches_start_window() -> None:
    front_start = datetime(2026, 6, 19, tzinfo=timezone.utc)
    prior_start = datetime(2026, 3, 20, tzinfo=timezone.utc)

    class _MDS:
        def _app(self) -> Any:
            return type("App", (), {"INSTRUMENT": "MES SEP26"})()

        def load_historical_ohlc_extended(self, **kwargs: Any) -> list[dict[str, Any]]:
            inst = str(kwargs.get("instrument") or "MES SEP26").upper()
            if "JUN26" in inst:
                return _day_ticks(prior_start, 90)
            return _day_ticks(front_start, 57)

    loaded = load_foundation_history_ticks(
        market_data_service=_MDS(),
        runtime=type("Rt", (), {"config": type("Cfg", (), {"instrument": "MES SEP26"})()})(),
        days_back=90,
    )
    assert loaded.requested_days == 90
    assert loaded.stitched is True
    assert "MES JUN26" in loaded.stitched_from
    assert loaded.actual_calendar_days >= 86


@pytest.mark.unit
def test_single_contract_57_days_stays_thin_without_prior_bars() -> None:
    front_start = datetime(2026, 6, 19, tzinfo=timezone.utc)

    class _MDS:
        def _app(self) -> Any:
            return type("App", (), {"INSTRUMENT": "MES SEP26"})()

        def load_historical_ohlc_extended(self, **kwargs: Any) -> list[dict[str, Any]]:
            inst = str(kwargs.get("instrument") or "MES SEP26").upper()
            if "SEP26" in inst:
                return _day_ticks(front_start, 57)
            return []

    loaded = load_foundation_history_ticks(
        market_data_service=_MDS(),
        runtime=type("Rt", (), {"config": type("Cfg", (), {"instrument": "MES SEP26"})()})(),
        days_back=90,
    )
    assert loaded.actual_calendar_days == 57
    assert training_window_sla_ok(
        days_loaded=loaded.actual_calendar_days,
        requested_days=loaded.requested_days,
    ) is False


@pytest.mark.unit
def test_load_fn_requests_start_rung_not_ceiling() -> None:
    seen: list[int] = []

    def _load(**kwargs: Any) -> list[dict[str, Any]]:
        seen.append(int(kwargs.get("days_back") or 0))
        start = datetime(2026, 5, 1, tzinfo=timezone.utc)
        return _day_ticks(start, 90)

    loaded = load_foundation_history_ticks(
        market_data_service=object(),
        runtime=object(),
        days_back=FOUNDATION_HISTORY_START_DAYS,
        load_fn=_load,
    )
    assert seen
    assert seen[0] == 90
    assert loaded.requested_days == 90
    assert loaded.actual_calendar_days >= 86


@pytest.mark.unit
def test_history_depth_fail_message_includes_chain() -> None:
    from lumina_core.birth.foundation_history import history_depth_fail_message

    msg = history_depth_fail_message(
        requested_days=90,
        actual_days=57,
        instruments=("MES SEP26", "MES JUN26"),
        stitched_from=("MES JUN26",),
    )
    assert "57/90" in msg
    assert "MES SEP26" in msg
    assert "MES JUN26" in msg
    assert "thin front-month" in msg
