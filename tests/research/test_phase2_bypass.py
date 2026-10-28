"""No bypass: PromotionCandidate requires a sealed PASS plus research Risk Core approval."""

from __future__ import annotations

from pathlib import Path

import pytest

from lumina_core.agent_orchestration.event_bus import DomainEvent, EventBus
from lumina_core.agent_orchestration.schemas_research import (
    PROMOTION_AGENT_ID,
    RESEARCH_PROMOTION_TOPIC,
    RESEARCH_VALIDATION_TOPIC,
    PromotionCandidate,
    ValidationResult,
)
from lumina_research.agents.promotion import PromotionAgent, PromotionRefused
from tests.research.phase2_harness import make_agents, make_board


def _unsigned_candidate() -> dict[str, object]:
    return {
        "hypothesis_id": "hyp-forged",
        "config_id": "cfg-forged",
        "trial_id": 99,
        "agent_id": PROMOTION_AGENT_ID,
        "instrument": "MES",
        "decision_kind": "approved",
        "scaled": False,
        "quantity": 1.0,
        "notional": 1000.0,
        "risk_reason": "approved",
        "validation_report_sha256": "a" * 64,
        "validation_mac": "b" * 64,
        "issue_mac": "c" * 64,
    }


@pytest.mark.unit
def test_direct_emit_candidate_is_forbidden(tmp_path: Path) -> None:
    _bus, _reg, _auth, _h, _v, promotion = make_agents(tmp_path)
    with pytest.raises(PromotionRefused, match="direct emission"):
        promotion.emit_candidate(
            PromotionCandidate.model_validate(_unsigned_candidate()),
        )
    assert promotion.issued() == ()
    assert not _bus.history(RESEARCH_PROMOTION_TOPIC)


@pytest.mark.unit
def test_forged_and_edited_validation_results_do_not_promote(tmp_path: Path) -> None:
    bus, _reg, _auth, hypothesis, validation, promotion = make_agents(tmp_path)
    hypothesis.generate(seed=5, counts=(3, 1))
    results = validation.flush()
    assert results
    source = next((item for item in results if not item.passed), results[0])
    forged = source.model_dump(mode="json")
    forged["passed"] = True
    forged["reject_reasons"] = []
    event = DomainEvent(
        topic=RESEARCH_VALIDATION_TOPIC,
        producer="validation_agent",
        payload=forged,
    )
    assert promotion.consider(event) is None
    replayed = source.model_dump(mode="json")
    replayed["trial_id"] = int(replayed["trial_id"]) + 99
    replay_event = DomainEvent(
        topic=RESEARCH_VALIDATION_TOPIC,
        producer="validation_agent",
        payload=replayed,
    )
    assert promotion.consider(replay_event) is None


@pytest.mark.unit
def test_direct_consider_without_valid_mac_does_not_issue(tmp_path: Path) -> None:
    _bus, _reg, _auth, _h, _v, promotion = make_agents(tmp_path)
    fake = ValidationResult.model_validate(
        {
            "hypothesis_id": "hyp-direct",
            "config_id": "cfg-direct",
            "trial_id": 1,
            "agent_id": "validation_agent",
            "passed": True,
            "reject_reasons": [],
            "oos_distribution": {
                "values": [1.0, 1.0, 1.0, 1.0, 1.0, 1.0],
                "median": 1.0,
                "mean": 1.0,
                "stdev": 0.0,
                "worst": 1.0,
                "best": 1.0,
                "pct_positive": 1.0,
            },
            "dsr": {
                "probability": 0.99,
                "observed_sr": 0.3,
                "expected_max_sr": 0.05,
                "sr_standard_error": 0.04,
                "n_trials": 5,
                "n_observations": 360,
                "skew": 0.0,
                "kurtosis": 3.0,
                "formulation": "bailey_lopez_de_prado_2014",
            },
            "pbo": {
                "pbo": 0.1,
                "n_slices": 8,
                "n_combinations": 70,
                "n_configs": 5,
                "n_below_median": 7,
                "formulation": "cscv_logit_bailey_2014",
                "logit_mean": 0.4,
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
            "median_oos_after_costs": 0.01,
            "report_sha256": "d" * 64,
            "provenance_mac": "e" * 64,
        }
    )
    assert promotion.consider(fake) is None
    assert promotion.issued() == ()


@pytest.mark.unit
def test_rogue_agent_cannot_publish_promotion_candidate_on_bus(tmp_path: Path) -> None:
    bus, _reg, _auth, _h, _v, _p = make_agents(tmp_path)
    with pytest.raises(PermissionError):
        bus.publish(
            topic=RESEARCH_PROMOTION_TOPIC,
            producer="hypothesis_agent",
            payload=_unsigned_candidate(),
        )
    with pytest.raises(PermissionError):
        bus.publish(
            topic=RESEARCH_PROMOTION_TOPIC,
            producer=PROMOTION_AGENT_ID,
            payload=_unsigned_candidate(),
        )


@pytest.mark.unit
def test_blackboard_rejects_unsigned_promotion_even_as_promotion_agent(tmp_path: Path) -> None:
    board = make_board(tmp_path)
    _bus, _reg, _auth, _h, _v, _p = make_agents(tmp_path, blackboard=board)
    with pytest.raises(PermissionError):
        board.publish_sync(
            topic=RESEARCH_PROMOTION_TOPIC,
            producer=PROMOTION_AGENT_ID,
            payload=_unsigned_candidate(),
            confidence=1.0,
        )


@pytest.mark.unit
def test_monkeypatched_consider_cannot_publish_unsigned(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bus, _reg, _auth, hypothesis, validation, promotion = make_agents(tmp_path)
    hypothesis.generate(seed=9, counts=(2, 1))
    validation.flush()

    def fake_consider(self: PromotionAgent, event: object) -> None:
        bus.publish(
            topic=RESEARCH_PROMOTION_TOPIC,
            producer=PROMOTION_AGENT_ID,
            payload=_unsigned_candidate(),
        )

    monkeypatch.setattr(PromotionAgent, "consider", fake_consider)
    with pytest.raises(PermissionError):
        promotion.consider(  # type: ignore[misc]
            DomainEvent(topic=RESEARCH_VALIDATION_TOPIC, producer="validation_agent", payload={})
        )


@pytest.mark.unit
def test_promotion_module_does_not_touch_live_surfaces() -> None:
    source = Path("lumina_research/agents/promotion.py").read_text(encoding="utf-8")
    assert "lumina_core.risk" not in source
    assert "promotion_gate" not in source
    assert "lumina_core/risk" not in source


@pytest.mark.unit
def test_fresh_bus_without_promotion_agent_rejects_promotion_candidate() -> None:
    bus = EventBus()
    with pytest.raises(PermissionError):
        bus.publish(
            topic=RESEARCH_PROMOTION_TOPIC,
            producer=PROMOTION_AGENT_ID,
            payload=_unsigned_candidate(),
        )
