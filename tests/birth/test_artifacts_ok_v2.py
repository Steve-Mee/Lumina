from __future__ import annotations

from datetime import datetime, timezone

import pytest

from lumina_core.birth.birth_certificate import (
    BirthCertificateV2,
    sha256_file,
    validate_certificate_artifacts,
    write_certificate,
)
from lumina_launcher.services.birth_service import BirthService


@pytest.mark.unit
def test_v1_flag_without_certificate_blocked(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("LUMINA_BIRTH_V2_DISABLED", raising=False)
    flag = tmp_path / "state" / "lumina_birth_completed.flag"
    flag.parent.mkdir(parents=True)
    flag.write_text("legacy", encoding="utf-8")
    policy = tmp_path / "lumina_agents" / "ppo" / "lumina_ppo_policy.zip"
    policy.parent.mkdir(parents=True)
    policy.write_bytes(b"zip")
    ok, reason, _ = validate_certificate_artifacts(tmp_path)
    assert ok is False
    assert reason == "missing_or_invalid_certificate"


@pytest.mark.unit
def test_birth_service_artifacts_ok_with_valid_certificate(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("LUMINA_BIRTH_V2_DISABLED", raising=False)
    svc = BirthService()
    svc.configure_workspace(tmp_path)
    policy = svc.policy_path
    policy.parent.mkdir(parents=True, exist_ok=True)
    policy.write_bytes(b"cert-policy")
    cert = BirthCertificateV2(
        issued_at=datetime.now(timezone.utc),
        policy_path=str(policy),
        policy_sha256=sha256_file(policy),
        real_data_pct=99.0,
        oos_winrate=0.5,
        oos_sharpe=0.4,
        oos_max_drawdown_pct=4.0,
        constitution_violations=0,
        regimes_covered=["TREND_UP", "TREND_DOWN", "NEUTRAL"],
        curriculum_stages_passed=["stage1_trend", "stage2_range", "stage3_mixed", "stage4_polish"],
        holdout_days=5,
        holdout_trades=60,
        training_trades=500,
        ppo_steps=1000,
    )
    write_certificate(tmp_path, cert)
    assert svc.artifacts_ok() is False  # evolution proof missing is fail-closed
    from lumina_core.birth.evolution_proof_gate import save_evolution_proof_record

    save_evolution_proof_record(tmp_path, {"passed": True})
    assert svc.artifacts_ok() is True


@pytest.mark.unit
def test_birth_service_artifacts_ok_blocks_failed_evolution_proof(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("LUMINA_BIRTH_V2_DISABLED", raising=False)
    from lumina_core.birth.evolution_proof_gate import save_evolution_proof_record

    svc = BirthService()
    svc.configure_workspace(tmp_path)
    policy = svc.policy_path
    policy.parent.mkdir(parents=True, exist_ok=True)
    policy.write_bytes(b"cert-policy")
    cert = BirthCertificateV2(
        issued_at=datetime.now(timezone.utc),
        policy_path=str(policy),
        policy_sha256=sha256_file(policy),
        real_data_pct=99.0,
        oos_winrate=0.5,
        oos_sharpe=0.4,
        oos_max_drawdown_pct=4.0,
        constitution_violations=0,
        regimes_covered=["TREND_UP", "TREND_DOWN", "NEUTRAL"],
        curriculum_stages_passed=["stage1_trend", "stage2_range", "stage3_mixed", "stage4_polish"],
        holdout_days=5,
        holdout_trades=60,
        training_trades=500,
        ppo_steps=1000,
    )
    write_certificate(tmp_path, cert)
    save_evolution_proof_record(
        tmp_path,
        {"passed": False, "reasons": ["insufficient lift"]},
    )
    assert svc.evolution_proof_ok() is False
    assert svc.artifacts_ok() is False
    assert svc.real_trading_eligible() is False
