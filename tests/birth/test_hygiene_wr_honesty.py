"""Hygiene WR vs Rolling WR operator honesty (Starship)."""

from __future__ import annotations

import pytest

from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.birth.curriculum import CurriculumStage, evaluate_stage_pass
from lumina_core.birth.stage_pass_receipt import (
    StagePassReceipt,
    receipt_from_stage_result,
    verify_stage_pass_receipt,
)
from lumina_core.birth.stage_scorecard import compute_stage_blocker
from lumina_core.birth.starship_birth import (
    EdgeScoreResult,
    gate_rolling_winrate,
    humanize_edgescore_blocker,
    hygiene_wr_telemetry,
    rolling_wr_pass_eligible,
)
from tests.birth.honest_settlement import foundation_eval_kwargs, honest_closes


@pytest.mark.unit
def test_rolling_wr_pass_eligible_requires_400_covered() -> None:
    assert rolling_wr_pass_eligible(source="true_window", covered=233, window=500) is False
    assert rolling_wr_pass_eligible(source="true_window", covered=400, window=500) is True
    assert rolling_wr_pass_eligible(source="lifetime_fallback", covered=500, window=500) is False
    assert gate_rolling_winrate(
        rolling_wr=0.40, source="true_window", covered=233, window=500
    ) is None
    assert gate_rolling_winrate(
        rolling_wr=0.40, source="true_window", covered=400, window=500
    ) == pytest.approx(0.40)


@pytest.mark.unit
def test_hygiene_wr_telemetry_effective_and_source() -> None:
    neither = hygiene_wr_telemetry(
        lifetime_wr=0.29,
        rolling_wr=0.335,
        rolling_source="true_window",
        rolling_covered=233,
        floor=0.35,
        window=500,
    )
    assert neither["rolling_wr_eligible"] is False
    assert neither["hygiene_wr_effective"] == pytest.approx(0.29)
    assert neither["hygiene_wr_source"] == "neither"
    assert neither["hygiene_wr_rolling"] == pytest.approx(0.335)

    rolling_pass = hygiene_wr_telemetry(
        lifetime_wr=0.30,
        rolling_wr=0.40,
        rolling_source="true_window",
        rolling_covered=420,
        floor=0.35,
        window=500,
    )
    assert rolling_pass["rolling_wr_eligible"] is True
    assert rolling_pass["hygiene_wr_effective"] == pytest.approx(0.40)
    assert rolling_pass["hygiene_wr_source"] == "rolling"


@pytest.mark.unit
def test_humanize_hygiene_shows_lifetime_and_rolling_with_eligibility() -> None:
    cfg = BirthCurriculumConfig(
        stage1_edgescore_enabled=True,
        stage1_winrate_pass_floor=0.35,
        stage1_rolling_pass_window=500,
    )
    edge = EdgeScoreResult(
        passed=False,
        score=0.45,
        hygiene_ok=False,
        activity_ok=True,
        entropy_ok=True,
        expectancy_ok=True,
        constitution_ok=True,
        message="debug",
    )
    text = humanize_edgescore_blocker(
        edge,
        cfg=cfg,
        wins=78,
        trades=269,
        rolling_winrate=None,
        rolling_winrate_display=0.334,
        rolling_wr_eligible=False,
        rolling_min_covered=400,
    )
    assert "lifetime 29%" in text
    assert "rolling 33%" in text
    assert "rolling counts after 400" in text
    # Survival-mode hygiene floor is 20% (legacy 35% only when not in survival).
    assert "need >=20%" in text


@pytest.mark.unit
def test_compute_stage_blocker_hygiene_copy_includes_rolling_display() -> None:
    cfg = BirthCurriculumConfig(
        stage1_edgescore_enabled=True,
        stage1_winrate_pass_floor=0.35,
        stage1_expectancy_floor=-0.15,
        stage1_entropy_floor=0.05,
        starship_entropy_required_after_ppo_steps=500,
    )
    # 10% lifetime WR fails survival hygiene (~20%); include rolling display in copy.
    metric, _value, reason = compute_stage_blocker(
        CurriculumStage.STAGE1_TREND,
        stage_trades=269,
        stage_wins=27,
        hold_ratio=0.50,
        required=200,
        constitution_violations=0,
        range_flat_ratio=0.5,
        range_round_trips=20,
        range_total_signals=100,
        cfg=cfg,
        rolling_winrate=None,
        rolling_winrate_display=0.335,
        rolling_wr_eligible=False,
        policy_entropy=0.20,
        ppo_steps=5000,
    )
    assert metric == "winrate"
    assert reason is not None
    assert "lifetime" in reason
    assert "rolling" in reason
    assert "400" in reason


@pytest.mark.unit
def test_receipt_rolling_only_hygiene_verifies() -> None:
    cfg = BirthCurriculumConfig(
        stage1_trend_trades=200,
        allow_provisional_pass=False,
        stage1_edgescore_enabled=True,
        stage1_winrate_pass_floor=0.35,
        stage1_entropy_floor=0.0,
        stage1_hold_ratio_min=0.05,
        stage1_hold_ratio_max=0.85,
        stage1_expectancy_floor=-0.15,
        starship_entropy_required_after_ppo_steps=500,
    )
    # Lifetime 30% fails hygiene; trusted rolling 40% passes when eligible.
    result = evaluate_stage_pass(
        CurriculumStage.STAGE1_TREND,
        trades=420,
        wins=126,
        hold_signals=200,
        total_signals=500,
        constitution_violations=0,
        target_trades=200,
        cfg=cfg,
        allow_provisional=False,
        rolling_winrate=0.40,
        ppo_steps=5000,
        **honest_closes(420),
        **foundation_eval_kwargs(policy_entropy=0.25),
    )
    assert result.passed
    receipt = receipt_from_stage_result(
        CurriculumStage.STAGE1_TREND,
        result,
        cfg=cfg,
        hold_signals=200,
        total_signals=500,
        policy_entropy=0.25,
        rolling_winrate=0.40,
        rolling_winrate_source="true_window",
        rolling_window_trades_covered=420,
        hygiene_wr_source="rolling",
    )
    assert receipt.winrate < 0.35
    ok, reason = verify_stage_pass_receipt(
        CurriculumStage.STAGE1_TREND,
        receipt,
        cfg=cfg,
        training_mode="certified",
    )
    assert ok is True, reason


@pytest.mark.unit
def test_receipt_rolling_ineligible_does_not_fake_pass() -> None:
    cfg = BirthCurriculumConfig(
        stage1_trend_trades=200,
        allow_provisional_pass=False,
        stage1_edgescore_enabled=True,
        birth_survival_pass_enabled=False,
        stage1_winrate_pass_floor=0.35,
        stage1_entropy_floor=0.0,
        stage1_hold_ratio_min=0.05,
        stage1_hold_ratio_max=0.85,
    )
    receipt = StagePassReceipt(
        stage="stage1_trend",
        trades=269,
        wins=78,
        winrate=0.29,
        required_trades=200,
        pass_criteria_id="trend_edgescore",
        provisional=False,
        passed_at="2026-01-01T00:00:00+00:00",
        engine_version="BRO-v2",
        hold_ratio=0.50,
        hold_signals=250,
        total_signals=500,
        policy_entropy=0.25,
        rolling_winrate=0.40,
        rolling_winrate_source="true_window",
        rolling_window_trades_covered=233,
        hygiene_wr_source="neither",
    )
    ok, reason = verify_stage_pass_receipt(
        CurriculumStage.STAGE1_TREND,
        receipt,
        cfg=cfg,
        training_mode="certified",
    )
    assert ok is False
    assert (
        "stage1_hygiene_below_floor" in reason
        or "missing_or_invalid_foundation_schema" in reason
        or "missing_median_loss_r" in reason
    )
