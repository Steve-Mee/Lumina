"""AST guards for certificate_pipeline god surface baseline (phase 1D)."""

from __future__ import annotations

from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_CERT_PIPELINE = _ROOT / "lumina_core" / "birth" / "certificate_pipeline.py"

_CERT_PIPELINE_LINE_BASELINE = 200


@pytest.mark.unit
def test_certificate_pipeline_loc_at_or_below_baseline() -> None:
    line_count = len(_CERT_PIPELINE.read_text(encoding="utf-8").splitlines())
    assert line_count <= _CERT_PIPELINE_LINE_BASELINE, (
        f"certificate_pipeline.py has {line_count} lines (baseline <= {_CERT_PIPELINE_LINE_BASELINE})"
    )


@pytest.mark.unit
def test_certificate_pipeline_class_exports_methods() -> None:
    text = _CERT_PIPELINE.read_text(encoding="utf-8")
    for name in (
        "ensure_holdout_preflight",
        "run_certificate_remediation",
        "complete_certified_birth",
    ):
        assert f"def {name}(" in text