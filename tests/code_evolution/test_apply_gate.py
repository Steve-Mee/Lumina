"""H5: controlled sandbox-store apply gates."""

from __future__ import annotations

from pathlib import Path

import pytest

from lumina_core.code_evolution.apply_gate import (
    ApplyEvidence,
    ApplyPolicy,
    CodeEvolutionApplyGate,
)
from lumina_core.code_evolution.pipeline import CodeEvolutionPipeline
from lumina_core.code_evolution.proposal import CodeMutationOperator, CodeMutationProposal


class _FakeTwin:
    def evaluate_code_proposal(self, proposal):  # noqa: ANN001
        del proposal
        return {
            "recommendation": True,
            "effective_recommendation": False,
            "confidence": 0.9,
            "risk_flags": [],
            "explanation": "fake",
            "mode": "shadow",
            "authority": "propose_only",
            "executable": False,
        }


def _param_proposal(pid: str = "codevo_param_h5test01") -> CodeMutationProposal:
    return CodeMutationProposal(
        proposal_id=pid,
        operator=CodeMutationOperator.PARAMETER_TWEAK,
        target="sandbox.params",
        description="tweak ema",
        payload={"key": "ema_fast_window", "old_value": 8.0, "new_value": 10.0},
        rationale="test",
        estimated_loc=1,
        before_snapshot={"ema_fast_window": 8.0},
        after_snapshot={"ema_fast_window": 10.0},
        constitution_passed=True,
        twin_recommendation=True,
        sandbox_passed=True,
    )


@pytest.mark.unit
def test_apply_disabled_by_default(tmp_path: Path) -> None:
    gate = CodeEvolutionApplyGate(journal_root=tmp_path / "ce")
    dec = gate.evaluate(
        ApplyEvidence(
            proposal=_param_proposal(),
            constitution_passed=True,
            sandbox_passed=True,
            twin_recommendation=True,
            human_approved=True,
        )
    )
    assert dec.allowed is False
    assert "apply_disabled" in dec.fail_reasons


@pytest.mark.unit
def test_apply_blocked_in_real_capital(tmp_path: Path) -> None:
    gate = CodeEvolutionApplyGate(
        journal_root=tmp_path / "ce",
        policy=ApplyPolicy(apply_enabled=True, require_human_approve=True),
    )
    dec = gate.evaluate(
        ApplyEvidence(
            proposal=_param_proposal(),
            capital_mode="real",
            constitution_passed=True,
            sandbox_passed=True,
            human_approved=True,
        )
    )
    assert dec.allowed is False
    assert "capital_mode_real" in dec.fail_reasons


@pytest.mark.unit
def test_apply_param_with_human_marker(tmp_path: Path) -> None:
    root = tmp_path / "ce"
    gate = CodeEvolutionApplyGate(
        journal_root=root,
        policy=ApplyPolicy(
            apply_enabled=True,
            require_human_approve=True,
            allow_twin_judgment_apply=False,
        ),
    )
    prop = _param_proposal()
    pdir = root / "pending" / prop.proposal_id
    pdir.mkdir(parents=True)
    (pdir / "APPROVED").write_text("approved by test", encoding="utf-8")
    # minimal proposal.json for journal path parity
    import json

    (pdir / "proposal.json").write_text(json.dumps(prop.to_dict()), encoding="utf-8")
    (pdir / "REVERT.json").write_text(
        json.dumps({"restore_snapshot": prop.before_snapshot}),
        encoding="utf-8",
    )

    res = gate.try_apply(
        ApplyEvidence(
            proposal=prop,
            capital_mode="sim",
            constitution_passed=True,
            sandbox_passed=True,
            twin_recommendation=True,
            human_approved=True,
            human_approver="test",
        )
    )
    assert res["applied"] is True
    assert res["reason"] == "applied_sandbox_store"
    params = gate.load_applied_params()
    assert params["ema_fast_window"] == 10.0

    rev = gate.revert_applied(prop.proposal_id)
    assert rev["reverted"] is True
    assert gate.load_applied_params()["ema_fast_window"] == 8.0


@pytest.mark.unit
def test_pipeline_apply_with_human_and_policy(tmp_path: Path) -> None:
    twin = _FakeTwin()
    root = tmp_path / "ce"
    pipe = CodeEvolutionPipeline(
        enabled=True,
        twin=twin,
        journal_root=root,
        audit_path=tmp_path / "audit.jsonl",
        apply_policy=ApplyPolicy(
            apply_enabled=True,
            require_human_approve=True,
            allow_twin_judgment_apply=False,
        ),
    )
    # First cycle: evaluate + journal (no APPROVED yet → not applied)
    out = pipe.run_cycle(seed="h5pipe1")
    assert out.decisions
    assert out.decisions[0]["applied"] is False
    pid = out.proposals[0].proposal_id

    # Human approves, re-apply via journal
    (root / "pending" / pid / "APPROVED").write_text("steve approved h5", encoding="utf-8")
    res = pipe.journal.try_apply_live(
        pid,
        evidence={
            "capital_mode": "sim",
            "constitution_passed": True,
            "sandbox_passed": True,
            "twin_recommendation": True,
            "human_approved": True,
            "human_approver": "steve",
        },
        policy=pipe.apply_policy,
    )
    assert res["applied"] is True
    assert (root / "applied" / "params.json").exists()


@pytest.mark.unit
def test_pipeline_never_applies_in_real_mode(tmp_path: Path) -> None:
    twin = _FakeTwin()
    pipe = CodeEvolutionPipeline(
        enabled=True,
        mode="real",
        twin=twin,
        journal_root=tmp_path / "ce",
        audit_path=tmp_path / "audit.jsonl",
        apply_policy=ApplyPolicy(
            apply_enabled=True,
            require_human_approve=False,
            allow_twin_judgment_apply=True,
        ),
    )
    out = pipe.run_cycle(seed="h5real")
    assert out.decisions[0]["applied"] is False
    # pre_promotion or capital gate
    reason = out.decisions[0]["reason"]
    assert reason in ("pre_promotion_blocked", "apply_gate_blocked") or "real" in str(
        out.decisions[0].get("apply", {})
    )
