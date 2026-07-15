"""Shared Approval Twin training loop (CLI + FastAPI).

Keeps Steve's labels local and auditable:
  - state/steve_values_registry.sqlite3 + .jsonl (append-only)
  - state/approval_twin_model.json (light RLHF weights)
  - state/monitoring_twin_decisions.jsonl / monitoring_twin_training.jsonl

Does **not** touch promotion, REAL capital paths, or hard safety gates.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict
from pathlib import Path
from typing import Any, Literal

from lumina_core.evolution.approval_gym import ApprovalGym, ApprovalProposal
from lumina_core.evolution.approval_twin_agent import ApprovalTwinAgent
from lumina_core.evolution.dna_registry import PolicyDNA
from lumina_core.evolution.steve_values_registry import SteveValueRecord, SteveValuesRegistry

DecisionKind = Literal["approve", "reject", "modify"]
StakesLevel = Literal["high", "routine"]

STATE_DIR = Path("state")
DEFAULT_TWIN_DECISIONS = STATE_DIR / "monitoring_twin_decisions.jsonl"
DEFAULT_TWIN_TRAINING = STATE_DIR / "monitoring_twin_training.jsonl"
DEFAULT_MODEL_PATH = STATE_DIR / "approval_twin_model.json"

# Matches birth/autonomy high-conf band (organism_autonomy: conf >= 0.80 + clean).
HIGH_CONF_THRESHOLD = 0.80
# How far back in the registry we look when filtering already-labeled DNA.
LABELED_LOOKBACK = 2000


def _tail_jsonl(path: Path, limit: int = 20) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        lines = path.read_text(encoding="utf-8").strip().splitlines()
        items: list[dict[str, Any]] = []
        for line in lines[-max(1, int(limit)) :]:
            line = line.strip()
            if not line:
                continue
            try:
                parsed = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                items.append(parsed)
        return items
    except OSError:
        return []


def decision_to_answer(decision: DecisionKind, notes: str = "") -> str:
    note = str(notes or "").strip()
    if decision == "approve":
        return "APPROVE" if not note else f"APPROVE: {note}"
    if decision == "reject":
        return "VETO" if not note else f"VETO: {note}"
    # modify
    return f"MODIFY: {note}" if note else "MODIFY"


def default_confidence(decision: DecisionKind) -> float:
    if decision == "approve":
        return 0.85
    if decision == "reject":
        return 0.25
    return 0.45


def build_vraag(
    *,
    dna_hash: str,
    twin_score: float | None,
    twin_recommendation: bool | None,
    explanation: str,
    risk_flags: list[str] | None,
    notes: str = "",
) -> str:
    score_s = f"{float(twin_score):.2%}" if twin_score is not None else "n/a"
    rec_s = str(bool(twin_recommendation)) if twin_recommendation is not None else "n/a"
    expl = str(explanation or "")[:200]
    risks = list(risk_flags or [])
    parts = [
        f"Twin decision review: dna={dna_hash} score={score_s} rec={rec_s}",
        f"risks={risks}",
        expl,
    ]
    note = str(notes or "").strip()
    if note:
        parts.append(f"steve_note={note}")
    return " | ".join(p for p in parts if p)


def _score_of(item: dict[str, Any]) -> float | None:
    raw = item.get("score", item.get("confidence"))
    if raw is None:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def classify_stakes(item: dict[str, Any]) -> StakesLevel:
    """High-stakes = risk flags, mid/low score, or approve-with-risks. Else routine."""
    risks = item.get("risk_flags") or []
    risk_list = [str(r) for r in risks] if isinstance(risks, list) else []
    if risk_list:
        return "high"
    score = _score_of(item)
    if score is None:
        return "high"
    if score < HIGH_CONF_THRESHOLD:
        return "high"
    return "routine"


def annotate_review_item(
    item: dict[str, Any],
    *,
    labeled_hashes: set[str],
) -> dict[str, Any]:
    """Copy decision row and attach UI/API metadata (stakes, already_labeled)."""
    out = dict(item)
    dna = str(out.get("dna_hash") or "").strip()
    out["already_labeled"] = bool(dna and dna in labeled_hashes)
    out["stakes"] = classify_stakes(out)
    return out


class TwinTrainingService:
    """Orchestrate review queue, Steve labels, and light RLHF updates."""

    def __init__(
        self,
        *,
        registry: SteveValuesRegistry | None = None,
        twin: ApprovalTwinAgent | None = None,
        model_path: Path | str = DEFAULT_MODEL_PATH,
        decisions_path: Path | str = DEFAULT_TWIN_DECISIONS,
        training_path: Path | str = DEFAULT_TWIN_TRAINING,
    ) -> None:
        self.model_path = Path(model_path)
        self.decisions_path = Path(decisions_path)
        self.training_path = Path(training_path)
        self.registry = registry or SteveValuesRegistry()
        self.twin = twin or ApprovalTwinAgent(registry=self.registry, model_path=self.model_path)
        # Ensure twin sees the same registry instance
        if getattr(self.twin, "_registry", None) is None:
            self.twin._registry = self.registry  # noqa: SLF001 — intentional bind

    def _labeled_dna_hashes(self, *, lookback: int = LABELED_LOOKBACK) -> set[str]:
        records = self.registry.list_recent(limit=max(1, int(lookback)))
        return {
            str(r.context_dna_hash).strip()
            for r in records
            if str(getattr(r, "context_dna_hash", "") or "").strip()
        }

    def list_review_queue(
        self,
        *,
        limit: int = 20,
        include_labeled: bool = False,
    ) -> list[dict[str, Any]]:
        """Recent twin decisions for Steve review.

        By default excludes DNA already labeled in the local SteveValues registry.
        High-stakes items (risk flags / sub high-conf score) sort first; then newest.
        """
        # Over-fetch so filtering still yields up to `limit` unlabeled items.
        fetch_n = max(1, int(limit)) * (4 if not include_labeled else 1)
        fetch_n = min(500, max(fetch_n, int(limit)))
        raw = _tail_jsonl(self.decisions_path, limit=fetch_n)
        # Newest first before stakes re-sort
        newest_first = list(reversed(raw))

        labeled = self._labeled_dna_hashes()
        annotated: list[dict[str, Any]] = []
        for item in newest_first:
            row = annotate_review_item(item, labeled_hashes=labeled)
            if not include_labeled and row.get("already_labeled"):
                continue
            annotated.append(row)

        # High stakes first; within same stakes band keep newest-first order (stable).
        annotated.sort(key=lambda r: 0 if r.get("stakes") == "high" else 1)
        return annotated[: max(1, int(limit))]

    def list_labels(self, *, limit: int = 50) -> list[dict[str, Any]]:
        records = self.registry.list_recent(limit=max(1, int(limit)))
        return [asdict(r) for r in records]

    def record_decision(
        self,
        *,
        decision: DecisionKind,
        dna_hash: str,
        notes: str = "",
        twin_score: float | None = None,
        twin_recommendation: bool | None = None,
        explanation: str = "",
        risk_flags: list[str] | None = None,
        confidence_score: float | None = None,
        train_now: bool = True,
    ) -> dict[str, Any]:
        dna = str(dna_hash or "").strip()
        if not dna:
            raise ValueError("dna_hash is required")
        if decision not in ("approve", "reject", "modify"):
            raise ValueError(f"invalid decision: {decision}")

        answer = decision_to_answer(decision, notes)
        conf = (
            max(0.0, min(1.0, float(confidence_score)))
            if confidence_score is not None
            else default_confidence(decision)
        )
        vraag = build_vraag(
            dna_hash=dna,
            twin_score=twin_score,
            twin_recommendation=twin_recommendation,
            explanation=explanation,
            risk_flags=risk_flags,
            notes=notes,
        )
        record = SteveValueRecord.create(
            vraag=vraag,
            steve_antwoord=answer,
            context_dna_hash=dna,
            confidence_score=conf,
        )
        self.registry.append(record)

        # Durable twin mode metrics: Steve label vs twin proposal (promotion evidence)
        steve_approve = decision == "approve"
        if hasattr(self.twin, "record_steve_label_comparison"):
            try:
                self.twin.record_steve_label_comparison(
                    twin_recommendation=twin_recommendation,
                    steve_approve=steve_approve,
                    risk_flags=list(risk_flags or []),
                    dna_hash=dna,
                )
            except Exception:
                pass

        result: dict[str, Any] = {
            "recorded": True,
            "decision": decision,
            "label": answer,
            "record": asdict(record),
            "local_only": True,
            "audit": {
                "registry_sqlite": str(self.registry.sqlite_path),
                "registry_jsonl": str(self.registry.jsonl_path),
                "model_path": str(self.model_path),
            },
            "rlhf": None,
            "metrics": None,
        }

        if train_now:
            result["rlhf"] = self.twin.rlhf_light_update(records=[record])
            result["metrics"] = self.metrics()

        return result

    def train(self, *, limit: int = 250) -> dict[str, Any]:
        res = self.twin.fine_tune_from_registry(limit=max(1, int(limit)))
        return {
            "trained": bool(res.get("updated")),
            "result": res,
            "metrics": self.metrics(),
            "local_only": True,
            "audit": {
                "registry_sqlite": str(self.registry.sqlite_path),
                "registry_jsonl": str(self.registry.jsonl_path),
                "model_path": str(self.model_path),
            },
        }

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
        gym = ApprovalGym(registry=self.registry, rng_seed=rng_seed)
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
        self.registry.append(record)

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
                "registry_sqlite": str(self.registry.sqlite_path),
                "registry_jsonl": str(self.registry.jsonl_path),
                "model_path": str(self.model_path),
            },
            "rlhf": None,
            "metrics": None,
        }
        if train_now:
            result["rlhf"] = self.twin.rlhf_light_update(records=[record])
            result["metrics"] = self.metrics()
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
            rlhf = self.twin.rlhf_light_update(records=records_for_rlhf)

        return {
            "recorded_count": len(recorded),
            "answers": recorded,
            "rlhf": rlhf,
            "metrics": self.metrics(),
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

    def metrics(self) -> dict[str, Any]:
        latest: dict[str, Any] = {}
        items = _tail_jsonl(self.training_path, limit=1)
        if items:
            latest = items[-1]

        model: dict[str, Any] = {}
        if self.model_path.exists():
            try:
                parsed = json.loads(self.model_path.read_text(encoding="utf-8"))
                if isinstance(parsed, dict):
                    model = parsed
            except (OSError, json.JSONDecodeError):
                model = {}

        agreement: float | None
        try:
            agreement = float(self.twin.compute_steve_agreement_pct(limit=100))
        except Exception:
            agreement = None

        labels_sample = self.registry.list_recent(limit=500)

        mode_metrics: dict[str, Any] = {}
        mode_status: dict[str, Any] = {}
        try:
            if hasattr(self.twin, "observation_metrics"):
                mode_metrics = dict(self.twin.observation_metrics() or {})
            if hasattr(self.twin, "mode_status"):
                mode_status = dict(self.twin.mode_status() or {})
            elif hasattr(self.twin, "metrics_store"):
                mode_metrics["durable_metrics"] = self.twin.metrics_store.metrics_dict()
        except Exception:
            pass

        durable = mode_metrics.get("durable_metrics") if isinstance(mode_metrics, dict) else {}
        if not isinstance(durable, dict):
            durable = {}

        return {
            "avg_prediction_error": latest.get(
                "avg_prediction_error", model.get("last_avg_error", None)
            ),
            "reward": latest.get("reward", None),
            "training_steps": latest.get(
                "training_steps", model.get("training_steps", 0)
            ),
            "threshold": model.get("threshold", 0.6),
            "last_avg_error": model.get("last_avg_error", None),
            "twin_steve_agreement_pct": latest.get(
                "twin_steve_agreement_pct",
                latest.get("agreement_pct", agreement),
            ),
            "samples": latest.get("samples", None),
            "labels_total_recent_cap": len(labels_sample),
            "model_path": str(self.model_path),
            "decisions_path": str(self.decisions_path),
            "training_path": str(self.training_path),
            "local_only": True,
            # Shadow mode / promotion gate metrics
            "mode": mode_status.get("mode") or mode_metrics.get("mode") or getattr(self.twin, "mode", "shadow"),
            "authority": mode_status.get("authority") or mode_metrics.get("authority"),
            "twin_agreement_pct": durable.get("agreement_pct", mode_metrics.get("agreement_pct")),
            "false_positives": durable.get("false_positives"),
            "false_positive_pct": durable.get("false_positive_pct"),
            "false_negatives": durable.get("false_negatives"),
            "risk_flags_caught": durable.get("risk_flags_caught"),
            "risk_flags_caught_pct": durable.get("risk_flags_caught_pct"),
            "constitution_adherence_pct": durable.get("constitution_adherence_pct"),
            "mode_samples": durable.get("samples"),
            "mode_readiness": mode_status.get("readiness"),
            "mode_metrics": durable,
        }

    def promote_mode(self, target: str) -> dict[str, Any]:
        """Fail-closed twin mode promotion via gate."""
        if not hasattr(self.twin, "try_promote"):
            return {"promoted": False, "reason": "twin_missing_try_promote"}
        return self.twin.try_promote(target)

    def mode_status(self) -> dict[str, Any]:
        if hasattr(self.twin, "mode_status"):
            return self.twin.mode_status()
        return {"mode": getattr(self.twin, "mode", "shadow")}
