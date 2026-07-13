"""One-shot mechanical split of lumina_launcher/services/smart_setup_service.py."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "lumina_launcher" / "services" / "smart_setup_service.py"
SERVICES = ROOT / "lumina_launcher" / "services"


def _slice(lines: list[str], start: int, end: int) -> str:
    return "".join(lines[start - 1 : end])


def main() -> None:
    lines = SRC.read_text(encoding="utf-8").splitlines(keepends=True)

    schemas = '''"""Smart setup dataclasses and progress constants."""

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
'''
    (SERVICES / "setup_schemas.py").write_text(schemas, encoding="utf-8")

    compat = '''"""Re-exported deps for smart_setup monkeypatch compatibility in tests."""

from __future__ import annotations

import shutil
import subprocess

from lumina_core.engine.hardware_inspector import HardwareInspector
from lumina_core.engine.model_catalog import ModelCatalog

__all__ = ["HardwareInspector", "ModelCatalog", "shutil", "subprocess"]
'''
    (SERVICES / "setup_compat.py").write_text(compat, encoding="utf-8")

    detector_header = '''"""First-run detection, status probes, and install instruction builders."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Any

from lumina_core.adaptive_intelligence import AdaptiveIntelligenceStatus
from lumina_core.engine.model_catalog import ModelDescriptor
from lumina_core.engine.ollama_model_resolve import resolve_ollama_model_tag
from lumina_core.logging_utils import get_logger
from lumina_launcher.services.setup_compat import ModelCatalog, shutil

if TYPE_CHECKING:
    from lumina_launcher.services.smart_setup_service import SmartSetupService

logger = get_logger(__name__)


def is_first_time(service: SmartSetupService) -> bool:
    first_time = not service._setup_service.is_setup_complete()
    logger.debug("smart_setup.first_time complete=%s", not first_time)
    return first_time


def is_intelligence_stack_ready(service: SmartSetupService) -> bool:
    status = get_setup_status(service)
    stack_missing = [item for item in status.get("missing", []) if item != "setup_complete"]
    if not stack_missing:
        return True
    loaded = service._setup_service.load_status()
    return bool(loaded.get("smart_setup")) and not stack_missing


def get_setup_status(service: SmartSetupService) -> dict[str, Any]:
'''
    detector_body = _slice(lines, 155, 188)
    detector_body = detector_body.replace("self.", "service.")
    detector_mid = '''

def get_install_instructions(service: SmartSetupService) -> dict[str, Any]:
'''
    detector_body2 = _slice(lines, 191, 268)
    detector_body2 = detector_body2.replace("self.", "service.")
    detector_tail = '''

def resolve_descriptor(
    service: SmartSetupService,
    intelligence_status: AdaptiveIntelligenceStatus,
    hardware: dict[str, Any],
) -> ModelDescriptor:
'''
    detector_body3 = _slice(lines, 868, 877)
    detector_body3 = detector_body3.replace("self.", "service.")
    detector_tail2 = '''

def ollama_on_path() -> bool:
    return shutil.which("ollama") is not None


def ollama_model_installed(ollama_tag: str) -> bool:
'''
    detector_body4 = _slice(lines, 881, 887)
    detector_tail3 = '''

def collect_missing(
    *,
    setup_complete: bool,
    ollama_required: bool,
    ollama_installed: bool,
    model_present: bool,
    ollama_tag: str,
) -> list[str]:
'''
    detector_body5 = _slice(lines, 898, 905)
    (SERVICES / "setup_detector.py").write_text(
        detector_header
        + detector_body
        + detector_mid
        + detector_body2
        + detector_tail
        + detector_body3
        + detector_tail2
        + detector_body4
        + detector_tail3
        + detector_body5,
        encoding="utf-8",
    )

    # Fix references in detector
    det_path = SERVICES / "setup_detector.py"
    det_text = det_path.read_text(encoding="utf-8")
    det_text = (
        det_text.replace("service._resolve_descriptor", "resolve_descriptor")
        .replace("service._ollama_on_path", "ollama_on_path")
        .replace("service._ollama_model_installed", "ollama_model_installed")
        .replace("service._collect_missing", "collect_missing")
        .replace("service._ollama_install_instruction_steps", "ollama_install_instruction_steps")
        .replace("get_setup_status(service)", "get_setup_status(service)", 1)
    )
    det_path.write_text(det_text, encoding="utf-8")

    installer_header = '''"""Ollama install, verify, and model pull subprocess helpers."""

from __future__ import annotations

import platform
from typing import TYPE_CHECKING, Any

from lumina_core.engine.model_catalog import ModelCatalog, ModelDescriptor
from lumina_core.logging_utils import get_logger
from lumina_launcher.services.setup_compat import shutil, subprocess
from lumina_launcher.services.setup_detector import ollama_model_installed, ollama_on_path
from lumina_launcher.services.setup_schemas import (
    OLLAMA_INSTALL_TIMEOUT_SEC,
    OLLAMA_PULL_TIMEOUT_SEC,
    OUTPUT_TAIL_CHARS,
    SetupProgressCallback,
    SubprocessStepResult,
)

if TYPE_CHECKING:
    from lumina_launcher.services.smart_setup_service import SmartSetupService

logger = get_logger(__name__)


def ollama_install_instruction_steps() -> list[dict[str, Any]]:
'''
    installer_body0 = _slice(lines, 908, 932)
    installer_mid = '''

def install_ollama_subprocess(service: SmartSetupService) -> tuple[SubprocessStepResult, list[dict[str, Any]]]:
'''
    installer_body1 = _slice(lines, 532, 592)
    installer_body1 = installer_body1.replace("self.", "service.")
    installer_mid2 = '''

def verify_ollama_runtime(service: SmartSetupService) -> SubprocessStepResult:
'''
    installer_body2 = _slice(lines, 595, 626)
    installer_body2 = installer_body2.replace("self.", "service.")
    installer_mid3 = '''

def pull_model_subprocess(
    service: SmartSetupService,
    descriptor: ModelDescriptor,
    *,
    on_progress: SetupProgressCallback | None = None,
) -> SubprocessStepResult:
'''
    installer_body3 = _slice(lines, 634, 698)
    installer_body3 = installer_body3.replace("self.", "service.")
    installer_mid4 = '''

def run_subprocess_step(
    service: SmartSetupService,
    name: str,
    command: list[str],
    *,
    timeout_sec: int,
    success_message: str,
) -> SubprocessStepResult:
'''
    installer_body4 = _slice(lines, 708, 743)
    installer_body4 = installer_body4.replace("self.", "service.")
    installer_tail = '''

def manual_steps_for_model(ollama_tag: str) -> list[dict[str, Any]]:
'''
    installer_body5 = _slice(lines, 750, 758)
    installer_tail2 = '''

def humanize_failure(
    phase: str,
    detail: str,
    stdout: str,
    command: str,
) -> str:
'''
    installer_body6 = _slice(lines, 767, 784)
    (SERVICES / "ollama_installer.py").write_text(
        installer_header
        + installer_body0
        + installer_mid
        + installer_body1
        + installer_mid2
        + installer_body2
        + installer_mid3
        + installer_body3
        + installer_mid4
        + installer_body4
        + installer_tail
        + installer_body5
        + installer_tail2
        + installer_body6,
        encoding="utf-8",
    )

    inst_path = SERVICES / "ollama_installer.py"
    inst_text = inst_path.read_text(encoding="utf-8")
    inst_text = (
        inst_text.replace("service._ollama_install_instruction_steps", "ollama_install_instruction_steps")
        .replace("service._ollama_on_path", "ollama_on_path")
        .replace("service._ollama_model_installed", "ollama_model_installed")
        .replace("service._run_subprocess_step", "run_subprocess_step")
        .replace("service._humanize_failure", "humanize_failure")
        .replace("service._emit_progress", "emit_progress")
        .replace("_OLLAMA_INSTALL_TIMEOUT_SEC", "OLLAMA_INSTALL_TIMEOUT_SEC")
        .replace("_OLLAMA_PULL_TIMEOUT_SEC", "OLLAMA_PULL_TIMEOUT_SEC")
        .replace("_OUTPUT_TAIL_CHARS", "OUTPUT_TAIL_CHARS")
    )
    inst_path.write_text(inst_text, encoding="utf-8")

    orch_header = '''"""Smart setup run orchestration and completion persistence."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import yaml

from lumina_core.config_loader import ConfigLoader
from lumina_core.engine.hardware_inspector import HardwareInspector
from lumina_core.engine.model_catalog import ModelDescriptor
from lumina_core.logging_utils import get_logger
from lumina_launcher.services import setup_detector
from lumina_launcher.services.ollama_installer import (
    install_ollama_subprocess,
    manual_steps_for_model,
    pull_model_subprocess,
    verify_ollama_runtime,
)
from lumina_launcher.services.setup_schemas import (
    PROGRESS_PERCENT,
    SetupProgressCallback,
    SetupProgressEvent,
    SmartSetupOptions,
    SmartSetupResult,
    SubprocessStepResult,
)

if TYPE_CHECKING:
    from lumina_launcher.services.smart_setup_service import SmartSetupService

logger = get_logger(__name__)


def emit_progress(
    callback: SetupProgressCallback | None,
    *,
    phase: str,
    message: str,
    level: str = "info",
    detail: dict[str, Any] | None = None,
) -> None:
    if callback is None:
        return
    event = SetupProgressEvent(
        phase=phase,
        message=message,
        percent=PROGRESS_PERCENT.get(phase),
        level=level,  # type: ignore[arg-type]
        detail=detail or {},
    )
    callback(event)


def apply_intelligence_mode(service: SmartSetupService, force_high: bool) -> None:
'''
    orch_body0 = _slice(lines, 842, 861)
    orch_body0 = orch_body0.replace("self.", "service.")
    orch_mid = '''

def mark_setup_complete(service: SmartSetupService) -> None:
'''
    orch_body1 = _slice(lines, 511, 529)
    orch_body1 = orch_body1.replace("self.", "service.")
    orch_body1 = orch_body1.replace("service._resolve_descriptor", "setup_detector.resolve_descriptor")
    orch_mid2 = '''

def complete_run(
    service: SmartSetupService,
    *,
    steps: list[dict[str, Any]],
    intelligence: dict[str, Any],
    descriptor: ModelDescriptor,
    on_progress: SetupProgressCallback | None,
    mark_complete: bool,
    degraded: bool,
    warnings: list[str],
    manual_steps: list[dict[str, Any]],
) -> SmartSetupResult:
'''
    orch_body2 = _slice(lines, 798, 839)
    orch_body2 = (
        orch_body2.replace("self.", "service.")
        .replace("service.mark_setup_complete", "mark_setup_complete")
        .replace("service.get_setup_status", "setup_detector.get_setup_status")
        .replace("service._emit_progress", "emit_progress")
    )
    orch_mid3 = '''

def finalize_run(
    service: SmartSetupService,
    *,
    success: bool,
    steps: list[dict[str, Any]],
    intelligence: dict[str, Any],
    on_progress: SetupProgressCallback | None,
    failure_message: str,
    warnings: list[str],
    manual_steps: list[dict[str, Any]],
    degraded: bool,
) -> SmartSetupResult:
'''
    orch_body3 = _slice(lines, 946, 971)
    orch_body3 = (
        orch_body3.replace("self.", "service.")
        .replace("service._emit_progress", "emit_progress")
        .replace("service.get_setup_status", "setup_detector.get_setup_status")
    )
    orch_mid4 = '''

def run_smart_setup(
    service: SmartSetupService,
    *,
    on_progress: SetupProgressCallback | None = None,
    options: SmartSetupOptions | None = None,
    mark_complete: bool = False,
) -> SmartSetupResult:
'''
    orch_body4 = _slice(lines, 278, 508)
    orch_body4 = (
        orch_body4.replace("self.", "service.")
        .replace("service.default_options", "service.default_options")
        .replace("service._apply_intelligence_mode", "apply_intelligence_mode")
        .replace("service._resolve_descriptor", "setup_detector.resolve_descriptor")
        .replace("service._emit_progress", "emit_progress")
        .replace("service._finalize_run", "finalize_run")
        .replace("service._install_ollama_subprocess", "install_ollama_subprocess")
        .replace("service._verify_ollama_runtime", "verify_ollama_runtime")
        .replace("service._pull_model_subprocess", "pull_model_subprocess")
        .replace("service._manual_steps_for_model", "manual_steps_for_model")
        .replace("service._complete_run", "complete_run")
    )
    (SERVICES / "setup_orchestrator.py").write_text(
        orch_header + orch_body0 + orch_mid + orch_body1 + orch_mid2 + orch_body2 + orch_mid3 + orch_body3 + orch_mid4 + orch_body4,
        encoding="utf-8",
    )

    facade = '''"""
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
        return ollama_installer.ollama_install_instruction_steps()

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
        setup_orchestrator.emit_progress(
            callback, phase=phase, message=message, level=level, detail=detail
        )
'''
    SRC.write_text(facade, encoding="utf-8")
    print("smart_setup_service split complete")


if __name__ == "__main__":
    main()