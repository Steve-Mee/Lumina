"""Sandbox isolation tests for code evolution."""

from __future__ import annotations

from pathlib import Path

from lumina_core.code_evolution.operators import sma_indicator_template, strategy_snippet_template
from lumina_core.safety.sandboxed_code_executor import SandboxedCodeExecutor


def test_parameter_tweak_sandbox_pass():
    sb = SandboxedCodeExecutor(timeout_s=20)
    res = sb.evaluate(
        proposal_id="t1",
        operator="parameter_tweak",
        payload={"key": "ema_fast_window", "old_value": 8.0, "new_value": 9.0},
        mode="sim",
    )
    assert res.passed
    assert res.sandbox_used
    assert res.score > 0
    assert res.input_hash
    assert res.output_hash


def test_parameter_out_of_bounds_sandbox_fail():
    sb = SandboxedCodeExecutor(timeout_s=20)
    res = sb.evaluate(
        proposal_id="t2",
        operator="parameter_tweak",
        payload={"key": "ema_fast_window", "old_value": 8.0, "new_value": 99.0},
        mode="sim",
    )
    assert not res.passed
    assert res.violations


def test_indicator_sandbox_pass():
    sb = SandboxedCodeExecutor(timeout_s=20)
    res = sb.evaluate(
        proposal_id="t3",
        operator="add_simple_indicator",
        payload={"name": "sma", "code": sma_indicator_template(5)},
        mode="sim",
    )
    assert res.passed, res.violations


def test_unsafe_import_rejected():
    sb = SandboxedCodeExecutor(timeout_s=20)
    bad = "import os\ndef indicator(series):\n    return list(series)\n"
    res = sb.evaluate(
        proposal_id="t4",
        operator="add_simple_indicator",
        payload={"code": bad},
        mode="sim",
    )
    assert not res.passed
    assert any("blocked" in v or "Import" in v for v in res.violations)


def test_strategy_snippet_sandbox_pass():
    sb = SandboxedCodeExecutor(timeout_s=20)
    res = sb.evaluate(
        proposal_id="t5",
        operator="strategy_snippet_adjust",
        payload={"code": strategy_snippet_template(fast_window=3)},
        mode="sim",
    )
    assert res.passed, res.violations


def test_sandbox_does_not_write_live_state(tmp_path: Path, monkeypatch):
    """Worker redirects LUMINA_STATE_DIR; live project state dir must not gain codevo files."""
    live_state = tmp_path / "live_state"
    live_state.mkdir()
    monkeypatch.setenv("LUMINA_STATE_DIR", str(live_state))
    before = set(p.name for p in live_state.iterdir())
    sb = SandboxedCodeExecutor(timeout_s=20)
    sb.evaluate(
        proposal_id="t6",
        operator="parameter_tweak",
        payload={"key": "ema_fast_window", "old_value": 8.0, "new_value": 9.0},
        mode="sim",
    )
    after = set(p.name for p in live_state.iterdir())
    # Sandbox uses private tmpdir; live state listing should be unchanged
    assert after == before
