"""Smart setup dataclasses and progress constants."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal

SetupProgressCallback = Callable[["SetupProgressEvent"], None]
ProgressLevel = Literal["info", "warning", "error"]

OLLAMA_INSTALL_TIMEOUT_SEC = 1800
OLLAMA_PULL_TIMEOUT_SEC = 7200
OUTPUT_TAIL_CHARS = 1200

PROGRESS_PERCENT: dict[str, int] = {
    "detect": 5,
    "launcher_deps": 20,
    "runtime_deps": 40,
    "ollama": 55,
    "ollama_verify": 58,
    "model_pull": 70,
    "model_pull_progress": 70,
    "extra_models": 75,
    "skipped_vllm_provider": 70,
    "config": 85,
    "complete": 100,
    "failed": 100,
}


@dataclass(slots=True)
class SetupProgressEvent:
    phase: str
    message: str
    percent: int | None = None
    level: ProgressLevel = "info"
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class SmartSetupOptions:
    install_ollama: bool = True
    download_recommended_model: bool = True
    force_high_tier: bool = False
    pull_extra_models: bool = False
    graceful_degrade: bool = True


@dataclass(slots=True)
class SubprocessStepResult:
    name: str
    success: bool
    message: str
    command: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "success": self.success,
            "message": self.message,
            "command": self.command,
        }


@dataclass(slots=True)
class SmartSetupResult:
    success: bool
    steps: list[dict[str, Any]]
    status: dict[str, Any]
    degraded: bool = False
    warnings: list[str] = field(default_factory=list)
    manual_steps: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "steps": self.steps,
            "status": self.status,
            "degraded": self.degraded,
            "warnings": list(self.warnings),
            "manual_steps": list(self.manual_steps),
        }
