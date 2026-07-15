"""Reversible journal for code-evolution proposals (evaluate-only v1).

Writes pending bundles under state/code_evolution/pending/<id>/ and an
append-only journal.jsonl. Never applies patches to the live tree.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lumina_core.code_evolution.proposal import CodeMutationProposal, CodeSandboxEvalResult

logger = logging.getLogger(__name__)

DEFAULT_ROOT = Path("state/code_evolution")


class CodeEvolutionJournal:
    """Persist proposal bundles + lifecycle events for audit/rollback."""

    def __init__(self, root: Path | str | None = None) -> None:
        self.root = Path(root) if root is not None else DEFAULT_ROOT
        self.pending_root = self.root / "pending"
        self.journal_path = self.root / "journal.jsonl"
        self.pending_root.mkdir(parents=True, exist_ok=True)
        self.root.mkdir(parents=True, exist_ok=True)

    def write_bundle(
        self,
        proposal: CodeMutationProposal,
        *,
        constitution_result: dict[str, Any],
        twin_result: dict[str, Any] | None = None,
        sandbox_result: CodeSandboxEvalResult | dict[str, Any] | None = None,
        final_decision: dict[str, Any] | None = None,
    ) -> Path:
        pdir = self.pending_root / proposal.proposal_id
        pdir.mkdir(parents=True, exist_ok=True)

        (pdir / "proposal.json").write_text(
            json.dumps(proposal.to_dict(), indent=2, default=str),
            encoding="utf-8",
        )
        (pdir / "before_snapshot.json").write_text(
            json.dumps(proposal.before_snapshot, indent=2, default=str),
            encoding="utf-8",
        )
        (pdir / "after_snapshot.json").write_text(
            json.dumps(proposal.after_snapshot, indent=2, default=str),
            encoding="utf-8",
        )
        (pdir / "constitution.json").write_text(
            json.dumps(constitution_result, indent=2, default=str),
            encoding="utf-8",
        )
        if twin_result is not None:
            (pdir / "twin_decision.json").write_text(
                json.dumps(twin_result, indent=2, default=str),
                encoding="utf-8",
            )
        if sandbox_result is not None:
            sb = (
                sandbox_result.to_dict()
                if isinstance(sandbox_result, CodeSandboxEvalResult)
                else dict(sandbox_result)
            )
            (pdir / "sandbox_report.json").write_text(
                json.dumps(sb, indent=2, default=str),
                encoding="utf-8",
            )
        if final_decision is not None:
            (pdir / "decision.json").write_text(
                json.dumps(final_decision, indent=2, default=str),
                encoding="utf-8",
            )

        revert = {
            "proposal_id": proposal.proposal_id,
            "operator": proposal.operator.value
            if hasattr(proposal.operator, "value")
            else str(proposal.operator),
            "restore_snapshot": proposal.before_snapshot,
            "instructions": (
                "v1 evaluate-only: no live apply occurred. "
                "To reverse a future apply, restore restore_snapshot values "
                "and delete pending bundle after audit."
            ),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        (pdir / "REVERT.json").write_text(json.dumps(revert, indent=2), encoding="utf-8")
        return pdir

    def append_event(self, event: dict[str, Any]) -> None:
        record = dict(event)
        record.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
        line = json.dumps(record, default=str, ensure_ascii=True)
        with self.journal_path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")

    def load_before_snapshot(self, proposal_id: str) -> dict[str, Any]:
        path = self.pending_root / proposal_id / "before_snapshot.json"
        if not path.exists():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))

    def load_revert(self, proposal_id: str) -> dict[str, Any]:
        path = self.pending_root / proposal_id / "REVERT.json"
        if not path.exists():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))

    def restore_from_revert(self, proposal_id: str) -> dict[str, Any]:
        """Reconstruct pre-proposal state from REVERT artifact (in-memory only)."""
        revert = self.load_revert(proposal_id)
        snap = revert.get("restore_snapshot") or self.load_before_snapshot(proposal_id)
        return dict(snap) if isinstance(snap, dict) else {}

    def try_apply_live(self, proposal_id: str) -> dict[str, Any]:
        """v1 stub: always reject live apply (fail-closed)."""
        return {
            "applied": False,
            "reason": "v1_evaluate_only",
            "proposal_id": proposal_id,
        }
