"""Phase 3 D5: invariants.json contract tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

DNA_ROOT = Path(__file__).resolve().parents[2] / "project-dna" / "lumina"
INVARIANTS = DNA_ROOT / "invariants.json"
CONSTITUTION = DNA_ROOT / "constitution.md"


@pytest.mark.unit
def test_no_structural_bypass_invariant_fatal():
    data = json.loads(INVARIANTS.read_text(encoding="utf-8"))
    inv = next(i for i in data["invariants"] if i["id"] == "no_structural_bypass_capital_paths")
    assert inv["severity"] == "fatal"
    assert inv.get("enforcement", {}).get("runtime") == "lumina_core.risk.aperture_guard"


@pytest.mark.unit
def test_constitution_references_d5_anchor():
    text = CONSTITUTION.read_text(encoding="utf-8")
    assert "no_structural_bypass_capital_paths" in text or "Geen structurele bypasses" in text
