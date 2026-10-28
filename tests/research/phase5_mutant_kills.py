"""Fail-closed kill battery for Phase 5 monitoring changes. No pytest."""

from __future__ import annotations

import math
from typing import Callable, Sequence, cast

from lumina_research.monitoring.acceptance import (
    HIGH_VOL_CONFIRM_WINDOWS,
    HIGH_VOL_VIX,
    MATERIAL_DD_MULT,
    confirm_windows_for,
)
from lumina_research.monitoring.config import load_default_config
from lumina_research.monitoring.horizons import combined_assessment
from lumina_research.monitoring.material import (
    _drawdown_breach,
    _expected_unit_range,
    _ic_halved,
    _max_drawdown,
    _n_large_diffs,
    _oos_expected_dd,
    _quiet_crash_recover,
    _restored_to_peak,
    _robust_diff_vol,
    _sharpe_halved,
    _time_underwater,
    assess_material,
)
from lumina_research.monitoring.statistics import assess_decay, effective_sigma, live_noise_vol
from lumina_research.monitoring.synthetic import DEFAULT_OOS
from lumina_research.monitoring.types import ContinuityRefused, DecayAssessment, VolRegime
from lumina_research.monitoring.vol_regime import classify_vol_regime, label_windows, realized_vol, trailing_percentile
from lumina_research.proof.independent import INDEPENDENT_OOS

RICH_OOS: tuple[float, ...] = (0.70, 0.72, 0.74, 0.76, 0.78, 0.80, 0.82, 0.84, 0.86)


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
    if classify_vol_regime(tuple(1.0 for _ in range(80)), instrument="MES") != "normal":
        raise AssertionError("flat MES must stay normal")
    labels = label_windows(quiet + loud, vix_path=tuple(10.0 for _ in quiet) + tuple(30.0 for _ in loud))
    if labels[0] != "normal" or labels[-1] != "high_vol":
        raise AssertionError("label_windows must switch between windows")
    if confirm_windows_for("normal") != 2 or confirm_windows_for("high_vol") != HIGH_VOL_CONFIRM_WINDOWS:
        raise AssertionError("confirm windows drifted")
    if confirm_windows_for("other") != 2:
        raise AssertionError("unknown regime must use the stricter 2-window confirm")


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


def _material_paths() -> None:
    cfg = load_default_config()
    oos = RICH_OOS
    mean = sum(oos) / float(len(oos))
    healthy = tuple(mean for _ in range(30))
    quiet_mat = assess_material(healthy, oos, cfg)
    if quiet_mat.stage != "active" or quiet_mat.votes_deweight != 0 or quiet_mat.votes_retire != 0:
        raise AssertionError("healthy material must stay active without votes")
    if assess_material(healthy[:5], oos, cfg).ready is True:
        raise AssertionError("short material window must not be ready")
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
    if assess_material(both, oos, cfg, vol_regime="normal").severity < 2:
        raise AssertionError("IC+DD must suspend")
    if assess_material(both, oos, cfg, vol_regime="high_vol").severity < 2:
        raise AssertionError("IC+DD must suspend in high_vol too")
    loud = tuple(mean + (0.25 if index % 2 == 0 else -0.25) for index in range(40))
    loud_mat = assess_material(loud, oos, cfg, vol_regime="high_vol")
    if loud_mat.severity != 0:
        raise AssertionError("symmetric high-vol chop around OOS mean must not trip material DD")
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
    recovered = tuple(mean - 3.0 * 0.05 for _ in range(20)) + tuple(mean for _ in range(20))
    medium = combined_assessment(recovered, oos, cfg)
    if medium.horizon != "medium" or medium.assessment.stage == "active":
        raise AssertionError("medium horizon must catch a recovered short window")
    if combined_assessment(healthy[:10], oos, cfg).assessment.ready is True:
        raise AssertionError("combined short series must not be ready")
    if live_noise_vol(dd_only, window=20) is None:
        raise AssertionError("noise vol of a long crash-recover must compute")


def _horizon_ties() -> None:
    from lumina_research.monitoring import horizons as horizons_mod

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
