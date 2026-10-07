"""Open-chart listing. The selector wins. The calendar is the unread fallback."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from lumina_core.broker.ninjatrader.open_charts import (
    _is_chart_window_name,
    _selector_hwnds,
    choose_listing,
    clear_open_chart_cache,
    normalize_chart_label,
    read_open_charts,
    subscription_plan,
    world_sentence,
)

NOW = datetime(2026, 9, 28, tzinfo=timezone.utc)


@pytest.mark.unit
def test_normalize_chart_label_accepts_named_and_numeric_months() -> None:
    assert normalize_chart_label("mes dec26") == "MES DEC26"
    assert normalize_chart_label("MES 12-26") == "MES DEC26"
    assert normalize_chart_label("MES") == ""
    assert normalize_chart_label("not a contract") == ""


@pytest.mark.unit
def test_open_chart_replaces_configured_month() -> None:
    listing, source = choose_listing("MES SEP26", ["MES DEC26"], now_utc=NOW)
    assert listing == "MES DEC26"
    assert source == "chart"


@pytest.mark.unit
def test_other_root_does_not_become_the_configured_contract() -> None:
    listing, source = choose_listing("MES SEP26", ["MNQ DEC26"], now_utc=NOW)
    assert listing == ""
    assert source == "other_charts"


@pytest.mark.unit
def test_unread_selector_uses_the_liquid_month() -> None:
    listing, source = choose_listing("MES", [], now_utc=NOW)
    assert listing == "MES DEC26"
    assert source == "calendar"


@pytest.mark.unit
def test_subscription_follows_open_charts_only() -> None:
    primary, symbols, source = subscription_plan(
        "MES SEP26",
        ["MES SEP26", "MNQ SEP26"],
        ["MES DEC26"],
        now_utc=NOW,
    )
    assert source == "chart"
    assert primary == "MES DEC26"
    assert symbols == ["MES DEC26"]


@pytest.mark.unit
def test_world_sentence_names_the_chart_and_the_floor() -> None:
    text = world_sentence(
        charts=["MES DEC26"],
        source="chart",
        listing="MES DEC26",
        seal_note="Dagvloer -2000 = -2% van 100000.",
        last_px=7772.5,
    )
    assert "Chart MES DEC26." in text
    assert "-2%" in text
    assert "7772.50" in text
    assert "Live prijs" in text


@pytest.mark.unit
def test_world_sentence_names_a_stale_tick() -> None:
    text = world_sentence(
        charts=["MES DEC26"],
        source="chart",
        listing="MES DEC26",
        seal_note="Dagvloer -2000 = -2% van cash 100000.",
        last_px=7772.25,
        price_age_sec=90_000.0,
        bar_quiet=True,
        hand_note="Markthand staat uit.",
    )
    assert "oud" in text
    assert "7772.25" in text
    assert "Supervisor-loop publiceert geen nieuwe bar." in text
    assert "Markthand staat uit." in text


@pytest.mark.unit
def test_login_and_shell_windows_are_not_chart_windows() -> None:
    assert _is_chart_window_name("Chart -  1 Minute") is True
    assert _is_chart_window_name("Control Center - Accounts") is False
    assert _is_chart_window_name("Log In") is False
    assert _is_chart_window_name("NinjaTrader") is False
    assert _is_chart_window_name("NINJATRADER") is False


@pytest.mark.unit
def test_selector_walk_skips_login_and_prefers_the_chart_window() -> None:
    login = [
        (1, "NinjaTrader"),
        (2, "Log In"),
        (3, "Control Center - Accounts"),
        (4, "Chart -  1 Minute"),
    ]
    assert _selector_hwnds(login) == [4]
    assert _selector_hwnds([(3, "Control Center - Accounts"), (1, "NINJATRADER")]) == [3]
    assert _selector_hwnds([(1, "NinjaTrader"), (2, "Log In")]) == []


@pytest.mark.unit
def test_chart_walk_is_cached_and_does_not_repeat(monkeypatch: pytest.MonkeyPatch) -> None:
    import lumina_core.broker.ninjatrader.open_charts as charts

    clear_open_chart_cache()
    calls = {"n": 0}

    def _fake() -> list[str]:
        calls["n"] += 1
        return ["MES DEC26"]

    monkeypatch.setattr(charts, "_read_uia_values", _fake)
    try:
        assert read_open_charts(now=1_000.0) == ["MES DEC26"]
        assert read_open_charts(now=1_010.0) == ["MES DEC26"]
        assert calls["n"] == 1
        assert read_open_charts(now=1_031.0) == ["MES DEC26"]
        assert calls["n"] == 2
    finally:
        clear_open_chart_cache()
