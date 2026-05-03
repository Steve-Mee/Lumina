from __future__ import annotations

import hashlib
import json
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Protocol

from lumina_core.audit import get_audit_logger

logger = logging.getLogger(__name__)


class EvolutionAuditWriterError(RuntimeError):
    """Raised when evolution audit writes must fail-closed in REAL mode."""


class AuditWriterProtocol(Protocol):
    def append(self, entry: dict[str, Any]) -> None: ...

    def last_hash(self) -> str: ...

    def entries_last_3_days(self) -> list[dict[str, Any]]: ...

    def log_agent_decision(
        self,
        *,
        raw_input: dict[str, Any],
        raw_output: dict[str, Any],
        confidence: float,
        policy_outcome: str,
        decision_context_id: str,
        evolution_log_hash: str | None = None,
    ) -> None: ...


class EvolutionAuditWriter:
    def __init__(
        self,
        *,
        log_path: Path,
        decision_log_provider: Callable[[], Any | None] | None = None,
    ) -> None:
        self.log_path = log_path
        self._decision_log_provider = decision_log_provider
        get_audit_logger().register_stream("evolution_meta", self.log_path)

    def append(self, entry: dict[str, Any]) -> None:
        payload = dict(entry)
        payload["log_version"] = "v1"
        is_real_mode = str(os.getenv("LUMINA_MODE", "sim")).strip().lower() == "real"
        get_audit_logger().append(
            stream="evolution_meta",
            payload=payload,
            path=self.log_path,
            mode="real" if is_real_mode else "sim",
            actor_id="self_evolution_meta_agent",
            severity="info",
            include_legacy_hash=True,
            fail_closed_real=is_real_mode,
        )

    def last_hash(self) -> str:
        try:
            rows = get_audit_logger().tail("evolution_meta", limit=1, path=self.log_path)
            if not rows:
                return "GENESIS"
            return str(rows[-1].get("entry_hash") or rows[-1].get("hash") or "GENESIS")
        except Exception:
            logger.exception("EvolutionAuditWriter failed to read last hash from %s", self.log_path)
            return "GENESIS"

    def entries_last_3_days(self) -> list[dict[str, Any]]:
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(days=3)
        out: list[dict[str, Any]] = []
        try:
            rows = get_audit_logger().tail("evolution_meta", limit=0, path=self.log_path)
            for parsed in rows:
                ts = str(parsed.get("timestamp", ""))
                if not ts:
                    continue
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                if dt >= cutoff:
                    out.append(parsed)
        except Exception:
            logger.exception("EvolutionAuditWriter failed to read last 3 days entries from %s", self.log_path)
            return []
        return out

    def log_agent_decision(
        self,
        *,
        raw_input: dict[str, Any],
        raw_output: dict[str, Any],
        confidence: float,
        policy_outcome: str,
        decision_context_id: str,
        evolution_log_hash: str | None = None,
        is_real_mode: bool | None = None,
    ) -> None:
        decision_log = self._decision_log_provider() if self._decision_log_provider is not None else None
        if decision_log is None or not hasattr(decision_log, "log_decision"):
            return
        resolved_real_mode = (
            bool(is_real_mode)
            if is_real_mode is not None
            else str(os.getenv("LUMINA_MODE", "sim")).strip().lower() == "real"
        )
        try:
            decision_log.log_decision(
                agent_id="SelfEvolutionMetaAgent",
                raw_input=raw_input,
                raw_output=raw_output,
                confidence=float(confidence),
                policy_outcome=policy_outcome,
                decision_context_id=decision_context_id,
                model_version="self-evolution-v51",
                prompt_hash=hashlib.sha256(
                    json.dumps(raw_input, sort_keys=True, ensure_ascii=True).encode("utf-8")
                ).hexdigest(),
                evolution_log_hash=evolution_log_hash,
                prompt_version="self-evolution-v1",
                policy_version="evolution-lifecycle-v1",
                provider_route=["self-evolution-engine"],
                calibration_factor=1.0,
                is_real_mode=resolved_real_mode,
            )
        except Exception as exc:
            logger.exception(
                "EvolutionAuditWriter failed to mirror agent decision (real_mode=%s)",
                resolved_real_mode,
            )
            if resolved_real_mode:
                raise EvolutionAuditWriterError("Evolution decision mirror write failed in REAL mode") from exc
