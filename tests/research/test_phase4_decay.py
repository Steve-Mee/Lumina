"""Decay detection, staged reductions, and synthetic detection-rate campaign."""

from __future__ import annotations

import math
import random
from dataclasses import asdict
from pathlib import Path

import pytest

from lumina_research.monitoring.config import config_from_mapping, load_default_config
from lumina_research.monitoring.loop import run_phase4_detection
from lumina_research.monitoring.statistics import assess_decay, cusum_down, empirical_percentile, sprt_llr, z_score
from lumina_research.monitoring.synthetic import DEFAULT_OOS, decaying_path, healthy_path, oos_stats
from tests.research.phase4_harness import admit_signal, make_runtime


@pytest.mark.unit
def test_decay_campaign_detects_and_keeps_false_alarms_low(tmp_path: Path) -> None:
    report = run_phase4_detection(
        audit_path=tmp_path / "audit.jsonl",
        experiment_log_path=tmp_path / "exp.jsonl",
        n_healthy=16,
        n_decaying=16,
        n_days=70,
        decay_start=20,
        seed=20261028,
        report_dir=tmp_path / "reports",
    )
    assert report.n_healthy == 16
    assert report.n_decaying == 16
    assert report.detection_rate >= 0.80
    assert report.false_alarm_rate <= 0.15
    assert report.median_time_to_detect is not None
    assert report.median_time_to_detect <= 35
    assert (tmp_path / "reports" / "phase4_detection.json").is_file()


@pytest.mark.unit
def test_staged_deweight_suspend_retire_never_increases(tmp_path: Path) -> None:
    runtime = make_runtime(tmp_path)
    signal = admit_signal(runtime, "hyp-stage", trial_id=1, quantity=4.0, notional=20_000.0)
    assert signal.weight == 1.0
    mean, stdev = oos_stats(DEFAULT_OOS)
    rng = random.Random(3)
    series = decaying_path(rng, oos_mean=mean, oos_stdev=stdev, n=80, decay_start=8)
    seen: list[str] = []
    for metric in series:
        updated = runtime.observe("hyp-stage", metric)
        if not seen or seen[-1] != updated.stage:
            seen.append(updated.stage)
    assert "deweighted" in seen or "suspended" in seen or "retired" in seen
    weights = [item.new_weight for item in runtime.monitor.deweight_events()]
    if weights:
        assert all(item < 1.0 for item in weights)
    final = runtime.registry.require("hyp-stage")
    assert final.weight <= 1.0
    with pytest.raises(Exception, match="cannot increase"):
        runtime.increase_weight("hyp-stage", 1.0)


@pytest.mark.unit
def test_ztest_percentile_cusum_sprt_methods() -> None:
    config = load_default_config()
    oos = DEFAULT_OOS
    mean, stdev = oos_stats(oos)
    healthy = tuple(mean for _ in range(30))
    decayed = tuple(mean - 3.0 * stdev for _ in range(30))
    for method in ("ztest", "percentile", "cusum", "sprt", "combined"):
        raw = asdict(config)
        raw["method"] = method
        cfg = config_from_mapping(raw)
        quiet = assess_decay(healthy, oos, cfg)
        loud = assess_decay(decayed, oos, cfg)
        assert quiet.ready is True
        assert quiet.severity == 0
        assert loud.severity >= 1


@pytest.mark.unit
def test_statistics_helpers_and_fail_closed() -> None:
    oos = DEFAULT_OOS
    mean, stdev = oos_stats(oos)
    assert z_score(live_mean=mean, oos_mean=mean, oos_stdev=stdev, n=20) == pytest.approx(0.0)
    assert z_score(live_mean=mean - 1.0, oos_mean=mean, oos_stdev=0.0, n=20) == float("-inf")
    assert empirical_percentile(min(oos) - 1.0, oos) == 0.0
    path = cusum_down((mean, mean - 1.0, mean - 1.0), mu0=mean, k=0.1)
    assert path[-1] > 0.0
    llr = sprt_llr((mean - 1.0,) * 10, mu0=mean, mu1=mean - 1.0, sigma=stdev)
    assert llr > 0.0
    with pytest.raises(Exception):
        z_score(live_mean=math.nan, oos_mean=mean, oos_stdev=stdev, n=20)
