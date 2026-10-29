"""Zero-gap: every S3 claim has code + test. No TODO in new S3 modules."""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
S3_PATHS = (
    "lumina_research/validation/nt_tape.py",
    "lumina_core/research_bridge/sim_gate.py",
    "lumina_core/research_bridge/independence.py",
    "lumina_core/research_bridge/sim_runtime.py",
    "lumina_core/risk/alarm_executor.py",
    "scripts/research/check_sim_entry.py",
)


@pytest.mark.unit
def test_s3_modules_have_no_todo_or_placeholder() -> None:
    banned = ("TODO", "FIXME", "placeholder", "NotImplemented", "pass  #")
    hits: list[str] = []
    for rel in S3_PATHS:
        text = (ROOT / rel).read_text(encoding="utf-8")
        for token in banned:
            if token in text:
                hits.append(f"{rel}:{token}")
        assert len(text.splitlines()) <= 400
    assert hits == []


@pytest.mark.unit
def test_named_s3_tests_exist() -> None:
    required = (
        "tests/research/test_nt_tape_no_lookahead.py",
        "tests/research/test_synthetic_cannot_be_survivor.py",
        "tests/research_bridge/test_sim_gate_requires_survivors.py",
        "tests/research_bridge/test_survivor_independence.py",
        "tests/research_bridge/test_sim_gate_mes_mnq_only.py",
        "tests/research_bridge/test_sim_gate_mode.py",
        "tests/research_bridge/test_sim_still_shadow_when_yaml_lies.py",
        "tests/research_bridge/test_supervisor_stays_closed_after_sim_gate.py",
        "tests/research_bridge/test_non_research_default_closed.py",
        "tests/research_bridge/test_research_order_hits_admission.py",
        "tests/research_bridge/test_promotion_gate_requires_mac.py",
        "tests/risk/test_alarm_executor_default_reduce.py",
        "tests/risk/test_alarm_executor_critical_flatten.py",
        "tests/risk/test_alarm_executor_sla.py",
        "tests/research_bridge/test_disconnect_no_new_orders.py",
        "tests/research_bridge/test_stale_equity_blocks_sim.py",
        "tests/research/test_monitor_cannot_place.py",
    )
    missing = [path for path in required if not (ROOT / path).is_file()]
    assert missing == []
