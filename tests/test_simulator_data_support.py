from __future__ import annotations

from lumina_core.evolution.simulator_data_support import (
    MIN_SIMULATOR_BARS,
    fallback_synthetic_bars,
    resolve_neuro_simulator_rows_for_neuro_cycle,
    validate_simulator_bars,
)


def test_validate_simulator_bars_accepts_close_series() -> None:
    bars = [{"close": 100.0 + i * 0.01, "last": 100.0 + i * 0.01} for i in range(100)]
    ok, reason = validate_simulator_bars(bars)
    assert ok
    assert reason == "ok"


def test_validate_simulator_bars_rejects_too_short() -> None:
    bars = [{"close": 1.0, "last": 1.0} for _ in range(10)]
    ok, reason = validate_simulator_bars(bars)
    assert not ok
    assert reason == "too_short"


def test_fallback_synthetic_meets_min_length() -> None:
    bars = fallback_synthetic_bars({"net_pnl": 1.0}, n=600)
    assert len(bars) >= MIN_SIMULATOR_BARS
    ok, _ = validate_simulator_bars(bars)
    assert ok


def test_resolve_strict_fails_closed_without_real_data() -> None:
    rows, source, skip = resolve_neuro_simulator_rows_for_neuro_cycle(
        {"net_pnl": 1.0, "max_drawdown": 0.1},
        engine=None,
        neuro_cfg={"require_real_simulator_data": True},
    )
    assert skip is not None
    assert skip.startswith("strict_missing_real_data:")
    assert rows == []
    assert source == "none"


def test_coerce_rl_training_raises_when_strict_and_no_historical(monkeypatch) -> None:
    monkeypatch.setattr(
        "lumina_core.evolution.simulator_data_support._neuro_section",
        lambda: {
            "require_real_simulator_data": True,
            "max_bars_in_report": 12000,
            "fetch_days_back": 90,
            "fetch_limit": 20000,
        },
    )
    import pytest

    from lumina_core.evolution.simulator_data_support import coerce_rl_training_bars

    with pytest.raises(RuntimeError, match="historical OHLC"):
        coerce_rl_training_bars(None, [], nightly_context=None)


def test_resolve_uses_simulator_data_when_valid() -> None:
    data = [{"close": 50.0 + i * 0.1, "last": 50.0 + i * 0.1} for i in range(100)]
    rows, source, skip = resolve_neuro_simulator_rows_for_neuro_cycle(
        {"simulator_data": data, "neuro_simulator_data_source": "simulator_data"},
        engine=None,
        neuro_cfg={},
    )
    assert skip is None
    assert len(rows) >= MIN_SIMULATOR_BARS
    assert source == "simulator_data"
