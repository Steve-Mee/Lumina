from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest

from lumina_core.engine.agent_decision_log import AgentDecisionLog, AgentDecisionLogChainError


def test_agent_decision_log_appends_hash_chain(tmp_path: Path) -> None:
    path = tmp_path / "agent_decision_log.jsonl"
    log = AgentDecisionLog(path=path)

    first = log.log_decision(
        agent_id="ReasoningService",
        raw_input={"prompt": "A"},
        raw_output={"signal": "HOLD"},
        confidence=0.5,
        policy_outcome="ok",
        decision_context_id="ctx-1",
        model_version="model-a",
    )
    second = log.log_decision(
        agent_id="NewsAgent",
        raw_input={"prompt": "B"},
        raw_output={"sentiment": "neutral"},
        confidence=0.4,
        policy_outcome="ok",
        decision_context_id="ctx-2",
        model_version="model-b",
    )

    lines = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(lines) == 2
    assert lines[0]["prev_hash"] == "GENESIS"
    assert lines[1]["prev_hash"] == lines[0]["hash"]
    assert lines[0]["hash"] == first["hash"]
    assert lines[1]["hash"] == second["hash"]
    assert isinstance(lines[0].get("config_snapshot_hash"), str)
    assert len(lines[0].get("config_snapshot_hash")) > 0
    assert lines[0]["lineage"]["config_snapshot_hash"] == lines[0]["config_snapshot_hash"]


def test_agent_decision_log_sim_mode_logs_and_recovers_corrupt_tail(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    path = tmp_path / "agent_decision_log.jsonl"
    path.write_text('{"broken": true\n', encoding="utf-8")
    log = AgentDecisionLog(path=path)

    with caplog.at_level(logging.ERROR):
        appended = log.log_decision(
            agent_id="ReasoningService",
            raw_input={"prompt": "recover"},
            raw_output={"signal": "HOLD"},
            confidence=0.1,
            policy_outcome="ok",
            decision_context_id="ctx-recover",
            model_version="model-recover",
            is_real_mode=False,
        )

    assert appended["prev_hash"] == "GENESIS"
    assert len(list(tmp_path.glob("agent_decision_log.jsonl.corrupt.*"))) >= 1


def test_agent_decision_log_real_mode_fails_closed_on_corrupt_tail(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    path = tmp_path / "agent_decision_log.jsonl"
    path.write_text('{"broken": true\n', encoding="utf-8")
    log = AgentDecisionLog(path=path)

    with caplog.at_level(logging.ERROR):
        with pytest.raises(AgentDecisionLogChainError):
            log.log_decision(
                agent_id="ReasoningService",
                raw_input={"prompt": "recover"},
                raw_output={"signal": "HOLD"},
                confidence=0.1,
                policy_outcome="ok",
                decision_context_id="ctx-recover",
                model_version="model-recover",
                is_real_mode=True,
            )

    assert ("failed to load previous hash" in caplog.text) or ("failed to append in REAL mode" in caplog.text)
