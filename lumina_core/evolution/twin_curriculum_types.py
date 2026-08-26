"""Typed contracts for Twin base/micro curriculum and escalations (ADR-0037).

Forced-choice labels only; optional free-text clarify ≤280 chars.
All ground truth stays local via SteveValuesRegistry.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

ValueAxis = Literal[
    "capital_preservation",
    "mutation_aggression",
    "regime_sensitivity",
    "drawdown_recovery",
    "approve_veto_modify",
    "edge_case",
]

ValueSignal = Literal[
    "conservative",
    "balanced",
    "aggressive",
    "need_more_data",
    "approve",
    "veto",
    "modify",
]

ChannelPolicy = Literal["app_only", "dual"]
PendingKind = Literal["base", "micro", "escalation"]
PendingStatus = Literal["pending", "resolved", "expired"]
ResolvedBy = Literal["deck", "telegram", "api", "cli"]

# base_v4 = teach-while-train + ± consequences + REAL-conscience frame (ADR-0038)
# One Twin DNA: labels always train capital-critical judgment; free SIM is authority, not training target.
CURRICULUM_VERSION = "base_v4"
HIGH_CONF_THRESHOLD = 0.80
MAX_CLARIFY_CHARS = 280
DEFAULT_ESCALATION_TTL_SEC = 3600


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True, slots=True)
class TwinChoice:
    id: str  # A/B/C/D
    label: str
    value_signal: ValueSignal

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class TwinMcQuestion:
    """Shared multiple-choice payload (app + Telegram)."""

    question_id: str
    axis: ValueAxis
    scenario: str
    choices: tuple[TwinChoice, ...]
    context_dna_hash: str
    channel_policy: ChannelPolicy = "app_only"
    allow_clarify: bool = True
    max_clarify_chars: int = MAX_CLARIFY_CHARS
    estimated_seconds: int = 12
    metrics_hint: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "question_id": self.question_id,
            "axis": self.axis,
            "scenario": self.scenario,
            "choices": [c.to_dict() for c in self.choices],
            "context_dna_hash": self.context_dna_hash,
            "channel_policy": self.channel_policy,
            "allow_clarify": self.allow_clarify,
            "max_clarify_chars": self.max_clarify_chars,
            "estimated_seconds": int(self.estimated_seconds),
            "metrics_hint": self.metrics_hint,
        }

    def choice_by_id(self, choice_id: str) -> TwinChoice | None:
        cid = str(choice_id or "").strip().upper()
        for c in self.choices:
            if c.id.upper() == cid:
                return c
        return None


@dataclass(slots=True)
class TwinMcAnswer:
    question_id: str
    choice_id: str
    clarify: str = ""
    channel: ResolvedBy = "deck"
    answered_at: str = field(default_factory=_utcnow)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# value_signal → RLHF label (ApprovalTwinAgent._label_from_answer tokens)
_SIGNAL_TO_LABEL: dict[str, str] = {
    "conservative": "VETO",
    "veto": "VETO",
    "aggressive": "APPROVE",
    "approve": "APPROVE",
    "opportunity": "APPROVE",
    "balanced": "MODIFY",
    "modify": "MODIFY",
    "need_more_data": "MODIFY",
}

_SIGNAL_TO_CONF: dict[str, float] = {
    "conservative": 0.25,
    "veto": 0.20,
    "aggressive": 0.85,
    "approve": 0.90,
    "opportunity": 0.80,
    "balanced": 0.45,
    "modify": 0.45,
    "need_more_data": 0.40,
}


def signal_to_rlhf_label(signal: str, *, clarify: str = "") -> str:
    """Map value_signal to APPROVE/VETO/MODIFY for light RLHF."""
    key = str(signal or "").strip().lower()
    base = _SIGNAL_TO_LABEL.get(key, "MODIFY")
    note = str(clarify or "").strip()[:MAX_CLARIFY_CHARS]
    if note:
        return f"{base}: {note}"
    return base


def signal_to_confidence(signal: str) -> float:
    key = str(signal or "").strip().lower()
    return float(_SIGNAL_TO_CONF.get(key, 0.45))


def build_mc_vraag(question: TwinMcQuestion, *, choice_id: str | None = None) -> str:
    """Structured audit string for SteveValuesRegistry.vraag."""
    lines = [
        f"twin_mc qid={question.question_id} axis={question.axis}",
        f"scenario={question.scenario}",
    ]
    if question.metrics_hint:
        lines.append(f"metrics={question.metrics_hint}")
    for c in question.choices:
        lines.append(f"choice_{c.id}={c.label} signal={c.value_signal}")
    if choice_id:
        lines.append(f"selected={str(choice_id).upper()}")
    # Seed keywords the light model already extracts (risk/kapitaal/approve/veto).
    axis = question.axis
    if axis == "capital_preservation":
        lines.append("keywords=kapitaal risk capital_preservation")
    elif axis == "drawdown_recovery":
        lines.append("keywords=drawdown risk recovery")
    elif axis == "mutation_aggression":
        lines.append("keywords=mutation radical risk fitness")
    elif axis == "approve_veto_modify":
        lines.append("keywords=approve veto modify guard")
    elif axis == "regime_sensitivity":
        lines.append("keywords=regime risk vol news")
    else:
        lines.append("keywords=edge risk liquidity overnight")
    return "\n".join(lines)


def mc_answer_to_steve_fields(
    question: TwinMcQuestion,
    *,
    choice_id: str,
    clarify: str = "",
) -> tuple[str, str, float]:
    """Return (vraag, steve_antwoord, confidence_score)."""
    choice = question.choice_by_id(choice_id)
    if choice is None:
        raise ValueError(f"invalid choice_id: {choice_id}")
    clar = str(clarify or "").strip()[: question.max_clarify_chars]
    vraag = build_mc_vraag(question, choice_id=choice.id)
    if clar:
        vraag = f"{vraag}\nsteve_note={clar}"
    label = signal_to_rlhf_label(choice.value_signal, clarify=clar)
    # Encode choice id for audit without breaking RLHF primary token.
    if ":" in label:
        head, rest = label.split(":", 1)
        antwoord = f"{head}: choice={choice.id} signal={choice.value_signal}{rest}"
    else:
        antwoord = f"{label}: choice={choice.id} signal={choice.value_signal}"
    conf = signal_to_confidence(choice.value_signal)
    return vraag, antwoord, conf
