from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from lumina_core.audit import validate_hash_chain

@dataclass(slots=True)
class DecisionReplayValidator:
    path: Path = Path("state/agent_decision_log.jsonl")

    def _load_entries(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        entries: list[dict[str, Any]] = []
        with self.path.open("r", encoding="utf-8") as handle:
            for raw in handle:
                raw = raw.strip()
                if not raw:
                    continue
                parsed = json.loads(raw)
                if isinstance(parsed, dict):
                    entries.append(parsed)
        return entries

    def verify_hash_chain(self) -> dict[str, Any]:
        entries = self._load_entries()
        ok, message = validate_hash_chain(self.path)
        errors: list[str] = [] if ok else [message]
        return {
            "valid": ok,
            "checked": len(entries),
            "errors": errors,
        }

    def verify_lineage(self) -> dict[str, Any]:
        entries = self._load_entries()
        required = [
            "model_identifier",
            "prompt_version",
            "prompt_hash",
            "policy_version",
            "provider_route",
            "calibration_factor",
        ]
        violations: list[dict[str, Any]] = []
        for idx, entry in enumerate(entries):
            lineage = entry.get("lineage", {}) if isinstance(entry.get("lineage"), dict) else {}
            missing = [name for name in required if name not in lineage]
            if missing:
                violations.append({"index": idx, "missing": missing})

        return {
            "valid": len(violations) == 0,
            "checked": len(entries),
            "violations": violations,
        }
