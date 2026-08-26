"""Sandbox isolation & real patch apply (ADR-0045)."""

from __future__ import annotations

import difflib
from pathlib import Path

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


def test_sandbox_real_unified_diff_applies(tmp_path: Path):
    target = "lumina_core/ports/__init__.py"
    repo = Path(__file__).resolve().parents[2]
    src = repo / target
    original = src.read_text(encoding="utf-8")
    updated = original + "\n# arch-sandbox-probe\n"
    diff = "".join(
        difflib.unified_diff(
            original.splitlines(keepends=True),
            updated.splitlines(keepends=True),
            fromfile="a/" + target,
            tofile="b/" + target,
        )
    )
    sb = ArchitectureMutationSandbox(timeout_s=10, repo_root=repo)
    res = sb.evaluate_patch(
        proposal_id="test-extract",
        target_file=target,
        diff=diff,
        mode="sim",
        before_health=6.0,
    )
    assert res.sandbox_used
    assert res.passed
    assert res.score_delta > 0.05
    # live tree untouched
    assert src.read_text(encoding="utf-8") == original
