"""Fix smart_setup split modules after mechanical extraction."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVICES = ROOT / "lumina_launcher" / "services"
def _original_lines() -> list[str]:
    import subprocess

    raw = subprocess.check_output(
        ["git", "show", "HEAD:lumina_launcher/services/smart_setup_service.py"],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
    )
    return raw.splitlines(keepends=True)


def _body(lines: list[str], start: int, end: int, *, self_name: str = "service") -> str:
    chunk = "".join(lines[start - 1 : end])
    chunk = chunk.replace("self.", f"{self_name}.")
    # Normalize 8-space method indent to 4-space function indent
    fixed: list[str] = []
    for line in chunk.splitlines(keepends=True):
        if line.startswith("        ") and not line.startswith("            "):
            fixed.append(line[4:])
        else:
            fixed.append(line)
    return "".join(fixed)


def main() -> None:
    lines = _original_lines()

    # setup_progress.py
    progress = '''"""Progress event emission for smart setup."""

from __future__ import annotations

from typing import Any

from lumina_launcher.services.setup_schemas import (
    PROGRESS_PERCENT,
    SetupProgressCallback,
    SetupProgressEvent,
)


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
'''
    (SERVICES / "setup_progress.py").write_text(progress, encoding="utf-8")

    detector = '''"""First-run detection, status probes, and install instruction builders."""

from __future__ import annotations

import platform
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
'''
    detector += _body(lines, 142, 144)
    detector += '''

def is_intelligence_stack_ready(service: SmartSetupService) -> bool:
'''
    detector += _body(lines, 147, 152)
    detector += '''

def get_setup_status(service: SmartSetupService) -> dict[str, Any]:
'''
    body = _body(lines, 155, 188)
    body = body.replace(
        "descriptor = resolve_descriptor(intelligence_status, hardware)",
        "descriptor = resolve_descriptor(service, intelligence_status, hardware)",
    )
    body = body.replace("ollama_installed = ollama_on_path()", "ollama_installed = ollama_on_path()")
    body = body.replace(
        "model_present = ollama_model_installed(descriptor.ollama_tag)",
        "model_present = ollama_model_installed(descriptor.ollama_tag)",
    )
    body = body.replace("missing = collect_missing(", "missing = collect_missing(")
    detector += body
    detector += '''

def get_install_instructions(service: SmartSetupService) -> dict[str, Any]:
'''
    body2 = _body(lines, 191, 269)
    body2 = body2.replace("status = service.get_setup_status()", "status = get_setup_status(service)")
    body2 = body2.replace(
        "steps.extend(ollama_install_instruction_steps())",
        "steps.extend(ollama_install_instruction_steps())",
    )
    detector += body2
    detector += '''

def resolve_descriptor(
    service: SmartSetupService,
    intelligence_status: AdaptiveIntelligenceStatus,
    hardware: dict[str, Any],
) -> ModelDescriptor:
'''
    detector += _body(lines, 868, 877)
    detector += '''

def ollama_on_path() -> bool:
    return shutil.which("ollama") is not None


def ollama_model_installed(ollama_tag: str) -> bool:
'''
    detector += _body(lines, 881, 887)
    detector += '''

def collect_missing(
    *,
    setup_complete: bool,
    ollama_required: bool,
    ollama_installed: bool,
    model_present: bool,
    ollama_tag: str,
) -> list[str]:
'''
    detector += _body(lines, 898, 905)
    detector += '''

def ollama_install_instruction_steps() -> list[dict[str, Any]]:
'''
    detector += _body(lines, 908, 932)
    (SERVICES / "setup_detector.py").write_text(detector, encoding="utf-8")

    installer = '''"""Ollama install, verify, and model pull subprocess helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from lumina_core.engine.model_catalog import ModelCatalog, ModelDescriptor
from lumina_core.logging_utils import get_logger
from lumina_launcher.services.setup_compat import shutil, subprocess
from lumina_launcher.services.setup_detector import (
    ollama_install_instruction_steps,
    ollama_model_installed,
    ollama_on_path,
)
from lumina_launcher.services.setup_progress import emit_progress
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


def install_ollama_subprocess(service: SmartSetupService) -> tuple[SubprocessStepResult, list[dict[str, Any]]]:
'''
    body = _body(lines, 532, 592)
    body = body.replace(
        "manual_steps = ollama_install_instruction_steps()",
        "manual_steps = ollama_install_instruction_steps()",
    )
    body = body.replace("_OLLAMA_INSTALL_TIMEOUT_SEC", "OLLAMA_INSTALL_TIMEOUT_SEC")
    body = body.replace("run_subprocess_step(", "run_subprocess_step(service, ")
    body = body.replace("humanize_failure(", "humanize_failure(")
    installer += body
    installer += '''

def verify_ollama_runtime(service: SmartSetupService) -> SubprocessStepResult:
'''
    body = _body(lines, 595, 626)
    body = body.replace("run_subprocess_step(", "run_subprocess_step(service, ")
    installer += body
    installer += '''

def pull_model_subprocess(
    service: SmartSetupService,
    descriptor: ModelDescriptor,
    *,
    on_progress: SetupProgressCallback | None = None,
) -> SubprocessStepResult:
'''
    body = _body(lines, 634, 698)
    body = body.replace("_OLLAMA_PULL_TIMEOUT_SEC", "OLLAMA_PULL_TIMEOUT_SEC")
    body = body.replace("_OUTPUT_TAIL_CHARS", "OUTPUT_TAIL_CHARS")
    body = body.replace("emit_progress(", "emit_progress(")
    body = body.replace("humanize_failure(", "humanize_failure(")
    installer += body
    installer += '''

def run_subprocess_step(
    service: SmartSetupService,
    name: str,
    command: list[str],
    *,
    timeout_sec: int,
    success_message: str,
) -> SubprocessStepResult:
'''
    body = _body(lines, 708, 743)
    body = body.replace("humanize_failure(", "humanize_failure(")
    installer += body
    installer += '''

def manual_steps_for_model(ollama_tag: str) -> list[dict[str, Any]]:
'''
    installer += _body(lines, 750, 758)
    installer += '''

def humanize_failure(
    phase: str,
    detail: str,
    stdout: str,
    command: str,
) -> str:
'''
    installer += _body(lines, 767, 784)
    (SERVICES / "ollama_installer.py").write_text(installer, encoding="utf-8")

    orch = '''"""Smart setup run orchestration and completion persistence."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import yaml

from lumina_core.config_loader import ConfigLoader
from lumina_core.engine.model_catalog import ModelDescriptor
from lumina_core.logging_utils import get_logger
from lumina_launcher.services import setup_detector
from lumina_launcher.services.ollama_installer import (
    install_ollama_subprocess,
    manual_steps_for_model,
    pull_model_subprocess,
    verify_ollama_runtime,
)
from lumina_launcher.services.setup_compat import HardwareInspector
from lumina_launcher.services.setup_progress import emit_progress
from lumina_launcher.services.setup_schemas import (
    SetupProgressCallback,
    SmartSetupOptions,
    SmartSetupResult,
)

if TYPE_CHECKING:
    from lumina_launcher.services.smart_setup_service import SmartSetupService

logger = get_logger(__name__)


def apply_intelligence_mode(service: SmartSetupService, force_high: bool) -> None:
'''
    orch += _body(lines, 842, 861)
    orch += '''

def mark_setup_complete(service: SmartSetupService) -> None:
'''
    body = _body(lines, 511, 529)
    body = body.replace(
        "descriptor = resolve_descriptor(intelligence_status, hardware_intel.to_dict())",
        "descriptor = setup_detector.resolve_descriptor(service, intelligence_status, hardware_intel.to_dict())",
    )
    orch += body
    orch += '''

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
    body = _body(lines, 798, 839)
    body = body.replace("mark_setup_complete()", "mark_setup_complete(service)")
    body = body.replace("get_setup_status()", "setup_detector.get_setup_status(service)")
    body = body.replace("emit_progress(", "emit_progress(")
    orch += body
    orch += '''

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
    body = _body(lines, 946, 971)
    body = body.replace("get_setup_status()", "setup_detector.get_setup_status(service)")
    orch += body
    orch += '''

def run_smart_setup(
    service: SmartSetupService,
    *,
    on_progress: SetupProgressCallback | None = None,
    options: SmartSetupOptions | None = None,
    mark_complete: bool = False,
) -> SmartSetupResult:
'''
    body = _body(lines, 278, 508)
    replacements = [
        ("apply_intelligence_mode(opts.force_high_tier)", "apply_intelligence_mode(service, opts.force_high_tier)"),
        (
            "descriptor = resolve_descriptor(intelligence_status, hardware_intel.to_dict())",
            "descriptor = setup_detector.resolve_descriptor(service, intelligence_status, hardware_intel.to_dict())",
        ),
        ("install_ollama_subprocess()", "install_ollama_subprocess(service)"),
        ("verify_ollama_runtime()", "verify_ollama_runtime(service)"),
        ("pull_model_subprocess(descriptor,", "pull_model_subprocess(service, descriptor,"),
        ("pull_model_subprocess(extra,", "pull_model_subprocess(service, extra,"),
        ("manual_steps_for_model(descriptor.ollama_tag)", "manual_steps_for_model(descriptor.ollama_tag)"),
        ("return finalize_run(", "return finalize_run(service, "),
        ("return complete_run(", "return complete_run(service, "),
    ]
    for old, new in replacements:
        body = body.replace(old, new)
    orch += body

    (SERVICES / "setup_orchestrator.py").write_text(orch, encoding="utf-8")

    # Update orchestrator to remove emit_progress (moved to setup_progress)
    orch_text = (SERVICES / "setup_orchestrator.py").read_text(encoding="utf-8")
    orch_text = re.sub(
        r"def emit_progress\([\s\S]*?callback\(event\)\n\n\n",
        "",
        orch_text,
        count=1,
    )
    (SERVICES / "setup_orchestrator.py").write_text(orch_text, encoding="utf-8")

    # Update smart_setup_service to use setup_progress
    facade = (SERVICES / "smart_setup_service.py").read_text(encoding="utf-8")
    facade = facade.replace(
        "setup_orchestrator.emit_progress(",
        "from lumina_launcher.services.setup_progress import emit_progress as _emit_progress\n\n        _emit_progress(",
    )
    # Fix the botched replace - do it properly
    facade = (SERVICES / "smart_setup_service.py").read_text(encoding="utf-8")
    facade = facade.replace(
        "        setup_orchestrator.emit_progress(\n            callback, phase=phase, message=message, level=level, detail=detail\n        )",
        "        from lumina_launcher.services.setup_progress import emit_progress\n\n        emit_progress(\n            callback, phase=phase, message=message, level=level, detail=detail\n        )",
    )
    (SERVICES / "smart_setup_service.py").write_text(facade, encoding="utf-8")

    print("fixed smart_setup modules")


if __name__ == "__main__":
    main()