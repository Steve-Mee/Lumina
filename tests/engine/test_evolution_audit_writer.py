from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pytest

from lumina_core.evolution.audit_writer import EvolutionAuditWriter, EvolutionAuditWriterError


class _FailingDecisionLog:
    def log_decision(self, **_: Any) -> None:
        raise RuntimeError("mirror failed")


@pytest.mark.unit
def test_evolution_audit_writer_mirror_failure_logs_but_allows_sim(caplog: pytest.LogCaptureFixture) -> None:
    writer = EvolutionAuditWriter(log_path=Path("state/test_evolution_meta.jsonl"), decision_log_provider=_FailingDecisionLog)

    with caplog.at_level(logging.ERROR):
        writer.log_agent_decision(
            raw_input={"x": 1},
            raw_output={"signal": "HOLD"},
            confidence=0.4,
            policy_outcome="sim_experiment",
            decision_context_id="ctx-sim",
            is_real_mode=False,
        )

    assert "failed to mirror agent decision" in caplog.text


@pytest.mark.unit
def test_evolution_audit_writer_mirror_failure_fails_closed_in_real(caplog: pytest.LogCaptureFixture) -> None:
    writer = EvolutionAuditWriter(log_path=Path("state/test_evolution_meta.jsonl"), decision_log_provider=_FailingDecisionLog)

    with caplog.at_level(logging.ERROR):
        with pytest.raises(EvolutionAuditWriterError):
            writer.log_agent_decision(
                raw_input={"x": 1},
                raw_output={"signal": "HOLD"},
                confidence=0.9,
                policy_outcome="real_gate",
                decision_context_id="ctx-real",
                is_real_mode=True,
            )

    assert "failed to mirror agent decision" in caplog.text
