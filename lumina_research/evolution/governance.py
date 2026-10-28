"""ADR + signed human review for Risk Core / threshold changes. Evolution never applies them."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
from collections.abc import Callable
from pathlib import Path
from typing import Literal, Mapping

from lumina_core.agent_orchestration.event_bus import EventBus
from lumina_core.agent_orchestration.schemas_research import (
    BIRTH_AGENT_ID,
    CAPACITY_AGENT_ID,
    GOVERNANCE_AGENT_ID,
    GOVERNANCE_SCHEMA_VERSION,
    GUARDIAN_AGENT_ID,
    HYPOTHESIS_AGENT_ID,
    MONITOR_AGENT_ID,
    PROMOTION_AGENT_ID,
    REFLECTOR_AGENT_ID,
    REPLENISH_AGENT_ID,
    RESEARCH_GOVERNANCE_TOPIC,
    VALIDATION_AGENT_ID,
    GovernanceDecision,
    MutationKind,
    MutationProposed,
    SignedReview,
)
from lumina_core.engine.agent_blackboard import AgentBlackboard
from lumina_research.agents.experiment_log import log_experiment
from lumina_research.agents.frozen import Frozen
from lumina_research.agents.objects import as_object_dict
from lumina_research.agents.payloads import dump_json
from lumina_research.agents.provenance import ProvenanceAuthority
from lumina_research.evolution.integrity import refuse_protected_write
from lumina_research.evolution.seal import (
    canonical_governance,
    canonical_mutation,
    mutation_fingerprint,
    review_binding,
)
from lumina_research.evolution.types import (
    ALLOWED_KINDS,
    FORBIDDEN_KINDS,
    GENOME_TARGET,
    PROTECTED_KINDS,
)
from lumina_research.validation.trial_registry import TrialRegistry

_HEX = 64
_ADR_NAME = re.compile(r"^\d{4}-[a-z0-9-]+\.md$")
_HEADINGS = ("## Context", "## Decision", "## Consequences")
_AGENT_IDS = frozenset(
    {
        HYPOTHESIS_AGENT_ID,
        VALIDATION_AGENT_ID,
        PROMOTION_AGENT_ID,
        REFLECTOR_AGENT_ID,
        BIRTH_AGENT_ID,
        GOVERNANCE_AGENT_ID,
        MONITOR_AGENT_ID,
        CAPACITY_AGENT_ID,
        GUARDIAN_AGENT_ID,
        REPLENISH_AGENT_ID,
    }
)
_Signer = Callable[[bytes], str]
_Verifier = Callable[[bytes, str], bool]


class GovernanceError(ValueError):
    """Protected change refused, or review/ADR missing."""


class ReviewError(ValueError):
    """Human review signature failed."""


class ReviewAuthority(Frozen):
    """Separate HMAC key from research provenance so agents cannot sign as humans."""

    _sign: _Signer
    _verify: _Verifier

    def __init_subclass__(cls) -> None:
        raise TypeError("ReviewAuthority cannot be subclassed")

    def __init__(self, key: bytes | None = None) -> None:
        material = key if key is not None else os.urandom(32)
        if len(material) < 16:
            raise ReviewError("review key is too short")

        def sign(message: bytes) -> str:
            return hmac.new(material, message, hashlib.sha256).hexdigest()

        def verify(message: bytes, mac: str) -> bool:
            if len(mac) != _HEX:
                return False
            expected = hmac.new(material, message, hashlib.sha256).hexdigest()
            return hmac.compare_digest(expected, mac)

        self._sign = sign
        self._verify = verify
        self._freeze()

    def sign_review(
        self,
        *,
        reviewer_id: str,
        adr_bytes: bytes,
        verdict: str,
        config_id: str,
        kind: str,
        target: str,
    ) -> SignedReview:
        if not is_human_reviewer(reviewer_id):
            raise ReviewError("reviewer must be human")
        if verdict not in {"approve", "reject"}:
            raise ReviewError("verdict must be approve or reject")
        adr_sha = hashlib.sha256(adr_bytes).hexdigest()
        mutation_sha = hashlib.sha256(review_binding(config_id=config_id, kind=kind, target=target)).hexdigest()
        payload = {
            "reviewer_id": reviewer_id.strip(),
            "adr_sha256": adr_sha,
            "mutation_sha256": mutation_sha,
            "verdict": verdict,
        }
        signature = self._sign(_canonical_review(payload))
        return SignedReview(
            reviewer_id=str(payload["reviewer_id"]),
            adr_sha256=adr_sha,
            mutation_sha256=mutation_sha,
            verdict="approve" if verdict == "approve" else "reject",
            signature=signature,
        )

    def verify_review(
        self,
        review: SignedReview,
        *,
        adr_bytes: bytes,
        config_id: str,
        kind: str,
        target: str,
    ) -> bool:
        if not is_human_reviewer(review.reviewer_id):
            return False
        adr_sha = hashlib.sha256(adr_bytes).hexdigest()
        if review.adr_sha256 != adr_sha:
            return False
        mutation_sha = hashlib.sha256(review_binding(config_id=config_id, kind=kind, target=target)).hexdigest()
        if review.mutation_sha256 != mutation_sha:
            return False
        payload = {
            "reviewer_id": review.reviewer_id.strip(),
            "adr_sha256": review.adr_sha256,
            "mutation_sha256": review.mutation_sha256,
            "verdict": review.verdict,
        }
        return self._verify(_canonical_review(payload), review.signature)


class GovernanceGate(Frozen):
    """Admit parameter/window mutations. Protected changes need ADR + human HMAC review and are not applied."""

    _bus: EventBus
    _authority: ProvenanceAuthority
    _reviews: ReviewAuthority
    _registry: TrialRegistry
    _log_path: Path
    _adr_root: Path
    _blackboard: AgentBlackboard | None
    _consume_trial: Callable[[int], bool]
    _consume_review: Callable[[str, str], bool]
    _decisions: list[GovernanceDecision]

    def __init_subclass__(cls) -> None:
        raise TypeError("GovernanceGate cannot be subclassed")

    def __init__(
        self,
        *,
        bus: EventBus,
        authority: ProvenanceAuthority,
        reviews: ReviewAuthority,
        registry: TrialRegistry,
        experiment_log_path: Path,
        adr_root: Path,
        blackboard: AgentBlackboard | None = None,
    ) -> None:
        self._bus = bus
        self._authority = authority
        self._reviews = reviews
        self._registry = registry
        self._log_path = experiment_log_path
        self._adr_root = adr_root
        self._blackboard = blackboard
        self._decisions = []
        seen: set[int] = set()
        seen_reviews: set[str] = set()
        seen_bindings: set[str] = set()

        def consume(trial_id: int) -> bool:
            if trial_id in seen:
                return False
            seen.add(trial_id)
            return True

        def consume_review(signature: str, binding: str) -> bool:
            if signature in seen_reviews or binding in seen_bindings:
                return False
            seen_reviews.add(signature)
            seen_bindings.add(binding)
            return True

        self._consume_trial = consume
        self._consume_review = consume_review
        self._freeze()
        bus.register_topic_guard(RESEARCH_GOVERNANCE_TOPIC, self._guard)
        if blackboard is not None:
            blackboard.register_topic_guard(RESEARCH_GOVERNANCE_TOPIC, self._guard)

    def decisions(self) -> tuple[GovernanceDecision, ...]:
        return tuple(self._decisions)

    def apply_protected(self, path: Path) -> None:
        refuse_protected_write(path)

    def admit(self, mutation: MutationProposed | Mapping[str, object]) -> GovernanceDecision:
        payload = dump_json(mutation) if isinstance(mutation, MutationProposed) else dict(mutation)
        if self._authority.mac_ok(canonical_mutation(payload), str(payload.get("provenance_mac", ""))) is False:
            return self._finish(payload, admitted=False, recorded=False, reasons=("provenance_invalid",))
        trial_id = payload.get("trial_id")
        if not isinstance(trial_id, int) or isinstance(trial_id, bool) or trial_id < 1:
            return self._finish(payload, admitted=False, recorded=False, reasons=("trial_id_invalid",))
        bound = self._registry_reasons(payload, trial_id=trial_id)
        if bound:
            return self._finish(payload, admitted=False, recorded=False, reasons=bound)
        if not self._consume_trial(trial_id):
            return self._finish(payload, admitted=False, recorded=False, reasons=("mutation_replay",))
        kind = str(payload.get("kind", ""))
        classified = _classify(kind)
        if classified == "forbidden":
            return self._finish(payload, admitted=False, recorded=False, reasons=(f"forbidden:{kind}",))
        if classified == "protected":
            reasons = self._protected_reasons(payload)
            if reasons:
                return self._finish(payload, admitted=False, recorded=False, reasons=reasons)
            return self._finish(
                payload,
                admitted=False,
                recorded=True,
                reasons=("protected_recorded_not_applied",),
            )
        if str(payload.get("target", "")) != GENOME_TARGET:
            return self._finish(payload, admitted=False, recorded=False, reasons=("target_not_genome",))
        return self._finish(payload, admitted=True, recorded=False, reasons=())

    def _protected_reasons(self, payload: Mapping[str, object]) -> tuple[str, ...]:
        adr_path = str(payload.get("adr_path", "")).strip()
        if not adr_path:
            return ("adr_required",)
        try:
            adr_bytes = read_adr(adr_path, adr_root=self._adr_root, target=str(payload.get("target", "")))
        except GovernanceError as exc:
            return (str(exc),)
        review_raw = as_object_dict(payload.get("review"))
        if review_raw is None:
            return ("human_review_required",)
        try:
            review = SignedReview.model_validate(review_raw)
        except Exception:
            return ("review_invalid",)
        if not self._reviews.verify_review(
            review,
            adr_bytes=adr_bytes,
            config_id=str(payload.get("config_id", "")),
            kind=str(payload.get("kind", "")),
            target=str(payload.get("target", "")),
        ):
            return ("review_invalid",)
        if review.verdict != "approve":
            return ("review_rejected",)
        binding = f"{review.mutation_sha256}:{review.adr_sha256}"
        if not self._consume_review(review.signature, binding):
            return ("review_replay",)
        return ()

    def _registry_reasons(self, payload: Mapping[str, object], *, trial_id: int) -> tuple[str, ...]:
        record = next((item for item in self._registry.records() if item.trial_id == trial_id), None)
        if record is None:
            return ("trial_not_in_registry",)
        if record.config_id != str(payload.get("config_id", "")):
            return ("trial_config_mismatch",)
        expected = mutation_fingerprint(
            config_id=str(payload.get("config_id", "")),
            kind=str(payload.get("kind", "")),
            target=str(payload.get("target", "")),
            genome=payload.get("genome"),
            parent_config_id=str(payload.get("parent_config_id", "")),
        )
        recorded = record.metrics.get("mutation_sha256")
        if recorded != expected:
            return ("trial_fingerprint_mismatch",)
        return ()

    def _finish(
        self,
        payload: Mapping[str, object],
        *,
        admitted: bool,
        recorded: bool,
        reasons: tuple[str, ...],
    ) -> GovernanceDecision:
        unsigned: dict[str, object] = {
            "schema_version": GOVERNANCE_SCHEMA_VERSION,
            "mutation_id": str(payload.get("mutation_id", "unknown")),
            "config_id": str(payload.get("config_id", "unknown")),
            "trial_id": _trial_id_or_one(payload.get("trial_id")),
            "agent_id": GOVERNANCE_AGENT_ID,
            "kind": _kind_or_skip(payload.get("kind", "noise")),
            "admitted": admitted,
            "recorded_for_human": recorded,
            "applied": False,
            "reasons": list(reasons),
        }
        mac = self._authority.mac(canonical_governance(unsigned))
        decision = GovernanceDecision.model_validate({**unsigned, "provenance_mac": mac})
        dumped = dump_json(decision)
        self._bus.publish(
            topic=RESEARCH_GOVERNANCE_TOPIC,
            producer=GOVERNANCE_AGENT_ID,
            payload=dict(dumped),
        )
        if self._blackboard is not None:
            self._blackboard.publish_sync(
                topic=RESEARCH_GOVERNANCE_TOPIC,
                producer=GOVERNANCE_AGENT_ID,
                payload=dict(dumped),
                confidence=1.0 if admitted else 0.0,
            )
        self._decisions.append(decision)
        log_experiment(
            path=self._log_path,
            agent_id=GOVERNANCE_AGENT_ID,
            event="governance",
            hypothesis_id=str(payload.get("mutation_id", "unknown")),
            rationale=None,
            metrics=dumped,
            reject_reason=None if admitted or recorded else (reasons[0] if reasons else "rejected"),
            failed_checks=reasons,
        )
        return decision

    def _guard(self, producer: str, payload: dict[str, object]) -> bool:
        if producer.strip() != GOVERNANCE_AGENT_ID:
            return False
        try:
            GovernanceDecision.model_validate(payload)
        except Exception:
            return False
        mac = payload.get("provenance_mac")
        if not isinstance(mac, str):
            return False
        return self._authority.mac_ok(canonical_governance(payload), mac)


def is_human_reviewer(reviewer_id: str) -> bool:
    text = reviewer_id.strip()
    if len(text) < 2:
        return False
    if text in _AGENT_IDS:
        return False
    if text.endswith("_agent"):
        return False
    return True


def read_adr(adr_path: str, *, adr_root: Path, target: str) -> bytes:
    root = adr_root.resolve()
    raw = Path(adr_path)
    resolved = raw.resolve() if raw.is_absolute() else (root / raw).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise GovernanceError("adr_path_escapes_root") from exc
    if not _ADR_NAME.match(resolved.name):
        raise GovernanceError("adr_filename_invalid")
    if not resolved.is_file():
        raise GovernanceError("adr_missing")
    text = resolved.read_text(encoding="utf-8")
    for heading in _HEADINGS:
        if heading not in text:
            raise GovernanceError("adr_incomplete")
    if target.strip() and target.strip() not in text:
        raise GovernanceError("adr_target_missing")
    return text.encode("utf-8")


def _classify(kind: str) -> Literal["allowed", "protected", "forbidden"]:
    if kind in FORBIDDEN_KINDS:
        return "forbidden"
    if kind in PROTECTED_KINDS:
        return "protected"
    if kind in ALLOWED_KINDS:
        return "allowed"
    return "forbidden"


_KIND_VALUES: tuple[MutationKind, ...] = (
    "parameter_tune",
    "open_window",
    "noise",
    "threshold_change",
    "risk_core_change",
    "strategy_switch",
    "skip_gate",
    "direct_promotion",
)


def _trial_id_or_one(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        return 1
    return value


def _kind_or_skip(value: object) -> MutationKind:
    for item in _KIND_VALUES:
        if value == item:
            return item
    return "skip_gate"


def _canonical_review(payload: Mapping[str, str]) -> bytes:
    body = {
        "reviewer_id": payload["reviewer_id"],
        "adr_sha256": payload["adr_sha256"],
        "mutation_sha256": payload["mutation_sha256"],
        "verdict": payload["verdict"],
    }
    return json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
