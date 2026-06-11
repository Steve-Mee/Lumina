"""Phase 3 D5: capital aperture static scan tests."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "dna_guardian"))

from capital_aperture_scan import (  # noqa: E402
    run_d5_capital_aperture_checks,
    scan_capital_aperture_forbidden_patterns,
    validate_constitution_invariant_alignment,
)


@pytest.mark.unit
def test_alignment_passes_on_repo():
    result = validate_constitution_invariant_alignment(ROOT)
    assert result["ok"] is True
    assert result["issues"] == []


@pytest.mark.unit
def test_static_scan_clean_on_repo():
    result = scan_capital_aperture_forbidden_patterns(ROOT)
    assert result["ok"] is True
    assert result["violations"] == []
    assert result["scanned_files"] > 0


@pytest.mark.unit
def test_combined_d5_checks_pass():
    result = run_d5_capital_aperture_checks(ROOT)
    assert result["ok"] is True


@pytest.mark.unit
def test_static_scan_fails_on_injected_violation(tmp_path: Path):
    fake_root = tmp_path / "repo"
    lumina = fake_root / "lumina_core"
    lumina.mkdir(parents=True)
    (lumina / "evil_bypass.py").write_text(
        "def submit():\n    skip_final_arbitration = True\n    return skip_final_arbitration\n",
        encoding="utf-8",
    )
    result = scan_capital_aperture_forbidden_patterns(fake_root)
    assert result["ok"] is False
    assert any(v["pattern_id"] == "B-001-skip-final-arbitration" for v in result["violations"])
