from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lumina_core.state.state_manager import safe_append_jsonl


@dataclass(slots=True)
class EvolutionLifecycleManager:
    path: Path = Path("state/evolution_lifecycle.jsonl")

    def _append(self, payload: dict[str, Any]) -> None:
        safe_append_jsonl(self.path, payload, hash_chain=False)

    def create_version(self, *, parent_version_id: str | None, metadata: dict[str, Any] | None = None) -> str:
        version_id = f"evo-{uuid.uuid4()}"
        self.transition(
            version_id=version_id,
            state="proposed",
            parent_version_id=parent_version_id,
            metadata=metadata or {},
            gates={},
        )
        return version_id

    def transition(
        self,
        *,
        version_id: str,
        state: str,
        parent_version_id: str | None,
        metadata: dict[str, Any],
        gates: dict[str, Any],
    ) -> dict[str, Any]:
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "version_id": version_id,
            "parent_version_id": parent_version_id,
            "state": state,
            "metadata": metadata,
            "gates": gates,
        }
        self._append(record)
        return record
