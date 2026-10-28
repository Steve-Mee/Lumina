"""AST guards for meta_controller god surface baseline (phase 1F follow-on).

meta_controller was extracted as a bounded owner from birth/engine.py.
Further split: signals / decisions / self_eval_ops + thin façade.
This guard prevents the façade (or any split piece) from growing back into a god file.
"""

from __future__ import annotations

from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_META = _ROOT / "lumina_core" / "birth" / "meta_controller.py"
_META_TYPES = _ROOT / "lumina_core" / "birth" / "meta_controller_types.py"
_META_SIGNALS = _ROOT / "lumina_core" / "birth" / "meta_controller_signals.py"
_META_DECISIONS = _ROOT / "lumina_core" / "birth" / "meta_controller_decisions.py"
_META_SELF_EVAL_OPS = _ROOT / "lumina_core" / "birth" / "meta_controller_self_eval_ops.py"

# Façade after signals/decisions/self_eval_ops split (should stay thin).
_META_LINE_BASELINE = 250
_SPLIT_LINE_BASELINE = 600


@pytest.mark.unit
def test_meta_controller_loc_at_or_below_baseline() -> None:
    line_count = len(_META.read_text(encoding="utf-8").splitlines())
    assert line_count <= _META_LINE_BASELINE, (
        f"meta_controller.py has {line_count} lines (baseline <= {_META_LINE_BASELINE}); "
        "extract to bounded modules instead of growing the god file"
    )


@pytest.mark.unit
def test_meta_controller_split_modules_exist_and_bounded() -> None:
    for path in (_META_SIGNALS, _META_DECISIONS, _META_SELF_EVAL_OPS):
        assert path.is_file(), f"missing split module {path.name}"
        lines = len(path.read_text(encoding="utf-8").splitlines())
        assert lines <= _SPLIT_LINE_BASELINE, f"{path.name} too large: {lines} lines"


@pytest.mark.unit
def test_meta_controller_exports_key_symbols() -> None:
    text = _META.read_text(encoding="utf-8")
    types_text = _META_TYPES.read_text(encoding="utf-8")
    signals_text = _META_SIGNALS.read_text(encoding="utf-8")
    # Core owners referenced by birth/engine and other birth surfaces
    assert "class AdaptationDecision" in types_text
    assert "class StallDetectionResult" in types_text or "detect_stall" in text
    assert "get_adaptation_decision" in text or "get_adaptation_decision" in signals_text
    assert "LearningHealth" in text or "LearningSnapshot" in text
    assert "class BirthMetaController" in text
    assert "MetaControllerDecisionsMixin" in text
    assert "MetaControllerSelfEvalMixin" in text
