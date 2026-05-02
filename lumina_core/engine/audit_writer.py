from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Protocol


class AuditWriterProtocol(Protocol):
    def append(self, entry: dict[str, Any]) -> None:
        ...

    def last_hash(self) -> str:
        ...

    def entries_last_3_days(self) -> list[dict[str, Any]]:
        ...

    def log_agent_decision(
        self,
        *,
        raw_input: dict[str, Any],
        raw_output: dict[str, Any],
        confidence: float,
        policy_outcome: str,
        decision_context_id: str,
        evolution_log_hash: str | None = None,
    ) -> None:
        ...


class EvolutionAuditWriter:
    def __init__(
        self,
        *,
        log_path: Path,
        decision_log_provider: Callable[[], Any | None] | None = None,
    ) -> None:
        self.log_path = log_path
        self._decision_log_provider = decision_log_provider

    def append(self, entry: dict[str, Any]) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        prev_hash = self.last_hash()
        payload = dict(entry)
        payload["prev_hash"] = prev_hash
        payload["log_version"] = "v1"
        canonical = json.dumps(payload, sort_keys=True, ensure_ascii=True)
        payload_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        payload["hash"] = payload_hash
        with self.log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")

    def last_hash(self) -> str:
        if not self.log_path.exists():
            return "GENESIS"
        try:
            with self.log_path.open("r", encoding="utf-8") as handle:
                lines = [line.strip() for line in handle if line.strip()]
            if not lines:
                return "GENESIS"
            last = json.loads(lines[-1])
            return str(last.get("hash", "GENESIS"))
        except Exception:
            return "GENESIS"

    def entries_last_3_days(self) -> list[dict[str, Any]]:
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(days=3)
        if not self.log_path.exists():
            return []
        out: list[dict[str, Any]] = []
        try:
            with self.log_path.open("r", encoding="utf-8") as handle:
                for raw in handle:
                    raw = raw.strip()
                    if not raw:
                        continue
                    parsed = json.loads(raw)
                    ts = str(parsed.get("timestamp", ""))
                    if not ts:
                        continue
                    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    if dt >= cutoff:
                        out.append(parsed)
        except Exception:
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
    ) -> None:
        decision_log = self._decision_log_provider() if self._decision_log_provider is not None else None
        if decision_log is None or not hasattr(decision_log, "log_decision"):
            return
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
            )
        except Exception:
            return
