"""Branch coverage for Phase 2 refuse paths, provenance, reports, and the loop."""

from __future__ import annotations

import json
import random
from dataclasses import replace
from pathlib import Path

import pytest

from lumina_core.agent_orchestration.event_bus import DomainEvent, EventBus
from lumina_core.agent_orchestration.schemas_research import (
    RESEARCH_HYPOTHESIS_TOPIC,
    RESEARCH_PROMOTION_TOPIC,
    RESEARCH_VALIDATION_TOPIC,
    EconomicRationale,
    HypothesisProposed,
    PromotionCandidate,
    ValidationResult,
)
from lumina_research.agents.generators import HypothesisDraft, HypothesisGenerator, NoiseGenerator
from lumina_research.agents.hypothesis import HypothesisAgent, HypothesisRefused, _instrument, _require_rationale
from lumina_research.agents.loop import run_multiseed_kill_rate, run_phase2_loop
from lumina_research.agents.objects import as_object_list, mapping_get
from lumina_research.agents.payloads import dump_json, integrity_fields
from lumina_research.agents.promotion import (
    PromotionAgent,
    PromotionRefused,
    _as_float,
    _as_int,
    _as_reasons,
    _gate_pass,
)
from lumina_research.agents.provenance import (
    ProvenanceAuthority,
    validation_fields_from_result,
)
from lumina_research.agents.report import (
    MultiSeedKillRateReport,
    build_kill_rate_report,
    write_kill_rate_reports,
    write_multiseed_kill_rate_reports,
)
from lumina_research.agents.synthetic import materialize
from lumina_research.agents.validation_agent import ValidationAgent, _latest_trial_id
from lumina_research.validation.cost_model import COST_COMPONENTS
from lumina_research.validation.pipeline import missing_evaluation
from lumina_research.validation.trial_registry import TrialRegistry
from lumina_research.validation.types import CostProvenance
from tests.research.phase2_harness import make_agents, make_board, run_small_loop, with_integrity


def _rationale() -> EconomicRationale:
    return EconomicRationale(
        mechanism="Inventory-holding premium after four-leg costs xx",
        why_edge_exists="Impatient demand pays spread and impact to move inventory",
        other_side="Noise traders demanding immediacy on the tape",
        expected_regime="trend-up moderate volatility",
        falsification_criterion="median OOS after costs <= 0 or PBO > 0.50",
    )


def _draft(*, kind: str = "noise", instrument: str = "MES", rationale: object = None) -> HypothesisDraft:
    payload = HypothesisDraft(
        config_id="d0",
        generator_id="g",
        kind="noise",
        instrument="MES",
        seed=1,
        n_obs=360,
        mu=0.0,
        sigma=0.01,
        planted=False,
        proposed_quantity=1.0,
        proposed_price=5000.0,
        proposed_notional=5000.0,
        rationale=_rationale(),
    )
    object.__setattr__(payload, "kind", kind)
    object.__setattr__(payload, "instrument", instrument)
    if rationale is not None or rationale is None and kind == "force_none":
        object.__setattr__(payload, "rationale", rationale)
    return payload


class _ScriptedGenerator(HypothesisGenerator):
    def __init__(self, drafts: tuple[HypothesisDraft, ...]) -> None:
        self._drafts = drafts

    @property
    def generator_id(self) -> str:
        return "scripted"

    def drafts(self, *, rng: object, count: int, start_index: int) -> tuple[HypothesisDraft, ...]:
        del rng, start_index
        return self._drafts[:count] if count < len(self._drafts) else self._drafts


@pytest.mark.unit
def test_require_rationale_accepts_dict_and_refuses_other_types() -> None:
    body = _rationale().model_dump()
    parsed = _require_rationale(body)
    assert parsed.mechanism
    with pytest.raises(HypothesisRefused):
        _require_rationale("not-a-rationale")
    with pytest.raises(HypothesisRefused):
        _require_rationale({"mechanism": "short"})
    with pytest.raises(HypothesisRefused):
        _require_rationale(None)


@pytest.mark.unit
def test_instrument_roots() -> None:
    assert _instrument("es") == "ES"
    assert _instrument("NQ") == "NQ"
    assert _instrument("mes") == "MES"
    assert _instrument("MNQ") == "MNQ"
    with pytest.raises(HypothesisRefused, match="unsupported instrument"):
        _instrument("FOO")


@pytest.mark.unit
def test_generator_dropped_variants_and_unknown_kind(tmp_path: Path) -> None:
    bus = EventBus()
    dropped = HypothesisAgent(
        bus=bus,
        registry=TrialRegistry(tmp_path / "a.jsonl"),
        generators=(_ScriptedGenerator(()),),
        experiment_log_path=tmp_path / "e.jsonl",
    )
    with pytest.raises(HypothesisRefused, match="dropped variants"):
        dropped.generate(seed=1, counts=(1,))
    unknown = HypothesisAgent(
        bus=bus,
        registry=TrialRegistry(tmp_path / "b.jsonl"),
        generators=(_ScriptedGenerator((_draft(kind="mystery"),)),),
        experiment_log_path=tmp_path / "e.jsonl",
    )
    with pytest.raises(HypothesisRefused, match="unknown hypothesis kind"):
        unknown.generate(seed=1, counts=(1,))
    bad_instr = HypothesisAgent(
        bus=bus,
        registry=TrialRegistry(tmp_path / "c.jsonl"),
        generators=(_ScriptedGenerator((_draft(instrument="FOO"),)),),
        experiment_log_path=tmp_path / "e.jsonl",
    )
    with pytest.raises(HypothesisRefused, match="unsupported instrument"):
        bad_instr.generate(seed=1, counts=(1,))


@pytest.mark.unit
def test_subclassing_is_forbidden() -> None:
    with pytest.raises(TypeError):

        class _H(HypothesisAgent):  # type: ignore[misc]
            pass

    with pytest.raises(TypeError):

        class _V(ValidationAgent):  # type: ignore[misc]
            pass

    with pytest.raises(TypeError):

        class _P(PromotionAgent):  # type: ignore[misc]
            pass

    with pytest.raises(TypeError):

        class _A(ProvenanceAuthority):  # type: ignore[misc]
            pass


@pytest.mark.unit
def test_blackboard_loop_publishes_all_three_topics(tmp_path: Path) -> None:
    board = make_board(tmp_path)
    bus, _reg, _auth, hypothesis, validation, promotion = make_agents(tmp_path, blackboard=board)
    generated = hypothesis.generate(seed=21, counts=(3, 1))
    results = validation.flush()
    assert len(generated) == 4
    assert len(results) == 4
    assert board.latest(RESEARCH_HYPOTHESIS_TOPIC) is not None
    assert board.latest(RESEARCH_VALIDATION_TOPIC) is not None
    assert bus.history(RESEARCH_HYPOTHESIS_TOPIC)
    planted = next(item for item in generated if item.planted)
    planted_result = next(item for item in results if item.hypothesis_id == planted.hypothesis_id)
    if planted_result.passed:
        assert promotion.issued()
        assert bus.history(RESEARCH_PROMOTION_TOPIC)


@pytest.mark.unit
def test_validation_missing_evaluation_still_publishes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bus, _reg, _auth, hypothesis, validation, _promo = make_agents(tmp_path)
    hypothesis.generate(seed=2, counts=(1, 0))

    def _boom(hyp: HypothesisProposed) -> object:
        raise RuntimeError("synthetic tape failed")

    monkeypatch.setattr("lumina_research.agents.validation_agent.materialize", _boom)
    results = validation.flush()
    assert len(results) == 1
    assert results[0].passed is False
    assert results[0].oos_distribution is not None
    assert results[0].reject_reasons
    assert bus.history(RESEARCH_VALIDATION_TOPIC)


@pytest.mark.unit
def test_latest_trial_id_fails_closed_when_missing(tmp_path: Path) -> None:
    registry = TrialRegistry(tmp_path / "a.jsonl")
    with pytest.raises(RuntimeError, match="trial missing"):
        _latest_trial_id(registry, "no-such-config")


@pytest.mark.unit
def test_provenance_digest_mismatch_and_missing_fields() -> None:
    authority = ProvenanceAuthority(key=b"k" * 16)
    fields = {
        "schema_version": "research.validation.result.v1",
        "hypothesis_id": "h",
        "config_id": "c",
        "trial_id": 1,
        "agent_id": "validation_agent",
        "passed": False,
        "reject_reasons": ["doubt"],
        "oos_distribution": {
            "values": [0.1],
            "median": 0.1,
            "mean": 0.1,
            "stdev": 0.0,
            "worst": 0.1,
            "best": 0.1,
            "pct_positive": 1.0,
        },
        "dsr": {
            "probability": 0.1,
            "observed_sr": 0.0,
            "expected_max_sr": 0.2,
            "sr_standard_error": 0.1,
            "n_trials": 1,
            "n_observations": 360,
            "skew": 0.0,
            "kurtosis": 3.0,
            "formulation": "bailey_lopez_de_prado_2014",
        },
        "pbo": {
            "pbo": 0.2,
            "n_slices": 8,
            "n_combinations": 70,
            "n_configs": 2,
            "n_below_median": 10,
            "formulation": "cscv_logit_bailey_2014",
            "logit_mean": 0.0,
        },
        "wfe": {
            "wfe": 0.6,
            "mean_is_sharpe": 1.0,
            "mean_oos_sharpe": 0.6,
            "n_windows": 6,
            "mode": "rolling",
            "parameter_stability": 0.5,
        },
        "regimes": {
            "vol_high_sharpe": 0.1,
            "vol_low_sharpe": 0.1,
            "trend_up_sharpe": 0.1,
            "trend_down_sharpe": 0.1,
            "robustness": 1.0,
        },
        "n_oos_windows": 6,
        "median_oos_after_costs": 0.01,
    }
    fields = with_integrity(fields)
    digest, mac = authority.seal_validation(fields)
    payload = {**fields, "report_sha256": "0" * 64, "provenance_mac": mac}
    assert authority.verify_validation(payload) is None
    payload["report_sha256"] = digest
    assert authority.verify_validation(payload) is not None
    assert authority.verify_validation({"provenance_mac": mac}) is None
    assert authority.verify_validation({**payload, "provenance_mac": 123}) is None
    assert authority.guard_promotion("promotion_agent", {}) is False


@pytest.mark.unit
def test_consider_unknown_hypothesis_and_direct_validation_result(tmp_path: Path) -> None:
    _bus, _reg, auth, _h, _v, promotion = make_agents(tmp_path)
    fields = {
        "schema_version": "research.validation.result.v1",
        "hypothesis_id": "hyp-ghost",
        "config_id": "ghost",
        "trial_id": 1,
        "agent_id": "validation_agent",
        "passed": True,
        "reject_reasons": [],
        "oos_distribution": {
            "values": [0.2, 0.3, 0.4, 0.5, 0.1],
            "median": 0.3,
            "mean": 0.3,
            "stdev": 0.1,
            "worst": 0.1,
            "best": 0.5,
            "pct_positive": 1.0,
        },
        "dsr": {
            "probability": 0.99,
            "observed_sr": 0.4,
            "expected_max_sr": 0.05,
            "sr_standard_error": 0.04,
            "n_trials": 4,
            "n_observations": 360,
            "skew": 0.0,
            "kurtosis": 3.0,
            "formulation": "bailey_lopez_de_prado_2014",
        },
        "pbo": {
            "pbo": 0.1,
            "n_slices": 8,
            "n_combinations": 70,
            "n_configs": 4,
            "n_below_median": 5,
            "formulation": "cscv_logit_bailey_2014",
            "logit_mean": 0.2,
        },
        "wfe": {
            "wfe": 0.8,
            "mean_is_sharpe": 1.0,
            "mean_oos_sharpe": 0.8,
            "n_windows": 6,
            "mode": "rolling",
            "parameter_stability": 0.9,
        },
        "regimes": {
            "vol_high_sharpe": 0.2,
            "vol_low_sharpe": 0.2,
            "trend_up_sharpe": 0.2,
            "trend_down_sharpe": 0.2,
            "robustness": 1.0,
        },
        "n_oos_windows": 6,
        "median_oos_after_costs": 0.02,
    }
    fields = with_integrity(fields)
    digest, mac = auth.seal_validation(fields)
    result = ValidationResult.model_validate({**fields, "report_sha256": digest, "provenance_mac": mac})
    assert validation_fields_from_result(result)["hypothesis_id"] == "hyp-ghost"
    assert promotion.consider(result) is None
    assert promotion.issued() == ()


@pytest.mark.unit
def test_gate_pass_independent_floors() -> None:
    good = with_integrity(
        {
            "passed": True,
            "reject_reasons": [],
            "dsr": {"probability": 0.99, "formulation": "bailey_lopez_de_prado_2014"},
            "pbo": {"pbo": 0.1, "formulation": "cscv_logit_bailey_2014"},
            "wfe": {"wfe": 0.8},
            "oos_distribution": {"values": [0.1, 0.2]},
            "n_oos_windows": 6,
            "median_oos_after_costs": 0.01,
        }
    )
    assert _gate_pass(good) is True
    assert _gate_pass({**good, "passed": False}) is False
    assert _gate_pass({**good, "reject_reasons": ["doubt"]}) is False
    assert _gate_pass({**good, "dsr": {"probability": 0.5, "formulation": "bailey_lopez_de_prado_2014"}}) is False
    assert _gate_pass({**good, "pbo": {"pbo": 0.9, "formulation": "cscv_logit_bailey_2014"}}) is False
    assert _gate_pass({**good, "wfe": {"wfe": 0.1}}) is False
    assert _gate_pass({**good, "n_oos_windows": 3}) is False
    assert _gate_pass({**good, "median_oos_after_costs": -0.01}) is False
    assert _gate_pass({**good, "oos_distribution": {"values": []}}) is False
    assert _gate_pass({**good, "dsr": "nope"}) is False
    assert _gate_pass({**good, "reject_reasons": None}) is True
    assert _gate_pass({**good, "purge_applied": False}) is False
    assert _gate_pass({**good, "embargo_applied": False}) is False
    assert _gate_pass({**good, "cost_applied": False}) is False
    assert _gate_pass({**good, "regimes_complete": False}) is False
    assert _gate_pass({**good, "cost_contract_root": "FOO"}) is False
    assert _gate_pass({**good, "cost_model_id": "not-the-cost-model"}) is False
    assert _gate_pass({**good, "dsr": {"probability": 0.99, "formulation": "other"}}) is False
    assert _gate_pass({**good, "pbo": {"pbo": 0.1, "formulation": "other"}}) is False
    assert _as_int(True) is None
    assert _as_int(3) == 3
    assert _as_float(1.5) == pytest.approx(1.5)
    assert _as_float(True) is None
    assert _as_float("x") is None
    assert _as_reasons("not-a-list") == ()


@pytest.mark.unit
def test_consider_error_is_logged(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _bus, _reg, _auth, hypothesis, validation, promotion = make_agents(tmp_path)

    def _boom(self: PromotionAgent, event: object) -> None:
        del self, event
        raise RuntimeError("core exploded")

    monkeypatch.setattr(PromotionAgent, "consider", _boom)
    hypothesis.generate(seed=4, counts=(0, 1))
    results = validation.flush()
    assert results
    log_path = tmp_path / "experiments.jsonl"
    rows = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert any(row["event"] == "kill" and row["metrics"]["reject_reason"] == "consider_error" for row in rows)
    assert promotion.issued() == ()


@pytest.mark.unit
def test_loop_without_report_dir_and_small_harness(tmp_path: Path) -> None:
    report = run_phase2_loop(
        audit_path=tmp_path / "audit.jsonl",
        experiment_log_path=tmp_path / "exp.jsonl",
        n_noise=2,
        n_planted=1,
        seed=11,
    )
    assert report.n_hypotheses == 3
    assert (tmp_path / "reports").exists() is False
    small = run_small_loop(tmp_path / "small", n_noise=2, n_planted=1, seed=12)
    assert small.n_hypotheses == 3  # type: ignore[union-attr]


@pytest.mark.unit
def test_unspecified_reject_counted_in_report() -> None:
    dummy = ValidationResult.model_validate(
        {
            "hypothesis_id": "hyp-x",
            "config_id": "c",
            "trial_id": 1,
            "agent_id": "validation_agent",
            "passed": False,
            "reject_reasons": [],
            "oos_distribution": {
                "values": [0.0],
                "median": 0.0,
                "mean": 0.0,
                "stdev": 0.0,
                "worst": 0.0,
                "best": 0.0,
                "pct_positive": 0.0,
            },
            "dsr": {
                "probability": 0.0,
                "observed_sr": 0.0,
                "expected_max_sr": 0.0,
                "sr_standard_error": 0.0,
                "n_trials": 1,
                "n_observations": 1,
                "skew": 0.0,
                "kurtosis": 0.0,
                "formulation": "bailey_lopez_de_prado_2014",
            },
            "pbo": {
                "pbo": 0.0,
                "n_slices": 0,
                "n_combinations": 0,
                "n_configs": 0,
                "n_below_median": 0,
                "formulation": "cscv_logit_bailey_2014",
                "logit_mean": 0.0,
            },
            "wfe": {
                "wfe": 0.0,
                "mean_is_sharpe": 0.0,
                "mean_oos_sharpe": 0.0,
                "n_windows": 0,
                "mode": "rolling",
                "parameter_stability": 0.0,
            },
            "regimes": {
                "vol_high_sharpe": 0.0,
                "vol_low_sharpe": 0.0,
                "trend_up_sharpe": 0.0,
                "trend_down_sharpe": 0.0,
                "robustness": 0.0,
            },
            "n_oos_windows": 0,
            "median_oos_after_costs": 0.0,
            "report_sha256": "a" * 64,
            "provenance_mac": "b" * 64,
        }
    )
    report = build_kill_rate_report(
        seed=0,
        planted_ids=(),
        results=(dummy,),
        promotions=(),
        planted_flags={},
    )
    assert report.reject_reason_counts["unspecified_reject"] == 1


@pytest.mark.unit
def test_materialize_noise_and_planted_lengths() -> None:
    hyp = HypothesisProposed(
        hypothesis_id="hyp-1",
        config_id="c1",
        trial_id=1,
        agent_id="hypothesis_agent",
        generator_id="noise",
        kind="noise",
        instrument="MES",
        seed=7,
        n_obs=241,
        mu=0.0,
        sigma=0.01,
        planted=False,
        proposed_quantity=1.0,
        proposed_price=5000.0,
        proposed_notional=5000.0,
        rationale=_rationale(),
    )
    gross, positions, markets = materialize(hyp)
    assert len(gross) == 241
    assert len(positions) == 241
    assert len(markets) == 241
    planted = hyp.model_copy(update={"kind": "planted_edge", "planted": True, "mu": 0.004})
    pg, pp, pm = materialize(planted)
    assert len(pg) == 241
    assert all(pos == 1.0 for pos in pp)
    assert len(pm) == 241


@pytest.mark.unit
def test_dump_json_and_noise_zero_count() -> None:
    drafts = NoiseGenerator().drafts(rng=random.Random(1), count=0, start_index=0)
    assert drafts == ()
    dumped = dump_json(_rationale())
    assert "mechanism" in dumped


@pytest.mark.unit
def test_emit_candidate_type_and_malformed_hypothesis(tmp_path: Path) -> None:
    _bus, _reg, _auth, _h, _v, promotion = make_agents(tmp_path)
    with pytest.raises(PromotionRefused):
        promotion.emit_candidate(
            PromotionCandidate.model_validate(
                {
                    "hypothesis_id": "h",
                    "config_id": "c",
                    "trial_id": 1,
                    "agent_id": "promotion_agent",
                    "instrument": "MES",
                    "decision_kind": "approved",
                    "scaled": False,
                    "quantity": 1.0,
                    "notional": 1.0,
                    "risk_reason": "approved",
                    "validation_report_sha256": "a" * 64,
                    "validation_mac": "b" * 64,
                    "issue_mac": "c" * 64,
                }
            )
        )
    promotion.remember_hypothesis("broken", {"instrument": 1})
    assert promotion._lookup("broken") is not None  # type: ignore[misc]
    assert promotion._risk_decide({"instrument": 1}) is None  # type: ignore[misc]
    assert promotion._risk_decide({"instrument": "MES", "proposed_quantity": "x"}) is None  # type: ignore[misc]


@pytest.mark.unit
def test_object_helpers_and_empty_markdown(tmp_path: Path) -> None:
    assert as_object_list((1, 2)) == [1, 2]
    assert as_object_list("nope") is None
    assert mapping_get({"a": 1}, "missing") is None
    assert mapping_get({"a": 1}, "a") == 1
    report = build_kill_rate_report(
        seed=0,
        planted_ids=(),
        results=(),
        promotions=(),
        planted_flags={},
    )
    md_path, _json_path = write_kill_rate_reports(report, tmp_path)
    assert "_(none)_" in md_path.read_text(encoding="utf-8")


@pytest.mark.unit
def test_replayed_trial_id_and_risk_reject(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _bus, _reg, auth, hypothesis, validation, promotion = make_agents(tmp_path)
    generated = hypothesis.generate(seed=8, counts=(0, 1))
    results = validation.flush()
    planted = next(item for item in generated if item.planted)
    source = next(item for item in results if item.hypothesis_id == planted.hypothesis_id)
    original = ProvenanceAuthority.verify_validation

    def _replay(self: ProvenanceAuthority, payload: object) -> dict[str, object] | None:
        verified = original(self, payload)  # type: ignore[misc]
        if verified is None:
            return None
        verified["trial_id"] = int(verified["trial_id"]) + 7
        return verified

    monkeypatch.setattr(ProvenanceAuthority, "verify_validation", _replay)
    assert promotion.consider(source) is None
    monkeypatch.setattr(ProvenanceAuthority, "verify_validation", original)


@pytest.mark.unit
def test_malformed_hypothesis_and_invalid_trial_id(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _bus, _reg, auth, _h, _v, promotion = make_agents(tmp_path)
    fields = {
        "schema_version": "research.validation.result.v1",
        "hypothesis_id": "hyp-malformed",
        "config_id": "malformed",
        "trial_id": 1,
        "agent_id": "validation_agent",
        "passed": True,
        "reject_reasons": [],
        "oos_distribution": {
            "values": [0.2, 0.3],
            "median": 0.25,
            "mean": 0.25,
            "stdev": 0.05,
            "worst": 0.2,
            "best": 0.3,
            "pct_positive": 1.0,
        },
        "dsr": {
            "probability": 0.99,
            "observed_sr": 0.4,
            "expected_max_sr": 0.05,
            "sr_standard_error": 0.04,
            "n_trials": 2,
            "n_observations": 360,
            "skew": 0.0,
            "kurtosis": 3.0,
            "formulation": "bailey_lopez_de_prado_2014",
        },
        "pbo": {
            "pbo": 0.1,
            "n_slices": 8,
            "n_combinations": 70,
            "n_configs": 2,
            "n_below_median": 5,
            "formulation": "cscv_logit_bailey_2014",
            "logit_mean": 0.2,
        },
        "wfe": {
            "wfe": 0.8,
            "mean_is_sharpe": 1.0,
            "mean_oos_sharpe": 0.8,
            "n_windows": 6,
            "mode": "rolling",
            "parameter_stability": 0.9,
        },
        "regimes": {
            "vol_high_sharpe": 0.2,
            "vol_low_sharpe": 0.2,
            "trend_up_sharpe": 0.2,
            "trend_down_sharpe": 0.2,
            "robustness": 1.0,
        },
        "n_oos_windows": 6,
        "median_oos_after_costs": 0.02,
    }
    fields = with_integrity(fields)
    digest, mac = auth.seal_validation(fields)
    result = ValidationResult.model_validate({**fields, "report_sha256": digest, "provenance_mac": mac})
    promotion.remember_hypothesis("hyp-malformed", {"instrument": 1})
    assert promotion.consider(result) is None
    assert promotion.issued() == ()


@pytest.mark.unit
def test_invalid_trial_id_type_does_not_promote(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _bus, _reg, auth, _h, _v, promotion = make_agents(tmp_path)
    fields = with_integrity(
        {
            "schema_version": "research.validation.result.v1",
            "hypothesis_id": "hyp-bad-trial",
            "config_id": "bad-trial",
            "trial_id": 3,
            "agent_id": "validation_agent",
            "passed": True,
            "reject_reasons": [],
            "oos_distribution": {
                "values": [0.2, 0.3],
                "median": 0.25,
                "mean": 0.25,
                "stdev": 0.05,
                "worst": 0.2,
                "best": 0.3,
                "pct_positive": 1.0,
            },
            "dsr": {
                "probability": 0.99,
                "observed_sr": 0.4,
                "expected_max_sr": 0.05,
                "sr_standard_error": 0.04,
                "n_trials": 2,
                "n_observations": 360,
                "skew": 0.0,
                "kurtosis": 3.0,
                "formulation": "bailey_lopez_de_prado_2014",
            },
            "pbo": {
                "pbo": 0.1,
                "n_slices": 8,
                "n_combinations": 70,
                "n_configs": 2,
                "n_below_median": 5,
                "formulation": "cscv_logit_bailey_2014",
                "logit_mean": 0.2,
            },
            "wfe": {
                "wfe": 0.8,
                "mean_is_sharpe": 1.0,
                "mean_oos_sharpe": 0.8,
                "n_windows": 6,
                "mode": "rolling",
                "parameter_stability": 0.9,
            },
            "regimes": {
                "vol_high_sharpe": 0.2,
                "vol_low_sharpe": 0.2,
                "trend_up_sharpe": 0.2,
                "trend_down_sharpe": 0.2,
                "robustness": 1.0,
            },
            "n_oos_windows": 6,
            "median_oos_after_costs": 0.02,
        }
    )
    digest, mac = auth.seal_validation(fields)
    result = ValidationResult.model_validate({**fields, "report_sha256": digest, "provenance_mac": mac})

    def _bad_trial(self: ProvenanceAuthority, payload: object) -> dict[str, object] | None:
        verified = original_verify(self, payload)  # type: ignore[misc]
        if verified is None:
            return None
        verified["trial_id"] = "not-an-int"
        return verified

    original_verify = ProvenanceAuthority.verify_validation
    monkeypatch.setattr(ProvenanceAuthority, "verify_validation", _bad_trial)
    assert promotion.consider(result) is None
    assert promotion.issued() == ()


@pytest.mark.unit
def test_provenance_short_mac_and_non_sequence_reasons() -> None:
    authority = ProvenanceAuthority(key=b"k" * 16)
    assert authority.verify_issue({}) is False
    assert authority.verify_issue({"issue_mac": 1}) is False
    fields = {
        "schema_version": "research.validation.result.v1",
        "hypothesis_id": "h",
        "config_id": "c",
        "trial_id": 1,
        "agent_id": "validation_agent",
        "passed": False,
        "reject_reasons": "doubt",
        "oos_distribution": {},
        "dsr": {},
        "pbo": {},
        "wfe": {},
        "regimes": {},
        "n_oos_windows": 0,
        "median_oos_after_costs": None,
    }
    assert authority.verify_validation({**fields, "provenance_mac": "aa", "report_sha256": "bb"}) is None
    sealed = with_integrity({**fields, "reject_reasons": ["doubt"]})
    digest, mac = authority.seal_validation(sealed)
    assert authority.verify_validation({**sealed, "report_sha256": digest, "provenance_mac": mac[:8]}) is None


@pytest.mark.unit
def test_domain_event_consider_without_mac(tmp_path: Path) -> None:
    _bus, _reg, _auth, _h, _v, promotion = make_agents(tmp_path)
    event = DomainEvent(topic=RESEARCH_VALIDATION_TOPIC, producer="validation_agent", payload={"hypothesis_id": "x"})
    assert promotion.consider(event) is None


@pytest.mark.unit
def test_verify_rejects_non_positive_trial_id() -> None:
    authority = ProvenanceAuthority(key=b"k" * 16)
    fields = with_integrity(
        {
            "schema_version": "research.validation.result.v1",
            "hypothesis_id": "h",
            "config_id": "c",
            "trial_id": 0,
            "agent_id": "validation_agent",
            "passed": False,
            "reject_reasons": ["doubt"],
            "oos_distribution": {
                "values": [],
                "median": None,
                "mean": None,
                "stdev": None,
                "worst": None,
                "best": None,
                "pct_positive": None,
            },
            "dsr": {
                "probability": None,
                "observed_sr": None,
                "expected_max_sr": None,
                "sr_standard_error": None,
                "n_trials": 0,
                "n_observations": 0,
                "skew": None,
                "kurtosis": None,
                "formulation": "bailey_lopez_de_prado_2014",
            },
            "pbo": {
                "pbo": None,
                "n_slices": 0,
                "n_combinations": 0,
                "n_configs": 0,
                "n_below_median": 0,
                "formulation": "cscv_logit_bailey_2014",
                "logit_mean": None,
            },
            "wfe": {
                "wfe": None,
                "mean_is_sharpe": None,
                "mean_oos_sharpe": None,
                "n_windows": 0,
                "mode": "",
                "parameter_stability": None,
            },
            "regimes": {
                "vol_high_sharpe": None,
                "vol_low_sharpe": None,
                "trend_up_sharpe": None,
                "trend_down_sharpe": None,
                "robustness": None,
            },
            "n_oos_windows": 0,
            "median_oos_after_costs": None,
        }
    )
    digest, mac = authority.seal_validation(fields)
    assert authority.verify_validation({**fields, "report_sha256": digest, "provenance_mac": mac}) is None


@pytest.mark.unit
def test_multiseed_helpers_fail_closed_on_empty_and_misaligned(tmp_path: Path) -> None:
    empty = MultiSeedKillRateReport.from_seeds(())
    assert empty.kill_rate == 0.0
    assert empty.false_kill_rate == 0.0
    assert empty.false_survivor_rate == 0.0
    md_path, _json_path = write_multiseed_kill_rate_reports(empty, tmp_path)
    assert "_(none)_" in md_path.read_text(encoding="utf-8")
    with pytest.raises(ValueError, match="align"):
        run_multiseed_kill_rate(
            audit_dir=tmp_path / "a",
            experiment_log_dir=tmp_path / "e",
            seeds=(1, 2),
            instruments=("MES",),
        )


@pytest.mark.unit
def test_integrity_fields_refuse_spoofed_cost_model_id(tmp_path: Path) -> None:
    evaluation = missing_evaluation(
        agent_id="validation_agent",
        audit_path=tmp_path / "a.jsonl",
        registry=TrialRegistry(tmp_path / "a.jsonl"),
    )
    spoofed = CostProvenance(
        model_id="not-the-cost-model",
        model_version="1.0.0",
        components=COST_COMPONENTS,
        applied=True,
        contract_root="MES",
        tick_size=0.25,
        tick_value_usd=1.25,
        commission_ticks=0.5,
    )
    report = replace(evaluation.report, cost_provenance=spoofed)
    fields = integrity_fields(report)
    assert fields["cost_applied"] is False
    assert fields["cost_model_id"] == ""
