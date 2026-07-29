"""Approval Gym session helpers for TwinTrainingService (Wave B2 PR-C1)."""

from __future__ import annotations

import uuid
from dataclasses import asdict
from typing import Any

from lumina_core.evolution.approval_gym import ApprovalGym, ApprovalProposal
from lumina_core.evolution.dna_registry import PolicyDNA
from lumina_core.evolution.steve_values_registry import SteveValueRecord
from lumina_core.evolution.twin_training_metrics import (
    DecisionKind,
    decision_to_answer,
    default_confidence,
)


class TwinGymSessionMixin:
    """Practice-drill gym session API (stateless; does not promote DNA)."""

    def start_gym_session(
        self,
        *,
        count: int = 4,
        prefer_historical: bool = True,
        historical_dna: list[PolicyDNA] | None = None,
        rng_seed: int | None = None,
    ) -> dict[str, Any]:
        """Generate 3–5 practice drills (stateless). Does not promote DNA."""
        target = max(3, min(5, int(count)))
        gym = ApprovalGym(registry=self.registry, rng_seed=rng_seed)  # type: ignore[attr-defined]
        hist: list[PolicyDNA] = []
        if prefer_historical:
            hist = list(historical_dna) if historical_dna is not None else self._load_historical_dna(limit=12)
        proposals = gym.generate_proposals(historical_dna=hist or None, count=target)
        items = [self._serialize_gym_proposal(p) for p in proposals]
        synthetic_n = sum(1 for i in items if i.get("source") == "synthetic")
        return {
            "session_id": str(uuid.uuid4()),
            "proposals": items,
            "count": len(items),
            "historical_count": len(items) - synthetic_n,
            "synthetic_count": synthetic_n,
            "practice_only": True,
            "promotes_dna": False,
            "local_only": True,
        }

    def record_gym_answer(
        self,
        *,
        decision: DecisionKind,
        dna_hash: str,
        summary: str = "",
        estimated_confidence: float | None = None,
        notes: str = "",
        session_id: str | None = None,
        train_now: bool = True,
    ) -> dict[str, Any]:
        """Record Steve's gym answer via the same local registry path as live review."""
        dna = str(dna_hash or "").strip()
        if not dna:
            raise ValueError("dna_hash is required")
        if decision not in ("approve", "reject", "modify"):
            raise ValueError(f"invalid decision: {decision}")

        conf_hint = (
            max(0.0, min(1.0, float(estimated_confidence)))
            if estimated_confidence is not None
            else None
        )
        proposal = ApprovalProposal(
            dna_hash=dna,
            summary=str(summary or "Approval Gym drill").strip() or "Approval Gym drill",
            estimated_confidence=float(conf_hint if conf_hint is not None else 0.6),
        )
        vraag = ApprovalGym._build_question(proposal)
        note = str(notes or "").strip()
        if note:
            vraag = f"{vraag}\nsteve_note={note}"
        if session_id:
            vraag = f"{vraag}\ngym_session={session_id}"

        answer = decision_to_answer(decision, notes)
        conf = (
            default_confidence(decision)
            if conf_hint is None
            else (
                max(0.65, min(1.0, conf_hint))
                if decision == "approve"
                else min(0.35, max(0.0, conf_hint))
                if decision == "reject"
                else 0.45
            )
        )
        if decision == "modify":
            conf = 0.45

        record = SteveValueRecord.create(
            vraag=vraag,
            steve_antwoord=answer,
            context_dna_hash=dna,
            confidence_score=conf,
        )
        self.registry.append(record)  # type: ignore[attr-defined]

        result: dict[str, Any] = {
            "recorded": True,
            "decision": decision,
            "label": answer,
            "record": asdict(record),
            "source": "synthetic" if dna.startswith("sim_") else "historical",
            "practice_only": True,
            "promotes_dna": False,
            "local_only": True,
            "session_id": session_id,
            "audit": {
                "registry_sqlite": str(self.registry.sqlite_path),  # type: ignore[attr-defined]
                "registry_jsonl": str(self.registry.jsonl_path),  # type: ignore[attr-defined]
                "model_path": str(self.model_path),  # type: ignore[attr-defined]
            },
            "rlhf": None,
            "metrics": None,
        }
        if train_now:
            result["rlhf"] = self.twin.rlhf_light_update(records=[record])  # type: ignore[attr-defined]
            result["metrics"] = self.metrics()  # type: ignore[attr-defined]
        return result

    def complete_gym_session(
        self,
        *,
        answers: list[dict[str, Any]],
        train_now: bool = True,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        """Batch-record gym answers; optional single RLHF pass over the batch."""
        if not answers:
            raise ValueError("answers list is empty")
        recorded: list[dict[str, Any]] = []
        records_for_rlhf: list[SteveValueRecord] = []
        for raw in answers:
            decision = str(raw.get("decision", "")).strip().lower()
            if decision not in ("approve", "reject", "modify"):
                raise ValueError(f"invalid decision in answers: {decision}")
            # Defer train; batch once at end
            out = self.record_gym_answer(
                decision=decision,  # type: ignore[arg-type]
                dna_hash=str(raw.get("dna_hash", "")),
                summary=str(raw.get("summary", "")),
                estimated_confidence=(
                    float(raw["estimated_confidence"])
                    if raw.get("estimated_confidence") is not None
                    else None
                ),
                notes=str(raw.get("notes", "") or ""),
                session_id=session_id or (str(raw.get("session_id")) if raw.get("session_id") else None),
                train_now=False,
            )
            recorded.append(out)
            rec = out.get("record")
            if isinstance(rec, dict):
                records_for_rlhf.append(
                    SteveValueRecord(
                        vraag=str(rec["vraag"]),
                        steve_antwoord=str(rec["steve_antwoord"]),
                        timestamp=str(rec["timestamp"]),
                        context_dna_hash=str(rec["context_dna_hash"]),
                        confidence_score=float(rec["confidence_score"]),
                    )
                )

        rlhf: dict[str, Any] | None = None
        if train_now and records_for_rlhf:
            rlhf = self.twin.rlhf_light_update(records=records_for_rlhf)  # type: ignore[attr-defined]

        return {
            "recorded_count": len(recorded),
            "answers": recorded,
            "rlhf": rlhf,
            "metrics": self.metrics(),  # type: ignore[attr-defined]
            "practice_only": True,
            "promotes_dna": False,
            "local_only": True,
        }

    @staticmethod
    def _serialize_gym_proposal(proposal: ApprovalProposal) -> dict[str, Any]:
        dna = str(proposal.dna_hash)
        source = "synthetic" if dna.startswith("sim_") else "historical"
        return {
            "dna_hash": dna,
            "summary": str(proposal.summary),
            "estimated_confidence": float(proposal.estimated_confidence),
            "source": source,
        }

    @staticmethod
    def _load_historical_dna(*, limit: int = 12) -> list[PolicyDNA]:
        """Best-effort load of recent DNA for gym realism; empty → pure synthetic."""
        try:
            from lumina_core.evolution.dna_registry import DNARegistry

            reg = DNARegistry()
            if hasattr(reg, "list_all_dna"):
                return list(reg.list_all_dna(limit=max(1, int(limit))))
            if hasattr(reg, "get_ranked_dna"):
                return list(reg.get_ranked_dna(limit=max(1, int(limit))))
        except Exception:
            return []
        return []
