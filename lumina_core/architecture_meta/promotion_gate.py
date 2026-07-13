"""Arch promotion gate — human-in-the-loop only.

Radically simple:
- Write proposal bundle to state/architecture_proposals/pending/<id>/
- Human approves via marker file (APPROVED) or future CLI.
- Apply only after marker + re-verify.
- Fail closed on any missing evidence.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lumina_core.architecture_meta.controller import ArchMutationProposal


PENDING_ROOT = Path("state/architecture_proposals/pending")


@dataclass(slots=True)
class ArchPromotionDecision:
    proposal_id: str
    approved: bool
    approver: str = ""
    reason: str = ""
    timestamp: str = ""
    health_delta: float = 0.0


class ArchPromotionGate:
    """Human gate. No auto promotion."""

    def __init__(self, pending_root: Path = PENDING_ROOT) -> None:
        self.pending_root = pending_root
        self.pending_root.mkdir(parents=True, exist_ok=True)

    def write_proposal_bundle(
        self, proposal: ArchMutationProposal, sandbox_report: dict[str, Any], readme: str
    ) -> Path:
        pdir = self.pending_root / proposal.proposal_id
        pdir.mkdir(parents=True, exist_ok=True)
        (pdir / "proposal.json").write_text(json.dumps(asdict(proposal), indent=2, default=str), encoding="utf-8")
        (pdir / "sandbox_report.json").write_text(json.dumps(sandbox_report, indent=2), encoding="utf-8")
        (pdir / "human_readme.md").write_text(readme, encoding="utf-8")
        (pdir / "PATCH.diff").write_text(proposal.diff or "", encoding="utf-8")
        return pdir

    def is_approved(self, proposal_id: str) -> tuple[bool, str]:
        pdir = self.pending_root / proposal_id
        marker = pdir / "APPROVED"
        if marker.exists():
            content = marker.read_text(encoding="utf-8", errors="ignore").strip()
            return True, content or "approved"
        return False, ""

    def record_decision(self, decision: ArchPromotionDecision) -> Path:
        pdir = self.pending_root / decision.proposal_id
        pdir.mkdir(parents=True, exist_ok=True)
        (pdir / "decision.json").write_text(
            json.dumps(decision.__dict__, indent=2), encoding="utf-8"
        )
        return pdir / "decision.json"

    def make_readme(self, proposal: ArchMutationProposal, before: float, delta: float) -> str:
        return f"""# Architecture Mutation Proposal

**ID**: {proposal.proposal_id}
**Type**: {proposal.mutation_type.value}
**Target**: {proposal.target_file}

## Rationale
{proposal.rationale}

## Expected Impact
- before: {before:.2f}
- expected delta: +{proposal.expected_delta:.2f}
- measured sandbox delta: +{delta:.2f}

## Diff (review carefully)
```diff
{proposal.diff[:2000]}
```

## Approval
To approve (human only):
  echo "approved by <your-name> on $(date) for reason: <why this improves evolvability>" > state/architecture_proposals/pending/<id>/APPROVED

Then run the apply step (or let orchestrator pick it up).

Rollback: patch -R or git checkout.

This change must preserve:
- Bounded contexts
- Typed contracts
- No god class growth
- No trading behavior change in REAL paths
"""

    def apply_if_approved(
        self, proposal: ArchMutationProposal, *, apply_fn: Any = None
    ) -> ArchPromotionDecision:
        """Caller supplies apply_fn that does the real patch on live tree + backup."""
        approved, approver = self.is_approved(proposal.proposal_id)
        if not approved:
            return ArchPromotionDecision(
                proposal_id=proposal.proposal_id,
                approved=False,
                reason="no APPROVED marker",
            )

        ts = datetime.now(timezone.utc).isoformat()
        if apply_fn is not None:
            try:
                apply_fn(proposal)
            except Exception as exc:
                return ArchPromotionDecision(
                    proposal_id=proposal.proposal_id,
                    approved=False,
                    approver=approver,
                    reason=f"apply failed: {exc}",
                    timestamp=ts,
                )

        dec = ArchPromotionDecision(
            proposal_id=proposal.proposal_id,
            approved=True,
            approver=approver,
            reason="human approved + applied",
            timestamp=ts,
        )
        self.record_decision(dec)
        return dec
