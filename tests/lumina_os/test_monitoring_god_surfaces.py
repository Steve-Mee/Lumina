"""AST guards for monitoring_endpoints facade (phase 7C)."""

from __future__ import annotations

from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_ENDPOINTS = _ROOT / "lumina_os" / "backend" / "monitoring_endpoints.py"
_ENDPOINTS_LINE_BASELINE = 538


def _source() -> str:
    return _ENDPOINTS.read_text(encoding="utf-8")


@pytest.mark.unit
def test_monitoring_endpoints_loc_at_or_below_baseline() -> None:
    line_count = len(_source().splitlines())
    assert line_count <= _ENDPOINTS_LINE_BASELINE, (
        f"monitoring_endpoints.py has {line_count} lines (baseline <= {_ENDPOINTS_LINE_BASELINE})"
    )


@pytest.mark.unit
def test_monitoring_endpoints_imports_snapshots_module() -> None:
    source = _source()
    assert "lumina_os.monitoring.snapshots" in source