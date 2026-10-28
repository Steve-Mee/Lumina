from __future__ import annotations

from datetime import datetime, timezone

import pytest

from lumina_core.birth.birth_certificate import (
    BirthCertificateThresholds,
    BirthCertificateV2,
    sha256_file,
    validate_certificate_artifacts,
    write_certificate,
)


@pytest.mark.unit
def test_birth_certificate_v2_meets_thresholds() -> None:
    cert = BirthCertificateV2(
        issued_at=datetime.now(timezone.utc),
        policy_path="lumina_agents/ppo/lumina_ppo_policy.zip",
        policy_sha256="a" * 64,
        real_data_pct=98.0,
        oos_winrate=0.52,
        oos_sharpe=0.4,
        oos_max_drawdown_pct=5.0,
        constitution_violations=0,
        regimes_covered=["TREND_UP", "TREND_DOWN", "NEUTRAL"],
        curriculum_stages_passed=["stage1_trend"],
        holdout_days=10,
        holdout_trades=60,
        training_trades=1000,
        ppo_steps=5000,
    )
    assert cert.meets_thresholds(BirthCertificateThresholds())


@pytest.mark.unit
def test_validate_certificate_artifacts_requires_policy_hash_match(tmp_path) -> None:
    policy = tmp_path / "lumina_agents" / "ppo" / "lumina_ppo_policy.zip"
    policy.parent.mkdir(parents=True)
    policy.write_bytes(b"policy-bytes")

    cert = BirthCertificateV2(
        issued_at=datetime.now(timezone.utc),
        policy_path=str(policy),
        policy_sha256="b" * 64,
        real_data_pct=98.0,
        oos_winrate=0.5,
        oos_sharpe=0.4,
        oos_max_drawdown_pct=5.0,
        constitution_violations=0,
        regimes_covered=["A", "B", "C"],
        curriculum_stages_passed=["stage1_trend"],
        holdout_days=5,
        holdout_trades=60,
        training_trades=100,
        ppo_steps=1000,
    )
    write_certificate(tmp_path, cert)
    ok, reason, _ = validate_certificate_artifacts(tmp_path)
    assert ok is False
    assert reason == "policy_hash_mismatch"


@pytest.mark.unit
def test_validate_certificate_rejects_invalid_integrity_version(tmp_path) -> None:
    policy = tmp_path / "lumina_agents" / "ppo" / "lumina_ppo_policy.zip"
    policy.parent.mkdir(parents=True)
    policy.write_bytes(b"policy-bytes")

    cert = BirthCertificateV2(
        issued_at=datetime.now(timezone.utc),
        policy_path=str(policy),
        policy_sha256=sha256_file(policy),
        real_data_pct=98.0,
        oos_winrate=0.5,
        oos_sharpe=0.4,
        oos_max_drawdown_pct=5.0,
        constitution_violations=0,
        regimes_covered=["A", "B", "C"],
        curriculum_stages_passed=["stage1_trend"],
        holdout_days=5,
        holdout_trades=60,
        training_trades=100,
        ppo_steps=1000,
    )
    payload = cert.model_dump(mode="json")
    payload["integrity_version"] = 1
    from lumina_core.birth.birth_certificate import certificate_path

    certificate_path(tmp_path).parent.mkdir(parents=True, exist_ok=True)
    certificate_path(tmp_path).write_text(__import__("json").dumps(payload), encoding="utf-8")
    ok, reason, _ = validate_certificate_artifacts(tmp_path)
    assert ok is False
    assert reason == "certificate_integrity_version_invalid"


@pytest.mark.unit
def test_meets_thresholds_requires_min_holdout_trades() -> None:
    cert = BirthCertificateV2(
        issued_at=datetime.now(timezone.utc),
        policy_path="lumina_agents/ppo/lumina_ppo_policy.zip",
        policy_sha256="a" * 64,
        real_data_pct=98.0,
        oos_winrate=0.52,
        oos_sharpe=0.4,
        oos_max_drawdown_pct=5.0,
        constitution_violations=0,
        regimes_covered=["TREND_UP", "TREND_DOWN", "NEUTRAL"],
        curriculum_stages_passed=["stage1_trend"],
        holdout_days=10,
        holdout_trades=10,
        training_trades=1000,
        ppo_steps=5000,
    )
    assert cert.meets_thresholds(BirthCertificateThresholds(min_holdout_trades=50)) is False
