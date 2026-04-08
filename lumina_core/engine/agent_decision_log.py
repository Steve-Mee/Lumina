from __future__ import annotations

import hashlib
import json
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class AgentDecisionLog:
    """Immutable append-only decision log with hash-chain integrity."""

    path: Path = Path("state/agent_decision_log.jsonl")
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

    def __post_init__(self) -> None:
        self._lock = threading.Lock()

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
    ) -> dict[str, Any]:
        ts = datetime.now(timezone.utc).isoformat()
        prompt_fingerprint = prompt_hash or self._sha256(prompt_text or json.dumps(raw_input, sort_keys=True, ensure_ascii=True))
        prev_hash = self._last_hash()

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
            "prev_hash": prev_hash,
            "log_version": "v1",
        }
        canonical = json.dumps(payload, sort_keys=True, ensure_ascii=True)
        payload["hash"] = self._sha256(canonical)

        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(payload, ensure_ascii=False) + "\n")

        return payload

    def _last_hash(self) -> str:
        if not self.path.exists():
            return "GENESIS"
        with self._lock:
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
            except Exception:
                return "GENESIS"

    @staticmethod
    def _sha256(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()
