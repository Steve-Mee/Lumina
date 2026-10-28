"""Every evaluated config increments the trial count. It cannot be passed in lower."""

from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from lumina_research.validation.audit import write_event


class TrialRegistryError(ValueError):
    """Illegal attempt to lower or skip the trial count."""


@dataclass(frozen=True, slots=True)
class TrialRecord:
    trial_id: int
    config_id: str
    agent_id: str
    metrics: Mapping[str, object]


class TrialRegistry:
    """Monotonic trial counter. There is no public decrement or overwrite."""

    def __init_subclass__(cls) -> None:
        raise TypeError("TrialRegistry cannot be subclassed")

    def __init__(self, audit_path: Path) -> None:
        self._audit_path = audit_path
        self._count = 0
        self._records: list[TrialRecord] = []
        self._lock = threading.Lock()

    @property
    def n_trials(self) -> int:
        return self._count

    @property
    def audit_path(self) -> Path:
        return self._audit_path

    def record(
        self,
        *,
        config_id: str,
        agent_id: str,
        metrics: Mapping[str, object],
        **kwargs: object,
    ) -> int:
        if kwargs:
            raise TypeError("n_trials cannot be passed in; skip flags are forbidden")
        if not config_id:
            raise TrialRegistryError("config_id is required")
        if not agent_id:
            raise TrialRegistryError("agent_id is required")
        with self._lock:
            next_id = self._count + 1
            snapshot = {
                "trial_id": next_id,
                "config_id": config_id,
                "n_trials": next_id,
                **{str(key): value for key, value in metrics.items()},
            }
            write_event(
                path=self._audit_path,
                agent_id=agent_id,
                event="trial",
                metrics=snapshot,
            )
            self._count = next_id
            self._records.append(
                TrialRecord(
                    trial_id=next_id,
                    config_id=config_id,
                    agent_id=agent_id,
                    metrics=dict(metrics),
                )
            )
            return self._count

    def records(self) -> tuple[TrialRecord, ...]:
        return tuple(self._records)

    def __setattr__(self, name: str, value: object) -> None:
        if name == "n_trials":
            raise AttributeError("n_trials is monotonic and comes only from record()")
        object.__setattr__(self, name, value)
