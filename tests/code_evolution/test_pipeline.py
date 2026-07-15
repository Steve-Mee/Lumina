"""End-to-end pipeline tests: constitution → twin → sandbox → journal."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from lumina_core.code_evolution.pipeline import CodeEvolutionPipeline, run_code_evolution_dry_cycle
from lumina_core.code_evolution.proposal import CodeMutationOperator, CodeMutationProposal


class _FakeTwin:
    def __init__(self, recommendation: bool = True, risk_flags: list[str] | None = None) -> None:
        self.calls: list[Any] = []
        self.recommendation = recommendation
        self.risk_flags = list(risk_flags or [])

    def evaluate_code_proposal(self, proposal: Any) -> dict[str, Any]:
        self.calls.append(proposal)
        return {
            "recommendation": self.recommendation,
            "effective_recommendation": False,  # shadow-like
            "confidence": 0.9 if self.recommendation else 0.1,
            "risk_flags": list(self.risk_flags),
            "explanation": "fake",
            "mode": "shadow",
            "authority": "propose_only",
            "executable": False,
        }


class _FakeBus:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict]] = []

    def publish_validated(self, *, topic: str, producer: str, payload: dict) -> None:
        del producer
        self.events.append((topic, dict(payload)))


def test_disabled_returns_no_proposals(tmp_path: Path):
    pipe = CodeEvolutionPipeline(
        enabled=False,
        twin=_FakeTwin(),
        journal_root=tmp_path / "ce",
        audit_path=tmp_path / "audit.jsonl",
    )
    out = pipe.run_cycle(seed="s1")
    assert out.enabled is False
    assert out.proposals == []
    assert out.decisions == []


def test_happy_path_param_tweak(tmp_path: Path):
    twin = _FakeTwin(recommendation=True)
    bus = _FakeBus()
    pipe = CodeEvolutionPipeline(
        enabled=True,
        max_proposals_per_cycle=1,
        twin=twin,
        event_bus=bus,
        journal_root=tmp_path / "ce",
        audit_path=tmp_path / "audit.jsonl",
    )
    out = pipe.run_cycle(seed="happy1")
    assert out.enabled
    assert len(out.proposals) == 1
    assert len(twin.calls) == 1
    assert len(out.decisions) == 1
    d = out.decisions[0]
    assert d["constitution_passed"] is True
    assert d["sandbox_passed"] is True
    assert d["applied"] is False
    assert d["reason"] == "evaluated_ok_not_applied"
    # journal bundle
    pid = out.proposals[0].proposal_id
    bundle = tmp_path / "ce" / "pending" / pid
    assert (bundle / "proposal.json").exists()
    assert (bundle / "REVERT.json").exists()
    assert (bundle / "before_snapshot.json").exists()
    # bus topics
    topics = {t for t, _ in bus.events}
    assert "evolution.code.proposal.created" in topics
    assert "evolution.code.sandbox.result" in topics
    assert "evolution.code.decision" in topics
    # audit chain fields
    audit_lines = (tmp_path / "audit.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert audit_lines
    rec = json.loads(audit_lines[-1])
    assert rec.get("schema_version")
    assert rec.get("entry_hash")


def test_twin_hard_veto_blocks_sandbox(tmp_path: Path):
    twin = _FakeTwin(recommendation=False, risk_flags=["constitution_code_forbidden:broker"])
    pipe = CodeEvolutionPipeline(
        enabled=True,
        twin=twin,
        journal_root=tmp_path / "ce",
        audit_path=tmp_path / "audit.jsonl",
    )
    out = pipe.run_cycle(seed="veto1")
    assert out.decisions
    d = out.decisions[0]
    assert d["sandbox_passed"] is False
    assert d["reason"] == "twin_blocked"


def test_out_of_bounds_constitution_blocks_before_twin(tmp_path: Path):
    """Force a bad proposal through pipeline by monkeypatching controller."""
    twin = _FakeTwin()
    pipe = CodeEvolutionPipeline(
        enabled=True,
        twin=twin,
        journal_root=tmp_path / "ce",
        audit_path=tmp_path / "audit.jsonl",
    )

    bad = CodeMutationProposal(
        proposal_id="bad_bounds",
        operator=CodeMutationOperator.PARAMETER_TWEAK,
        target="sandbox.params",
        description="bad",
        payload={"key": "ema_fast_window", "old_value": 8.0, "new_value": 99.0},
        rationale="test",
        estimated_loc=1,
        before_snapshot={"ema_fast_window": 8.0},
        after_snapshot={"ema_fast_window": 99.0},
    )
    d = pipe._process_proposal(bad)
    assert d["constitution_passed"] is False
    assert d["reason"] == "constitution_blocked"
    assert twin.calls == []  # twin not called when constitution fails first


def test_reversibility_restores_before_snapshot(tmp_path: Path):
    twin = _FakeTwin()
    pipe = CodeEvolutionPipeline(
        enabled=True,
        twin=twin,
        journal_root=tmp_path / "ce",
        audit_path=tmp_path / "audit.jsonl",
    )
    out = pipe.run_cycle(seed="rev1")
    pid = out.proposals[0].proposal_id
    restored = pipe.journal.restore_from_revert(pid)
    before = pipe.journal.load_before_snapshot(pid)
    assert restored == before
    assert before  # non-empty for param tweak


def test_try_apply_live_always_false(tmp_path: Path):
    twin = _FakeTwin()
    pipe = CodeEvolutionPipeline(
        enabled=True,
        twin=twin,
        journal_root=tmp_path / "ce",
        audit_path=tmp_path / "audit.jsonl",
    )
    out = pipe.run_cycle(seed="apply1")
    pid = out.proposals[0].proposal_id
    res = pipe.journal.try_apply_live(pid)
    assert res["applied"] is False
    assert res["reason"] == "v1_evaluate_only"


def test_dry_cycle_entry(tmp_path: Path):
    twin = _FakeTwin()
    result = run_code_evolution_dry_cycle(
        enabled=True,
        twin=twin,
        journal_root=tmp_path / "ce",
        seed="dry1",
    )
    assert result["enabled"] is True
    assert result["proposals"]
    assert result["decisions"][0]["applied"] is False


def test_live_tree_untouched(tmp_path: Path):
    """Dry cycle must not create/modify files under lumina_core/."""
    twin = _FakeTwin()
    core = Path("lumina_core")
    # sample mtimes of a few known files
    samples = [
        core / "code_evolution" / "__init__.py",
        core / "safety" / "sandboxed_code_executor.py",
    ]
    mtimes = {p: p.stat().st_mtime for p in samples if p.exists()}
    run_code_evolution_dry_cycle(
        enabled=True,
        twin=twin,
        journal_root=tmp_path / "ce",
        seed="notouch",
    )
    for p, mt in mtimes.items():
        assert p.stat().st_mtime == mt
