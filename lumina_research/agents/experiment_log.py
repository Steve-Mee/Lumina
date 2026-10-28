"""Append-only experiment JSONL. Reuses the Phase 1 audit writer (flock + fsync)."""

from __future__ import annotations

from pathlib import Path
from typing import Mapping

from lumina_research.validation.audit import write_event


def log_experiment(
    *,
    path: Path,
    agent_id: str,
    event: str,
    hypothesis_id: str,
    rationale: Mapping[str, object] | None,
    metrics: Mapping[str, object],
    reject_reason: str | None,
    failed_checks: tuple[str, ...],
) -> None:
    """UTC timestamp is assigned by the Phase 1 audit log. Caller timestamps are refused."""
    write_event(
        path=path,
        agent_id=agent_id,
        event=event,
        metrics={
            "hypothesis_id": hypothesis_id,
            "rationale": dict(rationale) if rationale is not None else None,
            "metrics": dict(metrics),
            "reject_reason": reject_reason,
            "failed_checks": list(failed_checks),
            "gate_check_failed": list(failed_checks),
        },
    )
