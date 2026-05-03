from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


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
        previous = "GENESIS"
        errors: list[str] = []
        checked = 0
        for idx, entry in enumerate(entries):
            checked += 1
            expected_prev = str(entry.get("prev_hash", ""))
            if expected_prev != previous:
                errors.append(f"entry[{idx}] prev_hash mismatch")
            provided_entry_hash = str(entry.get("entry_hash", ""))
            if provided_entry_hash:
                payload = {k: v for k, v in dict(entry).items() if k not in {"prev_hash", "entry_hash", "hash"}}
                canonical = json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
                computed_hash = hashlib.sha256(f"{expected_prev}|{canonical}".encode("utf-8")).hexdigest()
                if provided_entry_hash != computed_hash:
                    errors.append(f"entry[{idx}] entry_hash mismatch")
                previous = provided_entry_hash or previous
                continue

            provided_hash = str(entry.get("hash", ""))
            payload = dict(entry)
            payload.pop("hash", None)
            canonical = json.dumps(payload, sort_keys=True, ensure_ascii=True)
            computed_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
            if provided_hash != computed_hash:
                errors.append(f"entry[{idx}] hash mismatch")
            previous = provided_hash or previous

        return {
            "valid": len(errors) == 0,
            "checked": checked,
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
