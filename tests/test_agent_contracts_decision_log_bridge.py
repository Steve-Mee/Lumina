from __future__ import annotations

from pathlib import Path

from lumina_core.engine.TapeReadingAgent import TapeReadingAgent


def test_contract_agent_writes_agent_decision_log(tmp_path: Path, monkeypatch) -> None:
    state_dir = tmp_path / "state"
    monkeypatch.chdir(tmp_path)

    agent = TapeReadingAgent()
    result = agent.score_momentum(
        {
            "volume_delta": 500.0,
            "avg_volume_delta_10": 100.0,
            "bid_ask_imbalance": 2.2,
            "cumulative_delta_10": 300.0,
        }
    )

    assert result["signal"] in {"BUY", "HOLD"}

    decision_log = state_dir / "agent_decision_log.jsonl"
    assert decision_log.exists()
    lines = [line for line in decision_log.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(lines) >= 1
