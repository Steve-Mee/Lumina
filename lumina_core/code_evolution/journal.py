"""Reversible journal for code-evolution proposals.

Writes pending bundles under state/code_evolution/pending/<id>/ and an
append-only journal.jsonl. H5 may apply to sandbox store only (never live tree).
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
                "H5: apply targets sandbox store under state/code_evolution/applied/ only. "
                "Never mutates live repo. Revert via CodeEvolutionApplyGate.revert_applied "
                "or restore restore_snapshot into applied/params.json."
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

    def try_apply_live(
        self,
        proposal_id: str,
        *,
        evidence: dict[str, Any] | None = None,
        policy: Any | None = None,
    ) -> dict[str, Any]:
        """Controlled apply to sandbox store only (H5). Never live repo tree.

        Default policy keeps apply disabled (evaluate-only). When enabled, requires
        CodeEvolutionApplyGate evidence (constitution, sandbox, human/twin, non-REAL).
        """
        # Lazy import to avoid cycles
        from lumina_core.code_evolution.apply_gate import (
            ApplyEvidence,
            ApplyPolicy,
            CodeEvolutionApplyGate,
        )
        from lumina_core.code_evolution.proposal import (
            CodeMutationOperator,
            CodeMutationProposal,
        )

        prop_path = self.pending_root / proposal_id / "proposal.json"
        if not prop_path.exists():
            return {
                "applied": False,
                "reason": "proposal_bundle_missing",
                "proposal_id": proposal_id,
            }

        try:
            raw = json.loads(prop_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return {
                "applied": False,
                "reason": f"proposal_unreadable:{exc}",
                "proposal_id": proposal_id,
            }

        try:
            op = CodeMutationOperator(str(raw.get("operator") or ""))
        except ValueError:
            return {
                "applied": False,
                "reason": "unknown_operator",
                "proposal_id": proposal_id,
            }

        proposal = CodeMutationProposal(
            proposal_id=str(raw.get("proposal_id") or proposal_id),
            operator=op,
            target=str(raw.get("target") or ""),
            description=str(raw.get("description") or ""),
            payload=dict(raw.get("payload") or {}),
            rationale=str(raw.get("rationale") or ""),
            estimated_loc=int(raw.get("estimated_loc") or 0),
            before_snapshot=dict(raw.get("before_snapshot") or {}),
            after_snapshot=dict(raw.get("after_snapshot") or {}),
            constitution_passed=bool(raw.get("constitution_passed")),
            twin_recommendation=bool(raw.get("twin_recommendation")),
            twin_effective=bool(raw.get("twin_effective")),
            sandbox_passed=bool(raw.get("sandbox_passed")),
        )

        ev = dict(evidence or {})
        # Prefer explicit evidence over proposal flags
        human_ok = bool(ev.get("human_approved"))
        human_approver = str(ev.get("human_approver") or "")
        pol = policy if isinstance(policy, ApplyPolicy) else ApplyPolicy.from_config(
            policy if isinstance(policy, dict) else None
        )
        gate = CodeEvolutionApplyGate(journal_root=self.root, policy=pol)
        if not human_ok:
            human_ok, human_approver = gate.is_human_approved(proposal_id)

        apply_ev = ApplyEvidence(
            proposal=proposal,
            capital_mode=str(ev.get("capital_mode") or "sim"),
            constitution_passed=bool(ev.get("constitution_passed", proposal.constitution_passed)),
            sandbox_passed=bool(ev.get("sandbox_passed", proposal.sandbox_passed)),
            twin_recommendation=bool(ev.get("twin_recommendation", proposal.twin_recommendation)),
            twin_effective=bool(ev.get("twin_effective", proposal.twin_effective)),
            human_approved=human_ok,
            human_approver=human_approver,
        )
        return gate.try_apply(apply_ev)
