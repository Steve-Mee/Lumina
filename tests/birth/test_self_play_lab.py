"""ADR-0037 Phase 0 — self-play lab scaffold tests."""

from __future__ import annotations

import pytest

from lumina_core.birth.self_play import (
    SelfPlayLabConfig,
    SelfPlayVariantResult,
    assert_self_play_allowed,
    build_self_play_lab_report,
    evaluate_self_play_gate,
    rank_self_play_variants,
    score_variant,
)
from lumina_core.birth.self_play.gates import is_champion_freeze_active
from lumina_core.birth.self_play.report import FIXTURE_VARIANTS


def test_default_config_disabled() -> None:
    cfg = SelfPlayLabConfig()
    assert cfg.enabled is False
    assert cfg.allow_apply is False
    gate = evaluate_self_play_gate(config=cfg)
    assert gate.allowed is False
    assert gate.reason == "lab_disabled"


def test_real_capital_forbidden() -> None:
    cfg = SelfPlayLabConfig(enabled=True, capital_mode_hint="sim")
    gate = evaluate_self_play_gate(config=cfg, capital_mode="real")
    assert gate.allowed is False
    assert gate.reason == "real_capital_forbidden"

    report = build_self_play_lab_report(
        config=cfg, capital_mode="real", use_fixture=True
    )
    assert report["ok"] is False
    assert report["schema"] == "self_play_lab_v1"


def test_champion_freeze_blocks() -> None:
    cfg = SelfPlayLabConfig(enabled=True)
    progress = {"swarm_rejected_no_lift": True, "swarm_champion_accepted": False}
    assert is_champion_freeze_active(progress) is True
    gate = evaluate_self_play_gate(config=cfg, progress=progress)
    assert gate.allowed is False
    assert gate.reason == "blocked_champion_freeze"

    accepted = {"swarm_rejected_no_lift": True, "swarm_champion_accepted": True}
    assert is_champion_freeze_active(accepted) is False
    gate2 = evaluate_self_play_gate(config=cfg, progress=accepted)
    assert gate2.allowed is True


def test_assert_raises_when_blocked() -> None:
    with pytest.raises(ValueError, match="lab_disabled"):
        assert_self_play_allowed(config=SelfPlayLabConfig(enabled=False))


def test_rank_uses_tournament_score_not_vanity() -> None:
    ranked = rank_self_play_variants(list(FIXTURE_VARIANTS), champion_score=None)
    assert len(ranked) == 3
    assert ranked[0]["variant_id"] == "challenger_a"
    assert ranked[0]["rank"] == 1
    assert "tournament_score" in ranked[0]
    assert "edgescore" not in ranked[0]
    # challenger_a should beat champion and B
    scores = {r["variant_id"]: r["tournament_score"] for r in ranked}
    assert scores["challenger_a"] > scores["champion"]
    assert scores["champion"] > scores["challenger_b"]


def test_lift_vs_champion_baseline() -> None:
    champ = FIXTURE_VARIANTS[0]
    baseline = score_variant(champ)
    ranked = rank_self_play_variants(
        list(FIXTURE_VARIANTS),
        champion_score=baseline,
        meaningful_delta=0.01,
    )
    by_id = {r["variant_id"]: r for r in ranked}
    assert by_id["challenger_a"]["lift_ok"] is True
    assert by_id["challenger_b"]["lift_ok"] is False


def test_apply_forbidden_phase0() -> None:
    cfg = SelfPlayLabConfig(enabled=True, allow_apply=False)
    gate = evaluate_self_play_gate(config=cfg, for_apply=True)
    assert gate.allowed is False
    assert gate.reason == "apply_forbidden_phase0"


def test_report_fixture_schema() -> None:
    report = build_self_play_lab_report(use_fixture=True)
    assert report["schema"] == "self_play_lab_v1"
    assert report["phase"] == "0_lab_scaffold"
    assert report["ok"] is True  # disabled but not hard-fail
    assert report["enabled"] is False
    assert report["variant_count"] == 3
    assert len(report["ranked"]) == 3
    assert "auto_REAL" in report["forbidden"]
    assert any("OR1" in x for x in report["operator_residuals"])


def test_enabled_shadow_ok_with_fixture() -> None:
    cfg = SelfPlayLabConfig(enabled=True, capital_mode_hint="sim")
    report = build_self_play_lab_report(config=cfg, use_fixture=True)
    assert report["ok"] is True
    assert report["gate"]["allowed"] is True
    assert report["ranked"][0]["variant_id"] == "challenger_a"


def test_custom_variants() -> None:
    variants = [
        SelfPlayVariantResult("a", trades=10, wins=8, total_pnl=10.0),
        SelfPlayVariantResult("b", trades=10, wins=2, total_pnl=-10.0),
    ]
    ranked = rank_self_play_variants(variants)
    assert ranked[0]["variant_id"] == "a"
