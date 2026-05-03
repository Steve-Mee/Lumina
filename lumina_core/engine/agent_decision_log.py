from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from lumina_core.audit import AuditChainError, get_audit_logger

logger = logging.getLogger(__name__)


class AgentDecisionLogChainError(RuntimeError):
    """Raised when the immutable decision hash chain cannot be read in REAL mode."""


@dataclass(slots=True)
class AgentDecisionLog:
    """Immutable append-only decision log with hash-chain integrity."""

    path: Path = Path("state/agent_decision_log.jsonl")
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

    def __post_init__(self) -> None:
        self._lock = threading.Lock()
        self.path = Path(self.path)
        get_audit_logger().register_stream("agent_decision", self.path)

    def log_decision(
        self,
        *,
        agent_id: str,
        raw_input: dict[str, Any],
        raw_output: dict[str, Any],
        confidence: float,
        policy_outcome: str,
        decision_context_id: str,
        model_version: str = "unknown",
        prompt_text: str = "",
        prompt_hash: str | None = None,
        trade_record_id: str | None = None,
        evolution_log_hash: str | None = None,
        prompt_version: str = "unknown-prompt",
        policy_version: str = "unknown-policy",
        provider_route: list[str] | None = None,
        calibration_factor: float = 1.0,
        config_snapshot_hash: str | None = None,
        is_real_mode: bool = False,
    ) -> dict[str, Any]:
        ts = datetime.now(timezone.utc).isoformat()
        prompt_fingerprint = prompt_hash or self._sha256(
            prompt_text or json.dumps(raw_input, sort_keys=True, ensure_ascii=True)
        )
        config_fingerprint = str(config_snapshot_hash or self._default_config_snapshot_hash())

        payload = {
            "timestamp": ts,
            "agent_id": str(agent_id),
            "prompt_hash": str(prompt_fingerprint),
            "model_version": str(model_version),
            "raw_input": raw_input,
            "raw_output": raw_output,
            "confidence": float(confidence),
            "policy_outcome": str(policy_outcome),
            "decision_context_id": str(decision_context_id),
            "trade_record_id": trade_record_id,
            "evolution_log_hash": evolution_log_hash,
            "lineage": {
                "model_identifier": str(model_version),
                "prompt_version": str(prompt_version),
                "prompt_hash": str(prompt_fingerprint),
                "config_snapshot_hash": config_fingerprint,
                "policy_version": str(policy_version),
                "provider_route": [str(item) for item in (provider_route or ["unknown-provider"])],
                "calibration_factor": max(0.01, float(calibration_factor or 1.0)),
            },
            "config_snapshot_hash": config_fingerprint,
            "prev_hash": "GENESIS",
            "log_version": "v1",
        }
        return self._append_with_consistent_prev(payload, is_real_mode=bool(is_real_mode))

    def _append_with_consistent_prev(self, payload: dict[str, Any], *, is_real_mode: bool) -> dict[str, Any]:
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            try:
                return get_audit_logger().append(
                    stream="agent_decision",
                    payload=payload,
                    path=self.path,
                    mode="real" if is_real_mode else "sim",
                    actor_id=str(payload.get("agent_id", "agent_decision_log")),
                    severity="info",
                    include_legacy_hash=True,
                    fail_closed_real=bool(is_real_mode),
                )
            except AuditChainError as exc:
                logger.exception("AgentDecisionLog failed to append in REAL mode at %s", self.path)
                raise AgentDecisionLogChainError(f"Decision log chain unreadable at {self.path}") from exc

    def _last_hash(self) -> str:
        with self._lock:
            return self._last_hash_unlocked(is_real_mode=False)

    def _last_hash_unlocked(self, *, is_real_mode: bool) -> str:
        if not self.path.exists():
            return "GENESIS"
        try:
            last_line = ""
            with self.path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    if line.strip():
                        last_line = line.strip()
            if not last_line:
                return "GENESIS"
            parsed = json.loads(last_line)
            return str(parsed.get("hash", "GENESIS"))
        except Exception as exc:
            logger.exception("AgentDecisionLog failed to load previous hash from %s", self.path)
            if is_real_mode:
                raise AgentDecisionLogChainError(f"Decision log chain unreadable at {self.path}") from exc
            return "GENESIS"

    @staticmethod
    def _sha256(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    def _default_config_snapshot_hash(self) -> str:
        config_path = Path(os.getenv("LUMINA_CONFIG", "config.yaml"))
        if not config_path.exists():
            return "CONFIG_MISSING"
        try:
            raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
            canonical = json.dumps(raw if isinstance(raw, dict) else {"raw": raw}, sort_keys=True, ensure_ascii=True)
            return self._sha256(canonical)
        except Exception:
            logger.exception("AgentDecisionLog failed to parse config snapshot at %s", config_path)
            try:
                return self._sha256(config_path.read_text(encoding="utf-8", errors="replace"))
            except Exception:
                logger.exception("AgentDecisionLog failed to read config snapshot fallback at %s", config_path)
                return "CONFIG_UNREADABLE"
