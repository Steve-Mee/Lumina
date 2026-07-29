"""AST guards for plateau_escalator god surface baseline.

plateau_escalator was extracted as part of birth engine modularization.
This guard prevents it from growing into a new god file (following the same
discipline as stage_training_loop, certificate_pipeline, meta_controller, etc.).
"""

from __future__ import annotations

from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_P = _ROOT / "lumina_core" / "birth" / "plateau_escalator.py"

# Baseline after engine extractions. 976 lines at time of guard addition.
# 2026-07-25: dead-zone / terminal hard-stop ladder (+~100 LOC).
# 2026-07-26 Seal II: ladder tables/step API → plateau_evolution_ladder.py; ratchet host.
# 2026-07-28 Wave A: rolling/enter/terminal/telemetry extracts; thin façade host.
_P_LINE_BASELINE = 212


@pytest.mark.unit
def test_plateau_escalator_loc_at_or_below_baseline() -> None:
    line_count = len(_P.read_text(encoding="utf-8").splitlines())
    assert line_count <= _P_LINE_BASELINE, (
        f"plateau_escalator.py has {line_count} lines (baseline <= {_P_LINE_BASELINE}); "
        "extract to bounded modules instead of growing the god file"
    )


@pytest.mark.unit
def test_plateau_escalator_exports_key_symbols() -> None:
    text = _P.read_text(encoding="utf-8")
    assert "class PlateauState" in text or "class EvolutionAction" in text
    assert "plateau_trades_beyond_gate" in text
    assert "evolution_ladder_exhausted" in text or "evolution_actions_completed" in text
