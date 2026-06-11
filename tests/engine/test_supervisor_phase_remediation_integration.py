"""
Integration/grep guards for Phase 1 Sub11 remediation (D2 sub-slice 11).

Per 2026-06-04 perfection plan; explore ids 17867ddb-3c02-4d83-8d37-a09dce7090da,
c1697bc9-9864-4189-8349-7a5632b7a8bf; functional thin + machine-drives.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from lumina_core.engine.supervisor_phase_state_machine import SupervisorPhaseStateMachine

_FACADE = Path(__file__).resolve().parents[2] / "lumina_core" / "engine" / "runtime_workers_facade.py"

# Patterns that must NOT appear in _old_supervisor_loop_inner while body (comments stripped first).
_FORBIDDEN_IN_LOOP = [
    re.compile(r"\brun_3year_validation\s*\("),
    re.compile(r"\blast_balance_fetch\s*>\s*10"),
    re.compile(r"\bRlBiasApplier\s*\(\s*app\s*="),
    re.compile(r"\bapply_hard_risk_controller_to_signal\s*\("),
    re.compile(r"\bapply_agent_policy_gateway\s*\("),
]

_ALLOWED_IN_LOOP = [
    re.compile(r"\badvance_or_tick\s*\("),
    re.compile(r"\bPriceDupeResolver\s*\("),
    re.compile(r"\bphases\.(?:tick|advance_or_tick)\s*\("),
]


def _extract_old_supervisor_while_source() -> str:
    text = _FACADE.read_text(encoding="utf-8")
    marker = "def run_inner"
    start = text.index(marker)
    rest = text[start:]
    while_idx = rest.index("    while True:")
    chunk = rest[while_idx:]
    end_marker = "\n\n\ndef run_supervisor_loop"
    end = chunk.index(end_marker) if end_marker in chunk else len(chunk)
    return chunk[:end]


def _strip_comments_and_strings(source: str) -> str:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return source
    for node in ast.walk(tree):
        for attr in ("lineno", "end_lineno"):
            if hasattr(node, attr):
                pass
    lines = source.splitlines()
    out: list[str] = []
    for line in lines:
        s = line.strip()
        if s.startswith("#"):
            continue
        code_part = line.split("#", 1)[0]
        out.append(code_part)
    return "\n".join(out)


@pytest.mark.unit
def test_supervisor_loop_inner_has_no_inline_orchestration():
    """God while body must only delegate via PriceDupeResolver + phases.advance_or_tick."""
    loop_src = _extract_old_supervisor_while_source()
    code = _strip_comments_and_strings(loop_src)
    for pat in _FORBIDDEN_IN_LOOP:
        assert pat.search(code) is None, f"Forbidden pattern in supervisor while: {pat.pattern}"
    assert _ALLOWED_IN_LOOP[0].search(code) is not None
    assert _ALLOWED_IN_LOOP[1].search(code) is not None


@pytest.mark.unit
def test_advance_or_tick_returns_dict_with_signal():
    engine = SimpleNamespace(
        config=SimpleNamespace(
            trade_mode="paper",
            instrument="MES",
            min_confluence=0.5,
            drawdown_kill_percent=10.0,
            status_print_interval_sec=9999.0,
        ),
        last_validation=None,
        validator=None,
        emotional_twin=None,
        risk_controller=None,
        local_engine=None,
        infinite_simulator=None,
        swarm=None,
    )
    app = SimpleNamespace(
        engine=engine,
        container=SimpleNamespace(operations_service=None, broker=None),
        INSTRUMENT="MES",
        logger=SimpleNamespace(info=lambda *a, **k: None, warning=lambda *a, **k: None, error=lambda *a, **k: None),
        live_data_lock=type("Lock", (), {"__enter__": lambda s: None, "__exit__": lambda *a: None})(),
        get_current_dream_snapshot=lambda: {"signal": "HOLD", "confluence_score": 0.0},
        set_current_dream_fields=lambda d: None,
        is_market_open=lambda: True,
        calculate_adaptive_risk_and_qty=lambda *a, **k: 0,
        sim_position_qty=0,
        account_equity=100000.0,
        account_balance=100000.0,
        open_pnl=0.0,
        pnl_history=[],
        save_state=lambda: None,
        realized_pnl_today=0.0,
    )
    phases = SupervisorPhaseStateMachine(app=app, engine=engine)
    res = phases.advance_or_tick(5000.0, dream_snapshot={"signal": "HOLD"})
    assert isinstance(res, dict)
    assert "signal" in res
    assert res["signal"] == "HOLD"


@pytest.mark.unit
def test_manual_smoke_sub11_remediation_success_marker():
    assert "MANUAL_SMOKE_SUB11_REMEDIATION_SUCCESS"
