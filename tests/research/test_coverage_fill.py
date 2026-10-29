"""Fill fail-closed branches so lumina_research stays above 90% line/branch."""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from lumina_research.fitness import FitnessRefused, compute_fitness
from lumina_research.risk_core import (
    DecisionKind,
    OrderProposal,
    RiskConfig,
    RiskCore,
    load_default_config,
    propose_order,
)
from lumina_research.risk_core.config import RiskConfigError
from lumina_research.risk_core.engine import _Book
from lumina_research.risk_core.seal import RiskCoreSealError
from lumina_research.risk_core.types import Decision, cluster_for
from lumina_research.validation.audit import (
    AuditError,
    AuditLog,
    AuditRecord,
    default_audit_path,
    utc_now_iso,
    write_event,
)
from lumina_research.validation.contracts import CONTRACTS, ContractError, ContractSpec, spec_for
from lumina_research.validation.cost_model import CostModel, CostModelError, MarketSnapshot, apply_costs
from lumina_research.validation.cpcv import (
    CPCVConfig,
    CPCVError,
    combination_count,
    reconstruct_paths,
    run_cpcv,
)
from lumina_research.validation.dsr import DSRError, deflated_sharpe_ratio, expected_max_sharpe, sharpe_standard_error
from lumina_research.validation.gate import passes_validation_gate
from lumina_research.validation.metrics import annualized_sharpe, pearson_moments, period_sharpe
from lumina_research.validation.pbo import PBOError, probability_of_backtest_overfitting, slice_series
from lumina_research.validation.pipeline import evaluate_candidate
from lumina_research.validation.purge import contiguous_segments, purge_train_indices
from lumina_research.validation.thresholds import FrozenThresholds, load_thresholds
from lumina_research.validation.trial_registry import TrialRegistry, TrialRegistryError
from lumina_research.validation.types import OOSDistribution
from lumina_research.validation.walk_forward import (
    WalkForwardConfig,
    WalkForwardError,
    parameter_stability,
    split_walk_forward,
)
from tests.research.synthetic import always_long, constant_markets, noise_returns
from tests.research.test_gate import _good, _registry


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _proposal(**kwargs: object) -> OrderProposal:
    payload = {
        "agent_id": "alpha",
        "instrument": "MES",
        "side": "buy",
        "quantity": 1.0,
        "price": 5000.0,
        "notional": 1000.0,
        "cluster_id": "es_family",
        "submitted_at_utc": _now(),
    }
    payload.update(kwargs)
    return OrderProposal(**payload)  # type: ignore[arg-type]


@pytest.mark.unit
def test_fitness_refuses_bad_inputs(tmp_path: Path) -> None:
    path = tmp_path / "f.jsonl"
    passed, report = passes_validation_gate(_good(path), registry=_registry(path))
    assert passed is True
    with pytest.raises(FitnessRefused, match="in-sample"):
        compute_fitness(report, turnover=0.1, insample_pnl=1.0)
    with pytest.raises(FitnessRefused, match="unknown"):
        compute_fitness(report, turnover=0.1, foo=1)
    with pytest.raises(FitnessRefused, match="GateReport"):
        compute_fitness(object(), turnover=0.0)
    with pytest.raises(FitnessRefused, match="turnover"):
        compute_fitness(report, turnover=float("nan"))
    from dataclasses import replace

    with pytest.raises(FitnessRefused, match="negative"):
        compute_fitness(replace(report, median_oos_after_costs=-0.01), turnover=0.0)
    with pytest.raises(FitnessRefused, match="cost provenance"):
        compute_fitness(replace(report, cost_provenance=None), turnover=0.0)


@pytest.mark.unit
def test_risk_core_error_and_limit_branches() -> None:
    with pytest.raises(TypeError):
        RiskCore("nope", equity=1.0)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        _Book(-1.0)
    core = RiskCore(load_default_config(), equity=100_000.0)
    with pytest.raises(AttributeError):
        core.equity = 1  # type: ignore[misc]
    with pytest.raises(ValueError, match="timezone"):
        core.heartbeat(datetime.now())
    core.heartbeat(_now())
    with pytest.raises(ValueError, match="finite"):
        core.record_pnl(float("nan"))
    with pytest.raises(ValueError, match="finite"):
        core.set_exposure(gross_notional=float("nan"), cluster_id="es_family", cluster_notional=1.0)
    with pytest.raises(ValueError, match=">= 0"):
        core.set_exposure(gross_notional=-1.0, cluster_id="es_family", cluster_notional=0.0)
    with pytest.raises(ValueError, match="unknown"):
        core.set_exposure(gross_notional=1.0, cluster_id="nope", cluster_notional=1.0)

    timed = RiskCore(load_default_config(), equity=100_000.0)
    timed.heartbeat(_now())
    past = _proposal(submitted_at_utc=_now() - timedelta(seconds=5))
    assert timed.propose_order(past).reason == "timestamp_before_heartbeat"

    levered = RiskCore(load_default_config(), equity=100_000.0)
    levered.heartbeat(_now())
    levered.set_exposure(gross_notional=400_000.0, cluster_id="es_family", cluster_notional=0.0)
    lev = levered.propose_order(_proposal(notional=1_000.0))
    assert lev.kind is DecisionKind.REJECTED
    assert lev.reason == "leverage_cap"

    core2 = RiskCore(load_default_config(), equity=100_000.0)
    core2.heartbeat(_now())
    core2.set_exposure(gross_notional=0.0, cluster_id="es_family", cluster_notional=15_000.0)
    cluster = core2.propose_order(_proposal(notional=1_000.0, quantity=1.0))
    assert cluster.kind is DecisionKind.REJECTED
    assert cluster.reason == "correlation_cluster_limit"

    core3 = RiskCore(load_default_config(), equity=100_000.0)
    core3.heartbeat(_now())
    core3.record_pnl(-100_000.0)
    dead = core3.propose_order(_proposal())
    assert dead.kind is DecisionKind.REJECTED

    import lumina_research.risk_core.engine as engine

    popped = RiskCore(load_default_config(), equity=100_000.0)
    engine._DISPATCH.pop(id(popped), None)
    assert popped.propose_order(_proposal()).reason == "kill_switch:tamper"
    with pytest.raises(RuntimeError):
        _ = popped.config

    with pytest.raises(ValueError):
        cluster_for("CL")
    with pytest.raises(ValueError):
        _proposal(agent_id="")
    with pytest.raises(ValueError):
        _proposal(side="hold")
    with pytest.raises(TypeError, match="subclassed"):

        class Soft(Decision):  # type: ignore[misc]
            pass

    with pytest.raises(RiskCoreSealError):
        del engine.propose_order
    with pytest.raises(AttributeError):
        del engine.no_such_name

    naive = _proposal(submitted_at_utc=datetime(2026, 1, 1, 12, 0, 0))
    core_naive = RiskCore(load_default_config(), equity=100_000.0)
    core_naive.heartbeat(_now())
    assert core_naive.propose_order(naive).reason == "timestamp_not_utc"

    mutated = _proposal()
    object.__setattr__(mutated, "quantity", float("nan"))
    assert core_naive.propose_order(mutated).reason == "invalid_quantity"
    mutated2 = _proposal()
    object.__setattr__(mutated2, "price", float("nan"))
    assert core_naive.propose_order(mutated2).reason == "invalid_price"
    mutated3 = _proposal()
    object.__setattr__(mutated3, "notional", float("nan"))
    assert core_naive.propose_order(mutated3).reason == "invalid_notional"
    mutated4 = _proposal()
    object.__setattr__(mutated4, "instrument", "CL")
    assert core_naive.propose_order(mutated4).reason == "unknown_instrument"
    mutated5 = _proposal()
    object.__setattr__(mutated5, "cluster_id", "nq_family")
    assert core_naive.propose_order(mutated5).reason == "cluster_mismatch"

    scaled_lev = RiskCore(load_default_config(), equity=100_000.0)
    scaled_lev.heartbeat(_now())
    scaled_lev.set_exposure(gross_notional=395_000.0, cluster_id="es_family", cluster_notional=0.0)
    scaled = scaled_lev.propose_order(_proposal(notional=10_000.0, quantity=2.0))
    assert scaled.kind in {DecisionKind.SCALED, DecisionKind.REJECTED}

    def _book_of(core: RiskCore) -> _Book:
        bound = engine._DISPATCH[id(core)]
        for fn in (bound.propose, bound.heartbeat, bound.record_pnl, bound.set_exposure):
            for cell in fn.__closure__ or ():
                value = cell.cell_contents
                if type(value).__name__ == "_Book":
                    return value  # type: ignore[return-value]
        raise AssertionError("book not in closure")

    tamper = RiskCore(load_default_config(), equity=100_000.0)
    tamper.heartbeat(_now())
    object.__setattr__(_book_of(tamper), "equity", 1.0)
    assert tamper.propose_order(_proposal()).reason == "kill_switch:tamper"
    tamper_hb = RiskCore(load_default_config(), equity=100_000.0)
    object.__setattr__(_book_of(tamper_hb), "kill", True)
    with pytest.raises(RuntimeError, match="tamper"):
        tamper_hb.heartbeat(_now())
    tamper_pnl = RiskCore(load_default_config(), equity=100_000.0)
    tamper_pnl.heartbeat(_now())
    object.__setattr__(_book_of(tamper_pnl), "equity", 1.0)
    with pytest.raises(RuntimeError, match="tamper"):
        tamper_pnl.record_pnl(1.0)
    tamper_exp = RiskCore(load_default_config(), equity=100_000.0)
    tamper_exp.heartbeat(_now())
    object.__setattr__(_book_of(tamper_exp), "equity", 1.0)
    with pytest.raises(RuntimeError, match="tamper"):
        tamper_exp.set_exposure(gross_notional=1.0, cluster_id="es_family", cluster_notional=1.0)

    with pytest.raises(ValueError):
        _proposal(instrument="")
    with pytest.raises(ValueError):
        _proposal(price=0.0)
    with pytest.raises(ValueError):
        _proposal(notional=0.0)
    with pytest.raises(ValueError):
        _proposal(cluster_id="")


@pytest.mark.unit
def test_gate_evaluation_error_and_formulation_and_floors(tmp_path: Path) -> None:
    path = tmp_path / "g.jsonl"
    registry = _registry(path)
    frozen = load_thresholds()
    assert isinstance(frozen, FrozenThresholds)
    passed, report = passes_validation_gate(_good(path), registry=registry, thresholds=frozen)
    assert passed is True
    assert report.as_promotion_fragments()["cv_combinatorial"]["pbo"] is not None

    class Boom:
        @property
        def n_trials(self) -> int:
            raise RuntimeError("boom")

    passed_err, report_err = passes_validation_gate(_good(tmp_path / "e.jsonl"), registry=Boom())  # type: ignore[arg-type]
    assert passed_err is False
    assert any(reason.startswith("evaluation_error") for reason in report_err.reject_reasons)

    bad_form = tmp_path / "form.jsonl"
    reg2 = _registry(bad_form)
    from dataclasses import replace

    results = _good(bad_form)
    results = replace(
        results,
        dsr=replace(results.dsr, formulation="nope"),
        pbo=replace(results.pbo, formulation="nope"),
        purge_applied=False,
    )
    passed2, report2 = passes_validation_gate(results, registry=reg2)
    assert passed2 is False
    assert "dsr_formulation" in report2.reject_reasons
    assert "pbo_formulation" in report2.reject_reasons
    assert "purge_or_embargo_missing" in report2.reject_reasons

    mismatch = tmp_path / "mm.jsonl"
    reg3 = _registry(mismatch, n=3)
    passed3, report3 = passes_validation_gate(_good(mismatch), registry=reg3)
    assert passed3 is False
    assert "trial_count_mismatch" in report3.reject_reasons


@pytest.mark.unit
def test_metrics_dsr_pbo_purge_walk_forward_cost_audit_registry(tmp_path: Path) -> None:
    assert math.isnan(period_sharpe((0.01,)))
    assert math.isinf(period_sharpe((0.01, 0.01)))
    assert math.isnan(period_sharpe((0.0, 0.0)))
    assert math.isnan(annualized_sharpe((0.01, -0.01), periods_per_year=0.0))
    assert pearson_moments((1.0, 2.0))[0] != pearson_moments((1.0, 2.0))[0]
    assert pearson_moments((1.0, 1.0, 1.0)) == (0.0, 3.0)

    with pytest.raises(DSRError):
        expected_max_sharpe(n_trials=0, sr_std=1.0)
    with pytest.raises(DSRError):
        expected_max_sharpe(n_trials=2, sr_std=float("nan"))
    with pytest.raises(DSRError):
        sharpe_standard_error(sr=0.1, n_observations=1, skew=0.0, kurtosis=3.0)
    with pytest.raises(DSRError):
        sharpe_standard_error(sr=float("nan"), n_observations=10, skew=0.0, kurtosis=3.0)
    with pytest.raises(DSRError):
        deflated_sharpe_ratio((0.01, -0.01), registry=TrialRegistry(tmp_path / "d.jsonl"))

    with pytest.raises(PBOError):
        slice_series((1.0, 2.0), 4)
    with pytest.raises(PBOError):
        slice_series((1.0,) * 8, 3)

    assert contiguous_segments(()) == ()
    with pytest.raises(ValueError):
        purge_train_indices((0, 1), (2,), (0, 1, 2), embargo=-1, n_obs=3)
    assert purge_train_indices((0, 1), (), (0, 1), embargo=0, n_obs=2) == (0, 1)
    assert purge_train_indices((5,), (1,), t1=(0, 0, 0, 0, 0, 0), embargo=0, n_obs=3) == ()
    assert purge_train_indices((0,), (2,), t1=(-1,), embargo=0, n_obs=1) == (0,)

    with pytest.raises(WalkForwardError):
        WalkForwardConfig(is_size=1, oos_size=10, mode="rolling")
    with pytest.raises(WalkForwardError):
        WalkForwardConfig(is_size=20, oos_size=10, mode="slide")  # type: ignore[arg-type]
    with pytest.raises(WalkForwardError):
        WalkForwardConfig(is_size=20, oos_size=10, mode="rolling", embargo=-1)
    assert math.isnan(parameter_stability(({"a": 1.0}, {"b": 1.0})))
    with pytest.raises(WalkForwardError):
        split_walk_forward(10, WalkForwardConfig(is_size=20, oos_size=10, mode="rolling"))
    with pytest.raises(WalkForwardError):
        split_walk_forward(80, WalkForwardConfig(is_size=20, oos_size=10, mode="rolling"), t1=(1,))

    with pytest.raises(CPCVError):
        CPCVConfig(n_groups=6, n_test_groups=6)
    with pytest.raises(CPCVError):
        CPCVConfig(n_groups=6, n_test_groups=2, embargo=-1)
    assert combination_count(5, 9) == 0
    with pytest.raises(CPCVError):
        reconstruct_paths(3, [(0, 1), (0,)])
    with pytest.raises(CPCVError):
        reconstruct_paths(3, [(0, 0)])
    with pytest.raises(CPCVError):
        reconstruct_paths(3, [(0, 1)])
    with pytest.raises(CPCVError):
        run_cpcv((0.01, 0.02), CPCVConfig(n_groups=6, n_test_groups=2), t1=(1,))

    with pytest.raises(CostModelError):
        CostModel().ticks_for_fill(
            spec=spec_for("MES"),
            quantity=1.0,
            market=MarketSnapshot(volume=-1.0, average_volume=10.0, volatility_price=1.0),
        )
    with pytest.raises(CostModelError):
        CostModel().ticks_for_fill(
            spec=spec_for("MES"),
            quantity=1.0,
            market=MarketSnapshot(volume=1.0, average_volume=10.0, volatility_price=-1.0),
        )
    with pytest.raises(CostModelError):
        apply_costs(
            gross_returns=(0.01, 0.01),
            positions=(0.0, 1.0),
            equity=0.0,
            spec="MES",
            markets=(MarketSnapshot(1.0, 1.0, 1.0), MarketSnapshot(1.0, 1.0, 1.0)),
        )
    assert spec_for("mes").root == "MES"
    assert CONTRACTS["ES"].commission_usd_per_side > 0.0
    with pytest.raises(ContractError):
        ContractSpec(
            root="X",
            tick_size=0.5,
            tick_value_usd=1.0,
            multiplier=2.0,
            commission_ticks=0.0,
            half_spread_ticks=0.0,
        )
    with pytest.raises(ContractError):
        ContractSpec(
            root="X",
            tick_size=0.25,
            tick_value_usd=-1.0,
            multiplier=2.0,
            commission_ticks=0.0,
            half_spread_ticks=0.0,
        )
    with pytest.raises(ContractError):
        ContractSpec(
            root="X",
            tick_size=0.25,
            tick_value_usd=1.0,
            multiplier=8.0,
            commission_ticks=0.0,
            half_spread_ticks=0.0,
        )
    with pytest.raises(ContractError):
        ContractSpec(
            root="X",
            tick_size=0.25,
            tick_value_usd=0.25 * 4.0,
            multiplier=4.0,
            commission_ticks=-1.0,
            half_spread_ticks=0.0,
        )

    log = AuditLog(tmp_path / "a.jsonl")
    assert log.path.name == "a.jsonl"
    with pytest.raises(AuditError):
        log.append(AuditRecord(timestamp="not-a-date", agent_id="a", event="gate", metrics={}))
    with pytest.raises(AuditError):
        log.append(AuditRecord(timestamp="2026-01-01T00:00:00", agent_id="a", event="gate", metrics={}))
    with pytest.raises(TypeError):
        write_event(path=tmp_path / "x.jsonl", agent_id="a", event="gate", metrics={}, timestamp="x")
    assert default_audit_path().name.endswith(".jsonl")
    assert "T" in utc_now_iso()

    with pytest.raises(TypeError):

        class Quiet(TrialRegistry):  # type: ignore[misc]
            pass

    registry = TrialRegistry(tmp_path / "t.jsonl")
    with pytest.raises(TrialRegistryError):
        registry.record(config_id="", agent_id="a", metrics={})
    with pytest.raises(TrialRegistryError):
        registry.record(config_id="c", agent_id="", metrics={})
    assert registry.audit_path.name == "t.jsonl"
    registry.record(config_id="c", agent_id="a", metrics={})
    with pytest.raises(AttributeError):
        registry.n_trials = 0  # type: ignore[misc]
    with pytest.raises(AttributeError):
        registry._records = ()  # type: ignore[misc]
    corrupt = tmp_path / "bad.jsonl"
    corrupt.write_text("{not json\n", encoding="utf-8")
    with pytest.raises(TrialRegistryError, match="corrupt"):
        _ = TrialRegistry(corrupt).n_trials

    with pytest.raises(PBOError):
        probability_of_backtest_overfitting([[float("nan")] * 8, [1.0] * 8])
    with pytest.raises(PBOError):
        probability_of_backtest_overfitting([[1.0] * 8, [1.0] * 7 + [2.0, 3.0]])
    with pytest.raises(PBOError):
        probability_of_backtest_overfitting([[1.0] * 8, [1.0] * 8], n_slices=6)


@pytest.mark.unit
def test_config_bounds_and_oos_empty_and_pipeline_turnover(tmp_path: Path) -> None:
    with pytest.raises(RiskConfigError):
        RiskConfig(
            max_position_pct=1.5,
            max_daily_loss_pct=0.02,
            max_total_drawdown_pct=0.1,
            leverage_cap=4.0,
            correlation_cluster_limit_pct=0.15,
            heartbeat_timeout_sec=30.0,
            min_quantity=1.0,
        )
    with pytest.raises(RiskConfigError):
        RiskConfig(
            max_position_pct=0.1,
            max_daily_loss_pct=1.5,
            max_total_drawdown_pct=0.1,
            leverage_cap=4.0,
            correlation_cluster_limit_pct=0.15,
            heartbeat_timeout_sec=30.0,
            min_quantity=1.0,
        )
    with pytest.raises(RiskConfigError):
        RiskConfig(
            max_position_pct=0.1,
            max_daily_loss_pct=0.02,
            max_total_drawdown_pct=0.1,
            leverage_cap=4.0,
            correlation_cluster_limit_pct=1.5,
            heartbeat_timeout_sec=30.0,
            min_quantity=1.0,
        )
    with pytest.raises(RiskConfigError):
        RiskConfig.from_mapping({"max_position_pct": 0.1})
    with pytest.raises(RiskConfigError):
        RiskConfig.from_mapping(
            {
                "max_position_pct": True,
                "max_daily_loss_pct": 0.02,
                "max_total_drawdown_pct": 0.1,
                "leverage_cap": 4.0,
                "correlation_cluster_limit_pct": 0.15,
                "heartbeat_timeout_sec": 30.0,
                "min_quantity": 1.0,
            }
        )
    assert OOSDistribution.from_values(()).is_complete() is False

    audit = tmp_path / "p.jsonl"
    registry = TrialRegistry(audit)
    n = 360
    eps = noise_returns(n=n, sigma=0.008, seed=1)
    gross = tuple(0.004 + eps[i] for i in range(n))
    positions = always_long(n)
    peer, _p = (
        tuple(0.003 + eps[i] for i in range(n)),
        None,
    )
    from tests.research.synthetic import costed

    peer_net, _prov = costed(peer, positions)
    registry.record(config_id="peer", agent_id="e", metrics={})
    evaluation = evaluate_candidate(
        agent_id="e",
        config_id="c",
        gross_returns=gross,
        positions=(1.0,) + tuple(0.0 for _ in range(n - 1)),
        markets=constant_markets(n),
        spec="MES",
        registry=registry,
        peer_net_returns=(peer_net,),
        audit_path=audit,
        market_returns=gross,
    )
    assert evaluation.turnover >= 0.0
    assert propose_order(_proposal()).kind is DecisionKind.REJECTED


@pytest.mark.unit
def test_thresholds_remaining_errors(tmp_path: Path) -> None:
    from lumina_research.validation.thresholds import ThresholdConfigError

    warn = tmp_path / "w.toml"
    warn.write_text(
        "dsr_probability_min = 0.95\nwfe_min = 0.5\npbo_hard_reject = 0.50\npbo_warning = 0.40\nmin_oos_windows = 6\n",
        encoding="utf-8",
    )
    with pytest.raises(ThresholdConfigError):
        load_thresholds(warn)
    windows = tmp_path / "n.toml"
    windows.write_text(
        "dsr_probability_min = 0.95\nwfe_min = 0.5\npbo_hard_reject = 0.50\npbo_warning = 0.25\nmin_oos_windows = 6.0\n",
        encoding="utf-8",
    )
    with pytest.raises(ThresholdConfigError):
        load_thresholds(windows)
    wfe = tmp_path / "f.toml"
    wfe.write_text(
        "dsr_probability_min = 0.95\nwfe_min = -1\npbo_hard_reject = 0.50\npbo_warning = 0.25\nmin_oos_windows = 6\n",
        encoding="utf-8",
    )
    with pytest.raises(ThresholdConfigError):
        load_thresholds(wfe)
