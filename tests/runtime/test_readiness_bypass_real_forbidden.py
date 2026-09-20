"""SC-4: LUMINA_TEST_BYPASS_READINESS_GATE must never arm READY_FOR_REAL in real."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pytest

from lumina_core.runtime.headless_config import _resolve_test_bypass_readiness_gate
from lumina_core.runtime.headless_runtime import HeadlessRuntime
from lumina_core.runtime.headless_runtime_helpers import _apply_stability_and_bypass

_HELPERS = "lumina_core.runtime.headless_runtime_helpers"


def _not_ready_report() -> dict[str, Any]:
    return {
        "READY_FOR_REAL": False,
        "ready_for_real": False,
        "status": "RED",
        "criteria": {},
        "consecutive_green_days": 0,
        "days_to_green": 5,
    }


def _stub_stability_pipeline(monkeypatch: pytest.MonkeyPatch, report: dict[str, Any]) -> None:
    monkeypatch.setattr(
        f"{_HELPERS}.append_history_entry_for_summary",
        lambda *_args, **_kwargs: {"ok": True, "appended": 0},
    )
    monkeypatch.setattr(
        f"{_HELPERS}.generate_stability_report",
        lambda limit=0: dict(report),
    )


@pytest.mark.unit
@pytest.mark.safety_gate
def test_env_true_mode_real_resolver_stays_false(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LUMINA_TEST_BYPASS_READINESS_GATE", "true")

    assert _resolve_test_bypass_readiness_gate(mode="real") is False
    assert _resolve_test_bypass_readiness_gate(mode="REAL") is False


@pytest.mark.unit
@pytest.mark.safety_gate
def test_env_true_trade_mode_real_resolver_stays_false(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LUMINA_TEST_BYPASS_READINESS_GATE", "true")
    monkeypatch.setenv("TRADE_MODE", "real")

    assert _resolve_test_bypass_readiness_gate() is False
    assert _resolve_test_bypass_readiness_gate(mode="sim") is False


@pytest.mark.unit
def test_env_true_mode_sim_resolver_still_allows_lab_bypass(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LUMINA_TEST_BYPASS_READINESS_GATE", "true")

    assert _resolve_test_bypass_readiness_gate(mode="sim") is True


@pytest.mark.unit
@pytest.mark.safety_gate
def test_apply_stability_env_true_mode_real_still_not_ready(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LUMINA_TEST_BYPASS_READINESS_GATE", "true")
    _stub_stability_pipeline(monkeypatch, _not_ready_report())

    summary: dict[str, Any] = {"mode": "real", "stress_ready_for_real_gate": False}
    _apply_stability_and_bypass(summary, runtime_logger=logging.getLogger("test.sc4"))

    assert summary["READY_FOR_REAL"] is False
    assert summary["READY_FOR_REAL"] is not True
    assert summary.get("stability_status") != "TEST_BYPASS"
    assert summary.get("stress_ready_for_real_gate") is not True
    bypass = summary["test_readiness_bypass"]
    assert bypass["enabled"] is False
    assert bypass["refused"] is True
    assert bypass["reason"] == "test_bypass_forbidden_in_real"
    assert summary["stability_report"]["READY_FOR_REAL"] is False
    assert summary["stability_report"]["status"] != "TEST_BYPASS"


@pytest.mark.unit
def test_apply_stability_env_true_mode_sim_still_bypasses(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LUMINA_TEST_BYPASS_READINESS_GATE", "true")
    _stub_stability_pipeline(monkeypatch, _not_ready_report())

    summary: dict[str, Any] = {"mode": "sim", "stress_ready_for_real_gate": False}
    _apply_stability_and_bypass(summary, runtime_logger=logging.getLogger("test.sc4"))

    assert summary["READY_FOR_REAL"] is True
    assert summary["stability_status"] == "TEST_BYPASS"
    assert summary["test_readiness_bypass"]["enabled"] is True


@pytest.mark.unit
@pytest.mark.safety_gate
def test_headless_runtime_real_mode_ignores_bypass_env(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import lumina_core.runtime.headless_runtime as hr_mod

    monkeypatch.setattr(hr_mod, "_SUMMARY_PATH", tmp_path / "last_run_summary.json")
    monkeypatch.setenv("LUMINA_TEST_BYPASS_READINESS_GATE", "true")
    monkeypatch.setenv("TRADE_MODE", "real")
    monkeypatch.setenv("LUMINA_MODE", "real")

    runtime = HeadlessRuntime(container=None)
    summary = runtime.run(duration_minutes=1, mode="real", broker_mode="paper")

    assert summary["mode"] == "real"
    assert summary.get("READY_FOR_REAL") is not True
    assert summary.get("stability_status") != "TEST_BYPASS"
    bypass = summary.get("test_readiness_bypass")
    assert bypass is None or bypass.get("enabled") is not True
