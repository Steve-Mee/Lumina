"""Live PromotionGate rejects research evidence without MAC or nt_pit."""

from __future__ import annotations

from pathlib import Path

import pytest

from lumina_core.evolution.promotion_gate import PromotionGate
from tests.evolution.test_promotion_gate import _base_evidence


@pytest.mark.unit
def test_research_without_mac_or_nt_pit_rejected(tmp_path: Path) -> None:
    gate = PromotionGate(audit_path=tmp_path / "pg.jsonl")
    evidence = _base_evidence().model_copy(update={"source": "research"})
    decision = gate.evaluate(evidence.dna_hash, evidence=evidence)
    assert decision.promoted is False
    assert "research_seal" in decision.fail_reasons


@pytest.mark.unit
def test_research_nt_pit_with_mac_can_pass_seal(tmp_path: Path) -> None:
    gate = PromotionGate(audit_path=tmp_path / "pg.jsonl")
    evidence = _base_evidence().model_copy(
        update={
            "source": "research",
            "validation_mac": "ab" * 32,
            "report_sha256": "cd" * 32,
            "tape_kind": "nt_pit",
        }
    )
    decision = gate.evaluate(evidence.dna_hash, evidence=evidence)
    seal = next(item for item in decision.criteria if item.criterion.value == "research_seal")
    assert seal.passed is True


@pytest.mark.unit
def test_dict_evidence_rejected(tmp_path: Path) -> None:
    gate = PromotionGate(audit_path=tmp_path / "pg.jsonl")
    decision = gate.evaluate("dna_1234567890", evidence={"cv_combinatorial": {"pbo": 0.1}})  # type: ignore[arg-type]
    assert decision.promoted is False
    assert "research_seal" in decision.fail_reasons
