"""Every evaluated config increments the trial count. It cannot be passed in lower."""

from __future__ import annotations

import json
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
        self._records: tuple[TrialRecord, ...] = ()
        self._lock = threading.Lock()

    @property
    def n_trials(self) -> int:
        """High-water of in-memory records and durable trial events on the audit path.

        Lowering the in-memory counter cannot deflate N below what was already logged.
        """
        return max(len(self._records), _count_trial_events(self._audit_path))

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
            next_id = self.n_trials + 1
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
            object.__setattr__(
                self,
                "_records",
                self._records
                + (
                    TrialRecord(
                        trial_id=next_id,
                        config_id=config_id,
                        agent_id=agent_id,
                        metrics=dict(metrics),
                    ),
                ),
            )
            return self.n_trials

    def records(self) -> tuple[TrialRecord, ...]:
        return self._records

    def __setattr__(self, name: str, value: object) -> None:
        if name in {"n_trials", "_records"} and name in self.__dict__:
            raise AttributeError("n_trials is monotonic and comes only from record()")
        object.__setattr__(self, name, value)


def _count_trial_events(path: Path) -> int:
    if not path.is_file():
        return 0
    count = 0
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                text = line.strip()
                if not text:
                    continue
                payload = json.loads(text)
                if payload.get("event") == "trial":
                    count += 1
    except json.JSONDecodeError as exc:
        raise TrialRegistryError("audit log corrupt; trial count cannot be lowered") from exc
    except OSError as exc:
        raise TrialRegistryError("audit log unreadable; trial count cannot be lowered") from exc
    return count
