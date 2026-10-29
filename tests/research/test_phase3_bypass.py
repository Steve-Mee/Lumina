"""No path may bypass Risk Core, Validation Gate, trial counting, or regime-switch bans."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from lumina_core.agent_orchestration.event_bus import EventBus
from lumina_core.agent_orchestration.schemas_research import (
    GOVERNANCE_AGENT_ID,
    PROMOTION_AGENT_ID,
    REFLECTOR_AGENT_ID,
    RESEARCH_GOVERNANCE_TOPIC,
    RESEARCH_MUTATION_TOPIC,
    RESEARCH_PROMOTION_TOPIC,
    MutationProposed,
    PromotionCandidate,
    SignedReview,
)
from lumina_research import fitness as fitness_mod
from lumina_research.evolution.governance import ReviewAuthority
from lumina_research.evolution.loop import EvolutionIntegrityError
from lumina_research.evolution.reflector import ReflectorRefused
from lumina_research.evolution.regime import RegimeObservation
from lumina_research.evolution.seal import canonical_mutation, review_binding
from lumina_research.evolution.types import (
    GENOME_TARGET,
    LIVE_RISK_TARGET,
    RISK_CORE_TARGET,
    THRESHOLD_TARGET,
    evolution_rationale,
)
from lumina_research.fitness import FitnessRefused, compute_fitness
from lumina_research.validation import gate as gate_mod
from lumina_research.validation import pipeline as pipeline_mod
from lumina_research.validation.types import GateReport
from tests.research.phase3_harness import dummy_genome, make_runtime, sign_protected, write_adr


@pytest.mark.unit
def test_direct_promotion_and_reflector_apply_are_forbidden(tmp_path: Path) -> None:
    runtime = make_runtime(tmp_path)
    with pytest.raises(EvolutionIntegrityError, match="direct promotion"):
        runtime.promote_direct(
            PromotionCandidate.model_validate(
                {
                    "hypothesis_id": "h",
                    "config_id": "c",
                    "trial_id": 1,
                    "agent_id": "promotion_agent",
                    "instrument": "MES",
                    "direction": "BUY",
                    "decision_kind": "approved",
                    "scaled": False,
                    "quantity": 1.0,
                    "notional": 1.0,
                    "risk_reason": "approved",
                    "expected_horizon_bars": 8,
                    "validation_report_sha256": "a" * 64,
                    "validation_mac": "b" * 64,
                    "issue_mac": "c" * 64,
                }
            )
        )
    with pytest.raises(ReflectorRefused, match="only propose"):
        runtime.reflector.apply()
    with pytest.raises(ReflectorRefused, match="only propose"):
        runtime.reflector.emit_candidate()
    with pytest.raises(ReflectorRefused, match="thresholds"):
        runtime.reflector.set_thresholds()
    with pytest.raises(ReflectorRefused, match="Risk Core"):
        runtime.reflector.set_risk_limits()
    with pytest.raises(ReflectorRefused, match="counted"):
        runtime.reflector.skip_trial()
    with pytest.raises(EvolutionIntegrityError, match="counted"):
        runtime.skip_trials()
    with pytest.raises(Exception, match="only propose"):
        runtime.birth.apply()
    with pytest.raises(Exception, match="cannot hard-switch"):
        runtime.birth.switch_strategy()


@pytest.mark.unit
def test_skip_gate_strategy_switch_and_direct_promotion_kinds_die(tmp_path: Path) -> None:
    runtime = make_runtime(tmp_path)
    n0 = runtime.registry.n_trials
    kinds = ("skip_gate", "strategy_switch", "direct_promotion")
    mutations = []
    for index, kind in enumerate(kinds):
        mutations.append(
            runtime.reflector.propose(
                kind=kind,
                target="bypass",
                genome=dummy_genome(),
                rationale=evolution_rationale(f"Adversarial {kind} mutation that must never be admitted xx"),
                seed=10 + index,
                parent_config_id="parent",
                config_id=f"bypass-{kind}",
            )
        )
    assert runtime.registry.n_trials == n0 + 3
    report = runtime.process(tuple(mutations), seed=11)
    assert report.n_admitted == 0
    assert report.n_promoted == 0
    assert report.n_hypotheses == 0
    assert runtime.promotion.issued() == ()
    assert not runtime.bus.history(RESEARCH_PROMOTION_TOPIC)


@pytest.mark.unit
def test_unsigned_and_replayed_mutations_are_rejected(tmp_path: Path) -> None:
    runtime = make_runtime(tmp_path)
    mutation = runtime.reflector.propose(
        kind="noise",
        target=GENOME_TARGET,
        genome=dummy_genome().model_copy(update={"mu": 0.0, "planted": False, "kind": "noise"}),
        rationale=evolution_rationale("Replay and unsigned mutation must not skip governance xx"),
        seed=3,
        parent_config_id="parent",
        config_id="replay-me",
    )
    first = runtime.governance.admit(mutation)
    assert first.admitted is True
    second = runtime.governance.admit(mutation)
    assert second.admitted is False
    assert "mutation_replay" in second.reasons
    unsigned = mutation.model_dump(mode="json")
    unsigned["provenance_mac"] = "0" * 64
    unsigned["config_id"] = "unsigned-mut"
    unsigned["trial_id"] = runtime.registry.n_trials + 1
    third = runtime.governance.admit(unsigned)
    assert third.admitted is False
    assert "provenance_invalid" in third.reasons


@pytest.mark.unit
def test_monkeypatched_gate_is_detected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    runtime = make_runtime(tmp_path)

    def fake_gate(results: object, **kwargs: object) -> tuple[bool, object]:
        del results, kwargs
        raise AssertionError("monkeypatched gate must not run")

    monkeypatch.setattr(gate_mod, "passes_validation_gate", fake_gate)
    with pytest.raises(EvolutionIntegrityError, match="monkeypatched"):
        runtime.assert_intact()


@pytest.mark.unit
def test_monkeypatched_evaluate_is_detected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    runtime = make_runtime(tmp_path)

    def fake_evaluate(**kwargs: object) -> object:
        del kwargs
        raise AssertionError("monkeypatched evaluate must not run")

    monkeypatch.setattr(pipeline_mod, "evaluate_candidate", fake_evaluate)
    with pytest.raises(EvolutionIntegrityError, match="evaluate_candidate"):
        runtime.assert_intact()


@pytest.mark.unit
def test_rebound_instance_evaluate_is_detected(tmp_path: Path) -> None:
    runtime = make_runtime(tmp_path)
    object.__setattr__(runtime.validation, "_evaluate", lambda **kwargs: None)
    with pytest.raises(EvolutionIntegrityError, match="rebound"):
        runtime.assert_intact()


@pytest.mark.unit
def test_fitness_still_refuses_in_sample_pnl(tmp_path: Path) -> None:
    runtime = make_runtime(tmp_path)
    mutation = runtime.birth.open_window(dummy_genome(), seed=8, index=0)
    runtime.process((mutation,), seed=8)
    evaluations = runtime.validation.evaluations()
    assert evaluations
    with pytest.raises(FitnessRefused, match="in-sample"):
        compute_fitness(evaluations[0].report, turnover=0.1, in_sample_pnl=1.0)
    report = evaluations[0].report
    assert isinstance(report, GateReport)


@pytest.mark.unit
def test_rogue_cannot_publish_mutation_or_governance(tmp_path: Path) -> None:
    runtime = make_runtime(tmp_path)
    bus = runtime.bus
    mutation = runtime.reflector.propose(
        kind="noise",
        target=GENOME_TARGET,
        genome=dummy_genome().model_copy(update={"mu": 0.0, "planted": False, "kind": "noise"}),
        rationale=evolution_rationale("Unsigned mutation publish must hit the issuer guard xx"),
        seed=1,
        parent_config_id="parent",
        config_id="guard-mut",
    )
    unsigned = mutation.model_dump(mode="json")
    unsigned["provenance_mac"] = "0" * 64
    with pytest.raises(PermissionError):
        bus.publish(topic=RESEARCH_MUTATION_TOPIC, producer="rogue_agent", payload=unsigned)
    with pytest.raises(PermissionError, match="issuer guard"):
        bus.publish(topic=RESEARCH_MUTATION_TOPIC, producer=REFLECTOR_AGENT_ID, payload=unsigned)
    decision = runtime.governance.admit(mutation)
    gov = decision.model_dump(mode="json")
    gov["provenance_mac"] = "0" * 64
    with pytest.raises(PermissionError, match="issuer guard"):
        bus.publish(topic=RESEARCH_GOVERNANCE_TOPIC, producer=GOVERNANCE_AGENT_ID, payload=gov)
    fresh = EventBus()
    with pytest.raises(PermissionError, match="issuer guard"):
        fresh.publish(topic=RESEARCH_MUTATION_TOPIC, producer=REFLECTOR_AGENT_ID, payload=unsigned)


@pytest.mark.unit
def test_log_contains_timestamp_agent_and_metrics(tmp_path: Path) -> None:
    runtime = make_runtime(tmp_path)
    runtime.birth.noise_child(dummy_genome(), seed=9, index=0)
    log_path = tmp_path / "experiments.jsonl"
    rows = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert rows
    for row in rows:
        assert "timestamp" in row
        assert "agent_id" in row
        assert "metrics" in row
    mutation_rows = [row for row in rows if row["event"] == "mutation"]
    assert mutation_rows
    assert mutation_rows[0]["agent_id"] == REFLECTOR_AGENT_ID


@pytest.mark.unit
def test_allowed_mutation_with_non_genome_target_is_rejected(tmp_path: Path) -> None:
    runtime = make_runtime(tmp_path)
    mutation = runtime.reflector.propose(
        kind="parameter_tune",
        target=THRESHOLD_TARGET,
        genome=dummy_genome(),
        rationale=evolution_rationale("Parameter tune aimed at thresholds must not be admitted"),
        seed=6,
        parent_config_id="parent",
        config_id="tune-wrong-target",
    )
    decision = runtime.governance.admit(mutation)
    assert decision.admitted is False
    assert "target_not_genome" in decision.reasons


@pytest.mark.unit
def test_foreign_mutation_without_local_trial_is_fail_closed(tmp_path: Path) -> None:
    runtime = make_runtime(tmp_path)
    other_dir = tmp_path / "other"
    other_dir.mkdir()
    foreign = make_runtime(other_dir)
    mutation = foreign.birth.noise_child(dummy_genome(), seed=1, index=0)
    with pytest.raises(EvolutionIntegrityError, match="trial counting skipped"):
        runtime.process((mutation,), seed=1)


@pytest.mark.unit
def test_process_honors_regime_observation_without_switching(tmp_path: Path) -> None:
    runtime = make_runtime(tmp_path)
    mutation = runtime.birth.tune(dummy_genome(), seed=4, index=0)
    report = runtime.process(
        (mutation,),
        seed=4,
        regime_obs=RegimeObservation(vol="high", trend="down"),
    )
    assert report.n_admitted == 1
    assert report.n_hypotheses == 1


@pytest.mark.unit
def test_unknown_kind_and_invalid_review_payload_are_rejected(tmp_path: Path) -> None:
    runtime = make_runtime(tmp_path)
    mutation = runtime.reflector.propose(
        kind="noise",
        target=GENOME_TARGET,
        genome=dummy_genome(),
        rationale=evolution_rationale("Unknown kind must classify as forbidden and stay unapplied"),
        seed=12,
        parent_config_id="parent",
        config_id="unknown-kind",
    )
    payload = mutation.model_dump(mode="json")
    payload["kind"] = "not_a_kind"
    payload["provenance_mac"] = runtime.authority.mac(canonical_mutation(payload))
    decision = runtime.governance.admit(payload)
    assert decision.admitted is False
    assert decision.applied is False
    assert "trial_fingerprint_mismatch" in decision.reasons
    adr = write_adr(tmp_path / "adr", THRESHOLD_TARGET, name="0059-bad-review.md")
    protected = runtime.reflector.propose(
        kind="threshold_change",
        target=THRESHOLD_TARGET,
        genome=dummy_genome(),
        rationale=evolution_rationale("Malformed review object must not unlock a threshold write"),
        seed=13,
        parent_config_id="parent",
        config_id="bad-review",
        adr_path=adr.name,
    )
    bad = protected.model_dump(mode="json")
    bad["review"] = {"reviewer_id": "steve"}
    bad["provenance_mac"] = runtime.authority.mac(canonical_mutation(bad))
    decision2 = runtime.governance.admit(bad)
    assert "review_invalid" in decision2.reasons


@pytest.mark.unit
def test_ghost_trial_id_is_not_admitted(tmp_path: Path) -> None:
    runtime = make_runtime(tmp_path)
    local = runtime.birth.noise_child(dummy_genome(), seed=1, index=0)
    payload = local.model_dump(mode="json")
    payload["trial_id"] = 999
    payload["config_id"] = "ghost-999"
    payload["mutation_id"] = "mut-ghost-999"
    payload["provenance_mac"] = runtime.authority.mac(canonical_mutation(payload))
    ghost = MutationProposed.model_validate(payload)
    decision = runtime.governance.admit(ghost)
    assert decision.admitted is False
    assert "trial_not_in_registry" in decision.reasons
    with pytest.raises(EvolutionIntegrityError, match="trial counting skipped"):
        runtime.process((ghost,), seed=1)


@pytest.mark.unit
def test_stolen_trial_id_cannot_change_genome(tmp_path: Path) -> None:
    runtime = make_runtime(tmp_path)
    local = runtime.birth.noise_child(dummy_genome(), seed=1, index=0)
    payload = local.model_dump(mode="json")
    payload["genome"] = dummy_genome().model_copy(update={"mu": 0.01}).model_dump(mode="json")
    payload["provenance_mac"] = runtime.authority.mac(canonical_mutation(payload))
    decision = runtime.governance.admit(payload)
    assert decision.admitted is False
    assert "trial_fingerprint_mismatch" in decision.reasons


@pytest.mark.unit
def test_review_replay_on_new_trial_is_rejected(tmp_path: Path) -> None:
    runtime = make_runtime(tmp_path)
    adr = write_adr(tmp_path / "adr", RISK_CORE_TARGET)
    review = sign_protected(
        runtime,
        adr_path=adr,
        config_id="risk-same",
        kind="risk_core_change",
        target=RISK_CORE_TARGET,
    )
    first = runtime.reflector.propose(
        kind="risk_core_change",
        target=RISK_CORE_TARGET,
        genome=dummy_genome(),
        rationale=evolution_rationale("First risk-core proposal with a valid human review xx"),
        seed=1,
        parent_config_id="parent",
        config_id="risk-same",
        adr_path=adr.name,
        review=review,
    )
    second = runtime.reflector.propose(
        kind="risk_core_change",
        target=RISK_CORE_TARGET,
        genome=dummy_genome(),
        rationale=evolution_rationale("Replay the same signed review on a new trial id xx"),
        seed=2,
        parent_config_id="parent",
        config_id="risk-same",
        adr_path=adr.name,
        review=review,
    )
    d1 = runtime.governance.admit(first)
    d2 = runtime.governance.admit(second)
    assert "protected_recorded_not_applied" in d1.reasons
    assert "review_replay" in d2.reasons
    assert d2.recorded_for_human is False
    assert d2.applied is False


@pytest.mark.unit
def test_live_risk_core_target_without_and_with_forged_review(tmp_path: Path) -> None:
    runtime = make_runtime(tmp_path)
    unsigned = runtime.reflector.propose(
        kind="risk_core_change",
        target=LIVE_RISK_TARGET,
        genome=dummy_genome(),
        rationale=evolution_rationale("Rewrite live lumina_core/risk without ADR or review xx"),
        seed=1,
        parent_config_id="parent",
        config_id="live-risk",
    )
    d0 = runtime.governance.admit(unsigned)
    assert "adr_required" in d0.reasons
    adr = write_adr(tmp_path / "adr", LIVE_RISK_TARGET)
    other = ReviewAuthority(key=b"forged-human-review-key")
    forged = other.sign_review(
        reviewer_id="steve",
        adr_bytes=adr.read_bytes(),
        verdict="approve",
        config_id="live-forged",
        kind="risk_core_change",
        target=LIVE_RISK_TARGET,
    )
    mutation = runtime.reflector.propose(
        kind="risk_core_change",
        target=LIVE_RISK_TARGET,
        genome=dummy_genome(),
        rationale=evolution_rationale("Forged review on live Risk Core must not apply a write"),
        seed=2,
        parent_config_id="parent",
        config_id="live-forged",
        adr_path=adr.name,
        review=forged,
    )
    decision = runtime.governance.admit(mutation)
    assert decision.admitted is False
    assert decision.applied is False
    assert decision.recorded_for_human is False
    assert "review_invalid" in decision.reasons


@pytest.mark.unit
def test_provenance_hmac_cannot_forge_human_review(tmp_path: Path) -> None:
    runtime = make_runtime(tmp_path)
    adr = write_adr(tmp_path / "adr", THRESHOLD_TARGET)
    adr_sha = hashlib.sha256(adr.read_bytes()).hexdigest()
    mut_sha = hashlib.sha256(
        review_binding(config_id="thr-prov", kind="threshold_change", target=THRESHOLD_TARGET)
    ).hexdigest()
    canonical = json.dumps(
        {
            "reviewer_id": "steve",
            "adr_sha256": adr_sha,
            "mutation_sha256": mut_sha,
            "verdict": "approve",
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    review = SignedReview(
        reviewer_id="steve",
        adr_sha256=adr_sha,
        mutation_sha256=mut_sha,
        verdict="approve",
        signature=runtime.authority.mac(canonical),
    )
    mutation = runtime.reflector.propose(
        kind="threshold_change",
        target=THRESHOLD_TARGET,
        genome=dummy_genome(),
        rationale=evolution_rationale("Use research provenance HMAC as a human review signature"),
        seed=1,
        parent_config_id="parent",
        config_id="thr-prov",
        adr_path=adr.name,
        review=review,
    )
    decision = runtime.governance.admit(mutation)
    assert decision.recorded_for_human is False
    assert "review_invalid" in decision.reasons


@pytest.mark.unit
def test_direct_promotion_candidate_cannot_land_on_evolution_bus(tmp_path: Path) -> None:
    runtime = make_runtime(tmp_path)
    payload = {
        "hypothesis_id": "h",
        "config_id": "c",
        "trial_id": 1,
        "agent_id": PROMOTION_AGENT_ID,
        "instrument": "MES",
        "direction": "BUY",
        "decision_kind": "approved",
        "scaled": False,
        "quantity": 1.0,
        "notional": 1.0,
        "risk_reason": "approved",
        "expected_horizon_bars": 8,
        "validation_report_sha256": "a" * 64,
        "validation_mac": "b" * 64,
        "issue_mac": "c" * 64,
    }
    with pytest.raises(PermissionError, match="issuer guard"):
        runtime.bus.publish(
            topic=RESEARCH_PROMOTION_TOPIC,
            producer=PROMOTION_AGENT_ID,
            payload=payload,
        )


@pytest.mark.unit
def test_fitness_swap_is_detected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    runtime = make_runtime(tmp_path)

    def swapped(report: object, *, turnover: float, in_sample_pnl: object = None, **kwargs: object) -> object:
        del in_sample_pnl, kwargs
        return compute_fitness(report, turnover=turnover)

    monkeypatch.setattr(fitness_mod, "compute_fitness", swapped)
    with pytest.raises(EvolutionIntegrityError, match="fitness"):
        runtime.assert_intact()


@pytest.mark.unit
def test_registry_record_rebind_is_detected(tmp_path: Path) -> None:
    runtime = make_runtime(tmp_path)

    def noop(**kwargs: object) -> int:
        del kwargs
        return 1

    object.__setattr__(runtime.registry, "record", noop)
    with pytest.raises(EvolutionIntegrityError, match="trial counting skipped"):
        runtime.assert_intact()


@pytest.mark.unit
def test_overfit_parameter_tune_is_killed(tmp_path: Path) -> None:
    runtime = make_runtime(tmp_path)
    parent = dummy_genome()
    mutation = runtime.birth.overfit_tune(parent, seed=11, index=0)
    assert mutation.kind == "parameter_tune"
    assert mutation.genome.overfit_in_sample is True
    assert mutation.genome.planted is False
    report = runtime.process((mutation,), seed=11)
    assert report.n_admitted == 1
    assert report.n_hypotheses == 1
    assert report.n_overfit_mutations == 1
    assert report.n_overfit_promoted == 0
    assert report.n_promoted == 0
    assert report.n_trials_end > report.n_trials_start
