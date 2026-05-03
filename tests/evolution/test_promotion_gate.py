from __future__ import annotations

import json
from pathlib import Path

import pytest

from lumina_core.evolution.promotion_gate import PromotionGate, PromotionGateEvidence


def _base_evidence() -> PromotionGateEvidence:
    return PromotionGateEvidence(
        dna_hash="dna_1234567890",
        cv_combinatorial={
            "combinations": 8,
            "mean_oos_sharpe": 0.8,
            "sharpe_positive_pct": 0.75,
            "pbo": 0.2,
            "dsr": 0.35,
        },
        cv_walk_forward={
            "windows": 8,
            "sharpe_positive_pct": 0.75,
        },
        reality_gap_stats={
            "band_status": "YELLOW",
            "gap_trend": "STABLE",
            "mean_gap": 0.35,
        },
        stress_report={
            "stress_ready_for_real_gate": True,
            "worst_case_drawdown": 2000.0,
        },
        live_pnl_samples=[5.0 + (i * 0.02) for i in range(40)],
        backtest_pnl_samples=[4.0 + (i * 0.01) for i in range(40)],
        min_sample_trades=30,
        starting_equity=50_000.0,
        backtest_fill_rate=0.95,
        live_fill_rate=0.85,
        backtest_slippage=0.8,
        live_slippage=0.95,
    )


@pytest.mark.unit
class TestPromotionGate:
    @pytest.fixture
    def gate(self, tmp_path: Path) -> PromotionGate:
        return PromotionGate(audit_path=tmp_path / "promotion_gate_audit.jsonl")

    def test_good_backtest_but_bad_reality_gap_is_rejected(self, gate: PromotionGate) -> None:
        # gegeven
        evidence = _base_evidence()
        evidence = evidence.model_copy(
            update={
                "reality_gap_stats": {"band_status": "RED", "gap_trend": "WIDENING", "mean_gap": 1.25},
                "live_fill_rate": 0.45,
            }
        )

        # wanneer
        decision = gate.evaluate(evidence.dna_hash, evidence=evidence)

        # dan
        assert decision.promoted is False
        assert "reality_gap" in decision.fail_reasons

    def test_only_all_criteria_pass_allows_promotion(self, gate: PromotionGate) -> None:
        # gegeven
        evidence = _base_evidence()

        # wanneer
        decision = gate.evaluate(evidence.dna_hash, evidence=evidence)

        # dan
        assert decision.promoted is True
        assert decision.fail_reasons == ()
        assert all(item.passed for item in decision.criteria)

    def test_statistical_significance_failure_blocks_promotion(self, gate: PromotionGate) -> None:
        # gegeven
        evidence = _base_evidence().model_copy(
            update={
                "live_pnl_samples": [1.0] * 40,
                "backtest_pnl_samples": [1.0] * 40,
            }
        )

        # wanneer
        decision = gate.evaluate(evidence.dna_hash, evidence=evidence)

        # dan
        assert decision.promoted is False
        assert "statistical_significance" in decision.fail_reasons

    def test_incomplete_reality_gap_evidence_is_fail_closed(self, gate: PromotionGate) -> None:
        # gegeven
        evidence = _base_evidence().model_copy(
            update={
                "backtest_fill_rate": None,
                "live_fill_rate": None,
                "backtest_slippage": None,
                "live_slippage": None,
            }
        )

        # wanneer
        decision = gate.evaluate(evidence.dna_hash, evidence=evidence)

        # dan
        assert decision.promoted is False
        assert "reality_gap" in decision.fail_reasons

    def test_writes_audit_record(self, gate: PromotionGate, tmp_path: Path) -> None:
        # gegeven
        evidence = _base_evidence()
        audit_path = tmp_path / "promotion_gate_audit.jsonl"
        local_gate = PromotionGate(audit_path=audit_path)

        # wanneer
        decision = local_gate.evaluate(evidence.dna_hash, evidence=evidence)

        # dan
        assert decision.promoted is True
        lines = [line for line in audit_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        assert lines
        payload = json.loads(lines[-1])
        assert payload["event"] == "promotion_gate_evaluated"
        assert payload["dna_hash"] == evidence.dna_hash
