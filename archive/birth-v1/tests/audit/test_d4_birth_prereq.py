from __future__ import annotations

import pytest

from lumina_core.audit.d4_birth_prereq import ensure_birth_prereqs


@pytest.mark.unit
def test_ensure_birth_prereqs_fails_without_policy(tmp_path) -> None:
    ok, msg = ensure_birth_prereqs(workspace_root=tmp_path, seed=True)
    assert ok is False
    assert "missing birth policy" in msg


@pytest.mark.unit
def test_ensure_birth_prereqs_rejects_seed_without_certificate(tmp_path) -> None:
    policy = tmp_path / "lumina_agents" / "ppo" / "lumina_ppo_policy.zip"
    policy.parent.mkdir(parents=True)
    policy.write_bytes(b"zip")

    ok, msg = ensure_birth_prereqs(workspace_root=tmp_path, seed=True, label="unit-test")
    assert ok is False
    assert "certificate" in msg.lower()


@pytest.mark.unit
def test_ensure_birth_prereqs_no_seed_when_certificate_missing(tmp_path) -> None:
    policy = tmp_path / "lumina_agents" / "ppo" / "lumina_ppo_policy.zip"
    policy.parent.mkdir(parents=True)
    policy.write_bytes(b"zip")

    ok, msg = ensure_birth_prereqs(workspace_root=tmp_path, seed=False)
    assert ok is False
    assert "certificate" in msg.lower()
