from __future__ import annotations

from datetime import datetime, timezone

import pytest

from lumina_core.birth.birth_certificate import BirthCertificateV2
from lumina_core.birth.dna_handoff import register_birth_gen0_dna, resolve_birth_gen0_dna
from lumina_core.evolution.dna_registry import DNARegistry, PolicyDNA


@pytest.mark.unit
def test_register_and_resolve_birth_gen0_dna(tmp_path) -> None:
    policy = tmp_path / "lumina_agents" / "ppo" / "lumina_ppo_policy.zip"
    policy.parent.mkdir(parents=True, exist_ok=True)
    policy.write_bytes(b"policy")

    cert = BirthCertificateV2(
        issued_at=datetime.now(timezone.utc),
        policy_path=str(policy),
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
    register_birth_gen0_dna(tmp_path, cert)
    registry = DNARegistry(
        jsonl_path=tmp_path / "state" / "dna_registry.jsonl",
        sqlite_path=tmp_path / "state" / "dna_registry.sqlite3",
    )
    resolved = resolve_birth_gen0_dna(registry)
    assert resolved is not None
    assert resolved.prompt_id == "birth_v2_certificate"


@pytest.mark.unit
def test_resolve_birth_gen0_returns_none_for_synthetic_bootstrap(tmp_path) -> None:
    registry = DNARegistry(
        jsonl_path=tmp_path / "state" / "dna_registry.jsonl",
        sqlite_path=tmp_path / "state" / "dna_registry.sqlite3",
    )
    synthetic = PolicyDNA.create(
        prompt_id="bootstrap",
        version="active",
        content={"candidate_name": "synthetic_bootstrap"},
        fitness_score=0.1,
        generation=0,
        lineage_hash="boot123",
        mutation_rate=0.0,
    )
    registry.register_dna(synthetic)
    assert resolve_birth_gen0_dna(registry) is None
