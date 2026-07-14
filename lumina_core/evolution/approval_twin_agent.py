from __future__ import annotations
import logging

import json
import math
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol

from lumina_core.config_loader import ConfigLoader
from lumina_core.logging_utils import (
    correlation_id,
    get_logger,
    log_twin_decision,
    record_twin_decision_monitoring,
    record_twin_steve_accuracy_monitoring,
    record_twin_training_metrics_monitoring,
)
from .dna_registry import PolicyDNA
from .steve_values_registry import SteveValueRecord, SteveValuesRegistry

# EventBus + typed payloads (optional; best-effort publish never affects decisions)
from lumina_core.agent_orchestration.event_bus import EventBus
from lumina_core.agent_orchestration.schemas import TwinDecisionEvent, TwinTrainingUpdateEvent

# Constitution import is lazy inside methods to avoid any potential cycles and to support graceful handling of proxy DNA.
# We import TRADING_CONSTITUTION (the immutable singleton) for the authoritative audit.

logger = get_logger("lumina.evolution.twin")


@dataclass(slots=True)
class ApprovalTwinState:
    intercept: float
    weights: dict[str, float]
    threshold: float
    training_steps: int
    # last_avg_error used for simple confidence calibration (shrinks over-confident extremes when mimicry error is high)
    last_avg_error: float = 0.15


class ApprovalTwinBackend(Protocol):
    def score(self, *, dna: PolicyDNA, local_score: float, threshold: float) -> tuple[float | None, str]: ...


@dataclass(slots=True)
class LocalHeuristicBackend:
    def score(self, *, dna: PolicyDNA, local_score: float, threshold: float) -> tuple[float | None, str]:
        del dna
        return local_score, f"local_heuristic(threshold={threshold:.0%})"


@dataclass(slots=True)
class OllamaTwinBackend:
    model: str = "qwen2.5:3b-instruct"

    def score(self, *, dna: PolicyDNA, local_score: float, threshold: float) -> tuple[float | None, str]:
        try:
            import ollama  # type: ignore
        except Exception:
            logging.exception("Unhandled broad exception fallback in lumina_core/evolution/approval_twin_agent.py:40")
            return None, "ollama_unavailable_fallback_local"

        prompt = (
            "You are an approval gate for REAL DNA promotion. "
            "Return strict JSON only with keys score (0..1) and explanation. "
            "Score should represent approval confidence.\n"
            f"threshold={threshold:.2f}\n"
            f"local_score={local_score:.4f}\n"
            f"dna_content={dna.content}\n"
            f"dna_fitness={float(dna.fitness_score):.6f}\n"
            f"dna_mutation_rate={float(dna.mutation_rate):.6f}\n"
            f"dna_generation={int(dna.generation)}"
        )
        try:
            response = ollama.chat(
                model=self.model,
                messages=[
                    {"role": "system", "content": "Respond with valid compact JSON only."},
                    {"role": "user", "content": prompt},
                ],
                options={"temperature": 0.0},
            )
            content = str(response.get("message", {}).get("content", "") or "").strip()
            payload = json.loads(content)
            score = float(payload.get("score", local_score))
            score = max(0.0, min(1.0, score))
            explanation = str(payload.get("explanation", "ollama_decision")).strip() or "ollama_decision"
            return score, f"ollama:{self.model}:{explanation}"
        except Exception:
            logging.exception("Unhandled broad exception fallback in lumina_core/evolution/approval_twin_agent.py:69")
            return None, "ollama_error_fallback_local"


class ApprovalTwinAgent:
    """Small local approval model trained only on Steve's answers.

    This is the core of LUMINA's Approval Twin: a user-trained mimic that
    replaces human approval gates so the organism can evolve 24/7.

    Training path (CLI):
      python -m lumina_launcher twin review   # label recent decisions APPROVE/VETO
      python -m lumina_launcher twin train
      python -m lumina_launcher twin metrics

    After labels, rlhf_light_update is called automatically. Metrics
    (avg_prediction_error, reward, training_steps) are emitted to monitoring
    and used for calibrated confidence.

    Mimicry uses:
    - SteveValuesRegistry records (explicit labels + confidence)
    - emotional_twin_profile.json (fomo/tilt/... sensitivities as Steve bias signals)
    - decision_lineage hints (lineage_hash presence)

    Confidence is calibrated using recent avg_error so "high confidence"
    gates in birth autonomy are trustworthy.
    """

    def __init__(
        self,
        *,
        registry: SteveValuesRegistry | None = None,
        model_path: Path | str = Path("state/approval_twin_model.json"),
        learning_rate: float = 0.08,
        backend: str | None = None,
        ollama_model: str | None = None,
        engine: Any = None,  # Optional: for risk shadow validation on risky DNA
        event_bus: EventBus | None = None,  # Optional central bus for typed Twin* events
    ) -> None:
        self._registry = registry
        self._model_path = Path(model_path)
        self._learning_rate = float(learning_rate)
        self._state = self._load_state()
        self._backend_name, self._backend = self._build_backend(backend=backend, ollama_model=ollama_model)
        self._engine = engine  # for Phase 2 Deliverable 5 risk shadow integration
        self._event_bus: EventBus | None = event_bus  # for publishing TwinDecisionEvent / TwinTrainingUpdateEvent

    def bind_event_bus(self, bus: EventBus | None) -> None:
        """Wire (or re-wire) the central EventBus after construction.

        Used by orchestrator/container bind paths. Safe no-op if None.
        """
        self._event_bus = bus

    def _publish_decision(
        self,
        *,
        dna_hash: str,
        recommendation: bool,
        confidence: float,
        risk_flags: list[str],
        explanation: str,
        call: str = "evaluate_dna_promotion",
    ) -> None:
        """Best-effort publish of TwinDecisionEvent. Never affects decision path or raises."""
        if self._event_bus is None:
            return
        try:
            payload = TwinDecisionEvent(
                dna_hash=str(dna_hash),
                recommendation=bool(recommendation),
                confidence=float(confidence),
                risk_flags=list(risk_flags or []),
                explanation=str(explanation or ""),
                call=str(call),
            ).model_dump(mode="json")
            self._event_bus.publish_validated(
                topic="evolution.twin.decision",
                producer="evolution.approval_twin_agent",
                payload=payload,
            )
        except Exception:
            # Observability only; decisions and training must never be impacted.
            pass

    def _publish_training_update(self, *, result: dict[str, Any], records_len: int) -> None:
        """Best-effort publish of TwinTrainingUpdateEvent after RLHF/fine-tune."""
        if self._event_bus is None:
            return
        try:
            payload = TwinTrainingUpdateEvent(
                records_processed=int(records_len),
                updates=int(result.get("updates", 0) or 0),
                avg_prediction_error=float(result.get("avg_prediction_error", 0.0) or 0.0),
                reward=float(result.get("reward", 0.0) or 0.0),
                training_steps=int(result.get("training_steps", 0) or 0),
            ).model_dump(mode="json")
            self._event_bus.publish_validated(
                topic="evolution.twin.training_update",
                producer="evolution.approval_twin_agent",
                payload=payload,
            )
        except Exception:
            pass

    def evaluate_dna_promotion(self, dna: PolicyDNA) -> dict[str, Any]:
        dna_hash = str(getattr(dna, "hash", ""))
        with correlation_id(dna_hash):
            features = self._features_from_dna(dna)
            local_score = self._score(features)
            backend_score, backend_explanation = self._backend.score(
                dna=dna,
                local_score=local_score,
                threshold=self._state.threshold,
            )
            raw_score = float(backend_score if backend_score is not None else local_score)
            raw_score = max(0.0, min(1.0, raw_score))
            # Calibrated confidence (used for recommendation + "high conf" autonomy decisions)
            score = self._calibrate(raw_score)
            risk_flags = self._risk_flags(dna)
            recommendation = bool(score >= self._state.threshold and not risk_flags)
            shadow_suffix = ""

            # === Constitution hard veto (fail-closed) — twin can NEVER recommend unconstitutional DNA ===
            # This is the structural guarantee that the ApprovalTwin (judgment layer) cannot bypass
            # TradingConstitution / ConstitutionalGuard / sandbox / aperture. Even if the heuristic or
            # Ollama backend is tricked by crafted content (safety words, high fitness, low mut rate),
            # any FATAL principle violation forces recommendation=False + explicit risk flag.
            # Proxy / birth-autonomy synthetic DNA (non-trading shape) is handled gracefully: we only
            # enforce when the content parses as a plausible trading DNA (presence of hyperparams or
            # standard keys). Any exception during the check is treated as fatal (fail-closed).
            # Must run before risk shadow incorporation so constitution takes precedence.
            try:
                raw_content = getattr(dna, "content", {}) or {}
                if isinstance(raw_content, str):
                    import json as _json
                    try:
                        content_for_audit = _json.loads(raw_content)
                    except Exception:
                        content_for_audit = {}
                else:
                    content_for_audit = raw_content

                # Heuristic: only apply strict trading constitution when it looks like real DNA
                # (not pure birth proxy metadata). If only the "structured" principle would fire,
                # we treat as non-trading and skip the veto for autonomy meta-decisions.
                looks_like_trading_dna = bool(
                    isinstance(content_for_audit, dict)
                    and (
                        "hyperparam_suggestion" in content_for_audit
                        or "mutation_depth" in content_for_audit
                        or any(k in content_for_audit for k in ("max_risk_percent", "kelly_fraction", "drawdown_kill_percent", "risk", "signal", "bypass", "disable_risk", "disable_circuit", "approval_required"))
                        or any(str(k).startswith(("bypass_", "disable_")) for k in content_for_audit.keys())
                        or (isinstance(content_for_audit.get("content"), str) and len(str(content_for_audit.get("content"))) > 10)
                    )
                )

                if looks_like_trading_dna:
                    from lumina_core.safety.trading_constitution import TRADING_CONSTITUTION
                    # stringify for the audit API (accepts raw JSON string or will parse)
                    audit_input = _json.dumps(content_for_audit, sort_keys=True) if isinstance(content_for_audit, dict) else str(content_for_audit)
                    violations = TRADING_CONSTITUTION.audit(audit_input, mode="sim", raise_on_fatal=False)
                    fatals = [v for v in violations if getattr(v, "severity", "") == "fatal"]
                    if fatals:
                        recommendation = False
                        for fv in fatals:
                            flag = f"constitution_{getattr(fv, 'principle_name', 'fatal')}"
                            if flag not in risk_flags:
                                risk_flags.append(flag)
                        # ensure the generic marker too
                        if "constitution_fatal_violation" not in risk_flags:
                            risk_flags.append("constitution_fatal_violation")
            except Exception:
                # Fail-closed: any error in the twin's constitution check blocks recommendation.
                # This prevents a tricked / broken twin from ever allowing bad DNA through its output.
                recommendation = False
                if "twin_constitution_check_error" not in risk_flags:
                    risk_flags.append("twin_constitution_check_error")
            # ================================================================================

            # === Phase 2 Deliverable 5 (Aperture Hardening) — Proactive risk shadow validation ===
            # For any DNA evaluation where an engine is available, we proactively run
            # the risk logic through the isolated shadow aperture. This is the first
            # live enforcement point where evolution proposals are forced through
            # the shadow aperture before promotion decisions (using bridge + auto-record).
            #
            # We attempt to extract realistic risk parameters from the DNA content
            # so the shadow experiment is meaningful rather than using only defaults.
            if self._engine is not None:
                try:
                    from pathlib import Path

                    # Best-effort extraction of risk experiment parameters from DNA
                    content = getattr(dna, "content", {}) or {}
                    if isinstance(content, str):
                        import json
                        try:
                            content = json.loads(content)
                        except Exception:
                            content = {}

                    proposal = {
                        "experiment_id": f"risk-shadow-{dna_hash[:12]}",
                        "dna_hash": dna_hash,
                        "signal": content.get("signal") or content.get("action") or "BUY",
                        "confluence_score": float(content.get("confluence_score", content.get("confluence", 0.65))),
                        "proposed_risk": float(content.get("proposed_risk", content.get("risk", 150.0))),
                    }

                    from lumina_core.evolution.risk_shadow_bridge import validate_risk_proposal_in_shadow

                    shadow_result = validate_risk_proposal_in_shadow(
                        proposal=proposal,
                        engine=self._engine,
                        storage_path=Path("state/risk_shadow_evolution.jsonl"),
                        auto_record_promotion=True,
                    )

                    # Incorporate shadow outcome into the twin decision
                    # NOTE: this path (and all twin risk proposals) is protected by the permanent
                    # aperture regression detector (aperture_guard). Twin cannot create bypasses.
                    shadow_rec = shadow_result.recommendation or {}
                    if shadow_rec.get("suggested_stage") in ("human_approval", "reject"):
                        recommendation = False
                        risk_flags.append("risk_shadow_blocked")
                    shadow_suffix = f" | risk_shadow={shadow_rec.get('suggested_stage', 'unknown')}"
                except Exception:
                    # Shadow validation is best-effort; never break the twin gate
                    pass
            # ================================================================================
            explanation = (
                f"Twin score={score:.2%}, threshold={self._state.threshold:.0%}, backend={self._backend_name}, "
                f"fitness={float(dna.fitness_score):.4f}, mutation_rate={float(dna.mutation_rate):.2f}, "
                f"source={backend_explanation}{shadow_suffix}"
            )
            try:
                logger.info(
                    "twin.evaluate_promotion",
                    extra={
                        "event_data": {
                            "event": "twin.evaluate_promotion",
                            "dna_hash": dna_hash,
                            "features": features,
                            "local_score": local_score,
                            "backend_score": backend_score,
                            "final_score": score,
                            "threshold": self._state.threshold,
                            "risk_flags": risk_flags,
                            "recommendation": recommendation,
                            "explanation": explanation,
                        }
                    },
                )
                log_twin_decision(logger, dna_hash, score, recommendation, risk_flags, explanation)
                record_twin_decision_monitoring(
                    dna_hash=dna_hash,
                    score=score,
                    recommendation=recommendation,
                    risk_flags=risk_flags,
                    explanation=explanation,
                )
                if not recommendation:
                    logger.warning(
                        "twin.evaluate_rejection",
                        extra={
                            "event_data": {
                                "event": "twin.evaluate_rejection",
                                "dna_hash": dna_hash,
                                "final_score": score,
                                "threshold": self._state.threshold,
                                "risk_flags": risk_flags,
                            }
                        },
                    )
            except Exception:
                pass

            # Publish typed event to central bus (best effort; after logs)
            self._publish_decision(
                dna_hash=dna_hash,
                recommendation=recommendation,
                confidence=score,
                risk_flags=risk_flags,
                explanation=explanation,
                call="evaluate_dna_promotion",
            )

            return {
                "recommendation": recommendation,
                "confidence": round(score, 6),
                "explanation": explanation,
                "risk_flags": risk_flags,
            }

    def _build_backend(self, *, backend: str | None, ollama_model: str | None) -> tuple[str, ApprovalTwinBackend]:
        cfg = ConfigLoader.section("evolution", "approval_twin", default={})
        cfg = cfg if isinstance(cfg, dict) else {}

        resolved_backend = (
            str(
                backend
                or cfg.get("backend")
                or ConfigLoader.section("ai", "approval_twin_backend", default="")
                or "local"
            )
            .strip()
            .lower()
        )

        if resolved_backend == "ollama":
            model = str(
                ollama_model
                or cfg.get("ollama_model")
                or ConfigLoader.section("ai", "approval_twin_ollama_model", default="")
                or "qwen2.5:3b-instruct"
            ).strip()
            return "ollama", OllamaTwinBackend(model=model)

        return "local", LocalHeuristicBackend()

    def evaluate_shadow_promotion(
        self, *, dna: PolicyDNA, shadow_total_pnl: float, veto_blocked: bool
    ) -> dict[str, Any]:
        dna_hash = str(getattr(dna, "hash", ""))
        with correlation_id(dna_hash):
            base = self.evaluate_dna_promotion(dna)  # already applies _calibrate for confidence
            shadow_positive = float(shadow_total_pnl) > 0.0
            recommendation = bool(base.get("recommendation", False) and shadow_positive and not bool(veto_blocked))
            explanation = (
                f"{base.get('explanation', '')}; shadow_total_pnl={float(shadow_total_pnl):.4f}; "
                f"veto_blocked={bool(veto_blocked)}"
            )
            try:
                logger.info(
                    "twin.evaluate_shadow_promotion",
                    extra={
                        "event_data": {
                            "event": "twin.evaluate_shadow_promotion",
                            "dna_hash": dna_hash,
                            "shadow_total_pnl": float(shadow_total_pnl),
                            "veto_blocked": bool(veto_blocked),
                            "recommendation": recommendation,
                            "risk_flags": list(base.get("risk_flags", [])),
                            "explanation": explanation,
                        }
                    },
                )
                if not recommendation:
                    logger.warning(
                        "twin.shadow_rejection",
                        extra={
                            "event_data": {
                                "event": "twin.shadow_rejection",
                                "dna_hash": dna_hash,
                                "shadow_total_pnl": float(shadow_total_pnl),
                                "veto_blocked": bool(veto_blocked),
                            }
                        },
                    )
            except Exception:
                pass

            # Publish (shadow path reuses base but emits distinct call for traceability)
            self._publish_decision(
                dna_hash=dna_hash,
                recommendation=recommendation,
                confidence=float(base.get("confidence", 0.0) or 0.0),
                risk_flags=list(base.get("risk_flags", [])),
                explanation=explanation,
                call="evaluate_shadow_promotion",
            )

            return {
                **base,
                "recommendation": recommendation,
                "shadow_total_pnl": float(shadow_total_pnl),
                "veto_blocked": bool(veto_blocked),
                "explanation": explanation,
            }

    def fine_tune_from_registry(self, *, limit: int = 250) -> dict[str, Any]:
        if self._registry is None:
            return {"updated": False, "reason": "registry_unavailable"}
        records = self._registry.list_recent(limit=max(1, int(limit)))
        return self.rlhf_light_update(records=records)

    def rlhf_light_update(self, *, records: list[SteveValueRecord]) -> dict[str, Any]:
        updates = 0
        abs_errors: list[float] = []

        # Replay from oldest to newest so recent Steve judgments dominate.
        for record in reversed(records):
            label = self._label_from_answer(record.steve_antwoord)
            if label is None:
                continue
            features = self._features_from_record(record)
            pred = self._score(features)
            error = float(label) - pred

            self._state.intercept += self._learning_rate * error
            for key, value in features.items():
                self._state.weights[key] = (
                    float(self._state.weights.get(key, 0.0)) + self._learning_rate * error * value
                )

            abs_errors.append(abs(error))
            updates += 1

        avg_error = sum(abs_errors) / len(abs_errors) if abs_errors else 1.0
        reward = max(0.0, min(1.0, 1.0 - avg_error))

        if updates > 0:
            self._state.training_steps += updates
            self._state.last_avg_error = float(avg_error)
            self._save_state()

        result = {
            "updated": updates > 0,
            "updates": updates,
            "avg_prediction_error": round(avg_error, 6),
            "reward": round(reward, 6),
            "training_steps": int(self._state.training_steps),
        }
        try:
            logger.info(
                "twin.rlhf_update",
                extra={
                    "event_data": {
                        "event": "twin.rlhf_update",
                        "records_processed": len(records),
                        "updates": updates,
                        "avg_prediction_error": result["avg_prediction_error"],
                        "reward": result["reward"],
                        "training_steps": result["training_steps"],
                    }
                },
            )
            record_twin_training_metrics_monitoring(
                avg_prediction_error=float(result["avg_prediction_error"]),
                reward=float(result["reward"]),
                training_steps=int(result["training_steps"]),
            )
        except Exception:
            pass

        # Publish training update event (for every rlhf/fine-tune)
        self._publish_training_update(result=result, records_len=len(records))

        # Perfect Birth Phase KPI: twin accuracy vs Steve (label agreement %)
        try:
            agreement = self.compute_steve_agreement_pct(records=records)
            result["twin_steve_agreement_pct"] = agreement
            record_twin_steve_accuracy_monitoring(
                agreement_pct=float(agreement),
                samples=len(records) or 0,
                avg_error=float(result.get("avg_prediction_error", 0.0) or 0.0),
            )
        except Exception:
            pass

        return result

    def compute_steve_agreement_pct(
        self, records: list[SteveValueRecord] | None = None, limit: int = 100
    ) -> float:
        """Compute direct agreement % between twin recommendation and Steve labels.

        This is the primary 'twin accuracy vs Steve' measurable success metric for
        Perfect Birth Phase. Replays current model (features + threshold) on records.
        Returns 0.0 if no usable labels.
        """
        if self._registry is None and not records:
            return 0.0
        try:
            recs: list[SteveValueRecord] = []
            if records:
                recs = list(records)
            elif self._registry is not None:
                recs = self._registry.list_recent(max(1, int(limit)))
            if not recs:
                return 0.0

            matches = 0
            total = 0
            thr = float(getattr(self._state, "threshold", 0.6) or 0.6)

            for r in recs:
                label = self._label_from_answer(getattr(r, "steve_antwoord", ""))
                if label is None:
                    continue
                feats = self._features_from_record(r)
                pred = self._score(feats)
                twin_rec = bool(pred >= thr)
                steve_rec = bool(label >= 0.5)
                if twin_rec == steve_rec:
                    matches += 1
                total += 1

            if total <= 0:
                return 0.0
            return round((matches / total) * 100.0, 2)
        except Exception:
            return 0.0

    def _score(self, features: dict[str, float]) -> float:
        logit = float(self._state.intercept)
        for key, value in features.items():
            logit += float(self._state.weights.get(key, 0.0)) * float(value)
        # Stable sigmoid for confidence in [0,1].
        if logit >= 0.0:
            z = math.exp(-logit)
            out = 1.0 / (1.0 + z)
            try:
                logger.debug(
                    "twin.score_internal",
                    extra={"event_data": {"event": "twin.score_internal", "features": features, "score": out}},
                )
            except Exception:
                pass
            return out
        z = math.exp(logit)
        out = z / (1.0 + z)
        try:
            logger.debug(
                "twin.score_internal",
                extra={"event_data": {"event": "twin.score_internal", "features": features, "score": out}},
            )
        except Exception:
            pass
        return out

    def _calibrate(self, raw: float) -> float:
        """Simple confidence calibration driven by recent training error.

        When mimicry error (avg_prediction_error) is high, pull extreme
        confidences toward 0.5 so that "high confidence" decisions used for
        autonomous birth loops are honest.
        """
        err = float(getattr(self._state, "last_avg_error", 0.15) or 0.15)
        blend = min(0.45, max(0.0, err * 1.8))
        return max(0.0, min(1.0, raw * (1.0 - blend) + 0.5 * blend))

    @staticmethod
    def _load_emotional_profile() -> dict[str, float]:
        """Load Steve's emotional twin sensitivities (used as bias features for approval mimicry).
        Safe fallback to neutral 1.0 sensitivities if file missing/unreadable.
        """
        defaults = {
            "fomo_sensitivity": 1.0,
            "tilt_sensitivity": 1.0,
            "boredom_sensitivity": 1.0,
            "revenge_sensitivity": 1.0,
        }
        try:
            p = Path("lumina_agents/emotional_twin_profile.json")
            if p.exists():
                data = json.loads(p.read_text(encoding="utf-8"))
                for k in defaults:
                    if k in data:
                        defaults[k] = float(data[k])
        except Exception:
            pass
        return defaults

    @staticmethod
    def _features_from_dna(dna: PolicyDNA) -> dict[str, float]:
        """Richer feature set for Steve-mimicry.

        Sources:
        - SteveValuesRegistry (via training labels)
        - emotional_twin_profile.json (emotional bias signals Steve exhibits)
        - decision_lineage (lineage_hash presence as provenance signal)
        """
        content = str(dna.content).lower()
        emo = ApprovalTwinAgent._load_emotional_profile()
        lineage = getattr(dna, "lineage_hash", "") or ""
        has_lineage = 1.0 if lineage and str(lineage).upper() not in ("", "GENESIS", "BIRTH", "AUTO") else 0.0
        fitness = float(dna.fitness_score)
        return {
            "bias": 1.0,
            "fitness": fitness,
            "mutation_rate": float(dna.mutation_rate),
            "generation": float(dna.generation),
            "content_len_norm": min(1.0, len(str(dna.content)) / 600.0),
            "high_fitness": 1.0 if fitness > 1.0 else 0.0,
            "contains_risk_word": 1.0
            if any(token in content for token in ("aggressive", "leverage", "martingale"))
            else 0.0,
            "contains_safety_word": 1.0
            if any(token in content for token in ("risk", "guard", "stop", "cooldown", "constitution"))
            else 0.0,
            "has_lineage": has_lineage,
            # Emotional profile as Steve risk-tolerance / bias proxy (weights will learn correlations)
            "fomo_sens": emo["fomo_sensitivity"],
            "tilt_sens": emo["tilt_sensitivity"],
            "boredom_sens": emo["boredom_sensitivity"],
            "revenge_sens": emo["revenge_sensitivity"],
        }

    @staticmethod
    def _features_from_record(record: SteveValueRecord) -> dict[str, float]:
        """Richer record features (Steve's explicit answers drive weights)."""
        text = f"{record.vraag} {record.steve_antwoord}".lower()
        return {
            "bias": 1.0,
            "record_confidence": float(record.confidence_score),
            "mentions_real": 1.0 if "real" in text else 0.0,
            "mentions_risk": 1.0 if "risk" in text or "risico" in text else 0.0,
            "mentions_drawdown": 1.0 if "drawdown" in text else 0.0,
            "mentions_constitution": 1.0 if "constitution" in text or "kapitaal" in text else 0.0,
            "mentions_fitness": 1.0 if "fitness" in text else 0.0,
            "mentions_guard": 1.0 if "guard" in text or "safety" in text else 0.0,
            "approve_token": 1.0 if "approve" in text else 0.0,
            "veto_token": 1.0 if "veto" in text else 0.0,
        }

    @staticmethod
    def _label_from_answer(answer: str) -> float | None:
        lowered = str(answer).strip().lower()
        if "approve" in lowered:
            return 1.0
        if "veto" in lowered:
            return 0.0
        return None

    @staticmethod
    def _risk_flags(dna: PolicyDNA) -> list[str]:
        flags: list[str] = []
        if float(dna.fitness_score) <= 0.0:
            flags.append("non_positive_fitness")
        if float(dna.mutation_rate) > 0.35:
            flags.append("high_mutation_rate")
        content = str(dna.content).lower()
        if "martingale" in content:
            flags.append("martingale_detected")
        return flags

    def _load_state(self) -> ApprovalTwinState:
        if not self._model_path.exists():
            return ApprovalTwinState(intercept=0.0, weights={}, threshold=0.6, training_steps=0, last_avg_error=0.15)
        try:
            payload = json.loads(self._model_path.read_text(encoding="utf-8"))
            return ApprovalTwinState(
                intercept=float(payload.get("intercept", 0.0) or 0.0),
                weights={str(k): float(v) for k, v in dict(payload.get("weights", {})).items()},
                threshold=max(0.5, min(0.95, float(payload.get("threshold", 0.6) or 0.6))),
                training_steps=int(payload.get("training_steps", 0) or 0),
                last_avg_error=float(payload.get("last_avg_error", 0.15) or 0.15),
            )
        except Exception:
            logging.exception("Unhandled broad exception fallback in lumina_core/evolution/approval_twin_agent.py:273")
            return ApprovalTwinState(intercept=0.0, weights={}, threshold=0.6, training_steps=0, last_avg_error=0.15)

    def _save_state(self) -> None:
        self._model_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "intercept": float(self._state.intercept),
            "weights": dict(self._state.weights),
            "threshold": float(self._state.threshold),
            "training_steps": int(self._state.training_steps),
            "last_avg_error": float(getattr(self._state, "last_avg_error", 0.15)),
            "last_updated": datetime.now().isoformat(),
        }
        self._model_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
