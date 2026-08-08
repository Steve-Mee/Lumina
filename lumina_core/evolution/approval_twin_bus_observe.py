"""Approval Twin EventBus bind + shadow observation helpers."""
from __future__ import annotations

from typing import Any

from lumina_core.agent_orchestration.event_bus import DomainEvent, EventBus
from lumina_core.evolution.approval_twin_patch_bridge import twin_attr
from lumina_core.logging_utils import (
    get_logger,
    record_shadow_twin_alignment_monitoring,
)

logger = get_logger("lumina.evolution.twin")

# Topics Twin subscribes to for non-blocking shadow observation (ADR-0001 / 0031 finish).
_TWIN_SUBSCRIBE_TOPICS: tuple[str, ...] = (
    "evolution.shadow.verdict",
    "evolution.promotion.decision",
    "evolution.proposal.created",
    "safety.constitution.audit",
    "safety.constitution.violation",
    "risk.policy.decision",
)


class ApprovalTwinBusObserveMixin:
    _recent_constitution_flags: list[str]
    _recent_risk_flags: list[str]

    def bind_event_bus(self, bus: EventBus | None) -> None:
        """Wire (or re-wire) the central EventBus after construction.

        Publishes Twin* events and subscribes to shadow/promotion/constitution/risk
        topics for non-blocking observation. Safe no-op if None.
        """
        self._unsubscribe_all()
        self._event_bus = bus
        if bus is None:
            return
        for topic in _TWIN_SUBSCRIBE_TOPICS:
            try:
                token = bus.subscribe(topic, self._on_bus_event)
                self._subscription_tokens.append(token)
            except Exception:
                logger.debug("twin.subscribe_failed topic=%s", topic, exc_info=True)

    def _unsubscribe_all(self) -> None:
        bus = self._event_bus
        tokens = list(self._subscription_tokens)
        self._subscription_tokens.clear()
        if bus is None:
            return
        for token in tokens:
            try:
                bus.unsubscribe(token)
            except Exception:
                pass

    def _on_bus_event(self, event: DomainEvent | Any) -> None:
        """Observe-only EventBus callback. Never raises into the bus."""
        try:
            topic = str(getattr(event, "topic", "") or "").strip().lower()
            payload = getattr(event, "payload", None)
            if not isinstance(payload, dict):
                payload = {}
            if topic == "evolution.shadow.verdict":
                self.observe_shadow_verdict(payload)
            elif topic == "evolution.promotion.decision":
                self.observe_promotion_decision(payload)
            elif topic == "evolution.proposal.created":
                # Context only — no agreement metric without a twin evaluation target.
                pass
            elif topic in ("safety.constitution.audit", "safety.constitution.violation"):
                self.observe_constitution_event(topic=topic, payload=payload)
            elif topic == "risk.policy.decision":
                self._accumulate_risk_policy(payload)
        except Exception:
            logger.debug("twin.bus_observe_error", exc_info=True)

    def observe_shadow_verdict(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Non-blocking: compare twin bias to shadow verdict; log agreement only."""
        dna_hash = str(payload.get("dna_hash") or "")
        verdict = str(payload.get("verdict") or "pending").strip().lower()
        if verdict == "pending":
            return {"observed": False, "reason": "pending"}
        observed_pass = verdict == "pass"
        pnl = payload.get("pnl")
        try:
            pnl_f = float(pnl) if pnl is not None else (1.0 if observed_pass else -1.0)
        except (TypeError, ValueError):
            pnl_f = 1.0 if observed_pass else -1.0
        twin_rec, confidence, risk_flags = self._shadow_observe_recommendation(
            dna_hash=dna_hash, shadow_pnl=pnl_f
        )
        agreed = bool(twin_rec) == bool(observed_pass)
        return self._record_observation(
            dna_hash=dna_hash,
            source_topic="evolution.shadow.verdict",
            twin_recommendation=twin_rec,
            observed_allowed_or_pass=observed_pass,
            agreed=agreed,
            confidence=confidence,
            risk_flags=risk_flags,
            explanation=f"shadow_verdict={verdict}; twin_rec={twin_rec}; agreed={agreed}",
            shadow_pnl=pnl_f,
        )

    def observe_promotion_decision(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Non-blocking: compare twin bias to promotion allowed flag."""
        dna_hash = str(payload.get("dna_hash") or "")
        allowed = bool(payload.get("allowed", False))
        twin_rec, confidence, risk_flags = self._shadow_observe_recommendation(
            dna_hash=dna_hash, shadow_pnl=1.0 if allowed else -1.0
        )
        # Fail-closed context: constitution flags force twin_rec false for agreement fairness
        if self._recent_constitution_flags:
            twin_rec = False
            for f in self._recent_constitution_flags[-5:]:
                if f not in risk_flags:
                    risk_flags.append(f)
        agreed = bool(twin_rec) == bool(allowed)
        return self._record_observation(
            dna_hash=dna_hash,
            source_topic="evolution.promotion.decision",
            twin_recommendation=twin_rec,
            observed_allowed_or_pass=allowed,
            agreed=agreed,
            confidence=confidence,
            risk_flags=risk_flags,
            explanation=(
                f"promotion allowed={allowed} stage={payload.get('stage', '')}; "
                f"twin_rec={twin_rec}; agreed={agreed}"
            ),
            shadow_pnl=None,
        )

    def observe_constitution_event(self, *, topic: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Track constitution signals for risk context; never blocks producers."""
        codes: list[str] = []
        if topic.endswith("violation"):
            name = str(payload.get("principle_name") or "constitution_violation")
            codes.append(f"bus_{name}")
        else:
            passed = bool(payload.get("passed", True))
            if not passed:
                for c in list(payload.get("violation_codes") or []):
                    codes.append(f"bus_constitution_{c}")
                if not codes:
                    codes.append("bus_constitution_audit_failed")
        for c in codes:
            if c not in self._recent_constitution_flags:
                self._recent_constitution_flags.append(c)
        if len(self._recent_constitution_flags) > 32:
            self._recent_constitution_flags = self._recent_constitution_flags[-32:]
        dna_hash = str(payload.get("dna_hash") or "")
        if not codes:
            return {"observed": True, "flags_added": 0}
        # When audit fails / violation, twin should "agree" with reject (fail-closed alignment)
        twin_rec = False
        confidence = float(self._state.threshold)
        agreed = True  # twin refuses on constitution issues
        return self._record_observation(
            dna_hash=dna_hash,
            source_topic=topic,
            twin_recommendation=twin_rec,
            observed_allowed_or_pass=False,
            agreed=agreed,
            confidence=confidence,
            risk_flags=list(codes),
            explanation=f"constitution observe topic={topic}; flags={codes}",
            shadow_pnl=None,
        )

    def _accumulate_risk_policy(self, payload: dict[str, Any]) -> None:
        approved = payload.get("approved")
        if approved is False:
            reason = str(payload.get("reason") or payload.get("limit") or "risk_rejected")
            flag = f"bus_risk_{reason}"[:80]
            if flag not in self._recent_risk_flags:
                self._recent_risk_flags.append(flag)
            if len(self._recent_risk_flags) > 32:
                self._recent_risk_flags = self._recent_risk_flags[-32:]

    def _shadow_observe_recommendation(
        self, *, dna_hash: str, shadow_pnl: float
    ) -> tuple[bool, float, list[str]]:
        """Lightweight twin stance for observe paths without full DNA object.

        Uses model prior + pnl heuristic. Fail-closed if recent constitution flags present.
        """
        del dna_hash  # reserved for future lineage lookup
        features = {
            "bias": 1.0,
            "fitness": max(0.0, min(2.0, 1.0 + float(shadow_pnl) * 0.01)),
            "mutation_rate": 0.1,
            "generation": 0.0,
            "content_len_norm": 0.2,
            "high_fitness": 1.0 if shadow_pnl > 0 else 0.0,
            "contains_risk_word": 0.0,
            "contains_safety_word": 0.5,
            "has_lineage": 0.0,
            "fomo_sens": 1.0,
            "tilt_sens": 1.0,
            "boredom_sens": 1.0,
            "revenge_sens": 1.0,
        }
        raw = self._score(features)
        score = self._calibrate(raw)
        risk_flags = list(self._recent_constitution_flags[-3:]) + list(self._recent_risk_flags[-3:])
        recommendation = bool(score >= self._state.threshold and not risk_flags and shadow_pnl > 0.0)
        if risk_flags:
            recommendation = False
        return recommendation, float(score), risk_flags

    def _record_observation(
        self,
        *,
        dna_hash: str,
        source_topic: str,
        twin_recommendation: bool,
        observed_allowed_or_pass: bool,
        agreed: bool,
        confidence: float,
        risk_flags: list[str],
        explanation: str,
        shadow_pnl: float | None,
    ) -> dict[str, Any]:
        self.observations_total += 1
        if agreed:
            self.agreements += 1
        else:
            self.disagreements += 1
        # P2: sample twin INFO logs — disagreements / risk flags always; else 1/50.
        # Full durable metrics still recorded below (promotion evidence SSOT).
        _log_this = (
            (not agreed)
            or bool(risk_flags)
            or self.observations_total <= 3
            or self.observations_total % 50 == 0
        )
        if _log_this:
            try:
                logger.info(
                    "twin.shadow_observation",
                    extra={
                        "event_data": {
                            "event": "twin.shadow_observation",
                            "dna_hash": dna_hash,
                            "source_topic": source_topic,
                            "twin_recommendation": twin_recommendation,
                            "observed_allowed_or_pass": observed_allowed_or_pass,
                            "agreed": agreed,
                            "confidence": confidence,
                            "risk_flags": risk_flags,
                            "mode": self._mode,
                            "explanation": explanation,
                            "observations_total": self.observations_total,
                        }
                    },
                )
            except Exception:
                pass
        if shadow_pnl is not None:
            try:
                twin_attr("record_shadow_twin_alignment_monitoring", record_shadow_twin_alignment_monitoring)(
                    aligned=bool(agreed),
                    shadow_pnl=float(shadow_pnl),
                    twin_recommendation=bool(twin_recommendation),
                    confidence=float(confidence),
                    dna_hash=str(dna_hash),
                )
            except Exception:
                pass
        self._publish_shadow_observation(
            dna_hash=dna_hash,
            source_topic=source_topic,
            twin_recommendation=twin_recommendation,
            observed_allowed_or_pass=observed_allowed_or_pass,
            agreed=agreed,
            confidence=confidence,
            risk_flags=risk_flags,
            explanation=explanation,
        )
        # Durable metrics for promotion gates (agreement / FP / risk flags caught)
        try:
            source = "promotion_path"
            if "shadow" in source_topic:
                source = "shadow_path"
            elif "constitution" in source_topic:
                source = "constitution"
            # constitution_fatal: true when constitution signal present (independent of path allow)
            constitution_fatal = any(
                "constitution" in str(f).lower() or "fatal" in str(f).lower()
                for f in risk_flags
            ) or ("constitution" in source_topic)
            self._metrics_store.record_comparison(
                twin_recommendation=bool(twin_recommendation),
                ground_truth_approve=bool(observed_allowed_or_pass),
                source=source,  # type: ignore[arg-type]
                risk_flags=list(risk_flags or []),
                dna_hash=str(dna_hash or ""),
                mode=self._mode,
                constitution_fatal=bool(constitution_fatal),
                twin_confidence=float(confidence) if confidence is not None else None,
            )
        except Exception:
            pass
        return {
            "observed": True,
            "agreed": agreed,
            "twin_recommendation": twin_recommendation,
            "observed_allowed_or_pass": observed_allowed_or_pass,
            "confidence": confidence,
            "risk_flags": risk_flags,
            "mode": self._mode,
        }
