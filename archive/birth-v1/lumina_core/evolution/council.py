"""Critical Change Council — independent evidence fields (K14)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True, slots=True)
class CouncilVote:
    agent_id: str
    approve: bool
    veto: bool
    score: float
    evidence_field: str
    note: str
    unknown: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class CouncilDossier:
    question: str
    votes: list[CouncilVote] = field(default_factory=list)
    risk_veto: bool = False
    timeout_sec: int = 3600
    created_at: str = ""
    steve_ack: str = ""
    override_risk_veto: bool = False
    override_reason: str = ""
    dual_confirm: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "question": self.question,
            "votes": [v.to_dict() for v in self.votes],
            "risk_veto": self.risk_veto,
            "timeout_sec": self.timeout_sec,
            "created_at": self.created_at,
            "steve_ack": self.steve_ack,
            "override_risk_veto": self.override_risk_veto,
            "override_reason": self.override_reason,
            "dual_confirm": self.dual_confirm,
        }


def compose_dossier(
    *,
    question: str,
    twin_values_ok: bool,
    constitution_violations: int,
    risk_dd: float,
    swarm_fitness_delta: float,
    evolution_proof_passed: bool,
    timeout_sec: int = 3600,
) -> CouncilDossier:
    votes = [
        CouncilVote(
            "twin",
            approve=bool(twin_values_ok),
            veto=False,
            score=1.0 if twin_values_ok else 0.0,
            evidence_field="steve_values",
            note="Twin Steve-values alignment",
            unknown="Does not see DD path",
        ),
        CouncilVote(
            "constitution",
            approve=int(constitution_violations) == 0,
            veto=int(constitution_violations) > 0,
            score=1.0 if int(constitution_violations) == 0 else 0.0,
            evidence_field="violations",
            note="ConstitutionalGuard open violations",
            unknown="Does not see fitness",
        ),
        CouncilVote(
            "risk_guardian",
            approve=float(risk_dd) < 0.05,
            veto=float(risk_dd) >= 0.05,
            score=max(0.0, 1.0 - float(risk_dd) * 10.0),
            evidence_field="drawdown",
            note="Risk DD distribution",
            unknown="Does not see Steve labels",
        ),
        CouncilVote(
            "meta_swarm",
            approve=float(swarm_fitness_delta) > 0.0,
            veto=False,
            score=max(0.0, min(1.0, 0.5 + float(swarm_fitness_delta))),
            evidence_field="fitness_delta",
            note="Swarm fitness delta",
            unknown="Does not see constitution stream",
        ),
        CouncilVote(
            "evolution_proof",
            approve=bool(evolution_proof_passed),
            veto=not bool(evolution_proof_passed),
            score=1.0 if evolution_proof_passed else 0.0,
            evidence_field="evolution_proof",
            note="ADR-0026 proof record",
            unknown="Does not see live tape",
        ),
    ]
    risk_veto = any(v.veto and v.agent_id == "risk_guardian" for v in votes)
    return CouncilDossier(
        question=question,
        votes=votes,
        risk_veto=risk_veto,
        timeout_sec=int(timeout_sec),
        created_at=datetime.now(timezone.utc).isoformat(),
    )


def resolve_steve_decision(
    dossier: CouncilDossier,
    *,
    ack: str,
    override_risk_veto: bool = False,
    override_reason: str = "",
    dual_confirm: bool = False,
    timed_out: bool = False,
) -> dict[str, Any]:
    """Timeout = no. Risk veto requires explicit override + dual confirm (K14)."""
    if timed_out or str(ack or "").strip().lower() in {"", "timeout", "no", "nee"}:
        return {"allowed": False, "reason": "timeout_or_nack"}
    yes = str(ack).strip().lower() in {"yes", "ja", "approve", "approved"}
    if not yes:
        return {"allowed": False, "reason": "steve_nack"}
    if dossier.risk_veto:
        if not (override_risk_veto and dual_confirm and str(override_reason).strip()):
            return {"allowed": False, "reason": "risk_veto_requires_override"}
    return {"allowed": True, "reason": "steve_approved"}
