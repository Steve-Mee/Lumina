from __future__ import annotations

import logging
from typing import Any

import pytest

from lumina_core.engine import agent_contracts


class _FailingDecisionLog:
    def log_decision(self, **_: Any) -> None:
        raise RuntimeError("mirror failed")


def _sample_contract_payload() -> dict[str, Any]:
    return {
        "ts": "2026-05-03T11:00:00+00:00",
        "status": "accepted",
        "agent": "TestAgent",
        "method": "test_method",
        "prompt_version": "p-v1",
        "model_hash": "model-v1",
        "confidence": 0.5,
        "full_context": {"input": {"x": 1}, "output": {"signal": "HOLD"}},
    }


def test_agent_contract_mirror_failure_logs_but_allows_sim(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setenv("LUMINA_MODE", "sim")
    monkeypatch.setattr(agent_contracts, "_AGENT_DECISION_LOG", _FailingDecisionLog())

    with caplog.at_level(logging.ERROR):
        agent_contracts._append_immutable_decision_log(_sample_contract_payload())

    assert "failed to mirror contract decision" in caplog.text


def test_agent_contract_mirror_failure_fails_closed_in_real(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setenv("LUMINA_MODE", "real")
    monkeypatch.setattr(agent_contracts, "_AGENT_DECISION_LOG", _FailingDecisionLog())

    with caplog.at_level(logging.ERROR):
        with pytest.raises(agent_contracts.AgentContractError):
            agent_contracts._append_immutable_decision_log(_sample_contract_payload())

    assert "failed to mirror contract decision" in caplog.text
