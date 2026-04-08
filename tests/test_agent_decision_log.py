from __future__ import annotations

import json
from pathlib import Path

from lumina_core.engine.agent_decision_log import AgentDecisionLog


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
