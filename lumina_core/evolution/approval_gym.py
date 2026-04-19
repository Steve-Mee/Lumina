from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Iterable

from .dna_registry import PolicyDNA
from .steve_values_registry import SteveValueRecord, SteveValuesRegistry


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True, slots=True)
class ApprovalProposal:
    dna_hash: str
    summary: str
    estimated_confidence: float


class ApprovalGym:
    """Generate compact approval drills and store Steve's responses."""

    def __init__(self, *, registry: SteveValuesRegistry, rng_seed: int | None = None) -> None:
        self._registry = registry
        self._rng = random.Random(rng_seed)

    def generate_proposals(
        self,
        *,
        historical_dna: Iterable[PolicyDNA] | None = None,
        count: int | None = None,
    ) -> list[ApprovalProposal]:
        target = max(3, min(5, int(count if count is not None else self._rng.randint(3, 5))))
        historical = list(historical_dna or [])
        proposals: list[ApprovalProposal] = []

        if historical:
            self._rng.shuffle(historical)
            for dna in historical[:target]:
                proposals.append(
                    ApprovalProposal(
                        dna_hash=str(dna.hash),
                        summary=self._build_summary_from_dna(dna),
                        estimated_confidence=self._estimate_confidence_from_dna(dna),
                    )
                )

        while len(proposals) < target:
            synthetic_hash = f"sim_{self._rng.getrandbits(64):016x}"
            proposals.append(
                ApprovalProposal(
                    dna_hash=synthetic_hash,
                    summary=(
                        "Gesimuleerd voorstel met verhoogde risico-exposure en onzeker regime. "
                        "Zou je deze DNA naar REAL promoveren?"
                    ),
                    estimated_confidence=round(self._rng.uniform(0.45, 0.85), 4),
                )
            )

        return proposals

    def run_session(
        self,
        *,
        historical_dna: Iterable[PolicyDNA] | None = None,
        ask_fn: Callable[[str], str] | None = None,
        count: int | None = None,
        approval_twin: Any | None = None,
    ) -> list[SteveValueRecord]:
        proposals = self.generate_proposals(historical_dna=historical_dna, count=count)
        asker = ask_fn or self._console_ask
        records: list[SteveValueRecord] = []

        for proposal in proposals:
            vraag = self._build_question(proposal)
            antwoord = str(asker(vraag)).strip()
            confidence_score = self._extract_confidence(antwoord, fallback=proposal.estimated_confidence)
            record = SteveValueRecord.create(
                vraag=vraag,
                steve_antwoord=antwoord,
                timestamp=_utcnow(),
                context_dna_hash=proposal.dna_hash,
                confidence_score=confidence_score,
            )
            self._registry.append(record)
            records.append(record)

        if approval_twin is not None and hasattr(approval_twin, "rlhf_light_update"):
            approval_twin.rlhf_light_update(records=records)

        return records

    @staticmethod
    def _build_summary_from_dna(dna: PolicyDNA) -> str:
        return (
            f"Historische kandidaat {dna.hash[:8]} met fitness {float(dna.fitness_score):.4f} "
            f"(generation {int(dna.generation)})."
        )

    @staticmethod
    def _estimate_confidence_from_dna(dna: PolicyDNA) -> float:
        score = float(dna.fitness_score)
        normalized = 0.5 + max(-0.4, min(0.4, score / 10.0))
        return max(0.0, min(1.0, normalized))

    @staticmethod
    def _build_question(proposal: ApprovalProposal) -> str:
        return (
            "DNA-promotie review:\n"
            f"- Hash: {proposal.dna_hash}\n"
            f"- Context: {proposal.summary}\n"
            f"- Twin confidence indicatie: {proposal.estimated_confidence:.0%}\n"
            "Vraag: Keur je REAL-promotie goed? Antwoord met APPROVE of VETO"
        )

    @staticmethod
    def _extract_confidence(answer: str, *, fallback: float) -> float:
        lowered = answer.lower()
        if "approve" in lowered:
            return max(0.65, min(1.0, float(fallback)))
        if "veto" in lowered:
            return min(0.35, max(0.0, float(fallback)))
        return max(0.0, min(1.0, float(fallback)))

    @staticmethod
    def _console_ask(prompt: str) -> str:
        return input(f"{prompt}\n> ")
