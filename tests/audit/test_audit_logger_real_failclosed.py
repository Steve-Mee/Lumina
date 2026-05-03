from __future__ import annotations

from pathlib import Path

import pytest

from lumina_core.audit import AuditChainError, AuditLogger


@pytest.mark.unit
def test_corrupted_tail_real_mode_fails_closed(tmp_path: Path) -> None:
    path = tmp_path / "corrupt_real.jsonl"
    path.write_text('{"broken": true\n', encoding="utf-8")
    logger = AuditLogger()
    with pytest.raises(AuditChainError):
        logger.append(
            stream="agent_decision",
            path=path,
            payload={"agent_id": "A", "lineage": {}},
            mode="real",
            fail_closed_real=True,
        )


@pytest.mark.unit
def test_corrupted_tail_sim_mode_recovers(tmp_path: Path) -> None:
    path = tmp_path / "corrupt_sim.jsonl"
    path.write_text('{"broken": true\n', encoding="utf-8")
    logger = AuditLogger()
    row = logger.append(
        stream="agent_decision",
        path=path,
        payload={"agent_id": "A", "lineage": {}},
        mode="sim",
        fail_closed_real=False,
    )
    assert row["prev_hash"] == "GENESIS"
    backups = list(tmp_path.glob("corrupt_sim.jsonl.corrupt.*"))
    assert backups
