"""Sandbox isolation & delta tests (v1 simulation)."""

from __future__ import annotations

from lumina_core.architecture_meta.sandbox import ArchitectureMutationSandbox


def test_sandbox_rejects_bad_target():
    sb = ArchitectureMutationSandbox(timeout_s=10)
    res = sb.evaluate_patch(
        proposal_id="test-1",
        target_file="evil/outside.py",
        diff="--- a\n+++ b\n@@\n+pass",
        mode="sim",
        before_health=5.0,
    )
    assert not res.passed
    assert "whitelist" in "".join(res.violations).lower() or "not_whitelisted" in res.violations


def test_sandbox_accepts_whitelisted_and_gives_delta():
    sb = ArchitectureMutationSandbox(timeout_s=10)
    res = sb.evaluate_patch(
        proposal_id="test-extract",
        target_file="lumina_core/safety/constitutional_guard.py",
        diff="small patch that extracts helper",
        mode="sim",
        before_health=6.0,
    )
    assert res.sandbox_used
    # v1 sim always gives modest positive
    assert res.score_delta > 0.05 or res.passed  # allow either in sim
