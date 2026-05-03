from __future__ import annotations

import hashlib
import json
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Protocol

from lumina_core.audit import get_audit_logger
from lumina_core.fault import FaultDomain, FaultPolicy

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
        strict_real_mode = is_real_mode and not bool(payload.get("dry_run", False))
        try:
            get_audit_logger().append(
                stream="evolution_meta",
                payload=payload,
                path=self.log_path,
                mode="real" if is_real_mode else "sim",
                actor_id="self_evolution_meta_agent",
                severity="info",
                fail_closed_real=strict_real_mode,
            )
        except Exception as exc:
            # Fail-closed in REAL remains the default, but if the file is already
            # chain-corrupt we quarantine it once and retry append on a fresh stream.
            if self.log_path.exists() and "Audit chain invalid" in str(exc):
                try:
                    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
                    quarantine_path = self.log_path.with_name(f"{self.log_path.name}.corrupt.{stamp}")
                    self.log_path.replace(quarantine_path)
                    logger.error(
                        "Evolution audit chain corrupt; quarantined file to %s and retrying append",
                        quarantine_path,
                    )
                    get_audit_logger().append(
                        stream="evolution_meta",
                        payload=payload,
                        path=self.log_path,
                        mode="real" if is_real_mode else "sim",
                        actor_id="self_evolution_meta_agent",
                        severity="info",
                        fail_closed_real=strict_real_mode,
                    )
                    return
                except Exception:
                    logger.exception("EvolutionAuditWriter quarantine-retry failed")
            if strict_real_mode:
                FaultPolicy.handle(
                    domain=FaultDomain.EVOLUTION_AUDIT,
                    operation="append_evolution_meta",
                    exc=exc,
                    is_real_mode=True,
                    fault_cls=EvolutionAuditWriterError,
                    message="EvolutionAuditWriter failed to append evolution meta audit entry",
                    context={"path": str(self.log_path)},
                    logger_obj=logger,
                )
                return
            logger.warning("EvolutionAuditWriter append skipped in SIM due to audit chain issue: %s", exc)

    def last_hash(self) -> str:
        try:
            rows = get_audit_logger().tail("evolution_meta", limit=1, path=self.log_path)
            if not rows:
                return "GENESIS"
            return str(rows[-1].get("entry_hash") or "GENESIS")
        except (OSError, TypeError, ValueError) as exc:
            FaultPolicy.handle(
                domain=FaultDomain.EVOLUTION_AUDIT,
                operation="read_last_hash",
                exc=exc,
                is_real_mode=False,
                message=f"EvolutionAuditWriter failed to read last hash from {self.log_path}",
                context={"path": str(self.log_path)},
                logger_obj=logger,
            )
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
        except (OSError, TypeError, ValueError) as exc:
            FaultPolicy.handle(
                domain=FaultDomain.EVOLUTION_AUDIT,
                operation="read_recent_entries",
                exc=exc,
                is_real_mode=False,
                message=f"EvolutionAuditWriter failed to read last 3 days entries from {self.log_path}",
                context={"path": str(self.log_path)},
                logger_obj=logger,
            )
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
        except (RuntimeError, ValueError, TypeError, OSError) as exc:
            FaultPolicy.handle(
                domain=FaultDomain.EVOLUTION_AUDIT,
                operation="mirror_agent_decision",
                exc=exc,
                is_real_mode=resolved_real_mode,
                fault_cls=EvolutionAuditWriterError,
                message="EvolutionAuditWriter failed to mirror agent decision",
                context={"path": str(self.log_path), "is_real_mode": resolved_real_mode},
                logger_obj=logger,
            )
