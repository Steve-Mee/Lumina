"""S2 production sources have no TODO/placeholder and every plan test exists."""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
S2_PATHS = (
    Path("lumina_core/research_bridge/fill_stamp.py"),
    Path("lumina_core/research_bridge/fill_index.py"),
    Path("lumina_core/research_bridge/fill_translator.py"),
    Path("lumina_core/research_bridge/calibrator_rows.py"),
    Path("lumina_core/research_bridge/binding_policy.py"),
    Path("lumina_research/validation/cost_calibrate.py"),
    Path("lumina_core/broker/ninjatrader/fabric_mapper.py"),
)
BANNED = ("TODO", "FIXME", "XXX", "NotImplemented", "pass  #", "placeholder")
REQUIRED_TESTS = (
    "tests/research_bridge/test_fill_ssot.py",
    "tests/research_bridge/test_unmapped_fill_not_observed.py",
    "tests/broker/test_fabric_mapper_commission.py",
    "tests/broker/test_fill_slippage_ticks.py",
    "tests/risk/test_cost_model_calibration_per_root.py",
    "tests/research_bridge/test_hypothetical_excluded_from_live_calibration.py",
    "tests/research/test_cost_model_does_not_undercut_card.py",
    "tests/research_bridge/test_discrepancy_execution_wins.py",
    "tests/research/test_phase4_isolation.py",
    "tests/research_bridge/test_s2_attack.py",
    "tests/research_bridge/test_binding_policy.py",
    "tests/research_bridge/s2_mutant_kills.py",
    "tests/research_bridge/s2_mutants.py",
    "tests/research_bridge/test_s2_mutation.py",
    "tests/research_bridge/test_s2_codecov_gaps.py",
)


@pytest.mark.unit
@pytest.mark.safety_gate
def test_s2_sources_have_no_todo_or_pass_placeholders() -> None:
    hits: list[str] = []
    for rel in S2_PATHS:
        text = (ROOT / rel).read_text(encoding="utf-8")
        for index, line in enumerate(text.splitlines(), start=1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            for token in BANNED:
                if token in line:
                    hits.append(f"{rel}:{index}:{token}")
    assert hits == [], "placeholder in S2 source:\n" + "\n".join(hits)


@pytest.mark.unit
def test_plan_named_tests_exist() -> None:
    missing = [rel for rel in REQUIRED_TESTS if not (ROOT / rel).is_file()]
    assert missing == []


@pytest.mark.unit
def test_s2_modules_stay_under_400_loc() -> None:
    for rel in (
        Path("lumina_core/research_bridge/fill_translator.py"),
        Path("lumina_research/validation/cost_calibrate.py"),
        Path("lumina_core/research_bridge/fill_stamp.py"),
        Path("lumina_core/research_bridge/binding_policy.py"),
    ):
        lines = (ROOT / rel).read_text(encoding="utf-8").splitlines()
        assert len(lines) <= 400, f"{rel} is {len(lines)} LOC"
