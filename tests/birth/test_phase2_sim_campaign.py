"""H3: Phase 2 productive SIM shadow campaign after Perfect Birth."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lumina_core.birth.phase2_autonomy.orchestrator import build_orchestrator_from_cfg
from lumina_core.birth.phase2_autonomy.sim_campaign import (
    disable_sim_campaign,
    enable_sim_observe_campaign,
    enable_sim_shadow_campaign,
    load_sim_campaign,
    promote_sim_apply_campaign,
    resolve_features_with_campaign,
    sim_campaign_status,
)
from lumina_core.birth.config import BirthCurriculumConfig


def _declare_perfect(tmp_path: Path) -> None:
    from lumina_core.birth.perfect_birth_gate import PerfectBirthKpis, declare_perfect_birth

    kpis = PerfectBirthKpis(
        certificate_valid=True,
        constitution_violations=0,
        twin_steve_agreement_pct=85.0,
        twin_samples=40,
        autonomous_recovery_rate_pct=90.0,
        autonomous_recovery_attempts=12,
        auto_approved_pct=70.0,
        auto_approved_decisions=30,
        shadow_twin_alignment_pct=80.0,
        shadow_samples=10,
        terminal_notify_recent=0,
    )
    payload = declare_perfect_birth(tmp_path, kpis=kpis, force=False, record_maturity=False)
    assert payload["declared"] is True


@pytest.mark.unit
def test_ops_report_blocked_without_perfect_birth(tmp_path: Path) -> None:
    from lumina_core.birth.phase2_autonomy.sim_campaign import (
        build_phase2_shadow_campaign_ops_report,
    )

    report = build_phase2_shadow_campaign_ops_report(tmp_path)
    assert report["schema"] == "phase2_shadow_campaign_ops_v1"
    assert report["perfect_birth_unlock"] is False
    assert report["ok"] is False
    assert report["policy"]["real_apply_forbidden"] is True
    assert report["can_enable_shadow"] is False
    assert report["can_enable_observe"] is True
    assert report["policy"]["observe_without_perfect_birth"] is True


@pytest.mark.unit
def test_ops_report_ready_after_pb_and_enable(tmp_path: Path) -> None:
    from lumina_core.birth.phase2_autonomy.sim_campaign import (
        build_phase2_shadow_campaign_ops_report,
    )

    _declare_perfect(tmp_path)
    enable_sim_shadow_campaign(tmp_path, source="test")
    report = build_phase2_shadow_campaign_ops_report(tmp_path)
    assert report["perfect_birth_unlock"] is True
    assert report["campaign_active"] is True
    assert report["mode"] == "shadow"
    assert report["ok"] is True


@pytest.mark.unit
def test_enable_observe_without_perfect_birth(tmp_path: Path) -> None:
    """R3 M5: observe may start pre-PB (audit only)."""
    result = enable_sim_observe_campaign(tmp_path, source="test")
    assert result["ok"] is True
    assert result["mode"] == "observe"
    camp = load_sim_campaign(tmp_path)
    assert camp is not None
    assert camp["mode"] == "observe"
    assert camp["real_apply_forbidden"] is True
    cfg = BirthCurriculumConfig()
    features = resolve_features_with_campaign(cfg, tmp_path)
    assert features.enabled is True
    assert features.execution_mode == "observe"
    assert features.require_perfect_birth_flag is False
    orch = build_orchestrator_from_cfg(cfg, mode="sim", workspace_root=tmp_path)
    assert orch is not None
    assert orch.is_active() is True
    assert orch.execution_mode().value == "observe"


@pytest.mark.unit
def test_observe_cannot_promote_to_apply(tmp_path: Path) -> None:
    enable_sim_observe_campaign(tmp_path)
    result = promote_sim_apply_campaign(tmp_path)
    assert result["ok"] is False
    assert result["error"] == "observe_cannot_promote_to_apply"


@pytest.mark.unit
def test_enable_shadow_blocked_without_perfect_birth(tmp_path: Path) -> None:
    result = enable_sim_shadow_campaign(tmp_path)
    assert result["ok"] is False
    assert result["error"] == "perfect_birth_required"


@pytest.mark.unit
def test_enable_shadow_after_perfect_birth(tmp_path: Path) -> None:
    _declare_perfect(tmp_path)
    result = enable_sim_shadow_campaign(tmp_path, source="test")
    assert result["ok"] is True
    assert result["mode"] == "shadow"
    camp = load_sim_campaign(tmp_path)
    assert camp is not None
    assert camp["active"] is True
    assert camp["mode"] == "shadow"
    assert camp["real_apply_forbidden"] is True


@pytest.mark.unit
def test_resolve_features_overlay_activates_orchestrator(tmp_path: Path) -> None:
    _declare_perfect(tmp_path)
    enable_sim_shadow_campaign(tmp_path)
    cfg = BirthCurriculumConfig()  # master flag still false
    features = resolve_features_with_campaign(cfg, tmp_path)
    assert features.enabled is True
    assert features.execution_mode == "shadow"
    assert features.dynamic_wall_enabled is True
    orch = build_orchestrator_from_cfg(cfg, mode="sim", workspace_root=tmp_path)
    assert orch is not None
    assert orch.is_active() is True
    assert orch.execution_mode().value == "shadow"


@pytest.mark.unit
def test_resolve_features_does_not_demote_curriculum_apply(tmp_path: Path) -> None:
    """Observe campaign must not strip explicit curriculum closed-loop apply (SIM product)."""
    enable_sim_observe_campaign(tmp_path, source="test")
    cfg = BirthCurriculumConfig(
        phase2_autonomy_enabled=True,
        phase2_dynamic_wall_enabled=True,
        phase2_self_adaptive_params_enabled=True,
        phase2_instance_adapt_enabled=True,
        phase2_execution_mode="apply",
        phase2_require_perfect_birth_flag=False,
        phase2_allow_sim_scaffold=True,
        phase2_require_twin_for_apply=True,
    )
    features = resolve_features_with_campaign(cfg, tmp_path)
    assert features.enabled is True
    assert features.execution_mode == "apply"
    assert features.allow_sim_scaffold is True
    orch = build_orchestrator_from_cfg(cfg, mode="sim", workspace_root=tmp_path)
    assert orch is not None
    assert orch.execution_mode().value == "apply"
    status = sim_campaign_status(tmp_path, cfg=cfg)
    assert status["mode"] == "observe"
    assert status["effective_features"]["execution_mode"] == "apply"


@pytest.mark.unit
def test_resolve_features_campaign_raises_above_curriculum_observe(tmp_path: Path) -> None:
    """Shadow campaign may raise authority when curriculum only has observe."""
    _declare_perfect(tmp_path)
    enable_sim_shadow_campaign(tmp_path, source="test")
    cfg = BirthCurriculumConfig(
        phase2_autonomy_enabled=True,
        phase2_dynamic_wall_enabled=True,
        phase2_execution_mode="observe",
    )
    features = resolve_features_with_campaign(cfg, tmp_path)
    assert features.execution_mode == "shadow"


@pytest.mark.unit
def test_resolve_features_master_off_ignores_stale_curriculum_mode_field(
    tmp_path: Path,
) -> None:
    """If master flag is off, only campaign mode applies (no accidental apply from field)."""
    enable_sim_observe_campaign(tmp_path, source="test")
    cfg = BirthCurriculumConfig(
        phase2_autonomy_enabled=False,
        phase2_execution_mode="apply",  # stale / ignored while master off
    )
    features = resolve_features_with_campaign(cfg, tmp_path)
    assert features.enabled is True
    assert features.execution_mode == "observe"


@pytest.mark.unit
def test_promote_apply_requires_shadow_evidence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LUMINA_WORKSPACE_ROOT", str(tmp_path))
    (tmp_path / "state").mkdir(parents=True, exist_ok=True)
    _declare_perfect(tmp_path)
    enable_sim_shadow_campaign(tmp_path)
    # No audit rows → insufficient evidence
    result = promote_sim_apply_campaign(tmp_path)
    assert result["ok"] is False
    assert result["error"] == "shadow_evidence_insufficient"


@pytest.mark.unit
def test_promote_apply_with_shadow_rows(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LUMINA_WORKSPACE_ROOT", str(tmp_path))
    state = tmp_path / "state"
    state.mkdir(parents=True, exist_ok=True)
    mon = state
    # metrics module uses resolve_monitoring_state_dir — patch via env/workspace
    audit = mon / "monitoring_phase2_autonomy.jsonl"
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).isoformat()
    rows = []
    for i in range(10):
        rows.append(
            json.dumps(
                {
                    "ts": now,
                    "execution_mode": "shadow",
                    "shadow_would_apply": True,
                    "apply_requested": True,
                    "applied": False,
                }
            )
        )
    audit.write_text("\n".join(rows) + "\n", encoding="utf-8")

    _declare_perfect(tmp_path)
    enable_sim_shadow_campaign(tmp_path)

    # Point loaders at tmp monitoring if needed
    monkeypatch.setattr(
        "lumina_core.birth.phase2_autonomy.metrics.phase2_monitoring_path",
        lambda: audit,
    )
    result = promote_sim_apply_campaign(tmp_path)
    assert result["ok"] is True
    assert result["mode"] == "apply"
    camp = load_sim_campaign(tmp_path)
    assert camp["mode"] == "apply"
    assert camp["sim_only"] is True


@pytest.mark.unit
def test_disable_campaign(tmp_path: Path) -> None:
    enable_sim_shadow_campaign(tmp_path, allow_sim_scaffold=True)
    out = disable_sim_campaign(tmp_path)
    assert out["ok"] is True
    assert out["active"] is False
    status = sim_campaign_status(tmp_path)
    assert status["campaign_active"] is False
