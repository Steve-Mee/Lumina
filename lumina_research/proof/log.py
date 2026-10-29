"""Append Phase 5 results to the experiment JSONL and project-brain evolution log."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping

from lumina_research.agents.experiment_log import log_experiment
from lumina_research.validation.audit import utc_now_iso

PROOF_AGENT_ID = "empirical_proof_agent"
EVOLUTION_JSONL = "phase5-empirical.jsonl"
EVOLUTION_MD = "phase5-empirical.md"


def log_proof_event(
    *,
    path: Path,
    event: str,
    metrics: Mapping[str, object],
    evolution_log_dir: Path | None = None,
    reject_reason: str | None = None,
    failed_checks: tuple[str, ...] = (),
) -> None:
    log_experiment(
        path=path,
        agent_id=PROOF_AGENT_ID,
        event=event,
        hypothesis_id="phase5",
        rationale=None,
        metrics=dict(metrics),
        reject_reason=reject_reason,
        failed_checks=failed_checks,
    )
    if evolution_log_dir is None:
        return
    evolution_log_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "timestamp": utc_now_iso(),
        "agent_id": PROOF_AGENT_ID,
        "event": event,
        "metrics": dict(metrics),
        "reject_reason": reject_reason,
        "failed_checks": list(failed_checks),
    }
    line = json.dumps(payload, sort_keys=True, default=str) + "\n"
    target = evolution_log_dir / EVOLUTION_JSONL
    with target.open("a", encoding="utf-8") as handle:
        handle.write(line)
        handle.flush()
    weekly = evolution_log_dir / EVOLUTION_MD
    if not weekly.exists():
        weekly.write_text("# Phase 5 empirical proof\n\n", encoding="utf-8")
    with weekly.open("a", encoding="utf-8") as handle:
        handle.write(
            f"- `{payload['timestamp']}` agent=`{PROOF_AGENT_ID}` event=`{event}` "
            f"reject=`{reject_reason}`\n"
        )
