"""Architecture constitution fail-closed tests."""

from __future__ import annotations

from lumina_core.architecture_meta.constitution import ArchitectureConstitution


def test_small_diff_and_delta_required():
    c = ArchitectureConstitution(max_patch_lines=20)
    bad = type("P", (), {"diff": "\n" * 100, "expected_delta": 0.01, "target_file": "x.py", "mutation_type": "foo", "before_score": 5})()
    res = c.check_pre_mutation(bad)
    assert not res.passed
    assert any(v.principle_name in ("small_diff_only", "requires_measurable_improvement") for v in res.violations)
