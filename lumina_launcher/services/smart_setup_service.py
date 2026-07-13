"""
Smart setup orchestration for the Lumina launcher.

Delegates pip/config work to lumina_core.engine.setup_service.SetupService.
Ollama install/pull uses local subprocess helpers with progress and graceful degradation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from lumina_core.adaptive_intelligence import AdaptiveIntelligenceManager
from lumina_core.engine.model_catalog import ModelDescriptor
from lumina_core.engine.setup_service import SetupService
from lumina_launcher.services import ollama_installer, setup_detector, setup_orchestrator
from lumina_launcher.services.setup_compat import HardwareInspector, ModelCatalog, shutil, subprocess
from lumina_launcher.services.setup_schemas import (
    SetupProgressCallback,
    SetupProgressEvent,
    SmartSetupOptions,
    SmartSetupResult,
    SubprocessStepResult,
)
from lumina_launcher.core.workspace_root import resolve_birth_workspace_root  # direct (services reexport deleted)

__all__ = [
    "HardwareInspector",
    "ModelCatalog",
    "SetupProgressCallback",
    "SetupProgressEvent",
    "SmartSetupOptions",
    "SmartSetupResult",
    "SmartSetupService",
    "SubprocessStepResult",
    "shutil",
    "subprocess",
]


class SmartSetupService:
    """Orchestrates first-run detection, intelligence-aware setup, and guided install."""

    def __init__(
        self,
        workspace_root: Path | str | None = None,
        *,
        setup_service: SetupService | None = None,
        intelligence_manager: AdaptiveIntelligenceManager | None = None,
    ) -> None:
        self.workspace_root = resolve_birth_workspace_root(workspace_root)
        self._setup_service = setup_service or SetupService(
            workspace_root=self.workspace_root,
            config_path=self.workspace_root / "config.yaml",
            env_path=self.workspace_root / ".env",
        )
        self._intelligence_manager = intelligence_manager or AdaptiveIntelligenceManager(
            self.workspace_root
        )
        self._setup_config = None

    @property
    def setup_config(self):
        if self._setup_config is None:
            from lumina_launcher.core.setup_config import SetupConfig

            self._setup_config = SetupConfig.from_workspace(self.workspace_root)
        return self._setup_config

    def default_options(self) -> SmartSetupOptions:
        return self.setup_config.to_smart_setup_options()

    def is_first_time(self) -> bool:
        return setup_detector.is_first_time(self)

    def is_intelligence_stack_ready(self) -> bool:
        return setup_detector.is_intelligence_stack_ready(self)

    def get_setup_status(self) -> dict[str, Any]:
        return setup_detector.get_setup_status(self)

    def get_install_instructions(self) -> dict[str, Any]:
        return setup_detector.get_install_instructions(self)

    def run_smart_setup(
        self,
        *,
        on_progress: SetupProgressCallback | None = None,
        options: SmartSetupOptions | None = None,
        mark_complete: bool = False,
    ) -> SmartSetupResult:
        return setup_orchestrator.run_smart_setup(
            self,
            on_progress=on_progress,
            options=options,
            mark_complete=mark_complete,
        )

    def mark_setup_complete(self) -> None:
        setup_orchestrator.mark_setup_complete(self)

    def _install_ollama_subprocess(self) -> tuple[SubprocessStepResult, list[dict[str, Any]]]:
        return ollama_installer.install_ollama_subprocess(self)

    def _verify_ollama_runtime(self) -> SubprocessStepResult:
        return ollama_installer.verify_ollama_runtime(self)

    def _pull_model_subprocess(
        self,
        descriptor: ModelDescriptor,
        *,
        on_progress: SetupProgressCallback | None = None,
    ) -> SubprocessStepResult:
        return ollama_installer.pull_model_subprocess(self, descriptor, on_progress=on_progress)

    def _run_subprocess_step(
        self,
        name: str,
        command: list[str],
        *,
        timeout_sec: int,
        success_message: str,
    ) -> SubprocessStepResult:
        return ollama_installer.run_subprocess_step(
            self, name, command, timeout_sec=timeout_sec, success_message=success_message
        )

    @staticmethod
    def _ollama_on_path() -> bool:
        return setup_detector.ollama_on_path()

    def _manual_steps_for_model(self, ollama_tag: str) -> list[dict[str, Any]]:
        return ollama_installer.manual_steps_for_model(ollama_tag)

    @staticmethod
    def _humanize_failure(phase: str, detail: str, stdout: str, command: str) -> str:
        return ollama_installer.humanize_failure(phase, detail, stdout, command)

    def _complete_run(self, **kwargs: Any) -> SmartSetupResult:
        return setup_orchestrator.complete_run(self, **kwargs)

    def _apply_intelligence_mode(self, force_high: bool) -> None:
        setup_orchestrator.apply_intelligence_mode(self, force_high)

    def _resolve_descriptor(self, intelligence_status: Any, hardware: dict[str, Any]) -> ModelDescriptor:
        return setup_detector.resolve_descriptor(self, intelligence_status, hardware)

    @staticmethod
    def _ollama_model_installed(ollama_tag: str) -> bool:
        return setup_detector.ollama_model_installed(ollama_tag)

    @staticmethod
    def _collect_missing(**kwargs: Any) -> list[str]:
        return setup_detector.collect_missing(**kwargs)

    def _ollama_install_instruction_steps(self) -> list[dict[str, Any]]:
        return setup_detector.ollama_install_instruction_steps()

    def _finalize_run(self, **kwargs: Any) -> SmartSetupResult:
        return setup_orchestrator.finalize_run(self, **kwargs)

    @staticmethod
    def _emit_progress(
        callback: SetupProgressCallback | None,
        *,
        phase: str,
        message: str,
        level: str = "info",
        detail: dict[str, Any] | None = None,
    ) -> None:
        from lumina_launcher.services.setup_progress import emit_progress

        emit_progress(
            callback, phase=phase, message=message, level=level, detail=detail
        )
