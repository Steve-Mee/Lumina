"""End-to-end hypothesis → gate → survivors-only PromotionCandidate. Kill rate > 90%."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lumina_core.agent_orchestration.schemas_research import RESEARCH_PROMOTION_TOPIC
from lumina_research.agents.loop import run_phase2_loop
from lumina_research.agents.report import write_kill_rate_reports
from lumina_research.risk_core.types import DecisionKind
from tests.research.phase2_harness import make_agents


REPO_REPORTS = Path("experiments/reports")


@pytest.mark.unit
def test_end_to_end_flow_and_kill_rate_on_synthetic_data(tmp_path: Path) -> None:
    report = run_phase2_loop(
        audit_path=tmp_path / "audit.jsonl",
        experiment_log_path=tmp_path / "exp.jsonl",
        n_noise=23,
        n_planted=2,
        seed=20261028,
        report_dir=tmp_path / "reports",
    )
    assert report.n_hypotheses == 25
    assert report.kill_rate > 0.90
    assert report.n_promoted >= 1
    assert set(report.planted_survived) == set(report.planted_ids)
    assert report.planted_ids
    for hid in report.planted_ids:
        snapshot = next(item for item in report.candidates if item.hypothesis_id == hid)
        assert snapshot.passed_gate is True
        assert snapshot.promoted is True
        assert snapshot.oos_values
        assert snapshot.dsr is not None
        assert snapshot.pbo is not None
        assert snapshot.wfe is not None
        assert snapshot.n_oos_windows >= 6
    for item in report.candidates:
        assert item.oos_values is not None
        assert isinstance(item.reject_reasons, tuple)
    md = (tmp_path / "reports" / "phase2_kill_rate.md").read_text(encoding="utf-8")
    payload = json.loads((tmp_path / "reports" / "phase2_kill_rate.json").read_text(encoding="utf-8"))
    assert "OOS distribution" in md or "oos" in md.lower()
    assert "kill rate" in md.lower()
    assert payload["candidates"]
    for row in payload["candidates"]:
        assert "oos_distribution" in row
        assert "values" in row["oos_distribution"]
        assert "dsr" in row
        assert "pbo" in row
        assert "wfe" in row
    write_kill_rate_reports(report, REPO_REPORTS)
    assert (REPO_REPORTS / "phase2_kill_rate.md").is_file()
    assert (REPO_REPORTS / "phase2_kill_rate.json").is_file()


@pytest.mark.unit
def test_only_survivors_appear_on_promotion_topic(tmp_path: Path) -> None:
    bus, _reg, _auth, hypothesis, validation, promotion = make_agents(tmp_path)
    generated = hypothesis.generate(seed=20261028, counts=(8, 2))
    results = validation.flush()
    issued = promotion.issued()
    history = bus.history(RESEARCH_PROMOTION_TOPIC, limit=50)
    assert len(history) == len(issued)
    issued_ids = {item.hypothesis_id for item in issued}
    failed_ids = {item.hypothesis_id for item in results if not item.passed}
    assert issued_ids.isdisjoint(failed_ids)
    assert len(generated) == 10


@pytest.mark.unit
def test_scaled_risk_core_decision_is_treated_as_approved_with_scaled_size(tmp_path: Path) -> None:
    bus, _reg, _auth, hypothesis, validation, promotion = make_agents(
        tmp_path,
        planted_quantity=3.0,
        planted_price=5_000.0,
    )
    generated = hypothesis.generate(seed=13, counts=(4, 1))
    validation.flush()
    planted = next(item for item in generated if item.planted)
    issued = [item for item in promotion.issued() if item.hypothesis_id == planted.hypothesis_id]
    assert issued, "planted edge must survive so Scaled can be observed"
    candidate = issued[0]
    assert candidate.decision_kind in {DecisionKind.APPROVED.value, DecisionKind.SCALED.value, "approved", "scaled"}
    if candidate.scaled:
        assert candidate.notional < planted.proposed_notional
        assert candidate.quantity < planted.proposed_quantity
        assert candidate.quantity >= 1.0
    assert bus.history(RESEARCH_PROMOTION_TOPIC)
