"""Fail-closed source guard: quote-pad / last-fill / tz-strip / 24x7 must stay gone."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_history_does_not_last_fill_or_strip_tz() -> None:
    text = _read("lumina_core/engine/market_data_history.py")
    assert "tz_convert(None)" not in text
    assert 'or bar.get("last")' not in text
    assert "accept_source_bars" in text
    assert "partition_closed_and_forming" in text
    assert "apply_nt_bar(forming" in text
    assert "_fetch_closed_and_forming" in text
    assert "return pd.DataFrame(rows)" not in text
    assert "is_forming_bar" in text


def test_append_ohlc_rows_partitions_forming() -> None:
    text = _read("lumina_core/engine/market_data_manager.py")
    assert "def partition_closed_and_forming" in text
    assert "def append_ohlc_rows" in text
    assert "apply_nt_bar(forming" in text


def test_history_fetch_does_not_last_fill() -> None:
    text = _read("lumina_core/engine/market_data_history_fetch.py")
    assert 'b.get("open") or b.get("last")' not in text
    assert 'b.get("high") or b.get("last")' not in text
    assert 'b.get("low") or b.get("last")' not in text


def test_ingest_drains_nt_bars_not_quote_candles() -> None:
    text = _read("lumina_core/engine/market_data_ingest.py")
    assert "_drain_nt_bars" in text
    assert "take_bar" in text
    assert "tape_is_live" in text
    assert "closed_candle = self.engine.market_data.process_quote_tick" not in text


def test_integrity_excludes_forming_and_windows_nt_tail() -> None:
    text = _read("lumina_core/engine/bar_integrity.py")
    assert "is_forming_bar" in text
    assert "local_in_window" in text
    assert "tape_is_live" in text


def test_historical_provider_no_24x7_or_even_sample() -> None:
    text = _read("integrations/ninjatrader8/LuminaNt8AddOn/NtHistoricalDataProvider.cs")
    lower = text.lower()
    assert 'tradinghours.get("default' not in lower
    assert "even-sample" not in lower
    assert "even sample" not in lower
    assert "k * step" not in lower
    assert "BAR_WINDOW_TOO_LARGE" in text
    assert "TRADING_HOURS_MISSING" in text
    assert "BAR_PERIOD_UNSUPPORTED" in text


def test_live_bar_provider_uses_barsrequest_update() -> None:
    text = _read("integrations/ninjatrader8/LuminaNt8AddOn/NtLiveBarProvider.cs")
    assert "BarsRequest" in text
    assert "request.Update +=" in text
    assert "IsBar = true" in text
    assert "series == None" not in text
    assert "BarPeriod = canonical" in text
    assert "NtBarClock.ToUnixMs" in text


def test_decision_htf_is_not_pandas_resample() -> None:
    assert ".resample(" not in _read("lumina_core/engine/visualization_charts.py")
    assert ".resample(" not in _read("lumina_core/engine/operations_service_market.py")
    assert ".resample(" not in _read("lumina_core/engine/analysis_loop.py")
    assert "MES SEP26" not in _read("lumina_core/engine/engine_config_helpers.py")


def test_chart_ui_is_honest_nt_copy() -> None:
    viz = _read("lumina_core/engine/visualization_charts.py")
    png = _read("lumina_core/engine/chart_png.py")
    window = _read("lumina_core/engine/visualization_charts_window.py")
    assert "geen NT bars" in viz
    assert "geen NT bars" in png
    assert "Wachten op de eerste NT-grafiek" in window
    assert "from SIM bars" not in window
    assert "len(res) < 20" not in viz
    assert "MES {instrument}" not in viz
    assert "from SIM bars" not in viz
    assert "live SIM chart" not in png
    assert "NT-grafiek bijgewerkt" in viz
    assert "LUMINA · {listing}" in viz
    assert "operator_listing" in viz
    assert "listing onbekend" in _read("lumina_core/engine/nt_ohlc_frames.py")
    assert "detect_market_structure(closed_1m)" in viz
