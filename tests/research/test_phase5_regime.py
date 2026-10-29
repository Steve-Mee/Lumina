"""Primary high-vol FAR redefinition, variance scaling, holdout lock, first-cycle prep."""

from __future__ import annotations

import math
import random
from datetime import datetime, timezone
from pathlib import Path

import pytest

from lumina_research.cycles import first_cycle as first_cycle_mod
from lumina_research.cycles.catalog import HypothesisSpec
from lumina_research.cycles.data import LoadedTape, ResearchBar
from lumina_research.cycles.data_spec import DATA_SPEC, write_data_spec
from lumina_research.cycles.first_cycle import FIRST_CYCLE_CONFIG_IDS, first_cycle_specs, write_first_cycle_preregister
from lumina_research.cycles.holdout import (
    HOLDOUT_MONTHS,
    HoldoutLocked,
    access_bars,
    assert_not_holdout,
    holdout_start_ns,
    split_holdout,
)
from lumina_research.monitoring.config import load_default_config
from lumina_research.monitoring.report import DetectionPath, _regime_metrics
from lumina_research.monitoring.statistics import assess_decay, effective_sigma, live_noise_vol, rolling_mean, z_score
from lumina_research.monitoring.synthetic import DEFAULT_OOS, oos_stats
from lumina_research.monitoring.vol_regime import classify_vol_regime
from lumina_research.proof.independent import (
    HOLDOUT_SEEDS,
    INDEPENDENT_SEEDS,
    PRIMARY_HIGH_VOL_KIND,
    STRESS_HIGH_VOL_KIND,
    assert_holdout_seeds,
    healthy_regime_switch,
    path_for,
    regime_switch_index,
    vix_path_for,
)
from lumina_research.monitoring.campaign import DEFAULT_CAMPAIGN_SEEDS


def _calendar_bars(n: int = 400) -> tuple[ResearchBar, ...]:
    px = 5000.0
    start = datetime(2023, 10, 28, tzinfo=timezone.utc)
    end = datetime(2026, 10, 28, tzinfo=timezone.utc)
    step = (end - start).total_seconds() / float(max(n - 1, 1))
    rows: list[ResearchBar] = []
    for index in range(n):
        ts_ns = int((start.timestamp() + float(index) * step) * 1_000_000_000)
        rows.append(
            ResearchBar(ts_ns=ts_ns, open=px, high=px + 0.5, low=px - 0.5, close=px, volume=100.0)
        )
    return tuple(rows)


@pytest.mark.unit
def test_holdout_seeds_are_disjoint_from_phase4_and_pr63() -> None:
    assert_holdout_seeds(HOLDOUT_SEEDS)
    assert set(HOLDOUT_SEEDS).isdisjoint(set(DEFAULT_CAMPAIGN_SEEDS))
    assert set(HOLDOUT_SEEDS).isdisjoint(set(INDEPENDENT_SEEDS))
    with pytest.raises(Exception, match="overlap"):
        assert_holdout_seeds(INDEPENDENT_SEEDS)


@pytest.mark.unit
def test_primary_regime_switch_labels_and_stress_kind() -> None:
    rng = random.Random(HOLDOUT_SEEDS[0])
    n = 70
    series = path_for(
        PRIMARY_HIGH_VOL_KIND, rng, oos_mean=0.75, oos_stdev=0.05, n=n, decay_start=20
    )
    vix = vix_path_for(PRIMARY_HIGH_VOL_KIND, n)
    boundary = regime_switch_index(n)
    quiet_vix = vix[boundary - 1]
    loud_vix = vix[-1]
    assert quiet_vix is not None and quiet_vix < 25.0
    assert loud_vix is not None and loud_vix > 25.0
    assert classify_vol_regime(series[:boundary], vix=18.0) == "normal"
    assert classify_vol_regime(series, vix=30.0) == "high_vol"
    stress = healthy_regime_switch(rng, oos_mean=0.75, oos_stdev=0.05, n=40)
    assert len(stress) == 40
    assert STRESS_HIGH_VOL_KIND == "high_vol_mixture"
    assert regime_switch_index(3) >= 1


@pytest.mark.unit
def test_effective_sigma_scales_high_vol_without_changing_z_floor() -> None:
    cfg = load_default_config()
    mean, stdev = oos_stats(DEFAULT_OOS)
    loud = tuple(mean + ((-1.0) ** index) * 2.2 * stdev for index in range(40))
    sigma = effective_sigma(stdev, loud, window=cfg.window)
    assert sigma >= stdev
    live = rolling_mean(loud, cfg.window)
    z_scaled = z_score(live_mean=live, oos_mean=mean, oos_stdev=sigma, n=cfg.window)
    z_raw = z_score(live_mean=live, oos_mean=mean, oos_stdev=stdev, n=cfg.window)
    assert abs(z_scaled) <= abs(z_raw) + 1e-12
    shifted = tuple(mean for _ in range(20)) + tuple(mean - 2.8 * stdev for _ in range(20))
    decayed = assess_decay(shifted, DEFAULT_OOS, cfg)
    assert decayed.ready is True
    assert decayed.severity >= 1
    assert live_noise_vol((1.0, 2.0), window=20) is None
    with pytest.raises(Exception):
        live_noise_vol(tuple(1.0 for _ in range(19)) + (math.nan,), window=20)


@pytest.mark.unit
def test_holdout_lock_fails_closed(tmp_path: Path) -> None:
    bars = _calendar_bars()
    tape = LoadedTape(instrument="MES", bar_size="1m", path=tmp_path / "mes.csv", bars=bars)
    train, locked, start = split_holdout(bars)
    assert start == holdout_start_ns(bars)
    assert train[-1].ts_ns < start <= locked[0].ts_ns
    gate_bars = access_bars(tape, purpose="gate")
    assert gate_bars == train
    assert all(item.ts_ns < start for item in gate_bars)
    eval_bars = access_bars(tape, purpose="evaluation")
    assert eval_bars == locked
    with pytest.raises(HoldoutLocked, match="unknown"):
        access_bars(tape, purpose="tune_on_holdout")
    short = LoadedTape(
        instrument="MES",
        bar_size="1m",
        path=tmp_path / "short.csv",
        bars=bars[:10],
    )
    with pytest.raises(HoldoutLocked):
        access_bars(short, purpose="selection")
    with pytest.raises(HoldoutLocked, match="months"):
        holdout_start_ns(bars, months=5)
    assert HOLDOUT_MONTHS == 9
    with pytest.raises(HoldoutLocked, match="too short"):
        holdout_start_ns(bars[:1])
    assert_not_holdout(start - 1, holdout_start=start, purpose="evaluation")
    with pytest.raises(HoldoutLocked, match="refused"):
        assert_not_holdout(start, holdout_start=start, purpose="selection")
    drifted = LoadedTape(
        instrument="MES",
        bar_size="1m",
        path=tmp_path / "mes.csv",
        bars=bars,
        holdout_start_ns=start + 1,
    )
    with pytest.raises(HoldoutLocked, match="drifted"):
        access_bars(drifted, purpose="calibration")


@pytest.mark.unit
def test_first_cycle_preregister_and_data_spec(tmp_path: Path) -> None:
    specs = first_cycle_specs()
    assert len(specs) == len(FIRST_CYCLE_CONFIG_IDS) == 12
    path = write_first_cycle_preregister(tmp_path)
    text = path.read_text(encoding="utf-8")
    assert "before seeing data" in text
    assert "MES" in text
    spec_path = write_data_spec(tmp_path)
    spec_text = spec_path.read_text(encoding="utf-8")
    assert "nt8" in spec_text.lower() or "NT8" in spec_text or "1m" in spec_text
    assert "timestamp,open,high,low,close,volume" in spec_text
    assert "MES" in DATA_SPEC["universe_first"]
    with pytest.raises(RuntimeError, match="resolve"):
        first_cycle_specs(prefilter=())
    specs = first_cycle_specs()
    collapsed = tuple(
        HypothesisSpec(
            config_id=item.config_id,
            template_id="mean_reversion",
            family=item.family,
            instrument=item.instrument,
            lookback=item.lookback,
            threshold=item.threshold,
            mode=item.mode,
            target_ticks=item.target_ticks,
            stop_ticks=item.stop_ticks,
            rationale=item.rationale,
        )
        for item in specs
    )
    with pytest.raises(RuntimeError, match="12 registered"):
        first_cycle_specs(prefilter=collapsed)
    full_size = tuple(
        HypothesisSpec(
            config_id=item.config_id,
            template_id=item.template_id,
            family=item.family,
            instrument="ES",
            lookback=item.lookback,
            threshold=item.threshold,
            mode=item.mode,
            target_ticks=item.target_ticks,
            stop_ticks=item.stop_ticks,
            rationale=item.rationale,
        )
        for item in specs
    )
    with pytest.raises(RuntimeError, match="MES/MNQ"):
        first_cycle_specs(prefilter=full_size)


@pytest.mark.unit
def test_first_cycle_count_band(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(first_cycle_mod, "FIRST_CYCLE_N_MIN", 13)
    with pytest.raises(RuntimeError, match="10-15"):
        first_cycle_mod.first_cycle_specs()


def _path(
    *,
    kind: str,
    decaying: bool,
    false_alarm: bool = False,
    detected: bool = False,
    ttd: int | None = None,
    vol_regime: str = "normal",
    n_normal: int = 40,
    n_high: int = 0,
) -> DetectionPath:
    return DetectionPath(
        signal_id=f"{kind}-{n_normal}-{n_high}",
        decaying=decaying,
        detected=detected,
        false_alarm=false_alarm,
        time_to_detect=ttd,
        final_stage="suspended" if (false_alarm or detected) else "active",
        kind=kind,
        vol_regime=vol_regime,
        n_normal_windows=n_normal,
        n_high_vol_windows=n_high,
    )


@pytest.mark.unit
def test_regime_metrics_skip_mixture_and_group_by_majority_windows() -> None:
    rows = _regime_metrics(
        (
            _path(kind="high_vol_mixture", decaying=False, false_alarm=True, n_normal=50, n_high=0),
            _path(kind="healthy_laplace", decaying=False, n_normal=50, n_high=0),
            _path(
                kind="healthy_regime_switch",
                decaying=False,
                false_alarm=True,
                vol_regime="high_vol",
                n_normal=10,
                n_high=40,
            ),
            _path(
                kind="abrupt_student",
                decaying=True,
                detected=True,
                ttd=6,
                n_normal=50,
                n_high=0,
            ),
            _path(
                kind="regime_laplace",
                decaying=True,
                detected=True,
                ttd=8,
                vol_regime="high_vol",
                n_normal=10,
                n_high=40,
            ),
        )
    )
    by_name = {item.kind: item for item in rows}
    assert "high_vol_mixture" not in by_name
    assert tuple(item.kind for item in rows) == ("normal", "high_vol")
    assert by_name["normal"].false_alarm_rate == 0.0
    assert by_name["normal"].detection_rate == 1.0
    assert by_name["high_vol"].false_alarm_rate == 1.0
    assert by_name["high_vol"].detection_rate == 1.0
    assert by_name["high_vol"].max_time_to_detect == 8.0
