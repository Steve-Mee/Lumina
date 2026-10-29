"""Fail-closed kill battery for Phase 5 monitoring changes. No pytest."""

from __future__ import annotations

import math
from dataclasses import asdict
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Callable, Sequence, cast

from lumina_core.agent_orchestration.schemas_research import (
    MONITOR_AGENT_ID,
    RESEARCH_SUSPEND_TOPIC,
)
from lumina_core.engine.agent_blackboard import AgentBlackboard
from lumina_research.monitoring import horizons as horizons_mod
from lumina_research.monitoring.acceptance import (
    HIGH_VOL_CONFIRM_WINDOWS,
    HIGH_VOL_VIX,
    MATERIAL_DD_MULT,
    MEDIUM_WINDOW,
    confirm_windows_for,
)
from lumina_research.monitoring.config import config_from_mapping, load_default_config
from lumina_research.monitoring.horizons import combined_assessment
from lumina_research.monitoring.loop import ContinuityRuntime
from lumina_research.monitoring.monitor import _intermediate
from lumina_research.monitoring.material import (
    _drawdown_breach,
    _expected_unit_range,
    _ic_halved,
    _max_drawdown,
    _n_large_diffs,
    _oos_expected_dd,
    _quiet_crash_recover,
    _ratio,
    _restored_to_peak,
    _robust_diff_vol,
    _sharpe_halved,
    _time_underwater,
    assess_material,
)
from lumina_research.monitoring.statistics import assess_decay, effective_sigma, live_noise_vol, sprt_llr
from lumina_research.monitoring.seal import canonical_deweight, canonical_retire, canonical_suspend
from lumina_research.monitoring.synthetic import DEFAULT_OOS
from lumina_research.monitoring.types import ContinuityRefused, DecayAssessment, VolRegime
from lumina_research.monitoring.vol_regime import classify_vol_regime, label_windows, realized_vol, trailing_percentile
from lumina_research.proof.independent import INDEPENDENT_OOS
from tests.research.phase4_harness import admit_signal, make_runtime

RICH_OOS: tuple[float, ...] = (0.70, 0.72, 0.74, 0.76, 0.78, 0.80, 0.82, 0.84, 0.86)


def _signed_weight(
    runtime: ContinuityRuntime,
    *,
    schema: str,
    new_weight: float,
    previous_weight: float,
    signal_id: str = "hyp-g",
    trial_id: int = 2,
) -> dict[str, object]:
    unsigned: dict[str, object] = {
        "schema_version": schema,
        "signal_id": signal_id,
        "hypothesis_id": signal_id,
        "config_id": signal_id,
        "trial_id": trial_id,
        "agent_id": MONITOR_AGENT_ID,
        "previous_weight": previous_weight,
        "new_weight": new_weight,
        "reason": "signed-weight",
    }
    if schema.endswith("deweighted.v1"):
        digest = runtime.authority.mac(canonical_deweight(unsigned))
    elif schema.endswith("suspended.v1"):
        digest = runtime.authority.mac(canonical_suspend(unsigned))
    else:
        digest = runtime.authority.mac(canonical_retire(unsigned))
    return {**unsigned, "provenance_mac": digest}


def _refuse(exc: type[BaseException], fn: Callable[..., object], *args: object, **kwargs: object) -> None:
    try:
        fn(*args, **kwargs)
    except exc:
        return
    raise AssertionError(f"expected {exc.__name__}")


def _refuse_msg(
    exc: type[BaseException], needle: str, fn: Callable[..., object], *args: object, **kwargs: object
) -> None:
    try:
        fn(*args, **kwargs)
    except exc as err:
        if needle not in str(err):
            raise AssertionError(f"expected {needle!r} in {err}") from err
        return
    raise AssertionError(f"expected {exc.__name__} containing {needle!r}")


def _assessment(
    *, severity: int, window: int, statistic: float, horizon: str, method: str = "combined"
) -> DecayAssessment:
    stage = "active" if severity <= 0 else "deweighted" if severity == 1 else "suspended"
    return DecayAssessment(
        method=method,
        severity=severity,
        stage=stage,
        statistic=statistic,
        threshold=1.0,
        live_mean=0.7,
        oos_mean=0.75,
        oos_stdev=0.05,
        percentile=0.5,
        cusum=0.0,
        sprt_llr=0.0,
        window=window,
        votes_deweight=1 if severity >= 1 else 0,
        votes_suspend=1 if severity >= 2 else 0,
        votes_retire=0,
        ready=True,
        horizon=horizon,  # type: ignore[arg-type]
    )


def run_phase5_kills() -> None:
    _vol_and_accept()
    _material_helpers()
    _material_paths()
    _horizon_ties()
    _statistics_edges()
    with TemporaryDirectory() as tmp:
        _runtime_kills(tmp)


def _vol_and_accept() -> None:
    quiet = tuple(0.75 for _ in range(40))
    if classify_vol_regime(quiet, vix=10.0) != "normal":
        raise AssertionError("quiet VIX must classify normal")
    if classify_vol_regime(quiet, vix=HIGH_VOL_VIX) == "high_vol":
        raise AssertionError("VIX==25 is not high_vol")
    if classify_vol_regime(quiet, vix=HIGH_VOL_VIX + 1.0) != "high_vol":
        raise AssertionError("VIX>25 must classify high_vol")
    if classify_vol_regime(quiet[:5]) != "normal":
        raise AssertionError("short history must classify normal")
    _refuse_msg(ContinuityRefused, "VIX", classify_vol_regime, quiet, vix=-1.0)
    _refuse_msg(ContinuityRefused, "VIX", classify_vol_regime, quiet, vix=float("nan"))
    _refuse(ContinuityRefused, realized_vol, (0.7, 0.8), window=1)
    if realized_vol(tuple(0.70 + 0.01 * index for index in range(20)), window=2) is None:
        raise AssertionError("realized-vol window=2 must compute")
    if trailing_percentile((), pct=0.75) is not None:
        raise AssertionError("empty trailing percentile is None")
    if trailing_percentile((1.0, 2.0, 3.0, 4.0), pct=0.75) != 3.0:
        raise AssertionError("75th percentile drifted")
    if trailing_percentile((1.0, 2.0, 3.0, 4.0), pct=0.0) != 1.0:
        raise AssertionError("0th percentile drifted")
    if trailing_percentile((1.0, 2.0, 3.0, 4.0), pct=1.0) != 4.0:
        raise AssertionError("100th percentile drifted")
    _refuse(ContinuityRefused, trailing_percentile, (1.0, 2.0), pct=1.5)
    _refuse(ContinuityRefused, trailing_percentile, (1.0, 2.0), pct=-0.1)
    _refuse(ContinuityRefused, classify_vol_regime, quiet, trailing_window=1)
    loud = tuple(1.0 for _ in range(50)) + tuple(20.0 + float(index) for index in range(30))
    if classify_vol_regime(loud, instrument="ES") != "high_vol":
        raise AssertionError("ES 1.5x-median path must be high_vol")
    last_only = tuple(1.0 for _ in range(40)) + (100.0,)
    if classify_vol_regime(last_only, instrument="MES") != "high_vol":
        raise AssertionError("MES trailing-cap path must be high_vol without the ES median branch")
    if classify_vol_regime(tuple(1.0 for _ in range(80)), instrument="MES") != "normal":
        raise AssertionError("flat MES must stay normal")
    if classify_vol_regime(tuple(1.0 for _ in range(80)), instrument="ES") != "normal":
        raise AssertionError("flat ES must stay normal; median-is-not-None is not a high-vol OR")
    # Trailing 75th stays above current (high-vol history), median stays high, min is tiny.
    # The ES 1.5x-median branch must not fire; swapping median for min would.
    high_hist = tuple(0.0 if index % 2 == 0 else 20.0 for index in range(140))
    quiet_hist = tuple(5.0 if index % 2 == 0 else 5.2 for index in range(120))
    last_hist = tuple(5.0 if index % 2 == 0 else 8.0 for index in range(20))
    es_median = high_hist + quiet_hist + last_hist
    if classify_vol_regime(es_median, instrument="ES") != "normal":
        raise AssertionError("ES 1.5x-median must use the 50th percentile, not the min")
    if classify_vol_regime(es_median, instrument="MES") != "normal":
        raise AssertionError("MES must ignore the ES-family median branch")
    # Trailing 75th stays above current, but 1.5x median of the ES family fires.
    # A 0th-percentile (min) substitution would also fire, so pin median vs min:
    # history mostly ~1.0 with a single tiny vol; current modestly above 1.5x median
    # would require a different tape. Pin the 50th percentile helper instead.
    if trailing_percentile((1.0, 2.0, 3.0, 4.0), pct=0.50) != 2.0:
        raise AssertionError("50th percentile drifted")
    if trailing_percentile((1.0,), pct=0.50) != 1.0:
        raise AssertionError("single-sample 50th percentile is the sample")
    labels = label_windows(quiet + loud, vix_path=tuple(10.0 for _ in quiet) + tuple(30.0 for _ in loud))
    if labels[0] != "normal" or labels[-1] != "high_vol":
        raise AssertionError("label_windows must switch between windows")
    if confirm_windows_for("normal") != 2 or confirm_windows_for("high_vol") != HIGH_VOL_CONFIRM_WINDOWS:
        raise AssertionError("confirm windows drifted")
    if confirm_windows_for("other") != 2:
        raise AssertionError("unknown regime must use the stricter 2-window confirm")
    if classify_vol_regime(quiet, vix=0.0) != "normal" or classify_vol_regime(quiet, vix=0.5) != "normal":
        raise AssertionError("VIX in [0, 25] must stay normal")
    _refuse(ContinuityRefused, realized_vol, tuple(0.7 for _ in range(19)) + (math.nan,), window=20)
    last_jump = tuple(1.0 for _ in range(40)) + (100.0,)
    jump_labels = label_windows(last_jump, instrument="MES", realized_window=20, trailing_window=20)
    if jump_labels[-1] != "high_vol" or jump_labels[-2] == "high_vol":
        raise AssertionError("label_windows must include the last observation")


def _material_helpers() -> None:
    oos = RICH_OOS
    expected = _oos_expected_dd(oos, 0.05)
    if expected != max(max(oos) - min(oos), 0.10, 1e-12):
        raise AssertionError("OOS expected DD drifted")
    if _expected_unit_range(1) != 0.0 or _expected_unit_range(0) != 0.0:
        raise AssertionError("unit range of n<=1 is 0")
    if _expected_unit_range(20) <= _expected_unit_range(6):
        raise AssertionError("Blom range must grow with n")
    if _expected_unit_range(6) <= 2.0 or _expected_unit_range(6) >= 3.2:
        raise AssertionError(f"Blom n=6 drifted {_expected_unit_range(6)}")
    peak = 1.20
    spike = peak - 0.40
    dd_only = tuple(peak for _ in range(25)) + (spike,) + tuple(peak for _ in range(20))
    if abs(_max_drawdown(dd_only) - 0.40) > 1e-12:
        raise AssertionError("max DD of the crash-recover path drifted")
    if _time_underwater(dd_only, 0.24) != 1:
        raise AssertionError("crash-recover is underwater for exactly 1 bar")
    if _time_underwater(tuple(peak for _ in range(20)), 0.24) != 0:
        raise AssertionError("flat tape has zero time-under-water")
    if not _restored_to_peak(dd_only, slop=0.01):
        raise AssertionError("crash-recover must restore to the peak")
    hanging = tuple(peak for _ in range(20)) + (spike,)
    if _restored_to_peak(hanging, slop=0.01):
        raise AssertionError("unrecovered trough is not restored")
    near = tuple(peak for _ in range(20)) + (peak - 0.1 * 0.05,)
    if not _restored_to_peak(near, slop=0.5 * 0.05):
        raise AssertionError("0.1σ below peak must still restore at 0.5σ slop")
    far = tuple(peak for _ in range(20)) + (peak - 0.8 * 0.05,)
    if _restored_to_peak(far, slop=0.5 * 0.05):
        raise AssertionError("0.8σ below peak must not restore at 0.5σ slop")
    crash_window = dd_only[:27]
    if _n_large_diffs(crash_window, oos_stdev=0.05, window=20) != 2:
        raise AssertionError("crash-recover must count exactly two large diffs in the window")
    if _n_large_diffs(dd_only, oos_stdev=0.05, window=20) != 0:
        raise AssertionError("after the crash ages out, the window has no large diffs")
    if _n_large_diffs(tuple(peak for _ in range(30)), oos_stdev=0.05, window=20) != 0:
        raise AssertionError("flat tape has no large diffs")
    noisy = tuple(peak + (0.20 if index % 2 == 0 else -0.20) for index in range(30))
    if _n_large_diffs(noisy, oos_stdev=0.05, window=20) <= 2:
        raise AssertionError("alternating 0.40 moves must count as a loud tape")
    if _robust_diff_vol(tuple(peak for _ in range(30)), window=20) != 0.0:
        raise AssertionError("MAD vol of a constant is 0")
    if _robust_diff_vol(dd_only, window=20) > 0.05:
        raise AssertionError("MAD vol must ignore the single crash")
    raw_floor = MATERIAL_DD_MULT * expected
    if not _quiet_crash_recover(dd_only, oos_stdev=0.05, window=20, raw_floor=raw_floor):
        raise AssertionError("quiet crash-recover helper must fire")
    if _quiet_crash_recover(noisy, oos_stdev=0.05, window=20, raw_floor=0.01):
        raise AssertionError("loud alternating tape is not a quiet crash")
    if not _drawdown_breach(dd_only, oos, 0.05, window=20):
        raise AssertionError("DD helper must flag the 1.5x crash-recover")
    if _drawdown_breach(tuple(peak for _ in range(30)), oos, 0.05, window=20):
        raise AssertionError("flat tape must not breach DD")
    _refuse(ContinuityRefused, _max_drawdown, (peak, math.nan))
    _refuse(ContinuityRefused, _time_underwater, (peak, math.nan), 0.1)
    _refuse_msg(ContinuityRefused, "window", _robust_diff_vol, dd_only, window=1)
    if not _ic_halved(0.20 * 0.78, 0.78):
        raise AssertionError("IC halved must fire at 20% of OOS mean")
    if _ic_halved(0.80 * 0.78, 0.78):
        raise AssertionError("IC must not fire at 80% of OOS mean")
    if not _sharpe_halved(0.10, 1.0, 0.78, 0.05):
        raise AssertionError("Sharpe collapse must fire")
    if not _ic_halved(-0.80, -0.20):
        raise AssertionError("negative OOS IC must fire when live is worse by half")
    if _ic_halved(-0.21, -0.20):
        raise AssertionError("tiny negative drift is not an IC halt")
    if not _ic_halved(-0.10, 0.0) or _ic_halved(0.10, 0.0):
        raise AssertionError("zero OOS mean IC is a sign test")
    if _ratio(1.0, 0.0) != math.inf or _ratio(-1.0, 0.0) != -math.inf or _ratio(0.0, 0.0) != 0.0:
        raise AssertionError("zero-stdev ratio must be signed infinity")
    if not _sharpe_halved(-0.50, 0.10, -0.10, 0.10):
        raise AssertionError("negative expected Sharpe must fire when live is worse")
    if _sharpe_halved(-0.05, 0.10, -0.10, 0.10):
        raise AssertionError("live Sharpe above a negative expected Sharpe is not a halt")
    if _sharpe_halved(0.0, 1.0, 0.0, 0.0) is True:
        raise AssertionError("zero/zero Sharpe must not flag a zero live ratio")
    if _sharpe_halved(0.10, 1.0, 0.0, 0.0):
        raise AssertionError("positive live Sharpe vs zero expected is not a halt")
    if not _sharpe_halved(0.10, 1.0, 0.05, 0.10):
        raise AssertionError("expected Sharpe in (0, 1] must still use the 50% ratio")
    if _restored_to_peak((), slop=0.0):
        raise AssertionError("empty series is not restored")
    near_peak = tuple(peak for _ in range(25)) + (spike,) + (peak - 0.1 * 0.05,) + tuple(peak for _ in range(18))
    if not _quiet_crash_recover(near_peak[:27], oos_stdev=0.05, window=20, raw_floor=raw_floor):
        raise AssertionError("0.1σ restore slop must still count as a quiet crash")


def _material_paths() -> None:
    cfg = load_default_config()
    oos = RICH_OOS
    mean = sum(oos) / float(len(oos))
    healthy = tuple(mean for _ in range(30))
    quiet_mat = assess_material(healthy, oos, cfg)
    if (
        quiet_mat.stage != "active"
        or quiet_mat.votes_deweight != 0
        or quiet_mat.votes_suspend != 0
        or quiet_mat.votes_retire != 0
        or quiet_mat.statistic != 0.0
        or quiet_mat.threshold != 1.0
        or quiet_mat.severity != 0
    ):
        raise AssertionError("healthy material must stay active without votes")
    short = assess_material(healthy[:5], oos, cfg)
    if short.ready is True:
        raise AssertionError("short material window must not be ready")
    if (
        short.severity != 0
        or short.statistic != 0.0
        or short.threshold != 0.0
        or short.votes_deweight != 0
        or short.votes_suspend != 0
        or short.votes_retire != 0
    ):
        raise AssertionError("not-ready material fields must stay zero")
    one = assess_material(healthy, (0.70,), cfg)
    if one.oos_stdev != 0.0:
        raise AssertionError("single OOS value has stdev 0")
    raw = asdict(cfg)
    raw["min_observations"] = 10
    split_cfg = config_from_mapping(raw)
    split = assess_material(tuple(mean for _ in range(15)), oos, split_cfg)
    if split.ready is True:
        raise AssertionError("window=20 still not ready at 15 observations")
    _refuse_msg(ContinuityRefused, "empty", assess_material, healthy, (), cfg)
    _refuse_msg(ContinuityRefused, "non-finite OOS", assess_material, healthy, (math.nan, mean), cfg)
    _refuse_msg(
        ContinuityRefused,
        "unknown vol regime",
        assess_material,
        healthy,
        oos,
        cfg,
        vol_regime=cast(VolRegime, "nope"),
    )
    peak = mean + 0.40
    dd_only = tuple(peak for _ in range(25)) + (peak - 0.40,) + tuple(peak for _ in range(20))
    dd_normal = assess_material(dd_only, oos, cfg, vol_regime="normal")
    dd_high = assess_material(dd_only, oos, cfg, vol_regime="high_vol")
    if dd_normal.severity < 1:
        raise AssertionError("DD-only path must flag in normal vol")
    if dd_high.severity < 1 or dd_high.stage == "active":
        raise AssertionError("DD-only path must flag in high_vol; never skip DD")
    if dd_high.threshold != 1.0 or dd_high.votes_deweight != 1 or dd_high.votes_retire != 0:
        raise AssertionError("ready DD votes/threshold drifted")
    prefix = dd_only[:27]
    if assess_material(prefix, oos, cfg, vol_regime="high_vol").severity < 1:
        raise AssertionError("quiet crash-recover must flag while the spike is still in the window")
    combined_dd = combined_assessment(dd_only, oos, cfg, vix=HIGH_VOL_VIX + 5.0)
    if combined_dd.vol_regime != "high_vol":
        raise AssertionError("VIX must label the crash-recover high_vol")
    if combined_dd.assessment.stage == "active":
        raise AssertionError("combined high_vol must not stay active on a 1.5x DD-only crash")
    ic_break = tuple(mean for _ in range(20)) + tuple(0.20 * mean for _ in range(15))
    ic_high = assess_material(ic_break, oos, cfg, vol_regime="high_vol")
    if ic_high.severity < 1:
        raise AssertionError("IC collapse must still flag in high_vol")
    both = tuple(peak for _ in range(20)) + tuple(0.20 * mean for _ in range(20))
    both_normal = assess_material(both, oos, cfg, vol_regime="normal")
    both_high = assess_material(both, oos, cfg, vol_regime="high_vol")
    if both_normal.severity < 2 or both_normal.votes_suspend != 1:
        raise AssertionError("IC+DD must suspend")
    if both_high.severity < 2 or both_high.votes_suspend != 1:
        raise AssertionError("IC+DD must suspend in high_vol too")
    ic_mean = sum(ic_break[-20:]) / 20.0
    if ic_high.live_mean is None or abs(ic_high.live_mean - ic_mean) > 1e-12:
        raise AssertionError("material live_mean must be the last packaged window")
    loud = tuple(mean + (0.25 if index % 2 == 0 else -0.25) for index in range(40))
    loud_mat = assess_material(loud, oos, cfg, vol_regime="high_vol")
    if loud_mat.severity != 0:
        raise AssertionError("symmetric high-vol chop around OOS mean must not trip material DD")
    wide = tuple(mean + (2.0 if index % 2 == 0 else -2.0) for index in range(40))
    wide_mat = assess_material(wide, oos, cfg, vol_regime="high_vol")
    if wide_mat.severity != 0:
        raise AssertionError("wide symmetric chop must scale Sharpe by oos/base, not oos*base")
    step = tuple(mean for _ in range(20)) + tuple(mean - 0.20 for _ in range(10))
    step_mat = assess_material(step, oos, cfg, vol_regime="normal")
    if step_mat.severity != 0:
        raise AssertionError("a 0.20 step inside the window must use diff-noise, not level stdev")
    mixed_window = (
        tuple(mean for _ in range(10))
        + tuple(mean for _ in range(10))
        + tuple(mean - 0.35 if index < 10 else mean for index in range(20))
    )
    mixed_mat = assess_material(mixed_window, oos, cfg, vol_regime="normal")
    want_mean = sum(mixed_window[-20:]) / 20.0
    if mixed_mat.live_mean is None or abs(mixed_mat.live_mean - want_mean) > 1e-12:
        raise AssertionError("material live_mean must use series[-window:], not series[+window:]")
    if mixed_mat.severity < 1:
        raise AssertionError("level stdev of a half-window step must still feed Sharpe")
    independent_dd = tuple(0.90 for _ in range(25)) + (0.50,) + tuple(0.90 for _ in range(20))
    if assess_material(independent_dd, INDEPENDENT_OOS, cfg, vol_regime="high_vol").severity < 1:
        raise AssertionError("independent OOS crash-recover must flag in high_vol")
    noisy = tuple(mean + (((-1) ** index) * 0.25) for index in range(30))
    if effective_sigma(0.05, noisy, window=20) < 0.05:
        raise AssertionError("effective_sigma must not fall below OOS vol")
    combined = combined_assessment(ic_break, oos, cfg, vix=HIGH_VOL_VIX + 5.0)
    if combined.vol_regime != "high_vol":
        raise AssertionError("combined assessment must label high_vol")
    if combined.assessment.stage == "active":
        raise AssertionError("IC collapse must not stay active after combine")
    recovered = tuple(mean - 3.0 * 0.05 for _ in range(20)) + tuple(mean for _ in range(30))
    medium = combined_assessment(recovered, oos, cfg)
    if medium.horizon != "medium" or medium.assessment.stage == "active":
        raise AssertionError("medium horizon must catch a recovered short window")
    recovered_41 = tuple(mean - 3.0 * 0.05 for _ in range(20)) + tuple(mean for _ in range(21))
    medium_41 = combined_assessment(recovered_41, oos, cfg)
    if len(recovered_41) != MEDIUM_WINDOW + 1:
        raise AssertionError("41-bar recovered path length drifted")
    if medium_41.horizon != "medium" or medium_41.assessment.stage == "active":
        raise AssertionError("medium must still assess at n=MEDIUM_WINDOW+1, not stub as not-ready")
    if combined_assessment(healthy[:10], oos, cfg).assessment.ready is True:
        raise AssertionError("combined short series must not be ready")
    stub = horizons_mod._medium(healthy[:10], oos, cfg)
    if (
        stub.ready is True
        or stub.severity != 0
        or stub.statistic != 0.0
        or stub.threshold != 0.0
        or stub.votes_deweight != 0
        or stub.votes_suspend != 0
        or stub.votes_retire != 0
        or stub.window != MEDIUM_WINDOW
    ):
        raise AssertionError("not-ready medium stub fields must stay zero")
    if live_noise_vol(dd_only, window=20) is None:
        raise AssertionError("noise vol of a long crash-recover must compute")


def _horizon_ties() -> None:
    cfg = load_default_config()
    oos = DEFAULT_OOS
    original_decay = horizons_mod.assess_decay
    original_material = horizons_mod.assess_material
    original_medium = horizons_mod._medium

    short = _assessment(severity=1, window=20, statistic=1.1, horizon="short")
    material = _assessment(severity=1, window=20, statistic=2.2, horizon="short")
    medium = _assessment(severity=1, window=40, statistic=3.3, horizon="medium")

    def _short(_series: Sequence[float], _oos: Sequence[float], _cfg: object) -> DecayAssessment:
        return short

    try:
        horizons_mod.assess_decay = _short  # type: ignore[method-assign]
        horizons_mod.assess_material = lambda *_a, **_k: material  # type: ignore[method-assign]
        horizons_mod._medium = lambda *_a, **_k: medium  # type: ignore[method-assign]
        tied = combined_assessment(tuple(0.7 for _ in range(40)), oos, cfg)
        if tied.assessment.statistic != 1.1:
            raise AssertionError("strict stage ties must keep the short-window statistic")
        if tied.assessment.window != 20:
            raise AssertionError("strict stage ties must keep the short window")
        if tied.horizon != "short":
            raise AssertionError("tied short/medium must not flip horizon to medium")
        winner = _assessment(severity=2, window=40, statistic=9.9, horizon="medium")
        horizons_mod._medium = lambda *_a, **_k: winner  # type: ignore[method-assign]
        unique = combined_assessment(tuple(0.7 for _ in range(40)), oos, cfg)
        if unique.horizon != "medium" or unique.assessment.statistic != 9.9:
            raise AssertionError("unique medium maximizer must own horizon and statistic")
        mat_win = _assessment(severity=2, window=20, statistic=8.8, horizon="short")
        horizons_mod.assess_material = lambda *_a, **_k: mat_win  # type: ignore[method-assign]
        horizons_mod._medium = lambda *_a, **_k: medium  # type: ignore[method-assign]
        picked = combined_assessment(tuple(0.7 for _ in range(40)), oos, cfg)
        if picked.assessment.statistic != 8.8:
            raise AssertionError("stricter material must win the chosen assessment")
        short_only = _assessment(severity=1, window=20, statistic=1.1, horizon="short")
        quiet_mat = _assessment(severity=0, window=20, statistic=0.0, horizon="short")
        tied_med = _assessment(severity=1, window=40, statistic=3.3, horizon="medium")
        horizons_mod.assess_decay = lambda *_a, **_k: short_only  # type: ignore[method-assign]
        horizons_mod.assess_material = lambda *_a, **_k: quiet_mat  # type: ignore[method-assign]
        horizons_mod._medium = lambda *_a, **_k: tied_med  # type: ignore[method-assign]
        rank_tie = combined_assessment(tuple(0.7 for _ in range(40)), oos, cfg)
        if rank_tie.horizon != "short" or rank_tie.assessment.statistic != 1.1:
            raise AssertionError("short/medium rank tie must keep short horizon and statistic")
    finally:
        horizons_mod.assess_decay = original_decay  # type: ignore[method-assign]
        horizons_mod.assess_material = original_material  # type: ignore[method-assign]
        horizons_mod._medium = original_medium  # type: ignore[method-assign]


def _statistics_edges() -> None:
    cfg = load_default_config()
    oos = DEFAULT_OOS
    mean = sum(oos) / float(len(oos))
    if effective_sigma(0.05, tuple(mean for _ in range(30)), window=20) < 0.05:
        raise AssertionError("effective_sigma floors at OOS vol")
    if effective_sigma(0.0, tuple(mean for _ in range(30)), window=20) < 0.0:
        raise AssertionError("zero OOS vol must not go negative")
    zero = assess_decay(tuple(mean for _ in range(30)), (mean,) * 6, cfg)
    if zero.ready is not True:
        raise AssertionError("constant OOS must still assess")
    if live_noise_vol((0.1, 0.1), window=20) is not None:
        raise AssertionError("short series has no noise vol")
    if live_noise_vol(tuple(0.1 for _ in range(20)), window=2) is not None:
        raise AssertionError("window<3 has no noise vol")
    if live_noise_vol(tuple(0.10 + 0.01 * index for index in range(20)), window=0) is not None:
        raise AssertionError("window=0 must not compute via values[-0:]")
    if live_noise_vol(tuple(0.10 + 0.01 * index for index in range(20)), window=1) is not None:
        raise AssertionError("window=1 must not compute")
    mixed = tuple(0.2 * ((-1) ** index) for index in range(10)) + tuple(0.7 for _ in range(15))
    noise = live_noise_vol(mixed, window=20)
    if noise is None or noise <= 0.0:
        raise AssertionError("noise vol must see the spike inside the last window")
    if sprt_llr((0.70,) * 5, mu0=0.70, mu1=0.50, sigma=0.0) != 0.0:
        raise AssertionError("zero-sigma SPRT on the null is 0")
    if sprt_llr((0.10,) * 5, mu0=0.70, mu1=0.50, sigma=0.0) != float("inf"):
        raise AssertionError("zero-sigma SPRT off the null toward mu1 is +inf")
    if sprt_llr((0.60,) * 5, mu0=0.70, mu1=0.50, sigma=1.0) != 0.0:
        raise AssertionError("SPRT at the midpoint must accumulate 0")
    if _intermediate("active", "active") != () or _intermediate("suspended", "deweighted") != ():
        raise AssertionError("non-tightening intermediate stages must be empty")
    if _intermediate("active", "suspended") != ("deweighted", "suspended"):
        raise AssertionError("active to suspended must walk deweighted then suspended")
    if _intermediate("active", "retired") != ("deweighted", "suspended", "retired"):
        raise AssertionError("active to retired must walk every intermediate stage")


def _runtime_kills(tmp: str) -> None:
    root = Path(tmp)
    runtime = make_runtime(root / "rt")
    admit_signal(runtime, "hyp-hv", trial_id=1, oos=DEFAULT_OOS)
    mean = sum(DEFAULT_OOS) / float(len(DEFAULT_OOS))
    dropped = 0.20 * mean
    vix = HIGH_VOL_VIX + 5.0
    for _ in range(20):
        if runtime.observe("hyp-hv", dropped, vix=vix).stage != "active":
            raise AssertionError("unready high-vol window must stay active")
    if runtime.observe("hyp-hv", dropped, vix=vix).stage != "active":
        raise AssertionError("high-vol confirm 2/3 must wait")
    applied = runtime.observe("hyp-hv", dropped, vix=vix)
    if applied.stage == "active":
        raise AssertionError("high-vol confirm 3/3 must apply")
    admit_signal(runtime, "hyp-g", trial_id=2, oos=DEFAULT_OOS)
    suspended = runtime.monitor.apply_guardian_suspend("hyp-g", "guardian:daily")
    if suspended.stage != "suspended":
        raise AssertionError("guardian suspend must apply")
    dummy = runtime.monitor.decay_events()[-1]
    if dummy.statistic != 0.0 or dummy.threshold != 0.0:
        raise AssertionError("guardian dummy decay statistic and threshold must stay 0")
    _refuse(ContinuityRefused, runtime.observe, "hyp-g", True)
    _refuse(ContinuityRefused, runtime.observe, "hyp-g", "not-a-metric")
    _refuse(ContinuityRefused, runtime.observe, "hyp-g", math.nan)
    if runtime.monitor._guard_deweight(MONITOR_AGENT_ID, {}) is not False:
        raise AssertionError("invalid deweight payload must fail the guard")
    if runtime.monitor._guard_suspend(MONITOR_AGENT_ID, {}) is not False:
        raise AssertionError("invalid suspend payload must fail the guard")
    if runtime.monitor._guard_retire(MONITOR_AGENT_ID, {}) is not False:
        raise AssertionError("invalid retire payload must fail the guard")
    if runtime.monitor._guard_deweight_bb("evil", {}) is not False:
        raise AssertionError("blackboard deweight guard must refuse a wrong producer")
    if runtime.monitor._guard_suspend_bb("evil", {}) is not False:
        raise AssertionError("blackboard suspend guard must refuse a wrong producer")
    if runtime.monitor._guard_retire_bb("evil", {}) is not False:
        raise AssertionError("blackboard retire guard must refuse a wrong producer")
    if runtime.monitor._guard_decay_bb("evil", {}) is not False:
        raise AssertionError("blackboard decay guard must refuse a wrong producer")
    same_weight = _signed_weight(
        runtime,
        schema="research.signal.deweighted.v1",
        new_weight=0.5,
        previous_weight=0.5,
    )
    if runtime.monitor._check_deweight(MONITOR_AGENT_ID, same_weight, consume=True) is not False:
        raise AssertionError("deweight must refuse a non-decreasing weight")
    up_weight = _signed_weight(
        runtime,
        schema="research.signal.deweighted.v1",
        new_weight=0.8,
        previous_weight=0.5,
    )
    if runtime.monitor._check_deweight(MONITOR_AGENT_ID, up_weight, consume=True) is not False:
        raise AssertionError("deweight must refuse an exposure increase")
    ok_weight = _signed_weight(
        runtime,
        schema="research.signal.deweighted.v1",
        new_weight=0.5,
        previous_weight=1.0,
    )
    if runtime.monitor._check_deweight(MONITOR_AGENT_ID, ok_weight, consume=False) is not True:
        raise AssertionError("signed decreasing deweight must pass the MAC check")
    ok_suspend = _signed_weight(
        runtime,
        schema="research.signal.suspended.v1",
        new_weight=0.0,
        previous_weight=0.5,
    )
    if runtime.monitor._check_suspend(MONITOR_AGENT_ID, ok_suspend, consume=False) is not True:
        raise AssertionError("signed zero-weight suspend must pass the MAC check")
    ok_retire = _signed_weight(
        runtime,
        schema="research.signal.retired.v1",
        new_weight=0.0,
        previous_weight=0.5,
    )
    if runtime.monitor._check_retire(MONITOR_AGENT_ID, ok_retire, consume=False) is not True:
        raise AssertionError("signed zero-weight retire must pass the MAC check")
    _refuse(
        ContinuityRefused,
        runtime.monitor._emit_stage,
        runtime.registry.require("hyp-g"),
        previous_weight=1.0,
        stage="active",
        reason="nope",
    )
    if runtime.monitor._guard_decay("evil", {}) is not False:
        raise AssertionError("wrong producer must fail the decay guard")
    if runtime.monitor._guard_decay(MONITOR_AGENT_ID, {}) is not False:
        raise AssertionError("invalid decay payload must fail the guard")
    if runtime.monitor._guard_deweight("evil", {}) is not False:
        raise AssertionError("wrong producer must fail the deweight guard")
    if runtime.monitor._guard_suspend("evil", {}) is not False:
        raise AssertionError("wrong producer must fail the suspend guard")
    if runtime.monitor._guard_retire("evil", {}) is not False:
        raise AssertionError("wrong producer must fail the retire guard")
    bad_suspend = {
        "schema_version": "research.signal.suspended.v1",
        "signal_id": "hyp-g",
        "hypothesis_id": "hyp-g",
        "config_id": "hyp-g",
        "trial_id": 2,
        "agent_id": MONITOR_AGENT_ID,
        "previous_weight": 1.0,
        "new_weight": 0.5,
        "reason": "x",
        "provenance_mac": "aa",
    }
    if runtime.monitor._check_suspend(MONITOR_AGENT_ID, bad_suspend, consume=True) is not False:
        raise AssertionError("suspend with residual weight must fail")
    bad_retire = dict(bad_suspend)
    bad_retire["schema_version"] = "research.signal.retired.v1"
    bad_retire["new_weight"] = 0.1
    if runtime.monitor._check_retire(MONITOR_AGENT_ID, bad_retire, consume=True) is not False:
        raise AssertionError("retire with residual weight must fail")
    board = AgentBlackboard(persistence_path=root / "bb.jsonl")
    shadowed = ContinuityRuntime(
        audit_path=root / "bb-audit.jsonl",
        experiment_log_path=root / "bb-exp.jsonl",
        blackboard=board,
        evolution_log_dir=root / "bb-evo",
    )
    admit_signal(shadowed, "hyp-bb", trial_id=3, oos=DEFAULT_OOS)
    if shadowed.monitor.apply_guardian_suspend("hyp-bb", "guardian:daily").stage != "suspended":
        raise AssertionError("blackboard runtime must still apply guardian suspend")
    posted = board.history(RESEARCH_SUSPEND_TOPIC)
    if not posted or posted[-1].confidence != 1.0:
        raise AssertionError("monitor blackboard publish must use confidence 1.0")
