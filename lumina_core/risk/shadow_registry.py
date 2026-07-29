"""Shadow experiment run registry (in-memory + optional JSONL)."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from lumina_core.logging_utils import get_logger
from lumina_core.risk.shadow_types import ShadowExperimentResult

if TYPE_CHECKING:
    from lumina_core.agent_orchestration.schemas import EvolutionPromotionDecision

logger = get_logger("lumina.risk.shadow")


class ShadowRunRegistry:
    """
    Registry for shadow experiment runs with optional file persistence.

    - If no `storage_path` is provided: pure in-memory behavior (fast, for testing/SIM).
    - If `storage_path` is provided: uses a simple, robust JSONL append-only log.
      This gives durability across restarts with minimal complexity and very low risk
      of data corruption.

    This design allows easy evolution to a more sophisticated backend later
    while delivering immediate practical value for repeated shadow experimentation.
    """

    def __init__(self, storage_path: str | Path | None = None):
        self._runs: dict[str, dict[str, Any]] = {}
        self._storage_path: Path | None = Path(storage_path) if storage_path else None

        if self._storage_path:
            self._storage_path.parent.mkdir(parents=True, exist_ok=True)
            self._load_from_disk()

    def _load_from_disk(self) -> None:
        """Load existing runs from JSONL file (best-effort, non-fatal)."""
        if not self._storage_path or not self._storage_path.exists():
            return

        try:
            with self._storage_path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                        if "experiment_id" in record:
                            self._runs[record["experiment_id"]] = record
                    except json.JSONDecodeError:
                        logger.warning("shadow_registry_corrupt_line_skipped", extra={"path": str(self._storage_path)})
        except Exception:
            logger.warning("shadow_registry_load_failed", extra={"path": str(self._storage_path)})

    def _append_to_disk(self, record: dict[str, Any]) -> None:
        """Append a single record to the JSONL file (best-effort)."""
        if not self._storage_path:
            return

        try:
            with self._storage_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception:
            logger.warning("shadow_registry_append_failed", extra={"path": str(self._storage_path)})

    def record(self, experiment_id: str, result: ShadowExperimentResult) -> None:
        """Store a completed shadow experiment result (memory + optional disk)."""
        record = {
            "experiment_id": result.experiment_id,
            "dna_hash": result.dna_hash,
            "decision_trace": result.decision_trace,
            "success": result.success,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        self._runs[experiment_id] = record
        self._append_to_disk(record)

    def get(self, experiment_id: str) -> dict[str, Any] | None:
        """Retrieve a previously recorded shadow run by ID."""
        return self._runs.get(experiment_id)

    def get_decision_trace(self, experiment_id: str) -> dict[str, Any] | None:
        """Convenience method to directly get the decision trace for comparison."""
        run = self._runs.get(experiment_id)
        return run["decision_trace"] if run else None

    def list_recent(self, limit: int = 10) -> list[dict[str, Any]]:
        """Return the most recent recorded runs (newest first)."""
        runs = sorted(
            self._runs.values(),
            key=lambda r: r.get("timestamp", ""),
            reverse=True,
        )
        return runs[:limit]

    def record_promotion_decision(self, experiment_id: str, decision: "EvolutionPromotionDecision") -> None:
        """Store a promotion decision (e.g. after human approval)."""
        key = f"{experiment_id}:promotion:{decision.stage}"
        self._runs[key] = {
            "experiment_id": experiment_id,
            "stage": decision.stage,
            "allowed": decision.allowed,
            "reason": decision.reason,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._append_to_disk(self._runs[key])

    def list_pending_human_approvals(self) -> list[dict[str, Any]]:
        """
        Return experiments that have reached the human_approval stage
        but have not yet received a final decision.
        """
        pending = []
        # Group by base experiment_id
        by_experiment = {}
        for key, run in self._runs.items():
            if ":promotion:" in key:
                base_id = key.split(":promotion:")[0]
                if base_id not in by_experiment:
                    by_experiment[base_id] = []
                by_experiment[base_id].append(run)

        for exp_id, decisions in by_experiment.items():
            resolved_stages = {d.get("stage") for d in decisions}
            if resolved_stages & {"final", "reject"}:
                continue
            latest = max(decisions, key=lambda d: d.get("timestamp", ""))
            if latest.get("stage") == "human_approval":
                pending.append(latest)
        return pending
