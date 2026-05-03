from __future__ import annotations

import json
from pathlib import Path

from lumina_core.audit.agent_decision_log import AgentDecisionLog
from lumina_core.audit.replay_validator import DecisionReplayValidator


def test_replay_validator_accepts_valid_chain(tmp_path: Path) -> None:
    path = tmp_path / "agent_decision_log.jsonl"
    log = AgentDecisionLog(path=path)
    log.log_decision(
        agent_id="A",
        raw_input={"x": 1},
        raw_output={"signal": "HOLD"},
        confidence=0.4,
        policy_outcome="ok",
        decision_context_id="ctx-1",
        model_version="model-a",
        prompt_version="p-v1",
        policy_version="policy-v1",
        provider_route=["provider-a"],
        calibration_factor=1.0,
    )
    log.log_decision(
        agent_id="B",
        raw_input={"x": 2},
        raw_output={"signal": "BUY"},
        confidence=0.8,
        policy_outcome="ok",
        decision_context_id="ctx-2",
        model_version="model-b",
        prompt_version="p-v2",
        policy_version="policy-v1",
        provider_route=["provider-b"],
        calibration_factor=1.05,
    )

    validator = DecisionReplayValidator(path=path)
    chain = validator.verify_hash_chain()
    lineage = validator.verify_lineage()

    assert chain["valid"] is True
    assert lineage["valid"] is True


def test_replay_validator_detects_lineage_missing(tmp_path: Path) -> None:
    path = tmp_path / "agent_decision_log.jsonl"
    payload = {
        "timestamp": "2026-04-15T00:00:00+00:00",
        "agent_id": "X",
        "prompt_hash": "abc",
        "model_version": "model-x",
        "raw_input": {},
        "raw_output": {},
        "confidence": 0.1,
        "policy_outcome": "ok",
        "decision_context_id": "ctx",
        "trade_record_id": None,
        "evolution_log_hash": None,
        "prev_hash": "GENESIS",
        "log_version": "v1",
    }
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=True)
    import hashlib

    payload["hash"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")

    validator = DecisionReplayValidator(path=path)
    lineage = validator.verify_lineage()
    assert lineage["valid"] is False
    assert len(lineage["violations"]) == 1
