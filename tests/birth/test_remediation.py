from __future__ import annotations

from typing import Any

import pytest

from lumina_core.birth.remediation import (
    RemediationAction,
    curriculum_stages_complete,
    filter_train_ticks_for_holdout_profile,
    manifest_train_hash_matches,
    parse_failure_reason_keys,
    select_regime_diverse_train_ticks,
    select_remediation_plan,
    should_fast_path_remediation,
    should_fast_path_remediation_from_state,
)


@pytest.mark.unit
def test_parse_failure_reason_keys() -> None:
    keys = parse_failure_reason_keys(
        ["regimes_covered:1/3", "oos_sharpe:0.00/0.35", " holdout_trades:12/50 "]
    )
    assert keys == {"regimes_covered", "oos_sharpe", "holdout_trades"}


@pytest.mark.unit
@pytest.mark.parametrize(
    ("reasons", "expected_action"),
    [
        (["regimes_covered:1/3"], RemediationAction.REGIME_EXPAND),
        (["holdout_trades:12/50"], RemediationAction.HOLDOUT_ACTIVITY),
        (["oos_sharpe:0.00/0.35"], RemediationAction.SHARPE_POLISH),
        (["unknown_metric:bad"], RemediationAction.GENERIC_EXPLORE),
    ],
)
def test_select_remediation_plan_reason_branches(
    reasons: list[str],
    expected_action: RemediationAction,
) -> None:
    plan = select_remediation_plan(
        reasons,
        attempt=1,
        curriculum_ppo_timesteps=5000,
        polish_ppo_timesteps=8000,
        rollout_chunk_trades=100,
    )
    assert plan.action == expected_action


@pytest.mark.unit
def test_select_remediation_plan_regime_expand_sets_expand_data() -> None:
    plan = select_remediation_plan(
        ["regimes_covered:2/3"],
        attempt=1,
        curriculum_ppo_timesteps=5000,
        polish_ppo_timesteps=8000,
        rollout_chunk_trades=100,
    )
    assert plan.expand_data is True
    assert plan.explore_multiplier >= 3


@pytest.mark.unit
def test_filter_train_ticks_for_holdout_profile() -> None:
    holdout = [{"regime": "TREND_UP"}, {"regime": "NEUTRAL"}]
    train = [{"regime": "TREND_UP", "i": i} for i in range(250)] + [
        {"regime": "RANGE", "i": i} for i in range(50)
    ]
    filtered = filter_train_ticks_for_holdout_profile(train, holdout)
    assert all(str(t.get("regime", "")).upper() in {"TREND_UP", "NEUTRAL"} for t in filtered)
    assert len(filtered) >= 200


@pytest.mark.unit
def test_select_regime_diverse_train_ticks() -> None:
    train: list[dict[str, Any]] = []
    for regime in ("TREND_UP", "TREND_DOWN", "NEUTRAL", "RANGE"):
        train.extend({"regime": regime, "i": i} for i in range(80))
    diverse = select_regime_diverse_train_ticks(train, min_regimes=3)
    regimes = {str(t["regime"]).upper() for t in diverse}
    assert len(regimes) >= 3


_FOUNDATION_STAGES = [
    "stage1_trend",
    "stage2_range",
    "stage3_mixed",
    "stage4_viable_plant",
    "stage5_probe_handoff",
]


@pytest.mark.unit
def test_should_fast_path_remediation() -> None:
    stages = list(_FOUNDATION_STAGES)
    assert should_fast_path_remediation(checkpoint_phase="certificate_failed", stages_passed=stages)
    assert should_fast_path_remediation(
        checkpoint_phase="certificate_remediation", stages_passed=stages
    )
    assert not should_fast_path_remediation(checkpoint_phase="stage2_range", stages_passed=stages)
    assert not should_fast_path_remediation(
        checkpoint_phase="certificate_failed",
        stages_passed=["stage1_trend", "stage2_range", "stage3_mixed"],
    )


@pytest.mark.unit
def test_curriculum_stages_complete() -> None:
    assert curriculum_stages_complete(list(_FOUNDATION_STAGES))
    assert not curriculum_stages_complete(["stage1_trend", "stage2_range", "stage3_mixed"])
    assert not curriculum_stages_complete(["stage1_trend"])


@pytest.mark.unit
def test_manifest_train_hash_matches() -> None:
    assert manifest_train_hash_matches(
        current_hash="abc123",
        saved_manifest={"train_hash": "abc123"},
    )
    assert not manifest_train_hash_matches(
        current_hash="abc123",
        saved_manifest={"train_hash": "other"},
    )
    assert not manifest_train_hash_matches(current_hash="abc123", saved_manifest=None)


@pytest.mark.unit
def test_should_fast_path_remediation_from_state_uses_checkpoint_stages() -> None:
    progress = {"phase": "certificate_failed", "stages_passed": []}
    checkpoint = {
        "phase": "certificate_failed",
        "stages_passed": list(_FOUNDATION_STAGES),
    }
    assert should_fast_path_remediation_from_state(progress, checkpoint)


@pytest.mark.unit
def test_should_fast_path_remediation_from_state_rejects_incomplete_curriculum() -> None:
    progress = {
        "phase": "certificate_failed",
        "stages_passed": ["stage1_trend"],
    }
    assert not should_fast_path_remediation_from_state(progress, {})
