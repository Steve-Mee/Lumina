"""Compact fail-closed battery used to kill monitoring mutants. No pytest."""

from __future__ import annotations

import json
import math
from dataclasses import asdict, replace
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from lumina_core.agent_orchestration.event_bus import EventBus
from lumina_core.agent_orchestration.schemas_research import (
    CAPACITY_AGENT_ID,
    GUARDIAN_AGENT_ID,
    MONITOR_AGENT_ID,
    RESEARCH_DECAY_TOPIC,
)
from lumina_research.agents.provenance import ProvenanceAuthority
from lumina_research.evolution.integrity import capture_integrity
from lumina_research.evolution.regime import RegimeAction
from lumina_research.monitoring import config as continuity_config
from lumina_research.monitoring.acceptance import (
    CAMPAIGN_MIN_SEEDS,
    CAMPAIGN_MIN_SIGNALS,
    CONFIRM_WINDOWS,
    DETECTION_RATE_MIN,
    FAR_HEALTHY_MAX,
    FAR_HIGH_VOL_EXTREME_NOT_A_PASS,
    FAR_HIGH_VOL_MAX,
    FAR_HIGH_VOL_TARGET,
    HIGH_VOL_CONFIRM_WINDOWS,
    HIGH_VOL_REALIZED_MULT,
    HIGH_VOL_REALIZED_WINDOW,
    HIGH_VOL_TRAILING_PCT,
    HIGH_VOL_TRAILING_WINDOW,
    HIGH_VOL_VIX,
    MATERIAL_DD_MULT,
    MATERIAL_IC_RATIO,
    MATERIAL_SHARPE_RATIO,
    MEANINGFUL_RAMP_DAYS,
    MEDIUM_WINDOW,
    MUTATION_EQUIVALENT_MAX_FRAC,
    MUTATION_KILL_RATE_MIN,
    MUTATION_MIN_MUTANTS,
    TTD_MAX_TRADING_DAYS,
    TTD_MEDIUM_MAX_TRADING_DAYS,
    confirm_windows_for,
)
from lumina_research.monitoring.capacity import CapacityController, _needed, _sums
from lumina_research.monitoring.config import ContinuityConfigError, config_from_mapping, load_default_config
from lumina_research.monitoring.guardian import GuardianAgent
from lumina_research.monitoring.horizons import combined_assessment
from lumina_research.monitoring.loop import ContinuityIntegrityError, ContinuityRuntime, run_phase4_detection
from lumina_research.monitoring.material import (
    _drawdown_breach,
    _ic_halved,
    _max_drawdown,
    _sharpe_halved,
    assess_material,
)
from lumina_research.monitoring.monitor import LivePerformanceMonitor
from lumina_research.monitoring.registry import LiveSignalRegistry
from lumina_research.monitoring.replenish import ReplenishAgent
from lumina_research.monitoring.seal import (
    accept_mac,
    canonical_admission,
    canonical_capacity,
    canonical_decay,
    canonical_guardian,
    canonical_replenish,
    canonical_state,
    mac_ok,
)
from lumina_research.monitoring.sizing import ContinuitySizer
from lumina_research.monitoring.statistics import (
    _select,
    assess_decay,
    cusum_down,
    effective_sigma,
    empirical_percentile,
    rolling_mean,
    sprt_llr,
    sprt_threshold,
    z_score,
)
from lumina_research.monitoring.synthetic import DEFAULT_OOS, seal_promotion_pair
from lumina_research.monitoring.types import (
    ContinuityRefused,
    family_for,
    finite_series,
    require_cluster,
    stage_from_rank,
    stage_rank,
    stage_weight,
    tighter_stage,
)
from lumina_research.monitoring.vol_regime import classify_vol_regime, label_windows, realized_vol, trailing_percentile
from lumina_research.risk_core.config import load_default_config as load_risk_config
from lumina_research.risk_core.engine import RiskCore
from lumina_research.risk_core.types import DecisionKind
from lumina_research.validation.cost_model import COST_MODEL_ID
from lumina_research.validation.trial_registry import TrialRecord

RICH_OOS: tuple[float, ...] = (0.70, 0.72, 0.74, 0.76, 0.78, 0.80, 0.82, 0.84, 0.86)


def _refuse(exc: type[BaseException], fn: object, *args: object, **kwargs: object) -> None:
    try:
        if callable(fn):
            fn(*args, **kwargs)
    except exc:
        return
    raise AssertionError(f"expected {exc.__name__}")


def _refuse_msg(exc: type[BaseException], needle: str, fn: object, *args: object, **kwargs: object) -> None:
    try:
        if callable(fn):
            fn(*args, **kwargs)
    except exc as err:
        if needle not in str(err):
            raise AssertionError(f"expected {needle!r} in {err}") from err
        return
    raise AssertionError(f"expected {exc.__name__} containing {needle!r}")


def _raw() -> dict[str, object]:
    return dict(asdict(load_default_config()))


def _admit(
    registry: LiveSignalRegistry,
    authority: ProvenanceAuthority,
    hyp: str,
    trial: int,
    *,
    instrument: str = "MES",
    quantity: float = 2.0,
    notional: float = 10_000.0,
    oos: tuple[float, ...] = RICH_OOS,
    pbo: float = 0.12,
    dsr: float = 0.99,
    n_oos_windows: int | None = 9,
    passed: bool = True,
) -> None:
    mapped = "MES" if instrument == "MES" else "ES" if instrument == "ES" else "NQ" if instrument == "NQ" else "MNQ"
    candidate, validation = seal_promotion_pair(
        authority,
        hypothesis_id=hyp,
        config_id=hyp,
        trial_id=trial,
        instrument=mapped,
        quantity=quantity,
        notional=notional,
        oos=oos,
        pbo=pbo,
        dsr=dsr,
        n_oos_windows=n_oos_windows if n_oos_windows is not None else len(oos),
        passed=passed,
    )
    registry.admit(candidate, validation)


def _config_battery() -> None:
    if (
        CONFIRM_WINDOWS != 2
        or MEANINGFUL_RAMP_DAYS != 12
        or MUTATION_KILL_RATE_MIN != 0.80
        or MUTATION_MIN_MUTANTS != 320
        or MUTATION_EQUIVALENT_MAX_FRAC != 0.10
        or CAMPAIGN_MIN_SIGNALS != 300
        or CAMPAIGN_MIN_SEEDS != 10
        or FAR_HEALTHY_MAX != 0.05
        or FAR_HIGH_VOL_MAX != 0.10
        or DETECTION_RATE_MIN != 0.85
        or TTD_MAX_TRADING_DAYS != 15
        or HIGH_VOL_CONFIRM_WINDOWS != 3
        or TTD_MEDIUM_MAX_TRADING_DAYS != 45
        or MATERIAL_DD_MULT != 1.5
        or MATERIAL_IC_RATIO != 0.50
        or MATERIAL_SHARPE_RATIO != 0.50
        or FAR_HIGH_VOL_TARGET != 0.08
        or FAR_HIGH_VOL_EXTREME_NOT_A_PASS != 0.12
        or HIGH_VOL_REALIZED_WINDOW != 20
        or HIGH_VOL_TRAILING_WINDOW != 252
        or HIGH_VOL_TRAILING_PCT != 0.75
        or HIGH_VOL_REALIZED_MULT != 1.50
        or HIGH_VOL_VIX != 25.0
        or MEDIUM_WINDOW != 40
        or confirm_windows_for("normal") != 2
        or confirm_windows_for("high_vol") != 3
    ):
        raise AssertionError("Steve Phase 4 acceptance floors drifted")
    cfg = load_default_config()
    if cfg.window != 20 or cfg.method != "combined" or cfg.deweight_multiplier != 0.5:
        raise AssertionError("packaged floors drifted")
    if config_from_mapping(_raw()).equity != cfg.equity:
        raise AssertionError("mapping round-trip must equal packaged config")
    extra = _raw()
    extra["rogue"] = 1
    _refuse_msg(ContinuityConfigError, "invalid continuity keys", config_from_mapping, extra)
    missing = _raw()
    del missing["window"]
    _refuse_msg(ContinuityConfigError, "invalid continuity keys", config_from_mapping, missing)
    cases: tuple[tuple[str, object, str], ...] = (
        ("z_deweight", -2.20, "z_deweight"),
        ("z_suspend", -2.70, "z_suspend"),
        ("z_retire", -4.0, "z_retire"),
        ("percentile_deweight", 0.08, "percentile_deweight"),
        ("percentile_suspend", 0.02, "percentile_suspend"),
        ("percentile_retire", 0.0, "percentile_retire"),
        ("cusum_k", 9.0, "cusum_k"),
        ("cusum_h_deweight", 4.0, "cusum_h_deweight"),
        ("cusum_h_suspend", 6.0, "cusum_h_suspend"),
        ("cusum_h_retire", 90.0, "cusum_h_retire"),
        ("sprt_delta", 9.0, "sprt_delta"),
        ("sprt_alpha", 0.20, "sprt_alpha"),
        ("sprt_beta", 0.20, "sprt_beta"),
        ("deweight_multiplier", 0.9, "deweight_multiplier"),
        ("max_signal_notional_pct", 1.0, "max_signal_notional_pct"),
        ("max_instrument_notional_pct", 1.0, "max_instrument_notional_pct"),
        ("max_family_notional_pct", 1.0, "max_family_notional_pct"),
        ("max_cluster_notional_pct", 1.0, "max_cluster_notional_pct"),
        ("equity", 1_000_000_000.0, "equity"),
        ("window", 250, "window"),
        ("pbo_promote_max", 0.9, "pbo_promote_max"),
        ("pbo_reject_min", 0.1, "pbo_reject_min"),
        ("min_oos_windows", 1, "min_oos_windows"),
        ("method", "nope", "method"),
    )
    for key, value, needle in cases:
        raw = _raw()
        raw[key] = value
        _refuse_msg(ContinuityConfigError, needle, config_from_mapping, raw)
    tight = _raw()
    tight["z_deweight"] = -1.50
    if config_from_mapping(tight).z_deweight != -1.50:
        raise AssertionError("stricter z_deweight must load")
    tight_eq = _raw()
    tight_eq["equity"] = 50_000.0
    if config_from_mapping(tight_eq).equity != 50_000.0:
        raise AssertionError("lower equity must load")
    ordered = _raw()
    ordered["z_retire"] = -1.0
    _refuse_msg(ContinuityConfigError, "z thresholds", config_from_mapping, ordered)
    _refuse_msg(ContinuityConfigError, "must be finite", config_from_mapping, {**_raw(), "z_deweight": math.nan})
    _refuse_msg(ContinuityConfigError, "must be > 0", config_from_mapping, {**_raw(), "cusum_k": 0.0})
    _refuse_msg(ContinuityConfigError, "must be in (0, 1)", config_from_mapping, {**_raw(), "sprt_alpha": 0.0})
    _refuse_msg(ContinuityConfigError, "must be in (0, 1)", config_from_mapping, {**_raw(), "sprt_alpha": 1.0})
    _refuse_msg(ContinuityConfigError, "must be a number", config_from_mapping, {**_raw(), "equity": "x"})
    packaged = Path(continuity_config.__file__).with_name("limits.toml")
    with TemporaryDirectory() as tmp:
        loose = Path(tmp) / "loose.toml"
        loose.write_text(packaged.read_text(encoding="utf-8").replace("equity = 100000.0", "equity = 1000000000.0"), encoding="utf-8")
        _refuse_msg(ContinuityConfigError, "equity", load_default_config, loose)


def _statistics_battery() -> None:
    cfg = load_default_config()
    oos = DEFAULT_OOS
    mean = sum(oos) / float(len(oos))
    var = sum((item - mean) ** 2 for item in oos) / float(len(oos))
    stdev = var**0.5
    if abs(rolling_mean((0.8,) * 20, 20) - 0.8) > 1e-12:
        raise AssertionError("rolling mean of a constant is the constant")
    _refuse(ContinuityRefused, rolling_mean, (0.8,), 0)
    _refuse(ContinuityRefused, rolling_mean, (0.8, 0.8), 20)
    _refuse(ContinuityRefused, rolling_mean, (math.nan,) * 20, 20)
    z0 = z_score(live_mean=mean, oos_mean=mean, oos_stdev=stdev, n=20)
    if abs(z0) > 1e-12:
        raise AssertionError("equal means must have z=0")
    live = mean - 1.0
    got = z_score(live_mean=live, oos_mean=mean, oos_stdev=stdev, n=20)
    want = (live - mean) / (stdev / math.sqrt(20.0))
    if abs(got - want) > 1e-12:
        raise AssertionError("z-score formula drifted")
    if z_score(live_mean=mean, oos_mean=mean, oos_stdev=0.0, n=5) != 0.0:
        raise AssertionError("zero-stdev equal means")
    if z_score(live_mean=mean - 1.0, oos_mean=mean, oos_stdev=0.0, n=5) != float("-inf"):
        raise AssertionError("zero-stdev decay must be -inf")
    _refuse(ContinuityRefused, z_score, live_mean=mean, oos_mean=mean, oos_stdev=stdev, n=0)
    _refuse(ContinuityRefused, z_score, live_mean=math.nan, oos_mean=mean, oos_stdev=stdev, n=20)
    _refuse(ContinuityRefused, z_score, live_mean=mean, oos_mean=mean, oos_stdev=-0.1, n=20)
    if empirical_percentile(min(oos) - 1.0, oos) != 0.0:
        raise AssertionError("below-all percentile is 0")
    if empirical_percentile(max(oos) + 1.0, oos) != 1.0:
        raise AssertionError("above-all percentile is 1")
    _refuse(ContinuityRefused, empirical_percentile, 0.1, ())
    _refuse(ContinuityRefused, empirical_percentile, math.nan, oos)
    path = cusum_down((mean, mean - 1.0, mean - 1.0), mu0=mean, k=0.1)
    if abs(path[0] - 0.0) > 1e-12 or abs(path[1] - 0.9) > 1e-12 or abs(path[2] - 1.8) > 1e-12:
        raise AssertionError(f"CUSUM path drifted {path}")
    _refuse(ContinuityRefused, cusum_down, (0.1,), mu0=mean, k=-1.0)
    _refuse(ContinuityRefused, cusum_down, (math.nan,), mu0=mean, k=0.1)
    llr = sprt_llr((mean - 1.0,) * 10, mu0=mean, mu1=mean - 1.0, sigma=stdev)
    if llr <= 0.0:
        raise AssertionError("SPRT must rise on the alternative")
    _refuse(ContinuityRefused, sprt_llr, (0.1,), mu0=math.nan, mu1=0.0, sigma=1.0)
    _refuse(ContinuityRefused, sprt_llr, (math.nan,), mu0=0.0, mu1=-1.0, sigma=1.0)
    limit = sprt_threshold(alpha=0.05, beta=0.10)
    if abs(limit - math.log((1.0 - 0.10) / 0.05)) > 1e-12:
        raise AssertionError("SPRT threshold formula drifted")
    _refuse(ContinuityRefused, sprt_threshold, alpha=0.0, beta=0.1)
    quiet = assess_decay(tuple(mean for _ in range(30)), oos, cfg)
    if quiet.ready is not True or quiet.severity != 0:
        raise AssertionError("healthy window must stay active")
    loud = assess_decay(tuple(mean - 3.0 * stdev for _ in range(30)), oos, cfg)
    if loud.severity < 1:
        raise AssertionError("mean-shift decay must be detected")
    if assess_decay((0.8, 0.8), oos, cfg).ready is True:
        raise AssertionError("short window must not be ready")
    if _select("combined", z_sev=0, pct_sev=0, cusum_sev=2, sprt_sev=0) != 2:
        raise AssertionError("CUSUM-only suspend must remain")
    if _select("combined", z_sev=1, pct_sev=1, cusum_sev=0, sprt_sev=0) != 1:
        raise AssertionError("combined deweight still needs two votes")
    if _select("combined", z_sev=0, pct_sev=0, cusum_sev=0, sprt_sev=1) != 0:
        raise AssertionError("single SPRT vote must not deweight")
    if _select("combined", z_sev=3, pct_sev=3, cusum_sev=0, sprt_sev=0) != 3:
        raise AssertionError("two retire votes must retire")
    _refuse(ContinuityRefused, assess_decay, (0.1,) * 30, (), cfg)
    _refuse(ContinuityRefused, assess_decay, (0.1,) * 30, (math.nan,) * 6, cfg)


def _types_battery() -> None:
    if family_for("mes") != "es_index" or family_for("MNQ") != "nq_index":
        raise AssertionError("instrument families drifted")
    _refuse_msg(ContinuityRefused, "unknown instrument", family_for, "ZZ")
    _refuse_msg(ContinuityRefused, "unknown instrument", require_cluster, "ZZ")
    if stage_rank("active") != 0 or stage_rank("retired") != 3:
        raise AssertionError("stage ranks drifted")
    if stage_from_rank(0) != "active" or stage_from_rank(2) != "suspended" or stage_from_rank(9) != "retired":
        raise AssertionError("stage_from_rank drifted")
    if stage_from_rank(1) != "deweighted":
        raise AssertionError("rank 1 must be deweighted")
    if stage_weight("deweighted", deweight_multiplier=0.5) != 0.5:
        raise AssertionError("deweight multiplier must be 0.5")
    if stage_weight("active", deweight_multiplier=0.5) != 1.0:
        raise AssertionError("active weight must stay 1.0")
    if tighter_stage("active", "retired") != "retired" or tighter_stage("retired", "active") != "retired":
        raise AssertionError("tighter_stage must be monotonic")
    if finite_series((1.0, 2.0)) != (1.0, 2.0):
        raise AssertionError("finite_series round-trip")
    _refuse(ContinuityRefused, finite_series, (1.0, math.inf))


def _seal_battery(authority: ProvenanceAuthority) -> None:
    body = {
        "signal_id": "hyp-a",
        "hypothesis_id": "hyp-a",
        "config_id": "hyp-a",
        "trial_id": 1,
        "instrument": "MES",
        "family_id": "es_index",
        "cluster_id": "es",
        "base_quantity": 2.0,
        "base_price": 5000.0,
        "base_notional": 10000.0,
        "oos_values": [0.8, 0.7],
        "oos_mean": 0.75,
        "oos_stdev": 0.05,
        "n_oos_windows": 9,
        "median_oos_after_costs": 0.75,
        "pbo": 0.12,
        "dsr_probability": 0.99,
        "purge_applied": True,
        "embargo_applied": True,
        "cost_applied": True,
        "cost_model_id": COST_MODEL_ID,
        "regimes_complete": True,
        "validation_mac": "aa",
        "issue_mac": "bb",
        "report_sha256": "cc",
    }
    dumped = json.dumps(body, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    if canonical_admission(body) != dumped:
        raise AssertionError("admission canonical JSON drifted")
    digest = authority.mac(canonical_admission(body))
    if mac_ok(authority, canonical_admission(body), digest) is not True:
        raise AssertionError("mac_ok must accept the matching digest")
    if mac_ok(authority, canonical_admission(body), "deadbeef") is not False:
        raise AssertionError("mac_ok must reject a bad digest")
    if mac_ok(authority, canonical_admission(body), 1) is not False:
        raise AssertionError("mac_ok must reject a non-string digest")
    seen: set[str] = set()
    if accept_mac(authority, canonical_admission(body), digest, seen) is not True:
        raise AssertionError("first accept_mac must pass")
    if accept_mac(authority, canonical_admission(body), digest, None) is not True:
        raise AssertionError("accept_mac with no seen-set must pass")
    if accept_mac(authority, canonical_admission(body), digest, seen) is not False:
        raise AssertionError("replayed MAC must be refused")
    if accept_mac(authority, canonical_admission(body), 1, seen) is not False:
        raise AssertionError("non-string digest must be refused")
    decay = {
        "schema_version": "research.decay.detected.v1",
        "signal_id": "hyp-a",
        "hypothesis_id": "hyp-a",
        "config_id": "hyp-a",
        "trial_id": 1,
        "agent_id": MONITOR_AGENT_ID,
        "method": "combined",
        "statistic": 1.0,
        "threshold": 2.0,
        "window": 20,
        "live_mean": 0.1,
        "oos_mean": 0.8,
        "oos_stdev": 0.05,
        "percentile": 0.0,
        "cusum": 4.0,
        "sprt_llr": 1.0,
        "stage": "deweighted",
    }
    want_decay = json.dumps(decay, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    if canonical_decay(decay) != want_decay:
        raise AssertionError("decay canonical JSON drifted")
    cap = {
        "schema_version": "research.capacity.scaled.v1",
        "signal_id": "hyp-a",
        "instrument": "MES",
        "family_id": "es_index",
        "cluster_id": "es",
        "agent_id": CAPACITY_AGENT_ID,
        "previous_scale": 1.0,
        "new_scale": 0.4,
        "reasons": ["cluster"],
    }
    if canonical_capacity(cap) != json.dumps(cap, sort_keys=True, separators=(",", ":"), allow_nan=False).encode(
        "utf-8"
    ):
        raise AssertionError("capacity canonical JSON drifted")
    state = {"signal_id": "hyp-a", "admission_mac": "aa", "stage": "active", "weight": 1.0, "capacity_scale": 1.0}
    if canonical_state(state) != json.dumps(state, sort_keys=True, separators=(",", ":"), allow_nan=False).encode(
        "utf-8"
    ):
        raise AssertionError("state canonical JSON drifted")
    finding = {
        "schema_version": "research.guardian.finding.v1",
        "finding_id": "g-1",
        "cadence": "daily",
        "check_id": "trial_logged",
        "signal_id": "hyp-a",
        "agent_id": GUARDIAN_AGENT_ID,
        "passed": False,
        "severity": "violation",
        "suspend_proposed": True,
        "evidence": {"metric": "trial_id", "observed": "9", "required": "present"},
    }
    if canonical_guardian(finding) != json.dumps(
        finding, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8"):
        raise AssertionError("guardian canonical JSON drifted")
    req = {
        "schema_version": "research.replenishment.requested.v1",
        "request_id": "repl-1",
        "agent_id": "replenish_agent",
        "reason": "active_count",
        "n_active": 0,
        "floor": 2.0,
        "n_requested": 4,
    }
    if canonical_replenish(req) != json.dumps(req, sort_keys=True, separators=(",", ":"), allow_nan=False).encode(
        "utf-8"
    ):
        raise AssertionError("replenish canonical JSON drifted")


def _book_battery(tmp: Path) -> None:
    cfg = load_default_config()
    authority = ProvenanceAuthority()
    registry = LiveSignalRegistry(authority=authority, config=cfg)
    _refuse(ContinuityRefused, registry.increase_weight, "x", 2.0)
    _refuse(ContinuityRefused, registry.restore, "x")
    _refuse_msg(ContinuityRefused, "direct registry insertion", registry.insert_direct, None)
    _refuse_msg(ContinuityRefused, "unknown signal", registry.require, "missing")
    short, short_val = seal_promotion_pair(
        authority,
        hypothesis_id="hyp-short",
        config_id="hyp-short",
        trial_id=1,
        instrument="MES",
        quantity=2.0,
        notional=10_000.0,
        oos=(0.8, 0.81),
        n_oos_windows=6,
    )
    _refuse_msg(ContinuityRefused, "shorter than charter floor", registry.admit, short, short_val)
    failed, failed_val = seal_promotion_pair(
        authority,
        hypothesis_id="hyp-fail",
        config_id="hyp-fail",
        trial_id=2,
        instrument="MES",
        quantity=2.0,
        notional=10_000.0,
        passed=False,
        reject_reasons=("dsr_below_threshold",),
        n_oos_windows=9,
        oos=RICH_OOS,
    )
    _refuse_msg(ContinuityRefused, "validation gate failed", registry.admit, failed, failed_val)
    _admit(registry, authority, "hyp-ok", 3, notional=10_000.0, quantity=2.0)
    signal = registry.require("hyp-ok")
    if signal.weight != 1.0 or signal.stage != "active" or registry.verify(signal) is not True:
        raise AssertionError("admit must seal an active signal")
    if abs(signal.base_price - 5_000.0) > 1e-12:
        raise AssertionError("base_price must be notional/quantity")
    if abs(signal.effective_notional() - 10_000.0) > 1e-9:
        raise AssertionError("active effective notional must equal base")
    if registry.n_active() != 1:
        raise AssertionError("n_active after admit")
    if abs(registry.capacity_weight() - 1.0) > 1e-12:
        raise AssertionError("capacity_weight after admit")
    _refuse(ContinuityRefused, registry.insert, signal)
    _refuse_msg(ContinuityRefused, "hypothesis_already_live", registry.admit, *_pair(authority, "hyp-ok", 99))
    replay_c, replay_v = seal_promotion_pair(
        authority,
        hypothesis_id="hyp-replay",
        config_id="hyp-replay",
        trial_id=3,
        instrument="MES",
        quantity=2.0,
        notional=10_000.0,
        oos=RICH_OOS,
        n_oos_windows=9,
        dsr=0.99,
    )
    _refuse_msg(ContinuityRefused, "trial_replay", registry.admit, replay_c, replay_v)
    prov_c, prov_v = seal_promotion_pair(
        authority,
        hypothesis_id="hyp-prov",
        config_id="hyp-prov",
        trial_id=21,
        instrument="MES",
        quantity=2.0,
        notional=10_000.0,
        oos=RICH_OOS,
        n_oos_windows=9,
        dsr=0.99,
    )
    _refuse_msg(
        ContinuityRefused,
        "promotion provenance_invalid",
        registry.admit,
        prov_c.model_copy(update={"issue_mac": "ab" * 32}),
        prov_v,
    )
    _refuse_msg(
        ContinuityRefused,
        "validation provenance_invalid",
        registry.admit,
        prov_c,
        prov_v.model_copy(update={"provenance_mac": "cd" * 32}),
    )
    lowered = registry.apply_stage("hyp-ok", "deweighted")
    if lowered.weight != 0.5 or lowered.stage != "deweighted":
        raise AssertionError("deweight must apply packaged 0.5 multiplier")
    if abs(lowered.effective_notional() - 5_000.0) > 1e-9:
        raise AssertionError("deweighted notional must be base*0.5")
    _refuse_msg(ContinuityRefused, "illegal capacity scale", registry.apply_capacity_scale, "hyp-ok", 1.5)
    _refuse_msg(ContinuityRefused, "illegal capacity scale", registry.apply_capacity_scale, "hyp-ok", math.nan)
    scaled = registry.apply_capacity_scale("hyp-ok", 0.4)
    if abs(scaled.capacity_scale - 0.4) > 1e-12:
        raise AssertionError("capacity scale must drop to 0.4")
    if abs(scaled.effective_notional() - 2_000.0) > 1e-9:
        raise AssertionError("notional must be 10000*0.5*0.4")
    _refuse_msg(ContinuityRefused, "cannot increase", registry.apply_capacity_scale, "hyp-ok", 0.9)
    retired = registry.apply_stage("hyp-ok", "retired")
    if retired.weight != 0.0 or retired.stage != "retired" or registry.n_active() != 0:
        raise AssertionError("retire must zero weight and activity")
    zombie = replace(retired, stage="active", weight=1.0)
    if registry.verify(zombie) is not False:
        raise AssertionError("un-retire without state MAC must fail verify")

    bus = EventBus()
    log = tmp / "exp.jsonl"
    monitor = LivePerformanceMonitor(
        bus=bus,
        registry=registry,
        authority=authority,
        config=cfg,
        experiment_log_path=log,
    )
    _refuse_msg(ContinuityRefused, "non-finite live metric", monitor.observe, "hyp-ok", float("nan"))
    _refuse_msg(ContinuityRefused, "non-finite live metric", monitor.observe, "hyp-ok", math.inf)
    _refuse_msg(ContinuityRefused, "non-finite live metric", monitor.observe, "hyp-ok", True)
    _admit(registry, authority, "hyp-sz", 5, quantity=2.0, notional=10_000.0)
    _refuse_msg(ContinuityRefused, "unknown signal", monitor.observe, "missing", 0.8)
    _admit(registry, authority, "hyp-c", 4, quantity=2.0, notional=10_000.0)
    c_mean = sum(RICH_OOS) / float(len(RICH_OOS))
    c_var = sum((item - c_mean) ** 2 for item in RICH_OOS) / float(len(RICH_OOS))
    dropped = c_mean - 3.0 * (c_var**0.5)
    for _ in range(19):
        if monitor.observe("hyp-c", dropped).stage != "active":
            raise AssertionError("unready window must stay active")
    if monitor.observe("hyp-c", dropped).stage != "active":
        raise AssertionError("first ready window must wait for confirmation")
    confirmed = monitor.observe("hyp-c", dropped)
    if confirmed.stage == "active" or confirmed.weight >= 1.0:
        raise AssertionError("second ready window must apply a stage")
    _admit(registry, authority, "hyp-g", 11, quantity=2.0, notional=10_000.0)
    suspended = monitor.apply_guardian_suspend("hyp-g", "guardian:daily")
    if suspended.stage != "suspended" or suspended.weight != 0.0:
        raise AssertionError("guardian suspend must apply immediately")
    sizer = ContinuitySizer(core=RiskCore(load_risk_config(), equity=cfg.equity), registry=registry)
    now = datetime.now(timezone.utc)
    _refuse(ContinuityRefused, sizer.increase_quantity, "hyp-sz", 9.0)
    _refuse_msg(ContinuityRefused, "cannot increase", sizer.propose, "hyp-sz", quantity=9.0, price=100.0, at=now)
    _refuse_msg(ContinuityRefused, "cannot increase", sizer.propose, "hyp-sz", quantity=2.0, price=10_000.0, at=now)
    _refuse_msg(ContinuityRefused, "finite and positive", sizer.propose, "hyp-sz", quantity=-1.0, price=100.0, at=now)
    _refuse_msg(
        ContinuityRefused,
        "regime multiplier",
        sizer.propose,
        "hyp-sz",
        quantity=2.0,
        price=5_000.0,
        at=now,
        regime=RegimeAction(size_multiplier=1.5, throttle=False, vol="low", trend="up"),
    )
    halved = sizer.propose(
        "hyp-sz",
        quantity=2.0,
        price=5_000.0,
        at=now,
        regime=RegimeAction(size_multiplier=0.5, throttle=True, vol="high", trend="down"),
    )
    if halved.kind is DecisionKind.APPROVED and abs(float(halved.quantity) - 1.0) > 1e-9:
        raise AssertionError("regime 0.5 must halve quantity")
    ok = sizer.propose("hyp-sz", quantity=2.0, price=5_000.0, at=now)
    if ok.kind is DecisionKind.APPROVED and ok.quantity > 2.0 + 1e-9:
        raise AssertionError("sizer must not exceed base quantity")
    if abs(_needed(1.0, 20_000.0, 10_000.0) - 0.5) > 1e-12:
        raise AssertionError("capacity scale-back formula drifted")
    if abs(_needed(1.0, 5_000.0, 10_000.0) - 1.0) > 1e-12:
        raise AssertionError("under-cap scale must stay")
    live_sz = registry.require("hyp-sz")
    totals = _sums([live_sz], "instrument")
    if abs(totals["MES"] - live_sz.effective_notional()) > 1e-9:
        raise AssertionError("instrument sum must equal effective notional")

    capacity = CapacityController(
        bus=bus,
        registry=registry,
        authority=authority,
        config=cfg,
        experiment_log_path=log,
    )
    _refuse(ContinuityRefused, capacity.scale_up, "hyp-sz", 1.0)
    _admit(registry, authority, "hyp-es", 6, instrument="ES", quantity=2.0, notional=12_000.0)
    _admit(registry, authority, "hyp-mes2", 7, instrument="MES", quantity=2.0, notional=12_000.0)
    changed = capacity.rebalance()
    if not changed:
        raise AssertionError("cluster cap must scale MES+ES")
    cluster_total = sum(
        item.effective_notional()
        for item in registry.signals()
        if item.instrument in {"ES", "MES"} and item.stage != "retired"
    )
    cap = cfg.max_cluster_notional_pct * cfg.equity
    if cluster_total > cap + 1e-6:
        raise AssertionError("cluster cap must bind MES+ES")
    if cluster_total <= 1.0:
        raise AssertionError("cluster cap must not wipe remaining notional")
    live_sz = registry.require("hyp-sz")
    if live_sz.capacity_scale <= 1e-9:
        raise AssertionError("signal cap must not round-trip through equity inversion")
    post = sizer.propose("hyp-sz", quantity=2.0, price=5_000.0, at=now)
    if post.kind is DecisionKind.APPROVED and post.quantity > 2.0 + 1e-9:
        raise AssertionError("post-cap size must stay at or below base quantity")
    if post.quantity > 1e-9 and abs(float(post.notional) / float(post.quantity) - 5_000.0) > 0.05:
        raise AssertionError("notional must be quantity times price")
    _refuse_msg(
        ContinuityRefused,
        "cannot increase",
        capacity._emit,
        registry.require("hyp-sz"),
        previous_scale=0.1,
        reasons=("signal",),
    )

    snapshot = capture_integrity()
    guardian = GuardianAgent(
        bus=bus,
        registry=registry,
        authority=authority,
        config=cfg,
        experiment_log_path=log,
    )
    _refuse(ContinuityRefused, guardian.set_risk_limits)
    missing_trials = guardian.scan(cadence="daily", baseline=snapshot, trials=())
    if missing_trials.n_violations < 1:
        raise AssertionError("missing trial log must violate")
    if missing_trials.n_ok + missing_trials.n_warn + missing_trials.n_violations != missing_trials.n_checks:
        raise AssertionError("guardian counts must partition findings")
    if missing_trials.n_ok < 1:
        raise AssertionError("intact Risk Core must still emit ok findings")
    broken_live = replace(snapshot, live_risk_hash="0" * 64)
    broken = guardian.scan(cadence="daily", baseline=snapshot, trials=(), live=broken_live)
    if broken.passed is True or "hyp-sz" not in broken.suspend_proposals:
        raise AssertionError("Risk Core hash miss must suspend live signals")
    try:
        guardian.scan(cadence="daily", baseline=snapshot, trials=(), live=object())  # type: ignore[arg-type]
    except ContinuityRefused:
        pass
    else:
        raise AssertionError("guardian must fail closed on a broken snapshot")
    checks = {item.check_id for item in guardian.findings() if item.signal_id == "hyp-sz"}
    needed = {
        "wf_oos_windows",
        "oos_distribution_size",
        "cpcv_purge_embargo",
        "dsr_present",
        "pbo_band",
        "costs",
        "regimes",
        "trial_logged",
        "admission_mac",
        "promotion_via_gate",
        "sealed_gate_passage",
    }
    if not needed.issubset(checks):
        raise AssertionError(f"guardian rows missing {needed - checks}")
    mut_rows = [item for item in guardian.findings() if item.check_id == "mutation_kill_rate"]
    if not mut_rows:
        raise AssertionError("mutation_kill_rate must be scanned")
    _admit(registry, authority, "hyp-pbo", 8, pbo=0.40, dsr=0.99)
    warn = guardian.scan(
        cadence="weekly",
        baseline=snapshot,
        trials=(TrialRecord(trial_id=8, config_id="hyp-pbo", agent_id="hypothesis_agent", metrics={}),),
        decisions=({"hypothesis_id": "hyp-pbo", "kind": "ungated_promotion", "gated": False},),
    )
    if warn.passed is True or "hyp-pbo" not in warn.suspend_proposals:
        raise AssertionError("seeded ungated promotion must suspend")
    pbo_rows = [item for item in guardian.findings() if item.signal_id == "hyp-pbo" and item.check_id == "pbo_band"]
    if not pbo_rows or pbo_rows[-1].severity != "warn":
        raise AssertionError("pbo 0.40 must be a warn band, not ok/violation")
    wf_rows = [
        item
        for item in guardian.findings()
        if item.signal_id == "hyp-sz" and item.check_id == "wf_oos_windows" and item.passed is True
    ]
    if not wf_rows:
        raise AssertionError("n_oos_windows=9 must pass wf_oos_windows")
    happy_ids = ("oos_distribution_size", "cpcv_purge_embargo", "dsr_present", "costs", "regimes")
    for check_id in happy_ids:
        rows = [
            item
            for item in guardian.findings()
            if item.signal_id == "hyp-sz" and item.check_id == check_id and item.passed is True
        ]
        if not rows:
            raise AssertionError(f"hyp-sz must pass {check_id}")

    replenish = ReplenishAgent(
        bus=bus,
        registry=registry,
        authority=authority,
        config=cfg,
        experiment_log_path=log,
    )
    _refuse_msg(ContinuityRefused, "Validation Gate", replenish.shortcut_admit, "hyp-fake")
    if registry.n_active() < cfg.min_active_signals:
        raise AssertionError("book should be above the active floor after admits")
    if replenish.maybe_request(seed=1) is not None:
        raise AssertionError("replenish must no-op above the floor")
    g_live = registry.require("hyp-g")
    registry._signals["hyp-g"] = replace(g_live, admission_mac="0" * 64)
    _refuse_msg(ContinuityRefused, "signal_tampered", monitor.observe, "hyp-g", 0.8)
    _refuse_msg(ContinuityRefused, "signal_tampered", monitor.apply_guardian_suspend, "hyp-g", "x")
    _refuse_msg(
        ContinuityRefused,
        "signal_tampered",
        sizer.propose,
        "hyp-g",
        quantity=2.0,
        price=5_000.0,
        at=now,
    )
    _refuse_msg(
        ContinuityRefused,
        "cannot increase",
        monitor._emit_stage,
        registry.require("hyp-sz"),
        previous_weight=0.1,
        stage="deweighted",
        reason="up",
    )


def _pair(authority: ProvenanceAuthority, hyp: str, trial: int) -> tuple[object, object]:
    return seal_promotion_pair(
        authority,
        hypothesis_id=hyp,
        config_id=hyp,
        trial_id=trial,
        instrument="MES",
        quantity=2.0,
        notional=10_000.0,
        oos=RICH_OOS,
        n_oos_windows=9,
        dsr=0.99,
    )


def _runtime_battery(root: Path) -> None:
    log = root / "exp.jsonl"
    runtime = ContinuityRuntime(audit_path=root / "audit.jsonl", experiment_log_path=log)
    _refuse(ContinuityRefused, runtime.insert_direct, None)
    _refuse(ContinuityRefused, runtime.mutate_thresholds)
    _refuse(ContinuityRefused, runtime.write_risk_core, root / "limits.toml")
    _refuse(ContinuityRefused, runtime.set_risk_limits)
    _refuse(ContinuityRefused, ContinuityRuntime, audit_path=root / "a2.jsonl", experiment_log_path=log, equity=1e9)
    candidate, validation = seal_promotion_pair(
        runtime.authority,
        hypothesis_id="hyp-live",
        config_id="hyp-live",
        trial_id=1,
        instrument="MES",
        quantity=2.0,
        notional=10_000.0,
        oos=RICH_OOS,
        n_oos_windows=9,
        dsr=0.99,
    )
    runtime.admit(candidate, validation)
    live = runtime.registry.require("hyp-live")
    if not runtime.registry.verify(live):
        raise AssertionError("runtime admit must verify")
    mean = sum(DEFAULT_OOS) / len(DEFAULT_OOS)
    staged = False
    for _ in range(40):
        updated = runtime.observe("hyp-live", mean - 0.8)
        if updated.stage != "active":
            staged = True
            if updated.weight >= 1.0:
                raise AssertionError("decay must reduce weight")
            break
    if not staged:
        raise AssertionError("abrupt decay must de-weight")
    before = runtime.registry.require("hyp-live")
    events = runtime.bus.history(RESEARCH_DECAY_TOPIC, limit=20)
    if events:
        try:
            runtime.bus.publish(
                topic=RESEARCH_DECAY_TOPIC,
                producer=MONITOR_AGENT_ID,
                payload=dict(events[-1].payload),
            )
        except PermissionError:
            pass
        else:
            raise AssertionError("replay must be refused")
    after = runtime.registry.require("hyp-live")
    if after.stage != before.stage or after.weight != before.weight:
        raise AssertionError("replay must not change the book")
    empty = ContinuityRuntime(audit_path=root / "audit2.jsonl", experiment_log_path=root / "exp2.jsonl")
    _refuse_msg(ContinuityRefused, "generator counts", empty.replenish.maybe_request, seed=1)
    _refuse_msg(ContinuityRefused, "cadence must be daily or weekly", runtime.guardian_scan, "monthly")
    duplicate = seal_promotion_pair(
        runtime.authority,
        hypothesis_id="hyp-live",
        config_id="hyp-live",
        trial_id=77,
        instrument="MES",
        quantity=2.0,
        notional=10_000.0,
        oos=RICH_OOS,
        n_oos_windows=9,
        dsr=0.99,
    )[0]
    runtime.promotion._issued.append(duplicate)
    skipped = runtime.ingest_promotions()
    if skipped != ():
        raise AssertionError("already-live promotions must be skipped")
    ghost_c, _ghost_v = seal_promotion_pair(
        runtime.authority,
        hypothesis_id="ghost",
        config_id="ghost",
        trial_id=78,
        instrument="MES",
        quantity=2.0,
        notional=10_000.0,
        oos=RICH_OOS,
        n_oos_windows=9,
        dsr=0.99,
    )
    runtime.promotion._issued.append(ghost_c)
    _refuse_msg(ContinuityRefused, "promotion without ValidationResult", runtime.ingest_promotions)
    tiny = run_phase4_detection(
        audit_path=root / "det-audit.jsonl",
        experiment_log_path=root / "det-exp.jsonl",
        n_healthy=1,
        n_decaying=1,
        n_days=40,
        decay_start=8,
        seed=1,
    )
    if tiny.n_healthy != 1 or tiny.n_decaying != 1:
        raise AssertionError("tiny detection campaign shape drifted")
    if tiny.detection_rate < 1.0:
        raise AssertionError("abrupt decay must be detected")
    decaying = [item for item in tiny.paths if item.decaying]
    if not decaying or decaying[0].time_to_detect is None or decaying[0].time_to_detect < 1:
        raise AssertionError("TTD must be measured from decay onset")
    healthy = [item for item in tiny.paths if not item.decaying]
    if healthy and healthy[0].false_alarm and healthy[0].final_stage == "active":
        raise AssertionError("active healthy path is not a false alarm")
    object.__setattr__(runtime, "_snapshot", replace(runtime._snapshot, live_risk_hash="deadbeef"))
    try:
        runtime.observe("hyp-live", 0.8)
    except (ContinuityIntegrityError, ContinuityRefused):
        pass
    else:
        raise AssertionError("observe after Risk Core drift must fail closed")


def _phase5_battery() -> None:
    quiet = tuple(0.75 for _ in range(40))
    if classify_vol_regime(quiet, vix=10.0) != "normal":
        raise AssertionError("quiet VIX must classify normal")
    if classify_vol_regime(quiet, vix=HIGH_VOL_VIX + 1.0) != "high_vol":
        raise AssertionError("VIX>25 must classify high_vol")
    if classify_vol_regime(quiet[:5]) != "normal":
        raise AssertionError("short history must classify normal")
    _refuse_msg(ContinuityRefused, "VIX", classify_vol_regime, quiet, vix=-1.0)
    _refuse(ContinuityRefused, realized_vol, (0.7, 0.8), window=1)
    if realized_vol(tuple(0.70 + 0.01 * index for index in range(20)), window=2) is None:
        raise AssertionError("realized-vol window=2 must compute")
    if trailing_percentile((), pct=0.75) is not None:
        raise AssertionError("empty trailing percentile is None")
    if trailing_percentile((1.0, 2.0, 3.0, 4.0), pct=0.75) != 3.0:
        raise AssertionError("75th percentile drifted")
    _refuse(ContinuityRefused, trailing_percentile, (1.0, 2.0), pct=1.5)
    _refuse(ContinuityRefused, classify_vol_regime, quiet, trailing_window=1)
    loud = tuple(1.0 for _ in range(50)) + tuple(20.0 + float(index) for index in range(30))
    if classify_vol_regime(loud, instrument="ES") != "high_vol":
        raise AssertionError("ES 1.5x-median path must be high_vol")
    labels = label_windows(quiet + loud, vix_path=tuple(10.0 for _ in quiet) + tuple(30.0 for _ in loud))
    if labels[0] != "normal" or labels[-1] != "high_vol":
        raise AssertionError("label_windows must switch between windows")
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
    _refuse_msg(ContinuityRefused, "non-finite live", _max_drawdown, (mean, math.nan))
    if not _ic_halved(0.20 * mean, mean):
        raise AssertionError("IC halved must fire at 20% of OOS mean")
    if _ic_halved(0.80 * mean, mean):
        raise AssertionError("IC must not fire at 80% of OOS mean")
    if not _sharpe_halved(0.10, 1.0, mean, 0.05):
        raise AssertionError("Sharpe collapse must fire")
    ic_break = tuple(mean for _ in range(20)) + tuple(0.20 * mean for _ in range(15))
    ic_high = assess_material(ic_break, oos, cfg, vol_regime="high_vol")
    if ic_high.severity < 1:
        raise AssertionError("IC collapse must still flag in high_vol")
    peak = mean + 0.40
    dd_only = tuple(peak for _ in range(25)) + (peak - 0.40,) + tuple(peak for _ in range(20))
    if not _drawdown_breach(dd_only, oos, 0.05, vol_scale=1.0):
        raise AssertionError("DD helper must flag 1.5x path")
    dd_normal = assess_material(dd_only, oos, cfg, vol_regime="normal")
    if dd_normal.severity < 1:
        raise AssertionError("DD-only path must flag in normal vol")
    dd_high = assess_material(dd_only, oos, cfg, vol_regime="high_vol")
    if dd_high.severity != 0 or dd_high.stage != "active":
        raise AssertionError("packaged high_vol material skips DD-only")
    both = tuple(peak for _ in range(20)) + tuple(0.20 * mean for _ in range(20))
    if assess_material(both, oos, cfg, vol_regime="normal").severity < 2:
        raise AssertionError("IC+DD must suspend")
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
def run() -> None:
    _config_battery()
    _statistics_battery()
    _types_battery()
    _phase5_battery()
    _seal_battery(ProvenanceAuthority())
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        _book_battery(root)
        _runtime_battery(root)
