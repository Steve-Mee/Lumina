"""Zero-gap: every S4 claim has code + test. No TODO in new S4 modules."""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
S4_PATHS = (
    "lumina_core/research_bridge/continuity_meter.py",
    "lumina_core/research_bridge/protective_stop.py",
    "lumina_core/research_bridge/protective_attach.py",
    "lumina_core/research_bridge/sim_protected.py",
    "lumina_core/research_bridge/alerts.py",
    "lumina_core/research_bridge/sim_gate.py",
    "lumina_core/research_bridge/sim_runtime.py",
    "lumina_core/risk/alarm_executor.py",
    "lumina_research/cycles/sim_plan.py",
    "scripts/research/check_sim_entry.py",
    "docs/adr/0064-s4-sim-entry-hardening.md",
    "docs/runbooks/nt8-atm-template.md",
)
S4_LOC_PATHS = (
    "lumina_core/research_bridge/continuity_meter.py",
    "lumina_core/research_bridge/protective_stop.py",
    "lumina_core/research_bridge/protective_attach.py",
    "lumina_core/research_bridge/sim_protected.py",
    "lumina_core/research_bridge/alerts.py",
    "lumina_core/research_bridge/sim_gate.py",
    "lumina_core/research_bridge/sim_runtime.py",
    "lumina_core/risk/alarm_executor.py",
    "lumina_core/risk/risk_gates.py",
    "scripts/research/check_sim_entry.py",
)
SOURCE_LABEL = "research team decision (relayed by Steve 2026-10-29)"


@pytest.mark.unit
def test_s4_modules_have_no_todo_or_placeholder() -> None:
    banned = ("TODO", "FIXME", "placeholder", "NotImplemented", "pass  #")
    hits: list[str] = []
    for rel in S4_PATHS:
        text = (ROOT / rel).read_text(encoding="utf-8")
        for token in banned:
            if token in text:
                hits.append(f"{rel}:{token}")
    assert hits == []
    # risk_gates.py keeps pre-existing NotImplementedError stubs; LOC only.
    for rel in S4_LOC_PATHS:
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert len(text.splitlines()) <= 400, rel


@pytest.mark.unit
def test_named_s4_tests_exist() -> None:
    required = (
        "tests/research_bridge/test_continuity_meter.py",
        "tests/research_bridge/test_s4_e2e_shadow_nt_tape.py",
        "tests/research_bridge/test_telegram_alert_sink.py",
        "tests/research_bridge/test_protective_stop.py",
        "tests/research_bridge/test_protective_attach.py",
        "docs/runbooks/nt8-atm-template.md",
        "tests/research_bridge/test_s4_attack.py",
        "tests/risk/test_s4_caps_bypass_closed.py",
        "tests/risk/test_s4_stale_equity_sim.py",
        "tests/risk/test_alarm_prolonged_disconnect.py",
        "docs/adr/0064-s4-sim-entry-hardening.md",
    )
    missing = [path for path in required if not (ROOT / path).is_file()]
    assert missing == []


@pytest.mark.unit
def test_s4_source_label_is_research_team_relayed_by_steve() -> None:
    labeled = (
        "docs/adr/0064-s4-sim-entry-hardening.md",
        "docs/adr/0059-research-phase5-empirical-proof-and-fabric-ports.md",
        "docs/adr/0063-sim-orders-gated.md",
        "lumina_core/research_bridge/continuity_meter.py",
        "lumina_core/research_bridge/protective_stop.py",
        "lumina_core/research_bridge/protective_attach.py",
        "lumina_core/research_bridge/sim_protected.py",
        "lumina_core/research_bridge/alerts.py",
        "lumina_core/research_bridge/sim_gate.py",
        "lumina_research/cycles/sim_plan.py",
        "lumina_core/risk/risk_gates.py",
        "lumina_core/engine/mode_capabilities.py",
        "lumina_core/order_gatekeeper/engine_helpers.py",
        "lumina_core/risk/alarm_executor.py",
    )
    missing = [
        rel
        for rel in labeled
        if SOURCE_LABEL.lower() not in (ROOT / rel).read_text(encoding="utf-8").lower()
    ]
    assert missing == []
    adr = (ROOT / "docs/adr/0064-s4-sim-entry-hardening.md").read_text(encoding="utf-8")
    assert "needs human review" in adr.lower()
    assert "Status:** Proposed" in adr or "Status: Proposed" in adr
