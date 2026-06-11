"""
AST/grep guards for D2 sub-slice 18: runtime_workers god surface close-out.

Ensures runtime_workers.py stays a thin compat hub; non-trivial logic lives in bounded modules.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_RUNTIME_WORKERS = _ROOT / "lumina_core" / "runtime_workers.py"
_FACADE = _ROOT / "lumina_core" / "engine" / "runtime_workers_facade.py"

# Inline patterns that must not appear in runtime_workers (owned by bounded modules).
_FORBIDDEN_IN_GOD = [
    "np.maximum.accumulate",
    "write_runtime_monitoring_snapshot",
    "def _emotional_twin_worker",
    "while True:",
    "recognize_google",
    "set_current_dream",
    "PaperSimulator(",
    "RlBiasApplier(",
    "run_3year_validation(",
]

_THIN_DELEGATE_MARKERS = [
    "PriceDupeResolver",
    "RuntimeMonitoringService",
    "VoiceLegacyHandler",
    "PreDreamDaemon",
    "StatePersistDaemon",
    "SupervisorLoopRunner",
    "TraderLeagueWebhook",
    "EODForceCloseService",
]


def _function_body_lines(source: str, name: str) -> str:
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            lines = source.splitlines()
            start = node.lineno - 1
            end = node.end_lineno or start + 1
            return "\n".join(lines[start:end])
    msg = f"function {name!r} not found"
    raise AssertionError(msg)


@pytest.mark.unit
def test_runtime_workers_loc_at_or_below_target():
    line_count = len(_RUNTIME_WORKERS.read_text(encoding="utf-8").splitlines())
    assert line_count <= 120, f"runtime_workers.py has {line_count} lines (target <=120)"


@pytest.mark.unit
def test_runtime_workers_forbidden_inline_patterns():
    text = _RUNTIME_WORKERS.read_text(encoding="utf-8")
    for pat in _FORBIDDEN_IN_GOD:
        assert pat not in text, f"Forbidden inline pattern in god hub: {pat!r}"


@pytest.mark.unit
def test_runtime_workers_delegate_functions_are_thin():
    text = _RUNTIME_WORKERS.read_text(encoding="utf-8")
    thin_names = [
        "_compute_session_kpis",
        "_publish_runtime_monitoring_snapshot",
        "_push_trader_league_trade",
        "pre_dream_daemon",
        "voice_listener_thread",
        "state_persist_daemon",
        "_old_supervisor_loop",
        "_old_supervisor_loop_inner",
        "supervisor_loop",
    ]
    for name in thin_names:
        body = _function_body_lines(text, name)
        assert len(body.splitlines()) <= 8, f"{name} should be thin delegate (got {len(body.splitlines())} lines)"


@pytest.mark.unit
def test_runtime_workers_has_bounded_module_markers():
    text = _RUNTIME_WORKERS.read_text(encoding="utf-8")
    hits = sum(1 for m in _THIN_DELEGATE_MARKERS if m in text)
    assert hits >= 6


@pytest.mark.unit
def test_facade_owns_supervisor_while_loop():
    text = _FACADE.read_text(encoding="utf-8")
    assert "while True:" in text
    assert "SupervisorPhaseStateMachine" in text
    assert "PriceDupeResolver" in text
    assert "EmotionalTwinWorker" in text
    loop_start = text.index("    while True:")
    loop_chunk = text[loop_start : loop_start + 600]
    assert "advance_or_tick" in loop_chunk
    assert "run_3year_validation" not in loop_chunk
    print("MANUAL_SMOKE_SUB18_GOD_SURFACES_SUCCESS")
