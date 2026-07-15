"""AST guards for meta_controller god surface baseline (phase 1F follow-on).

meta_controller was extracted as a bounded owner from birth/engine.py.
This guard prevents it from growing back into a god file.
"""

from __future__ import annotations

from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_META = _ROOT / "lumina_core" / "birth" / "meta_controller.py"
_META_TYPES = _ROOT / "lumina_core" / "birth" / "meta_controller_types.py"

# Baseline captured after engine extractions (phase 1 series).
# meta_controller owns adaptation decisions, stall detection, recovery strategy, learning health.
# Further growth should trigger additional extraction (e.g. separate strategy or health modules).
_META_LINE_BASELINE = 1310


@pytest.mark.unit
def test_meta_controller_loc_at_or_below_baseline() -> None:
    line_count = len(_META.read_text(encoding="utf-8").splitlines())
    assert line_count <= _META_LINE_BASELINE, (
        f"meta_controller.py has {line_count} lines (baseline <= {_META_LINE_BASELINE}); "
        "extract to bounded modules instead of growing the god file"
    )


@pytest.mark.unit
def test_meta_controller_exports_key_symbols() -> None:
    text = _META.read_text(encoding="utf-8")
    types_text = _META_TYPES.read_text(encoding="utf-8")
    # Core owners referenced by birth/engine and other birth surfaces
    assert "class AdaptationDecision" in types_text
    assert "class StallDetectionResult" in types_text or "detect_stall" in text
    assert "get_adaptation_decision" in text
    assert "LearningHealth" in text or "LearningSnapshot" in text
