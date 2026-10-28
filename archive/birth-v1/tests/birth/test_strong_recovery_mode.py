"""Strong recovery mode: exploit exploration, aggressive mining, provisional pass."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.birth.curriculum import CurriculumStage
from lumina_core.birth.engine import BirthPhaseEngineV2
from lumina_core.birth.stage_scorecard import enrich_adaptation_payload


def _engine(tmp_path: Path) -> BirthPhaseEngineV2:
    return BirthPhaseEngineV2(
        runtime=SimpleNamespace(),
        ppo_trainer=SimpleNamespace(),
        market_data_service=SimpleNamespace(),
        workspace_root=tmp_path,
    )


def _cfg(**overrides: object) -> BirthCurriculumConfig:
    base = BirthCurriculumConfig(
        exploration_steps=8000,
        oracle_scan_stride=10,
        oracle_patterns_per_stage=50,
        velocity_stall_epsilon=0.002,
        strong_recovery_no_improvement_threshold=12,
        strong_recovery_explore_fraction=0.5,
        strong_recovery_oracle_stride_divisor=2,
        strong_recovery_pattern_multiplier=2,
    )
    for key, value in overrides.items():
        setattr(base, key, value)
    return base


def _provisional_kwargs(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "stage": CurriculumStage.STAGE1_TREND,
        "stage_trades": 200,
        "required": 150,
        "attempt": 50,
        "strong_recovery_attempts": 12,
        "patterns_mined": 120,
        "buffer_size": 300,
        "constitution_violations": 0,
        "combined_velocity": 0.0,
        "allow_provisional": True,
        "cfg": _cfg(),
    }
    base.update(overrides)
    return base


@pytest.mark.unit
def test_provisional_pass_blocked_in_certified_mode(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    decision = engine._maybe_trigger_provisional_pass(
        **_provisional_kwargs(allow_provisional=False),
    )
    assert decision.should_grant is False
    assert decision.blocked_reason == "certified_mode_strict"


@pytest.mark.unit
def test_provisional_pass_granted_in_practice_with_safeguards(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    decision = engine._maybe_trigger_provisional_pass(**_provisional_kwargs())
    assert decision.should_grant is True
    assert decision.reason == "strong_recovery_exhausted_soft_pass"
    assert decision.blocked_reason is None


@pytest.mark.unit
def test_provisional_pass_blocked_on_constitution_violation(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    decision = engine._maybe_trigger_provisional_pass(
        **_provisional_kwargs(constitution_violations=1),
    )
    assert decision.should_grant is False
    assert decision.safeguards["constitution_clean"] is False


@pytest.mark.unit
def test_provisional_pass_blocked_on_insufficient_recovery_attempts(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    decision = engine._maybe_trigger_provisional_pass(
        **_provisional_kwargs(strong_recovery_attempts=5),
    )
    assert decision.should_grant is False
    assert decision.safeguards["recovery_attempts_met"] is False


@pytest.mark.unit
def test_strong_recovery_explore_fraction_reduces_steps() -> None:
    cfg = _cfg(exploration_steps=8000, strong_recovery_explore_fraction=0.5)
    normal = cfg.exploration_steps * (1 + 0)
    exploit = max(200, int(cfg.exploration_steps * cfg.strong_recovery_explore_fraction))
    assert exploit < normal
    assert exploit == 4000


@pytest.mark.unit
def test_aggressive_mining_halves_stride_and_doubles_patterns() -> None:
    cfg = _cfg(oracle_scan_stride=10, oracle_patterns_per_stage=50)
    normal_patterns, normal_stride = BirthPhaseEngineV2._resolve_oracle_mining_params(
        cfg,
        aggressive=False,
    )
    aggressive_patterns, aggressive_stride = BirthPhaseEngineV2._resolve_oracle_mining_params(
        cfg,
        aggressive=True,
    )
    assert normal_stride == 10
    assert aggressive_stride == 5
    assert normal_patterns == 50
    assert aggressive_patterns == 100


@pytest.mark.unit
def test_enrich_adaptation_payload_exposes_strong_recovery_fields() -> None:
    payload = enrich_adaptation_payload(
        stage_trades=200,
        required=150,
        winrate_history=[0.40] * 6,
        retries_this_stage=0,
        adaptation_history=[],
        adaptation_enabled=True,
        wall_behavior="adaptive",
        strong_recovery_mode=True,
        velocity_stall_attempts=32,
        strong_recovery_attempts=8,
        provisional_pass_considered=True,
    )
    assert payload["strong_recovery_mode"] is True
    assert payload["strong_recovery_attempts"] == 8
    assert payload["provisional_pass_considered"] is True
