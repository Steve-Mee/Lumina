"""Typed EventBus / Blackboard payload contracts (runtime).

Canonical re-export surface: ``lumina_core.agent_orchestration.schemas``.
"""
from __future__ import annotations


from pydantic import BaseModel, ConfigDict, Field

class RuntimeConfigReloaded(BaseModel):
    """Published after a successful runtime config hot-reload."""

    model_config = ConfigDict(extra="forbid")

    config_path: str
    changed_sections: list[str] = Field(default_factory=list)
    timestamp: str = ""


class RuntimeConfigReloadFailed(BaseModel):
    """Published when runtime config hot-reload is rejected (validation or immutable fields)."""

    model_config = ConfigDict(extra="forbid")

    config_path: str
    reason: str
    validation_errors: list[str] = Field(default_factory=list)
    immutable_fields: list[str] = Field(default_factory=list)
    timestamp: str = ""


class RuntimeConfigReloadRequested(BaseModel):
    """In-process nudge to reload config from disk without waiting for file watcher debounce."""

    model_config = ConfigDict(extra="forbid")

    config_path: str = ""
    source: str = "manual"
    timestamp: str = ""

