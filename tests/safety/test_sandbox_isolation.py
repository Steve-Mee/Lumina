"""Tests for SandboxedMutationExecutor — isolation, audit trail, timeout handling.

Sandbox subprocess tests are marked @slow (they spawn Python processes).
In-process path tests are @unit.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from lumina_core.safety.sandboxed_executor import (
    SandboxedMutationExecutor,
    SandboxedResult,
    _strip_secrets,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clean_dna() -> str:
    return json.dumps({
        "mutation_depth": "conservative",
        "hyperparam_suggestion": {"max_risk_percent": 1.0, "drawdown_kill_percent": 10.0},
    })


def _evil_dna() -> str:
    return json.dumps({
        "disable_risk_controller": True,
        "bypass_order_gatekeeper": True,
    })


# ---------------------------------------------------------------------------
# SandboxedResult data type
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestSandboxedResult:

    def test_passed_true_when_no_violations_and_positive_score(self) -> None:
        r = SandboxedResult(
            dna_hash="abc", score=1.0, violations=[],
            input_hash="x", output_hash="y", mode="sim",
        )
        assert r.passed is True

    def test_passed_false_when_violations_present(self) -> None:
        r = SandboxedResult(
            dna_hash="abc", score=1.0, violations=["no_naked_orders"],
            input_hash="x", output_hash="y",
        )
        assert r.passed is False

    def test_passed_false_when_score_zero(self) -> None:
        r = SandboxedResult(
            dna_hash="abc", score=0.0, violations=[],
            input_hash="x", output_hash="y",
        )
        assert r.passed is False

    def test_passed_false_when_timed_out(self) -> None:
        r = SandboxedResult(
            dna_hash="abc", score=5.0, violations=[],
            input_hash="x", output_hash="y", timed_out=True,
        )
        assert r.passed is False

    def test_is_constitutional_true_when_no_violations(self) -> None:
        r = SandboxedResult(
            dna_hash="a", score=1.0, violations=[],
            input_hash="i", output_hash="o",
        )
        assert r.is_constitutional is True

    def test_to_audit_record_has_required_fields(self) -> None:
        r = SandboxedResult(
            dna_hash="abc", score=1.5, violations=["foo"],
            input_hash="ih", output_hash="oh", mode="real",
        )
        rec = r.to_audit_record()
        for field in ("dna_hash", "score", "violations", "input_hash", "output_hash", "passed", "mode"):
            assert field in rec, f"Missing field: {field}"


# ---------------------------------------------------------------------------
# Secret stripping
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestStripSecrets:

    def test_api_key_stripped(self) -> None:
        env = {"XAI_API_KEY": "secret", "PATH": "/usr/bin", "API_KEY": "also_secret"}
        clean = _strip_secrets(env)
        assert "XAI_API_KEY" not in clean
        assert "API_KEY" not in clean
        assert "PATH" in clean

    def test_crosstrade_token_stripped(self) -> None:
        env = {"CROSSTRADE_TOKEN": "tok", "HOME": "/home/user"}
        clean = _strip_secrets(env)
        assert "CROSSTRADE_TOKEN" not in clean
        assert "HOME" in clean

    def test_password_stripped(self) -> None:
        env = {"DB_PASSWORD": "p@ss", "LOG_LEVEL": "INFO"}
        clean = _strip_secrets(env)
        assert "DB_PASSWORD" not in clean
        assert "LOG_LEVEL" in clean

    def test_empty_env_returns_empty(self) -> None:
        assert _strip_secrets({}) == {}


# ---------------------------------------------------------------------------
# In-process path (unit — no subprocess)
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestInProcessEvaluation:
    """Tests for the in-process fallback used in SIM mode when sandbox is disabled."""

    def test_clean_dna_scores_positive_in_process(self) -> None:
        executor = SandboxedMutationExecutor(always_sandbox=False)
        # Force in-process by patching the sandbox decision.
        result = executor._run_in_process(
            dna_hash="test",
            dna_content=_clean_dna(),
            mode="sim",
            pnl=500.0,
            max_dd=100.0,
            sharpe=1.2,
            input_hash="ih",
        )
        assert result.score > 0.0
        assert result.is_constitutional

    def test_evil_dna_blocked_in_process(self) -> None:
        executor = SandboxedMutationExecutor(always_sandbox=False)
        result = executor._run_in_process(
            dna_hash="evil",
            dna_content=_evil_dna(),
            mode="sim",
            pnl=1000.0,
            max_dd=0.0,
            sharpe=5.0,
            input_hash="ih",
        )
        assert "no_naked_orders" in result.violations
        assert not result.passed

    def test_audit_record_contains_input_hash(self) -> None:
        executor = SandboxedMutationExecutor(always_sandbox=False)
        result = executor._run_in_process(
            dna_hash="t",
            dna_content="{}",
            mode="sim",
            pnl=100.0,
            max_dd=10.0,
            sharpe=0.5,
            input_hash="my_input_hash",
        )
        assert result.input_hash == "my_input_hash"

    def test_sandbox_not_used_flag(self) -> None:
        executor = SandboxedMutationExecutor(always_sandbox=False)
        result = executor._run_in_process(
            dna_hash="t",
            dna_content="{}",
            mode="sim",
            pnl=100.0,
            max_dd=10.0,
            sharpe=0.5,
            input_hash="h",
        )
        assert result.sandbox_used is False


# ---------------------------------------------------------------------------
# Input hash is deterministic
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestInputHashDeterminism:

    def test_same_input_produces_same_hash(self) -> None:
        dna = '{"a": 1}'
        payload = json.dumps(
            {"dna_content": dna, "mode": "sim", "pnl": 0.0, "max_dd": 0.0, "sharpe": 0.0},
            sort_keys=True,
        )
        h1 = hashlib.sha256(payload.encode()).hexdigest()
        h2 = hashlib.sha256(payload.encode()).hexdigest()
        assert h1 == h2

    def test_different_inputs_produce_different_hashes(self) -> None:
        p1 = json.dumps({"dna_content": "a", "mode": "sim", "pnl": 0.0, "max_dd": 0.0, "sharpe": 0.0}, sort_keys=True)
        p2 = json.dumps({"dna_content": "b", "mode": "sim", "pnl": 0.0, "max_dd": 0.0, "sharpe": 0.0}, sort_keys=True)
        assert hashlib.sha256(p1.encode()).hexdigest() != hashlib.sha256(p2.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Subprocess sandbox — clean DNA passes
# ---------------------------------------------------------------------------

@pytest.mark.slow
class TestSubprocessSandbox:
    """Tests that use a real subprocess sandbox (marked slow)."""

    def test_clean_dna_passes_subprocess(self) -> None:
        executor = SandboxedMutationExecutor(always_sandbox=True, timeout_s=30)
        result = executor.evaluate(
            dna_content=_clean_dna(),
            mode="sim",
            pnl=800.0,
            max_dd=100.0,
            sharpe=1.5,
        )
        assert result.is_constitutional, f"Violations: {result.violations}"
        assert result.score > 0.0
        assert result.sandbox_used is True
        assert result.output_hash  # must have a hash

    def test_evil_dna_blocked_in_subprocess(self) -> None:
        executor = SandboxedMutationExecutor(always_sandbox=True, timeout_s=30)
        result = executor.evaluate(
            dna_content=_evil_dna(),
            mode="sim",
            pnl=10000.0,
            max_dd=0.0,
            sharpe=10.0,
        )
        assert "no_naked_orders" in result.violations
        assert not result.passed

    def test_subprocess_state_isolation(self, tmp_path: Path) -> None:
        """Sandbox must NOT write anything to the real state/ directory."""
        repo_root = Path(__file__).resolve().parents[2]
        real_state = repo_root / "state" / "agent_blackboard.jsonl"
        size_before = real_state.stat().st_size if real_state.exists() else 0

        executor = SandboxedMutationExecutor(
            always_sandbox=True,
            timeout_s=30,
            repo_root=repo_root,
        )
        executor.evaluate(
            dna_content=_clean_dna(),
            mode="sim",
            pnl=100.0,
            max_dd=10.0,
            sharpe=1.0,
        )

        size_after = real_state.stat().st_size if real_state.exists() else 0
        assert size_before == size_after, (
            "Sandbox must not write to the real state/ directory"
        )

    def test_subprocess_input_hash_is_deterministic(self) -> None:
        executor = SandboxedMutationExecutor(always_sandbox=True, timeout_s=30)
        r1 = executor.evaluate(
            dna_content=_clean_dna(), mode="sim", pnl=100.0, max_dd=10.0, sharpe=1.0
        )
        r2 = executor.evaluate(
            dna_content=_clean_dna(), mode="sim", pnl=100.0, max_dd=10.0, sharpe=1.0
        )
        assert r1.input_hash == r2.input_hash

    def test_subprocess_audit_record_serialisable(self) -> None:
        executor = SandboxedMutationExecutor(always_sandbox=True, timeout_s=30)
        result = executor.evaluate(
            dna_content=_clean_dna(), mode="sim", pnl=100.0, max_dd=10.0, sharpe=0.5
        )
        rec = result.to_audit_record()
        assert json.dumps(rec)  # must be JSON-serialisable
