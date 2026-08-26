"""Base training curriculum session for TwinTrainingService (Birth-ready).

App-only forced-choice flow. On complete: RLHF + birth_ready flag + training event.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lumina_core.evolution.steve_values_registry import SteveValueRecord
from lumina_core.evolution.twin_base_curriculum import (
    BASE_CURRICULUM_VERSION,
    build_base_curriculum,
    get_question,
    question_count,
)
from lumina_core.evolution.twin_curriculum_types import (
    TwinMcQuestion,
    mc_answer_to_steve_fields,
)

_DEFAULT_SESSION = Path("state/twin_base_training.json")
_DEFAULT_READINESS = Path("state/twin_birth_readiness.json")


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_birth_readiness(path: Path | str = _DEFAULT_READINESS) -> dict[str, Any]:
    p = Path(path)
    if not p.exists():
        return {
            "base_trained": False,
            "birth_ready": False,
            "curriculum_version": BASE_CURRICULUM_VERSION,
            "question_count": 0,
            "completed_at": None,
        }
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return {"base_trained": False, "birth_ready": False}
        return raw
    except (OSError, json.JSONDecodeError):
        return {"base_trained": False, "birth_ready": False}


def is_twin_birth_ready(
    path: Path | str = _DEFAULT_READINESS,
    *,
    required_version: str = BASE_CURRICULUM_VERSION,
) -> bool:
    """True only when base completed on the *current* curriculum version (fail-closed)."""
    raw = load_birth_readiness(path)
    if not bool(raw.get("base_trained") or raw.get("birth_ready")):
        return False
    # Missing or stale version → not ready (base_v4 REAL-conscience requires retrain)
    ver = str(raw.get("curriculum_version") or "").strip()
    if ver != str(required_version):
        return False
    return True


def write_birth_readiness(
    path: Path | str,
    *,
    base_trained: bool,
    question_count: int,
    curriculum_version: str = BASE_CURRICULUM_VERSION,
    session_id: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "base_trained": bool(base_trained),
        "birth_ready": bool(base_trained),
        "curriculum_version": curriculum_version,
        "question_count": int(question_count),
        "completed_at": _utcnow() if base_trained else None,
        "session_id": session_id,
        "local_only": True,
    }
    if extra:
        payload.update(extra)
    p.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return payload


class TwinBaseTrainingMixin:
    """Mixin: start/next/submit/complete base curriculum (app-only)."""

    # Overridable paths on service instance
    base_session_path: Path = _DEFAULT_SESSION
    birth_readiness_path: Path = _DEFAULT_READINESS

    def _base_session_file(self) -> Path:
        return Path(getattr(self, "base_session_path", _DEFAULT_SESSION))

    def _readiness_file(self) -> Path:
        return Path(getattr(self, "birth_readiness_path", _DEFAULT_READINESS))

    def _load_base_session(self) -> dict[str, Any]:
        path = self._base_session_file()
        if not path.exists():
            return {}
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            return raw if isinstance(raw, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}

    def _save_base_session(self, session: dict[str, Any]) -> None:
        path = self._base_session_file()
        path.parent.mkdir(parents=True, exist_ok=True)
        session = {**session, "updated_at": _utcnow()}
        path.write_text(json.dumps(session, indent=2, ensure_ascii=False), encoding="utf-8")

    def readiness(self) -> dict[str, Any]:
        """Birth-ready flag + base progress for Phase Hub / API."""
        ready_raw = load_birth_readiness(self._readiness_file())
        session = self._load_base_session()
        total = question_count()
        answers_raw = session.get("answers")
        answers: dict[str, Any] = answers_raw if isinstance(answers_raw, dict) else {}
        answered = len(answers)
        if session.get("status") == "completed":
            answered = max(answered, total)
        pct = round(100.0 * answered / max(1, total), 1)
        remaining = max(0, total - answered)
        eta_sec = remaining * 12
        birth_ready = is_twin_birth_ready(self._readiness_file())
        return {
            "base_trained": bool(ready_raw.get("base_trained") or birth_ready),
            "birth_ready": birth_ready,
            "curriculum_version": BASE_CURRICULUM_VERSION,
            "readiness_version": ready_raw.get("curriculum_version"),
            "question_count_total": total,
            "question_count_answered": answered,
            "base_training_completion_pct": pct if session or birth_ready else 0.0,
            "estimated_seconds_left": 0 if birth_ready else eta_sec,
            "session_status": session.get("status") or ("completed" if birth_ready else "none"),
            "session_id": session.get("session_id"),
            "completed_at": ready_raw.get("completed_at"),
            "local_only": True,
        }

    def start_base_training(self, *, force_restart: bool = False) -> dict[str, Any]:
        """Start or resume app-only base curriculum."""
        existing = self._load_base_session()
        if (
            not force_restart
            and existing.get("status") == "in_progress"
            and existing.get("curriculum_version") == BASE_CURRICULUM_VERSION
        ):
            return self.base_training_status()

        if not force_restart and is_twin_birth_ready(self._readiness_file()):
            return {
                **self.readiness(),
                "started": False,
                "reason": "already_base_trained",
                "message": "Base training already complete. Use force_restart to retrain.",
            }

        qs = build_base_curriculum()
        session = {
            "session_id": str(uuid.uuid4()),
            "status": "in_progress",
            "curriculum_version": BASE_CURRICULUM_VERSION,
            "started_at": _utcnow(),
            "channel_policy": "app_only",
            "question_ids": [q.question_id for q in qs],
            "answers": {},
            "current_index": 0,
        }
        self._save_base_session(session)
        # Fast path: return first question without re-reading session + rebuilding status.
        first = qs[0].to_dict() if qs else None
        total = len(qs)
        ready = self.readiness()
        return {
            **ready,
            "started": True,
            "active": True,
            "session_id": session["session_id"],
            "status": "in_progress",
            "total": total,
            "answered": 0,
            "current_index": 0,
            "progress_pct": 0.0,
            "estimated_seconds_left": total * 12,
            "question": first,
            "channel_policy": "app_only",
            "telegram_disabled": True,
            "local_only": True,
        }

    def base_training_status(self) -> dict[str, Any]:
        session = self._load_base_session()
        readiness = self.readiness()
        if not session:
            return {**readiness, "active": False, "question": None}
        total = len(session.get("question_ids") or [])
        answers_raw = session.get("answers")
        answers: dict[str, Any] = answers_raw if isinstance(answers_raw, dict) else {}
        idx = int(session.get("current_index") or 0)
        answered = len(answers)
        # Advance index past answered
        qids = list(session.get("question_ids") or [])
        while idx < len(qids) and qids[idx] in answers:
            idx += 1
        question = None
        if idx < len(qids) and session.get("status") == "in_progress":
            q = get_question(str(qids[idx]))
            question = q.to_dict() if q else None
        pct = round(100.0 * answered / max(1, total), 1)
        return {
            **readiness,
            "active": session.get("status") == "in_progress",
            "session_id": session.get("session_id"),
            "status": session.get("status"),
            "total": total,
            "answered": answered,
            "current_index": idx,
            "progress_pct": pct,
            "estimated_seconds_left": max(0, (total - answered) * 12),
            "question": question,
            "channel_policy": "app_only",
            "telegram_disabled": True,
            "local_only": True,
        }

    def next_base_question(self) -> dict[str, Any]:
        return self.base_training_status()

    def submit_base_answer(
        self,
        *,
        question_id: str,
        choice_id: str,
        clarify: str = "",
        session_id: str | None = None,
        train_now: bool = True,
    ) -> dict[str, Any]:
        session = self._load_base_session()
        if not session or session.get("status") != "in_progress":
            raise ValueError("no_active_base_session")
        if session_id and session.get("session_id") != session_id:
            raise ValueError("session_id_mismatch")
        if session.get("channel_policy") != "app_only":
            # Hard invariant: base is app-only (never Telegram)
            raise ValueError("base_training_app_only")
        # Defense: never route base answers through dual-channel pending store
        if str(getattr(self, "_force_telegram_base", "") or ""):
            raise ValueError("base_training_telegram_forbidden")

        qid = str(question_id or "").strip()
        q = get_question(qid)
        if q is None:
            raise ValueError(f"unknown_question_id: {qid}")
        qids = list(session.get("question_ids") or [])
        if qid not in qids:
            raise ValueError("question_not_in_session")

        answers = dict(session.get("answers") or {})
        if qid in answers:
            return {
                "recorded": True,
                "already_answered": True,
                "question_id": qid,
                "answer": answers[qid],
                "progress": self.base_training_status(),
            }

        choice = q.choice_by_id(choice_id)
        if choice is None:
            raise ValueError(f"invalid_choice_id: {choice_id}")

        record = self._record_mc_label(q, choice_id=choice_id, clarify=clarify, train_now=train_now)
        answers[qid] = {
            "choice_id": choice.id,
            "value_signal": choice.value_signal,
            "clarify": str(clarify or "").strip()[:280],
            "answered_at": _utcnow(),
            "label": record.get("label"),
        }
        # Advance index
        idx = qids.index(qid)
        next_idx = idx + 1
        session["answers"] = answers
        session["current_index"] = next_idx
        if len(answers) >= len(qids):
            session["status"] = "ready_to_complete"
        self._save_base_session(session)

        return {
            "recorded": True,
            "already_answered": False,
            "question_id": qid,
            "choice_id": choice.id,
            "label": record.get("label"),
            "rlhf": record.get("rlhf"),
            "progress": self.base_training_status(),
            "local_only": True,
        }

    def complete_base_training(self, *, train_batch: bool = True) -> dict[str, Any]:
        session = self._load_base_session()
        if not session:
            raise ValueError("no_base_session")
        qids = list(session.get("question_ids") or [])
        answers = dict(session.get("answers") or {})
        if len(answers) < len(qids):
            missing = [q for q in qids if q not in answers]
            raise ValueError(f"incomplete_base_training missing={missing[:5]}")

        rlhf: dict[str, Any] | None = None
        if train_batch and hasattr(self, "twin") and hasattr(self.twin, "fine_tune_from_registry"):
            try:
                rlhf = self.twin.fine_tune_from_registry(limit=max(50, len(answers) * 2))  # type: ignore[attr-defined]
            except Exception:
                rlhf = {"updated": False, "reason": "fine_tune_failed"}

        session["status"] = "completed"
        session["completed_at"] = _utcnow()
        self._save_base_session(session)

        readiness = write_birth_readiness(
            self._readiness_file(),
            base_trained=True,
            question_count=len(answers),
            curriculum_version=str(session.get("curriculum_version") or BASE_CURRICULUM_VERSION),
            session_id=str(session.get("session_id") or ""),
        )

        # Best-effort bus + monitoring
        self._emit_base_complete(readiness=readiness, rlhf=rlhf, answer_count=len(answers))

        metrics = None
        if hasattr(self, "metrics"):
            try:
                metrics = self.metrics()  # type: ignore[attr-defined]
            except Exception:
                metrics = None

        return {
            "completed": True,
            "birth_ready": True,
            "base_trained": True,
            "readiness": readiness,
            "rlhf": rlhf,
            "metrics": metrics,
            "answered": len(answers),
            "curriculum_version": session.get("curriculum_version"),
            "local_only": True,
            "message": "Twin base training complete — Birth autonomy paths may use high-conf Twin.",
        }

    def _record_mc_label(
        self,
        question: TwinMcQuestion,
        *,
        choice_id: str,
        clarify: str = "",
        train_now: bool = True,
    ) -> dict[str, Any]:
        vraag, antwoord, conf = mc_answer_to_steve_fields(
            question, choice_id=choice_id, clarify=clarify
        )
        record = SteveValueRecord.create(
            vraag=vraag,
            steve_antwoord=antwoord,
            context_dna_hash=question.context_dna_hash,
            confidence_score=conf,
        )
        self.registry.append(record)  # type: ignore[attr-defined]

        # Map for steve comparison metrics when possible
        from lumina_core.evolution.approval_twin_scoring import ApprovalTwinScoringMixin

        label_score = ApprovalTwinScoringMixin._label_from_answer(antwoord)
        steve_approve = label_score is not None and label_score >= 0.6
        if hasattr(self, "twin") and hasattr(self.twin, "record_steve_label_comparison"):
            try:
                self.twin.record_steve_label_comparison(  # type: ignore[attr-defined]
                    twin_recommendation=None,
                    steve_approve=steve_approve,
                    risk_flags=[],
                    dna_hash=question.context_dna_hash,
                    twin_confidence=None,
                    steve_label=antwoord[:64],
                )
            except Exception:
                pass

        rlhf = None
        if train_now and hasattr(self, "twin") and hasattr(self.twin, "rlhf_light_update"):
            rlhf = self.twin.rlhf_light_update(records=[record])  # type: ignore[attr-defined]

        return {
            "record": asdict(record),
            "label": antwoord,
            "rlhf": rlhf,
        }

    def _emit_base_complete(
        self,
        *,
        readiness: dict[str, Any],
        rlhf: dict[str, Any] | None,
        answer_count: int,
    ) -> None:
        try:
            from lumina_core.logging_utils import record_twin_training_metrics_monitoring

            record_twin_training_metrics_monitoring(
                avg_prediction_error=float((rlhf or {}).get("avg_prediction_error") or 0.0),
                reward=float((rlhf or {}).get("reward") or 0.0),
                training_steps=int((rlhf or {}).get("training_steps") or 0),
            )
        except Exception:
            pass
        # Append readiness marker to training JSONL (best-effort audit)
        try:
            import json
            from pathlib import Path

            train_path = Path(getattr(self, "training_path", Path("state/monitoring_twin_training.jsonl")))
            train_path.parent.mkdir(parents=True, exist_ok=True)
            with train_path.open("a", encoding="utf-8") as fh:
                fh.write(
                    json.dumps(
                        {
                            "event": "twin.base_training_complete",
                            "records_processed": int(answer_count),
                            "base_trained": True,
                            "birth_ready": True,
                            "curriculum_version": readiness.get("curriculum_version"),
                            "avg_prediction_error": (rlhf or {}).get("avg_prediction_error"),
                            "reward": (rlhf or {}).get("reward"),
                            "training_steps": (rlhf or {}).get("training_steps"),
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )
        except Exception:
            pass
        twin = getattr(self, "twin", None)
        if twin is not None and hasattr(twin, "_publish_training_update"):
            try:
                twin._publish_training_update(  # noqa: SLF001
                    result=dict(rlhf or {}),
                    records_len=int(answer_count),
                )
            except Exception:
                pass
