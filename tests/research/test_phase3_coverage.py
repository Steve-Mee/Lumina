"""Branch coverage for Phase 3 refuse paths, reports, integrity, and seals."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from lumina_core.agent_orchestration.event_bus import EventBus
from lumina_core.agent_orchestration.schemas_research import (
    GOVERNANCE_SCHEMA_VERSION,
    MUTATION_SCHEMA_VERSION,
    EconomicRationale,
    MutationProposed,
    ParameterGenome,
)
from lumina_core.engine.agent_blackboard import AgentBlackboard
from lumina_research.agents.provenance import ProvenanceAuthority
from lumina_research.evolution.governance import GovernanceError, ReviewAuthority, ReviewError, read_adr
from lumina_research.evolution import integrity as integrity_mod
from lumina_research.evolution.integrity import (
    IntegrityError,
    assert_canonical_floors,
    assert_canonical_risk,
    assert_intact,
    capture_integrity,
    refuse_protected_write,
)
from lumina_research.evolution.loop import EvolutionIntegrityError, EvolutionRuntime
from lumina_research.evolution.mutations import copy_genome, mutation_to_draft
from lumina_research.evolution.reflector import ReflectorAgent
from lumina_research.evolution.regime import RegimeAction, throttled_quantity
from lumina_research.evolution.report import (
    MultiSeedEvolutionReport,
    SeedEvolution,
    build_evolution_report,
    write_evolution_reports,
    write_multiseed_evolution_reports,
)
from lumina_research.evolution.seal import canonical_governance, canonical_mutation
from lumina_research.evolution.types import (
    MutationRefused,
    default_parent,
    evolution_rationale,
    require_feasible,
)
from lumina_research.validation.trial_registry import TrialRegistry
from tests.research.phase3_harness import make_runtime, write_adr


def _rationale() -> EconomicRationale:
    return evolution_rationale("Coverage rationale with enough characters for the schema")


@pytest.mark.unit
def test_require_feasible_and_copy_genome_bounds() -> None:
    parent = default_parent()
    require_feasible(parent)
    with pytest.raises(MutationRefused, match="n_obs"):
        copy_genome(parent, n_obs=800)
    with pytest.raises(MutationRefused, match="sigma"):
        copy_genome(parent, sigma=1.0)
    child = copy_genome(parent, mu=0.003)
    assert child.mu == pytest.approx(0.003)
    with pytest.raises(MutationRefused, match="is_size"):
        copy_genome(parent, is_size=10)
    with pytest.raises(MutationRefused, match="oos_size"):
        copy_genome(parent, oos_size=5)
    with pytest.raises(MutationRefused, match="walk-forward"):
        copy_genome(parent, is_size=120, oos_size=60)
    with pytest.raises(MutationRefused, match="quantity"):
        copy_genome(parent, quantity=20.0)


@pytest.mark.unit
def test_integrity_helpers_and_refuse_write(tmp_path: Path) -> None:
    snap = capture_integrity()
    assert_intact(snap)
    assert_canonical_floors()
    assert_canonical_risk()
    with pytest.raises(IntegrityError, match="cannot write"):
        refuse_protected_write(tmp_path / "limits.toml")
    with pytest.raises(TypeError):

        class _RT(EvolutionRuntime):  # type: ignore[misc]
            pass
    broken = replace(snap, live_risk_hash="0" * 64)
    with pytest.raises(IntegrityError, match="lumina_core/risk drifted"):
        assert_intact(broken)
    with pytest.raises(IntegrityError, match="research Risk Core drifted"):
        assert_intact(replace(snap, research_risk_hash="0" * 64))
    with pytest.raises(IntegrityError, match="gate_thresholds.toml drifted"):
        assert_intact(replace(snap, thresholds_toml_hash="0" * 64))
    with pytest.raises(IntegrityError, match="thresholds.py drifted"):
        assert_intact(replace(snap, thresholds_py_hash="0" * 64))
    with pytest.raises(IntegrityError, match="gate.py drifted"):
        assert_intact(replace(snap, gate_py_hash="0" * 64))
    with pytest.raises(IntegrityError, match="gate floor constants drifted"):
        assert_intact(replace(snap, floors=(0.0, 0.0, 0.0, 0.0, 0.0)))
    with pytest.raises(IntegrityError, match="Risk Core config drifted"):
        assert_intact(replace(snap, risk_file=(0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)))
    with pytest.raises(IntegrityError, match="bound validation gate rebound"):
        assert_intact(replace(snap, bound_gate_id=0))
    with pytest.raises(IntegrityError, match="evaluate_candidate monkeypatched"):
        assert_intact(replace(snap, evaluate_id=0))


@pytest.mark.unit
def test_empty_evolution_report_markdown(tmp_path: Path) -> None:
    report = build_evolution_report(
        seed=0,
        mutations=(),
        decisions=(),
        results=(),
        promotions=(),
        planted_flags={},
        n_trials_start=0,
        n_trials_end=0,
        floors_intact=True,
        risk_core_intact=True,
    )
    md_path, _json_path = write_evolution_reports(report, tmp_path)
    assert "_(none)_" in md_path.read_text(encoding="utf-8")
    empty = MultiSeedEvolutionReport.from_seeds(())
    assert empty.kill_rate == 0.0
    md2, _j2 = write_multiseed_evolution_reports(empty, tmp_path)
    assert "0.0000" in md2.read_text(encoding="utf-8")
    filled = MultiSeedEvolutionReport.from_seeds(
        (
            SeedEvolution(seed=1, instrument="MES", report=report),
        )
    )
    assert filled.n_mutations == 0


@pytest.mark.unit
def test_canonical_bytes_and_mac_ok(tmp_path: Path) -> None:
    authority = ProvenanceAuthority(key=b"k" * 16)
    fields = {
        "schema_version": MUTATION_SCHEMA_VERSION,
        "mutation_id": "mut-x",
        "parent_config_id": "p",
        "config_id": "c",
        "trial_id": 1,
        "agent_id": "reflector_agent",
        "kind": "noise",
        "target": "genome",
        "seed": 1,
        "genome": default_parent().model_dump(mode="json"),
        "rationale": _rationale().model_dump(mode="json"),
        "adr_path": "",
        "review": None,
    }
    mac = authority.mac(canonical_mutation(fields))
    assert authority.mac_ok(canonical_mutation(fields), mac) is True
    assert authority.mac_ok(canonical_mutation(fields), "aa") is False
    gov = {
        "schema_version": GOVERNANCE_SCHEMA_VERSION,
        "mutation_id": "mut-x",
        "config_id": "c",
        "trial_id": 1,
        "agent_id": "governance_agent",
        "kind": "noise",
        "admitted": False,
        "recorded_for_human": False,
        "applied": False,
        "reasons": ["doubt"],
    }
    gmac = authority.mac(canonical_governance(gov))
    assert authority.mac_ok(canonical_governance(gov), gmac) is True
    MutationProposed.model_validate({**fields, "provenance_mac": mac})
    ParameterGenome.model_validate(default_parent().model_dump())
    with pytest.raises(KeyError, match="reasons"):
        canonical_governance({**gov, "reasons": object()})


@pytest.mark.unit
def test_reflector_without_generators_paths(tmp_path: Path) -> None:
    bus = EventBus()
    with pytest.raises(MutationRefused, match="config_id"):
        ReflectorAgent(
            bus=bus,
            registry=TrialRegistry(tmp_path / "a.jsonl"),
            authority=ProvenanceAuthority(),
            experiment_log_path=tmp_path / "e.jsonl",
        ).propose(
            kind="noise",
            target="genome",
            genome=default_parent(),
            rationale=_rationale(),
            seed=1,
            parent_config_id="p",
            config_id="  ",
        )
    agent = ReflectorAgent(
        bus=bus,
        registry=TrialRegistry(tmp_path / "b.jsonl"),
        authority=ProvenanceAuthority(),
        experiment_log_path=tmp_path / "e.jsonl",
    )
    with pytest.raises(MutationRefused, match="target"):
        agent.propose(
            kind="noise",
            target=" ",
            genome=default_parent(),
            rationale=_rationale(),
            seed=1,
            parent_config_id="p",
            config_id="cfg",
        )
    with pytest.raises(TypeError):

        class _Ref(ReflectorAgent):  # type: ignore[misc]
            pass
    proposed = agent.propose(
        kind="noise",
        target="genome",
        genome=default_parent().model_copy(update={"mu": 0.0, "planted": False, "kind": "noise"}),
        rationale=_rationale(),
        seed=2,
        parent_config_id="p",
        config_id="cfg-ok",
    )
    dumped = proposed.model_dump(mode="json")
    assert agent._guard("rogue", dumped) is False
    assert agent._guard("reflector_agent", {"mutation_id": "x"}) is False
    dumped["provenance_mac"] = 1
    assert agent._guard("reflector_agent", dumped) is False
    qty_bad = default_parent()
    with pytest.raises(Exception, match="non-positive"):
        throttled_quantity(
            qty_bad,
            RegimeAction(size_multiplier=0.0, throttle=True, vol="high", trend="down"),
        )


@pytest.mark.unit
def test_blackboard_evolution_loop(tmp_path: Path) -> None:
    board = AgentBlackboard(persistence_path=tmp_path / "bb.jsonl")
    adr_root = tmp_path / "adr"
    adr_root.mkdir()
    runtime = EvolutionRuntime(
        audit_path=tmp_path / "audit.jsonl",
        experiment_log_path=tmp_path / "exp.jsonl",
        adr_root=adr_root,
        blackboard=board,
        review_key=b"phase3-human-review-key",
    )
    parent = default_parent()
    mutation = runtime.birth.noise_child(parent, seed=3, index=0)
    report = runtime.process((mutation,), seed=3)
    assert report.n_mutations == 1
    assert board.latest("research.mutation.proposed") is not None
    assert board.latest("research.governance.decision") is not None


@pytest.mark.unit
def test_read_adr_missing_file_and_bad_name(tmp_path: Path) -> None:
    root = tmp_path / "adr"
    root.mkdir()
    with pytest.raises(GovernanceError, match="adr_filename_invalid"):
        read_adr("not-an-adr.txt", adr_root=root, target="x")
    with pytest.raises(GovernanceError, match="adr_missing"):
        read_adr("0057-missing.md", adr_root=root, target="x")
    write_adr(root, "x")
    with pytest.raises(ReviewError, match="verdict"):
        ReviewAuthority(key=b"k" * 16).sign_review(
            reviewer_id="steve",
            adr_bytes=b"x",
            verdict="maybe",
            config_id="c",
            kind="noise",
            target="genome",
        )


@pytest.mark.unit
def test_governance_invalid_trial_id_type(tmp_path: Path) -> None:
    runtime = make_runtime(tmp_path)
    mutation = runtime.birth.noise_child(default_parent(), seed=1, index=0)
    payload = mutation.model_dump(mode="json")
    payload["trial_id"] = True
    payload["provenance_mac"] = runtime.authority.mac(
        canonical_mutation({**payload, "review": payload.get("review")})
    )
    decision = runtime.governance.admit(payload)
    assert "trial_id_invalid" in decision.reasons or "provenance_invalid" in decision.reasons


@pytest.mark.unit
def test_proposed_accessor(tmp_path: Path) -> None:
    runtime = make_runtime(tmp_path)
    assert runtime.reflector.proposed() == ()
    runtime.birth.tune(default_parent(), seed=2, index=0)
    assert len(runtime.reflector.proposed()) == 1
    assert runtime.governance.decisions() == ()


@pytest.mark.unit
def test_review_verify_mismatches_and_governance_guard(tmp_path: Path) -> None:
    runtime = make_runtime(tmp_path)
    adr = write_adr(tmp_path / "adr", "genome")
    review = runtime.reviews.sign_review(
        reviewer_id="steve",
        adr_bytes=adr.read_bytes(),
        verdict="approve",
        config_id="c",
        kind="noise",
        target="genome",
    )
    assert runtime.reviews.verify_review(
        review,
        adr_bytes=b"other-adr",
        config_id="c",
        kind="noise",
        target="genome",
    ) is False
    assert runtime.reviews.verify_review(
        review.model_copy(update={"reviewer_id": "reflector_agent"}),
        adr_bytes=adr.read_bytes(),
        config_id="c",
        kind="noise",
        target="genome",
    ) is False
    assert runtime.reviews.verify_review(
        review,
        adr_bytes=adr.read_bytes(),
        config_id="other",
        kind="noise",
        target="genome",
    ) is False
    mutation = runtime.birth.noise_child(default_parent(), seed=1, index=0)
    decision = runtime.governance.admit(mutation)
    dumped = decision.model_dump(mode="json")
    assert runtime.governance._guard("rogue", dumped) is False
    assert runtime.governance._guard("governance_agent", {"mutation_id": "x"}) is False
    dumped["provenance_mac"] = 1
    assert runtime.governance._guard("governance_agent", dumped) is False


@pytest.mark.unit
def test_canonical_floor_and_risk_drift_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(integrity_mod, "FLOOR_DSR_PROBABILITY_MIN", 0.1)
    with pytest.raises(IntegrityError, match="dsr floor"):
        assert_canonical_floors()
    monkeypatch.setattr(integrity_mod, "FLOOR_DSR_PROBABILITY_MIN", 0.95)
    monkeypatch.setattr(integrity_mod, "FLOOR_WFE_MIN", 0.0)
    with pytest.raises(IntegrityError, match="wfe floor"):
        assert_canonical_floors()
    monkeypatch.setattr(integrity_mod, "FLOOR_WFE_MIN", 0.5)
    monkeypatch.setattr(integrity_mod, "FLOOR_PBO_HARD_REJECT", 0.9)
    with pytest.raises(IntegrityError, match="pbo hard"):
        assert_canonical_floors()
    monkeypatch.setattr(integrity_mod, "FLOOR_PBO_HARD_REJECT", 0.50)
    monkeypatch.setattr(integrity_mod, "FLOOR_PBO_WARNING", 0.9)
    with pytest.raises(IntegrityError, match="pbo warning"):
        assert_canonical_floors()
    monkeypatch.setattr(integrity_mod, "FLOOR_PBO_WARNING", 0.25)
    monkeypatch.setattr(integrity_mod, "FLOOR_MIN_OOS_WINDOWS", 1)
    with pytest.raises(IntegrityError, match="min OOS"):
        assert_canonical_floors()
    monkeypatch.setattr(integrity_mod, "_parse_limits", lambda: (0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0))
    with pytest.raises(IntegrityError, match="limits.toml"):
        assert_canonical_risk()


@pytest.mark.unit
def test_mutation_to_draft_refuses_forbidden_and_protected(tmp_path: Path) -> None:
    runtime = make_runtime(tmp_path)
    action = RegimeAction(size_multiplier=1.0, throttle=False, vol="low", trend="up")
    forbidden = runtime.reflector.propose(
        kind="strategy_switch",
        target="bypass",
        genome=default_parent(),
        rationale=_rationale(),
        seed=1,
        parent_config_id="p",
        config_id="sw",
    )
    with pytest.raises(MutationRefused, match="forbidden"):
        mutation_to_draft(forbidden, action=action)
    protected = runtime.reflector.propose(
        kind="risk_core_change",
        target="lumina_research/risk_core/limits.toml",
        genome=default_parent(),
        rationale=_rationale(),
        seed=2,
        parent_config_id="p",
        config_id="rk",
    )
    with pytest.raises(MutationRefused, match="protected"):
        mutation_to_draft(protected, action=action)


@pytest.mark.unit
def test_applied_protected_change_fail_closes_process(tmp_path: Path) -> None:
    runtime = make_runtime(tmp_path)
    mutation = runtime.birth.noise_child(default_parent(), seed=1, index=0)
    original = runtime.governance.admit

    def lie(payload: object) -> object:
        decision = original(payload)
        return decision.model_copy(update={"applied": True})

    object.__setattr__(runtime.governance, "admit", lie)
    with pytest.raises(EvolutionIntegrityError, match="applied a protected change"):
        runtime.process((mutation,), seed=1)
